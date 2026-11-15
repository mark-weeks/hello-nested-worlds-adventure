"""Operator commands keep collection private and preflight free of side effects."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import socket
import uuid

import pytest

import main
import persistence
from server import community_policy


@pytest.fixture(autouse=True)
def isolated_community_policy(monkeypatch):
    for name in (community_policy.POLICY_ENV, community_policy.DISABLE_CHAT_ENV,
                 community_policy.DISABLE_REPORTS_ENV):
        monkeypatch.delenv(name, raising=False)
    community_policy.reset_for_tests()
    yield
    community_policy.reset_for_tests()


def _forbidden(*_args, **_kwargs):
    raise AssertionError("Offline check must not activate, open a database or use the network.")


def test_real_offline_check_does_not_activate_open_db_or_connect(tmp_path, monkeypatch, capsys):
    document = {"schema_version": 1, "policy_id": "cli-test",
                "chat": {"enabled": False}, "reports": {"enabled": False}}
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(document))
    monkeypatch.setattr(community_policy, "initialize", _forbidden)
    monkeypatch.setattr(persistence, "init_db", _forbidden)
    monkeypatch.setattr(persistence, "_connect", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    main.main(["community-policy", "--check", "--policy", str(path)])
    result = json.loads(capsys.readouterr().out)
    assert result["configuration"]["collection_configured"] is False
    assert result["configuration"]["chat_retention_days"] is None
    assert result["configuration"]["report_retention_days"] is None
    assert result["activated"] is result["database_opened"] is result["live_calls"] is False
    assert community_policy._snapshot is None
    assert not persistence._DB_PATH.exists()


def test_invalid_preflight_returns_safe_json_without_file_contents(tmp_path, capsys):
    path = tmp_path / "private-policy.json"
    path.write_text('{"secret":"do-not-print-this\\u001b[31m"}')
    with pytest.raises(SystemExit) as caught:
        main.main(["community-policy", "--check", "--policy", str(path)])
    assert caught.value.code == 1
    result = capsys.readouterr()
    assert not result.out
    assert json.loads(result.err) == {"error": "Community collection policy is invalid."}
    assert "do-not-print" not in result.err
    assert not persistence._DB_PATH.exists()


@pytest.mark.parametrize("args", [[], ["--check"], ["--policy", "somewhere"]])
def test_preflight_requires_explicit_check_and_path(args):
    with pytest.raises(SystemExit) as caught:
        main.main(["community-policy", *args])
    assert caught.value.code == 2
    assert not persistence._DB_PATH.exists()


def test_operator_json_escapes_controls_and_non_ascii(capsys):
    main._community_output({"name": "\x1b[31mÉlodie", "note": "line one\nline two\u202e"})
    raw = capsys.readouterr().out
    assert "\x1b" not in raw and "É" not in raw and "\u202e" not in raw
    assert "\\u001b" in raw and "\\u00c9" in raw and "\\u202e" in raw
    assert json.loads(raw)["name"] == "\x1b[31mÉlodie"


def _report_fixture(monkeypatch):
    from persistence import community, participants
    moment = [datetime(2026, 11, 14, 12, tzinfo=timezone.utc)]
    monkeypatch.setattr(community, "utc_now", lambda: moment[0])
    sender, reporter = "nw_" + "a" * 32, "nw_" + "b" * 32
    persistence.mint_invite_key(sender, "Ada")
    persistence.mint_invite_key(reporter, "Bea")
    # Explicit test windows, not production defaults or selected owner values.
    snapshot = json.dumps({"schema_version": 1, "policy_id": "cli-fixture",
                           "chat": {"enabled": True, "retention_days": 1},
                           "reports": {"enabled": True, "retention_days": 3},
                           "contact": "Test facilitator", "backup_notice": "Test-only copies"})
    text = "Private line \x1b[31mÉlodie"
    message = community.append_chat(
        user_key=sender, session_id=uuid.uuid4().hex, world_seed=382,
        node_name="Test room", text=text, display_name="Ada", retention_days=1,
        policy_snapshot=snapshot)
    report = community.submit_report(
        user_key=reporter, request_id=uuid.uuid4().hex,
        fingerprint=hashlib.sha256(b"CLI fixture submission").hexdigest(),
        world_seed=382, target_id=participants.identify(sender)["id"],
        evidence_ref=message["evidence_ref"], reason="harassment", detail="Private explanation",
        retention_days=3, policy_snapshot=snapshot)
    return community, moment, report["report_id"], text


def test_real_queue_triage_uses_stdin_notes_and_keeps_list_summary_private(monkeypatch, capsys):
    community, _clock, report_id, text = _report_fixture(monkeypatch)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    main.main(["report", "list", "--state", "open"])
    raw = capsys.readouterr().out
    assert json.loads(raw)["reports"][0]["id"] == report_id
    assert text not in raw and "Private explanation" not in raw
    monkeypatch.setattr("sys.stdin", io.StringIO("Operator note \x1b[31mÉlodie\n"))
    main.main(["report", "acknowledge", report_id, "--operator", "Facilitator", "--note", "-"])
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "acknowledged"
    main.main(["report", "show", report_id])
    shown = capsys.readouterr().out
    assert "\x1b" not in shown and "É" not in shown
    record = json.loads(shown)["report"]
    assert record["evidence"]["text"] == text
    assert record["actions"][0]["note"] == "Operator note \x1b[31mÉlodie"
    assert record["actions"][0]["expires_at"] == record["expires_at"]
    main.main(["report", "close", report_id, "--operator", "Facilitator", "--note", "Reviewed"])
    assert json.loads(capsys.readouterr().out)["status"] == "closed"
    assert community.show_report(report_id)["status"] == "closed"


def test_polling_defaults_to_open_after_a_full_page_of_older_closed_reports(monkeypatch, capsys):
    from persistence import participants

    community, clock, first_id, _text = _report_fixture(monkeypatch)
    first = community.show_report(first_id)
    with persistence._connection() as conn:
        snapshot = conn.execute("SELECT snapshot_json FROM community_policies WHERE digest=?",
                                (first["policy_digest"],)).fetchone()[0]
    closed = [first_id]
    community.close_report(first_id, operator="Test facilitator")

    def submit():
        request_id = uuid.uuid4().hex
        return community.submit_report(
            user_key="nw_" + "b" * 32, request_id=request_id,
            fingerprint=hashlib.sha256(request_id.encode()).hexdigest(),
            world_seed=382, target_id=participants.identify("nw_" + "a" * 32)["id"],
            evidence_ref=None, reason="spam", detail="Private queue fixture",
            retention_days=3, policy_snapshot=snapshot)["report_id"]

    for _ in range(49):
        report_id = submit()
        community.close_report(report_id, operator="Test facilitator")
        closed.append(report_id)
    clock[0] += timedelta(seconds=1)
    new_open = submit()

    main.main(["report", "list"])
    assert [row["id"] for row in json.loads(capsys.readouterr().out)["reports"]] == [new_open]
    main.main(["report", "list", "--state", "all"])
    first_page = json.loads(capsys.readouterr().out)["reports"]
    assert len(first_page) == 50 and {row["id"] for row in first_page} == set(closed)
    main.main(["report", "list", "--state", "all", "--limit", "51"])
    all_reports = json.loads(capsys.readouterr().out)["reports"]
    assert len(all_reports) == 51
    assert {row["status"] for row in all_reports} == {"open", "closed"}
    assert all_reports[-1]["id"] == new_open


def test_closed_case_uses_recorded_expiry_and_prune_is_operational(monkeypatch, capsys):
    community, clock, report_id, text = _report_fixture(monkeypatch)
    community.close_report(report_id, operator="Fixture")
    clock[0] += timedelta(days=2)
    main.main(["report", "show", report_id])
    raw = capsys.readouterr().out
    assert json.loads(raw)["report"]["evidence"] == {"status": "expired"}
    assert text not in raw and "Private explanation" in raw
    main.main(["community-status"])
    status = json.loads(capsys.readouterr().out)["storage"]
    assert status["retained_chat"] == 0 and status["closed_reports"] == 1
    clock[0] += timedelta(days=2)
    with pytest.raises(SystemExit) as caught:
        main.main(["report", "show", report_id])
    assert caught.value.code == 1
    assert json.loads(capsys.readouterr().err) == {"error": "The report operation was refused."}
    main.main(["community-prune"])
    removed = json.loads(capsys.readouterr().out)["pruned"]
    assert removed["chat_messages"] == 1 and removed["reports"] == 1
    main.main(["community-status"])
    assert json.loads(capsys.readouterr().out)["storage"]["open_reports"] == 0


def test_real_chat_delete_commands_report_holds_and_delete_eligible_tester_lines(monkeypatch, capsys):
    community, clock, report_id, _text = _report_fixture(monkeypatch)
    record = community.show_report(report_id)
    reference = record["evidence_ref"]
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    main.main(["chat-log", "delete", reference])
    result = json.loads(capsys.readouterr().out)
    assert result["held"] == 1 and result["deleted"] == 0 and result["hold_reason"]
    snapshot = '{"chat":{"enabled":true,"retention_mode":"until_deleted"}}'
    community.append_chat(user_key="nw_" + "a" * 32, session_id=uuid.uuid4().hex,
                          world_seed=383, node_name="Other test room", text="Delete this eligible line",
                          display_name="Ada", retention_days=None, retention_mode="until_deleted",
                          policy_snapshot=snapshot)
    main.main(["chat-log", "delete-tester", "Ada"])
    result = json.loads(capsys.readouterr().out)
    assert (result["matched"], result["deleted"], result["held"]) == (2, 1, 1)
    clock[0] += timedelta(days=4)
    assert community.show_report(report_id)["evidence"]["status"] == "retained"
    main.main(["report", "close", report_id, "--operator", "Fixture"])
    capsys.readouterr()
    main.main(["chat-log", "delete", reference])
    result = json.loads(capsys.readouterr().out)
    assert result["deleted"] == 1 and result["held"] == 0 and result["hold_reason"] is None
    with persistence._connection() as conn:
        assert conn.execute("SELECT count(*) FROM private_chat_messages").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM world_mutations").fetchone()[0] == 0


@pytest.mark.parametrize("command", [["delete", "invalid"], ["delete-tester", "Unknown tester"]])
def test_chat_delete_errors_are_safe_operator_json(monkeypatch, capsys, command):
    _report_fixture(monkeypatch)
    with pytest.raises(SystemExit) as caught:
        main.main(["chat-log", *command])
    assert caught.value.code == 1
    assert json.loads(capsys.readouterr().err) == {"error": "The private chat deletion was refused."}


def test_unavailable_status_never_creates_a_world_database(capsys):
    with pytest.raises(SystemExit) as caught:
        main.main(["community-status"])
    assert caught.value.code == 1
    state = json.loads(capsys.readouterr().out)["storage"]
    assert state["available"] is False and state["storage_error"] is False
    assert not persistence._DB_PATH.exists()


@pytest.mark.parametrize("note", ["\ud800", "x" * 2001])
def test_invalid_stdin_note_is_refused_without_a_triage_write(monkeypatch, capsys, note):
    community, _clock, report_id, _text = _report_fixture(monkeypatch)
    monkeypatch.setattr("sys.stdin", io.StringIO(note))
    with pytest.raises(SystemExit) as caught:
        main.main(["report", "acknowledge", report_id, "--operator", "Facilitator", "--note", "-"])
    assert caught.value.code == 1
    assert json.loads(capsys.readouterr().err) == {"error": "The report operation was refused."}
    assert community.show_report(report_id)["actions"] == []
