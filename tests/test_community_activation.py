"""Community startup fences and idle retention are independent of gameplay."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import threading
from types import SimpleNamespace
import uuid

import pytest

import consciousness
import main
from consciousness import model_check, model_policy
import persistence
from persistence import community, participants
import server
from server import block_targets, community_policy, guard, heartbeat, observability, websocket
from tests import watch_policy_template as template


_PRIVATE = "private chat, report detail or credential in an exception"


def _forbidden(*args, **kwargs):
    raise AssertionError("a forbidden startup side effect was reached")


@pytest.fixture(autouse=True)
def isolated_community(monkeypatch, _community_test_policy):
    monkeypatch.delenv(community_policy.POLICY_ENV, raising=False)
    community_policy.reset_for_tests()
    yield
    community_policy.reset_for_tests()


def _quiet_dependencies(monkeypatch, events):
    """Leave community initialization/cleanup real; silence unrelated services."""
    monkeypatch.setattr(model_policy, "initialize", lambda: None)
    monkeypatch.setattr(model_check, "enforce_model_configuration", lambda: None)
    monkeypatch.setattr(consciousness, "warn_if_cache_ineffective", lambda: None)
    monkeypatch.setattr(server, "model_banner", lambda: [])
    monkeypatch.setattr(observability, "setup", lambda: events.append("observability"))
    monkeypatch.setattr(guard, "canonical_seed", lambda: None)
    monkeypatch.setattr(guard, "budget_configuration_warning_line", lambda: None)
    monkeypatch.setattr(guard, "budget_configuration_line", lambda: None)
    monkeypatch.setattr(heartbeat, "enabled", lambda: False)
    monkeypatch.setattr(heartbeat, "pump_enabled", lambda: False)
    monkeypatch.setattr(websocket, "stop_credential_sweep", lambda: events.append("sweep.stop"))
    monkeypatch.setattr(server.signal, "signal", lambda *args: None)
    monkeypatch.setattr(persistence, "checkpoint", lambda: events.append("checkpoint"))


def _expired_closed_report(monkeypatch):
    clock = SimpleNamespace(now=datetime(2026, 1, 1, 12, tzinfo=timezone.utc))
    monkeypatch.setattr(community, "utc_now", lambda: clock.now)
    snapshot = ('{"chat":{"enabled":true,"retention_mode":"until_deleted"},'
                '"reports":{"enabled":true,"retention_days":1}}')
    line = community.append_chat(
        user_key=None, session_id=uuid.uuid4().hex, world_seed=382,
        node_name="Synthetic place", text="Private fixture line.", display_name="Fixture traveler",
        retention_days=None, retention_mode="until_deleted", policy_snapshot=snapshot,
    )
    reporter = "nw_" + "a" * 32
    persistence.mint_invite_key(reporter, "Fixture reporter")
    report = community.submit_report(user_key=reporter, request_id=uuid.uuid4().hex,
        fingerprint="a" * 64, world_seed=382, target_id=None, evidence_ref=line["evidence_ref"],
        reason="other", detail="Expired private reporter statement", retention_days=1,
        policy_snapshot=snapshot)
    community.close_report(report["report_id"], operator="Fixture")
    community.delete_chat_message(line["evidence_ref"])
    clock.now += timedelta(days=2)
    return clock


@pytest.mark.parametrize("failure", ["file", "untrusted_exception"])
def test_invalid_community_policy_precedes_migration_observability_and_listener(tmp_path, monkeypatch, capsys, failure):
    monkeypatch.setattr(model_policy, "initialize", lambda: None)
    if failure == "file":
        path = tmp_path / "invalid-community.json"
        path.write_text(json.dumps({"private": _PRIVATE}))
        monkeypatch.setenv(community_policy.POLICY_ENV, str(path))
    else:
        def refuse():
            error = community_policy.CommunityPolicyError()
            error.args = (_PRIVATE,)
            raise error
        monkeypatch.setattr(community_policy, "initialize", refuse)
    monkeypatch.setattr(persistence, "init_db", _forbidden)
    monkeypatch.setattr(observability, "setup", _forbidden)
    monkeypatch.setattr(server.logging, "basicConfig", _forbidden)
    monkeypatch.setattr(server, "_ThreadedServer", _forbidden)
    monkeypatch.setattr(server, "_start_community_retention", _forbidden)
    with pytest.raises(SystemExit) as caught:
        server.run(port=0)
    assert caught.value.code == 1 and not persistence._DB_PATH.exists()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "error: community collection policy is invalid\n"
    assert _PRIVATE not in captured.err


def test_all_off_startup_prunes_before_binding_and_owns_worker_shutdown(monkeypatch):
    _expired_closed_report(monkeypatch)
    assert not community_policy.chat_enabled() and not community_policy.reports_enabled()
    events = []
    _quiet_dependencies(monkeypatch, events)
    original_init = persistence.init_db
    original_prune = community.prune_expired

    def migrate():
        events.append("migrate")
        original_init()

    def prune():
        events.append("prune")
        result = original_prune()
        assert result["chat_messages"] == 0 and result["reports"] == 1
        assert result["actions"] == 1 and result["policies"] == 1
        return result

    def retention():
        events.append("retention.start")
        return (SimpleNamespace(set=lambda: events.append("retention.stop")),
                SimpleNamespace(join=lambda **kwargs: events.append("retention.join"), is_alive=lambda: False))

    class Listener:
        def __init__(self, *args):
            assert events.index("migrate") < events.index("prune")
            with persistence._connection() as conn:
                assert conn.execute("SELECT COUNT(*) FROM private_chat_messages").fetchone()[0] == 0
                assert conn.execute("SELECT COUNT(*) FROM community_policies").fetchone()[0] == 0
            events.append("bind")

        def serve_forever(self):
            events.append("serve")

        def server_close(self):
            events.append("close")

    monkeypatch.setattr(persistence, "init_db", migrate)
    monkeypatch.setattr(community, "prune_expired", prune)
    monkeypatch.setattr(server, "_ThreadedServer", Listener)
    monkeypatch.setattr(server, "_start_community_retention", retention)
    server.run(port=0)
    assert events == ["observability", "migrate", "prune", "bind", "retention.start", "serve",
                      "retention.stop", "retention.join", "sweep.stop", "close", "checkpoint"]


def test_startup_prune_failure_refuses_listener_with_safe_error(monkeypatch, capsys):
    events = []
    _quiet_dependencies(monkeypatch, events)

    def fail():
        raise RuntimeError(_PRIVATE)

    monkeypatch.setattr(community, "prune_expired", fail)
    monkeypatch.setattr(server, "_ThreadedServer", _forbidden)
    monkeypatch.setattr(server, "_start_community_retention", _forbidden)
    with pytest.raises(SystemExit) as caught:
        server.run(port=0)
    assert caught.value.code == 1 and persistence._DB_PATH.exists()
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "error: community retention is unavailable\n"
    assert _PRIVATE not in captured.err


def test_idle_worker_prunes_expired_closed_report_text_when_collection_is_off(monkeypatch):
    _expired_closed_report(monkeypatch)
    assert not community_policy.chat_enabled() and not community_policy.reports_enabled()
    completed = threading.Event()
    removed = []

    def prune():
        removed.append(community.prune_expired())
        completed.set()

    stopped, worker = server._start_community_retention(interval_seconds=0.001, prune=prune)
    try:
        assert completed.wait(2)
    finally:
        stopped.set()
        worker.join(timeout=1)
    assert not worker.is_alive() and worker.name == "community-retention"
    assert sum(row["chat_messages"] for row in removed) == 0
    assert sum(row["reports"] for row in removed) == 1
    with persistence._connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM private_chat_messages").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM private_reports").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM world_mutations").fetchone()[0] == 0


def test_retention_retries_with_class_only_logs_and_stops(caplog):
    retried, release = threading.Event(), threading.Event()
    calls = []

    def prune():
        calls.append(1)
        if len(calls) == 1:
            raise ValueError(_PRIVATE)
        retried.set()
        assert release.wait(2)

    stopped, worker = server._start_community_retention(interval_seconds=0, prune=prune)
    try:
        assert retried.wait(2)
    finally:
        stopped.set()
        release.set()
        worker.join(timeout=1)
    assert not worker.is_alive() and len(calls) == 2
    records = [record for record in caplog.records if record.name == "nested_worlds.community_retention"]
    assert len(records) == 1 and records[0].exc_info is None
    assert records[0].getMessage() == "community retention unavailable (ValueError)"
    assert _PRIVATE not in caplog.text


def test_stopping_retention_interrupts_the_idle_wait_without_a_cleanup_tick():
    calls = []
    stopped, worker = server._start_community_retention(interval_seconds=3600, prune=lambda: calls.append(1))
    stopped.set()
    worker.join(timeout=1)
    assert not worker.is_alive() and calls == []


# The watch template, activated the way O12 orders it: offline check, the
# environment variable, a restart, then GET /community against the checked
# revision. The template and its backup wording are read from the guide.

@pytest.fixture
def watch_template_policy(tmp_path, monkeypatch, capsys):
    path = template.write_filled(tmp_path)
    main.main(["community-policy", "--check", "--policy", str(path)])
    checked = json.loads(capsys.readouterr().out)
    assert checked["activated"] is checked["database_opened"] is checked["live_calls"] is False
    assert not community_policy.chat_enabled() and not community_policy.reports_enabled()
    community_policy.reset_for_tests()
    monkeypatch.setenv(community_policy.POLICY_ENV, str(path))
    return checked["configuration"]


def test_activated_watch_template_serves_its_checked_revision_and_takes_a_report(
        watch_template_policy, http, accounts):
    assert watch_template_policy["chat_retention_mode"] == "until_deleted"
    assert watch_template_policy["report_retention_days"] == 90
    status, served, _ = http("/community", key="")
    assert status == 200
    assert served["revision"] == watch_template_policy["revision"]
    assert served["chat"]["enabled"] is True and served["chat"]["retention_mode"] == "until_deleted"
    assert served["chat"]["retention_days"] is None
    assert served["reports"]["enabled"] is True and served["reports"]["retention_days"] == 90
    assert served["contact"] == template.TEST_CONTACT
    assert served["backup_notice"] == template.backup_wording()

    status, notice, _ = http("/participation", key="")
    assert status == 200 and notice["required"] is True and notice["ready"] is True
    assert any(line.endswith("Backup copies and deletion: " + template.backup_wording())
               for line in notice["paragraphs"])

    reporter, target = (participants.identify(key) for key in accounts)
    status, receipt, _ = http("/reports", body={
        "request_id": str(uuid.uuid4()), "evidence_ref": None, "reason": "other",
        "participant": block_targets.handle(reporter["id"], target["id"]),
        "detail": "Synthetic watch-template report."})
    assert status == 200 and receipt["status"] == "received"
    stored = community.show_report(receipt["report_id"])
    assert stored["status"] == "open" and stored["retention_days"] == 90
    created, expires = (datetime.fromisoformat(stored[name].replace("Z", "+00:00"))
                        for name in ("created_at", "expires_at"))
    assert expires - created == timedelta(days=90)


def test_watch_template_chat_line_is_kept_until_deleted(watch_template_policy, accounts):
    declared = community_policy.current()
    assert community_policy.chat_enabled()
    line = community.append_chat(
        user_key=accounts[0], session_id=uuid.uuid4().hex, world_seed=382,
        node_name="Synthetic place", text="Synthetic watch line.", display_name="Ada",
        retention_days=declared.chat_days, retention_mode=declared.chat_retention_mode,
        policy_snapshot=declared.snapshot_json)
    assert line["expires_at"] is None
