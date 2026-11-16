"""Chat lasts until deletion; report windows and complaint holds stay separate."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import threading
from types import SimpleNamespace
import uuid

import pytest

import persistence as db
from persistence import blocks, community, participants, sanctions


@pytest.fixture
def clock(monkeypatch):
    result = SimpleNamespace(now=datetime(2026, 11, 14, 12, tzinfo=timezone.utc))
    monkeypatch.setattr(community, "utc_now", lambda: result.now)
    return result


def _snapshot(report_days=3):
    return json.dumps({"chat": {"enabled": True, "retention_mode": "until_deleted"},
                       "reports": {"enabled": True, "retention_days": report_days}})


def chat(key=None, **overrides):
    options = dict(user_key=key, session_id=uuid.uuid4().hex, world_seed=382,
                   node_name="Fixture place", text="A private line.", display_name="Local traveler",
                   retention_days=None, retention_mode="until_deleted", policy_snapshot=_snapshot())
    options.update(overrides)
    return community.append_chat(**options)


def report_options(key, evidence=None, **overrides):
    options = dict(user_key=key, request_id=str(uuid.uuid4()), fingerprint=hashlib.sha256(b"fixture").hexdigest(),
                   world_seed=382, target_id=None, evidence_ref=evidence,
                   reason="other", detail="A reporter statement.", retention_days=3,
                   policy_snapshot=_snapshot(overrides.get("retention_days", 3)))
    options.update(overrides)
    return options


def report(key, evidence=None, **overrides):
    return community.submit_report(**report_options(key, evidence, **overrides))


def rows(table):
    with db._connection() as conn:
        cursor = conn.execute(f"SELECT * FROM {table}")
        return [dict(zip((column[0] for column in cursor.description), row)) for row in cursor]


def counts(*tables):
    with db._connection() as conn:
        return tuple(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables)


def test_keyed_chat_commits_authoritative_identity_without_chronicle_or_secrets(accounts, clock):
    message = chat(accounts[0], display_name="Forged name")
    saved = rows("private_chat_messages")[0]
    assert message == {"evidence_ref": saved["evidence_ref"], "participant_id": saved["participant_id"],
                       "name": "Ada", "at": "2026-11-14T12:00:00.000000Z",
                       "expires_at": None}
    assert saved["name"] == "Ada" and saved["text"] == "A private line."
    assert saved["id"] != saved["evidence_ref"]
    assert saved["participant_id"] == participants.identify(accounts[0])["id"]
    assert saved["world_seed"] == 382 and saved["node_name"] == "Fixture place"
    assert saved["retention_days"] is saved["expires_at"] is None
    assert counts("world_mutations") == (0,)
    serialized = json.dumps(rows("private_chat_messages") + rows("community_policies"))
    assert accounts[0] not in serialized and db._credential_digest(accounts[0]) not in serialized
    assert "credential" not in " ".join(saved) and "ip" not in saved
    # A separate SQLite connection observes the committed row before return.
    with sqlite3.connect(db._DB_PATH) as conn:
        assert conn.execute("SELECT text FROM private_chat_messages WHERE evidence_ref=?",
                            (message["evidence_ref"],)).fetchone() == ("A private line.",)


def test_local_anonymous_chat_has_no_participant_enrollment(clock):
    db.init_db()
    session = uuid.uuid4().hex
    item = chat(session_id=session, display_name="Local friend")
    assert item["participant_id"] is None and item["name"] == "Local friend"
    assert counts("participants", "participant_credentials", "world_mutations") == (0, 0, 0)
    saved = rows("private_chat_messages")[0]
    assert saved["session_id"] == session and saved["participant_id"] is None


@pytest.mark.parametrize("gate", ["invite", "revoked", "registration", "cancelled"])
def test_anonymous_collection_checks_permanent_invite_gate(clock, gate):
    db.init_db()
    if gate in ("invite", "revoked"):
        key = "nw_" + "a" * 32
        db.mint_invite_key(key, "Ada")
        if gate == "revoked":
            db.revoke_invite_key(key)
    else:
        db.create_registration_token("registration-fixture-token")
        if gate == "cancelled":
            db.cancel_registration_token("registration-fixture-token")
    with pytest.raises(participants.Unauthorized):
        chat()
    assert counts("private_chat_messages", "community_policies", "participants") == (0, 0, 0)


@pytest.mark.parametrize("key_kind", ["missing", "unknown", "revoked", "sanctioned"])
def test_keyed_chat_and_reports_require_live_personal_credential(accounts, clock, key_kind):
    evidence = chat(accounts[1])["evidence_ref"]
    key = accounts[0]
    if key_kind == "missing":
        key = ""
    elif key_kind == "unknown":
        key = "nw_" + "e" * 32
    elif key_kind == "revoked":
        db.revoke_invite_key(key)
    else:
        sanctions.ban("Ada", "Fixture sanction")
    before = counts("participants", "participant_credentials")
    for operation in (lambda: chat(key), lambda: report(key, evidence),
                      lambda: community.lookup_report_retry(key, uuid.uuid4().hex, "a" * 64)):
        with pytest.raises(participants.Unauthorized):
            operation()
    assert counts("private_chat_messages", "private_reports") == (1, 0)
    assert counts("participants", "participant_credentials") == before


def test_chat_insert_failure_rolls_back_first_enrollment_and_never_returns_evidence(accounts, clock):
    with db._connection() as conn:
        conn.execute("""CREATE TRIGGER reject_chat BEFORE INSERT ON private_chat_messages
            BEGIN SELECT RAISE(ABORT,'fixture confidential disk error'); END""")
    with pytest.raises(community.CommunityUnavailable, match="^Private community storage is unavailable.$"):
        chat(accounts[0])
    assert counts("private_chat_messages", "community_policies", "participants", "participant_credentials") == (0, 0, 0, 0)


def test_collection_and_actions_refuse_caller_owned_transaction(accounts, clock):
    item = chat(accounts[1])
    receipt = report(accounts[0], item["evidence_ref"])
    with db.transaction():
        for operation in (lambda: chat(accounts[0]), lambda: report(accounts[0], item["evidence_ref"]),
                          lambda: community.close_report(receipt["report_id"], operator="Fixture"),
                          community.prune_expired):
            with pytest.raises(community.CommunityUnavailable):
                operation()
    assert counts("private_chat_messages", "private_reports", "report_actions") == (1, 1, 0)


def test_draft_correlation_is_not_chat_deduplication(accounts, clock):
    session = uuid.uuid4().hex
    first, second = chat(accounts[0], session_id=session), chat(accounts[0], session_id=session)
    assert first["evidence_ref"] != second["evidence_ref"]
    assert counts("private_chat_messages") == (2,)


def test_evidence_author_survives_disconnect_and_key_rotation_but_hides_text(accounts, clock):
    session = uuid.uuid4().hex
    item = chat(accounts[1], session_id=session)
    replacement = "nw_" + "c" * 32
    participants.rotate(accounts[1], replacement)
    found = community.evidence_author(evidence_ref=item["evidence_ref"], world_seed=382)
    assert found == {"participant_id": participants.identify(replacement)["id"], "session_id": session,
                     "name": "Bea", "expires_at": item["expires_at"]}
    for reference, seed in ((item["evidence_ref"], 383), ("f" * 32, 382), ("bad", 382)):
        with pytest.raises(community.EvidenceUnavailable) as error:
            community.evidence_author(evidence_ref=reference, world_seed=seed)
        assert "Bea" not in str(error.value)
    clock.now += timedelta(days=3650)
    assert community.evidence_author(evidence_ref=item["evidence_ref"], world_seed=382) == found
    assert community.delete_chat_message(item["evidence_ref"])["deleted"] == 1
    with pytest.raises(community.EvidenceUnavailable):
        community.evidence_author(evidence_ref=item["evidence_ref"], world_seed=382)
    assert counts("private_chat_messages") == (0,)


def test_report_receipt_has_no_target_kind_private_payload_or_quotation(accounts, clock):
    item = chat(accounts[1], text="An authoritative source line.")
    receipt = report(accounts[0], item["evidence_ref"], detail="The reporter's separate statement.")
    assert set(receipt) == {"report_id", "received"} and receipt["received"] is True
    saved = rows("private_reports")[0]
    assert saved["target_id"] == item["participant_id"]
    assert saved["evidence_ref"] == item["evidence_ref"]
    assert saved["evidence_expires_at"] == item["expires_at"]
    assert saved["detail"] == "The reporter's separate statement."
    assert "An authoritative source line." not in json.dumps(saved)
    shown = community.show_report(receipt["report_id"])
    assert shown["evidence"]["status"] == "retained"
    assert shown["evidence"]["text"] == "An authoritative source line."
    assert shown["actions"] == [] and shown["status"] == "open"
    assert counts("world_mutations", "sanctions") == (0, 0)


def test_anonymous_evidence_can_be_reported_after_key_issuance(clock):
    db.init_db()
    item = chat(display_name="Earlier guest")
    key = "nw_" + "a" * 32
    db.mint_invite_key(key, "Ada")
    receipt = report(key, item["evidence_ref"])
    saved = community.show_report(receipt["report_id"])
    assert saved["target_id"] is None
    assert saved["target_session_id"] == saved["evidence"]["session_id"]
    assert saved["evidence"]["name"] == "Earlier guest"


@pytest.mark.parametrize("target_kind", ["human", "agent"])
def test_roster_report_uses_trusted_stable_target_without_chat(accounts, clock, target_kind):
    target = participants.identify(accounts[1])["id"] if target_kind == "human" else blocks.agent_target("Tessera")
    assert target
    receipt = report(accounts[0], target_id=target, detail="")
    saved = community.show_report(receipt["report_id"])
    assert saved["target_id"] == target and saved["target_session_id"] is None
    assert saved["evidence"] == {"status": "none"}


def test_new_report_rejects_deleted_unknown_wrong_world_and_mismatched_evidence(accounts, clock):
    item = chat(accounts[1])
    target = participants.identify(accounts[0])["id"]
    for overrides in ({"world_seed": 383}, {"evidence_ref": "f" * 32}, {"target_id": target}):
        with pytest.raises(community.EvidenceUnavailable):
            report(accounts[0], item["evidence_ref"], **overrides)
    community.delete_chat_message(item["evidence_ref"])
    with pytest.raises(community.EvidenceUnavailable):
        report(accounts[0], item["evidence_ref"])
    assert counts("private_reports") == (0,)


def test_invalid_evidence_rolls_back_new_reporter_enrollment(accounts, clock):
    assert counts("participants", "participant_credentials") == (0, 0)
    with pytest.raises(community.EvidenceUnavailable):
        report(accounts[0], "f" * 32)
    assert counts("participants", "participant_credentials", "private_reports", "community_policies") == (0, 0, 0, 0)


def test_report_evidence_deletion_is_rechecked_after_acquiring_writer(accounts, clock, monkeypatch):
    item = chat(accounts[1])
    # A surface may have resolved this reference before its write transaction.
    assert community.evidence_author(evidence_ref=item["evidence_ref"], world_seed=382)
    original = db.transaction
    waiting = True

    @contextmanager
    def delayed_writer():
        nonlocal waiting
        if waiting:
            waiting = False
            # Commit a real operator deletion before the report gets its writer.
            assert community.delete_chat_message(item["evidence_ref"])["deleted"] == 1
        with original() as conn:
            yield conn

    monkeypatch.setattr(db, "transaction", delayed_writer)
    with pytest.raises(community.EvidenceUnavailable):
        report(accounts[0], item["evidence_ref"])
    assert counts("private_reports", "participants", "participant_credentials") == (0, 1, 1)
    assert counts("private_chat_messages") == (0,)


def test_report_insert_fault_rolls_back_enrollment_and_new_policy(accounts, clock):
    item = chat(accounts[1])
    with db._connection() as conn:
        conn.execute("""CREATE TRIGGER reject_report BEFORE INSERT ON private_reports
            BEGIN SELECT RAISE(ABORT,'fixture private error'); END""")
    with pytest.raises(community.CommunityUnavailable):
        report(accounts[0], item["evidence_ref"], policy_snapshot='{"policy":"new-report-policy"}')
    assert counts("private_reports", "participants", "participant_credentials", "community_policies") == (0, 1, 1, 1)


def test_retry_recovers_exact_receipt_after_rotation_and_in_new_process(accounts, clock):
    item = chat(accounts[1])
    options = report_options(accounts[0], item["evidence_ref"])
    first = community.submit_report(**options)
    deadline = rows("private_reports")[0]["expires_at"]
    community.close_report(first["report_id"], operator="Fixture")
    community.delete_chat_message(item["evidence_ref"])
    replacement = "nw_" + "c" * 32
    participants.rotate(accounts[0], replacement)
    clock.now += timedelta(days=2)  # Source chat was deleted; receipt is still retained.
    options["user_key"] = replacement
    assert community.lookup_report_retry(replacement, options["request_id"], options["fingerprint"]) == first
    # The persistence retry itself runs before stale/invalid target and evidence.
    assert community.submit_report(**{**options, "target_id": "stale-handle", "retention_days": 0,
                                      "policy_snapshot": "invalid"}) == first
    script = """
from datetime import datetime
from pathlib import Path
import json, os
import persistence as db
from persistence import community
db._DB_PATH = Path(os.environ['COMMUNITY_TEST_DB'])
community.utc_now = lambda: datetime.fromisoformat(os.environ['COMMUNITY_TEST_NOW'])
print(json.dumps(community.lookup_report_retry(os.environ['COMMUNITY_TEST_KEY'],
    os.environ['COMMUNITY_TEST_REQUEST'], os.environ['COMMUNITY_TEST_FINGERPRINT'])))
"""
    environment = {**os.environ, "COMMUNITY_TEST_DB": str(db._DB_PATH), "COMMUNITY_TEST_NOW": clock.now.isoformat(),
                   "COMMUNITY_TEST_KEY": replacement, "COMMUNITY_TEST_REQUEST": options["request_id"],
                   "COMMUNITY_TEST_FINGERPRINT": options["fingerprint"]}
    result = subprocess.run([sys.executable, "-c", script], env=environment, capture_output=True,
                            text=True, check=True, timeout=10)
    assert json.loads(result.stdout) == first
    assert counts("private_reports") == (1,) and rows("private_reports")[0]["expires_at"] == deadline


def test_retry_conflict_is_scoped_to_stable_reporter(accounts, clock):
    item = chat(accounts[1])
    options = report_options(accounts[0], item["evidence_ref"])
    first = community.submit_report(**options)
    with pytest.raises(community.ReportConflict):
        community.lookup_report_retry(accounts[0], options["request_id"], "e" * 64)
    with pytest.raises(community.ReportConflict):
        community.submit_report(**{**options, "fingerprint": "e" * 64})
    assert community.lookup_report_retry(accounts[1], options["request_id"], options["fingerprint"]) is None
    second = community.submit_report(**{**options, "user_key": accounts[1], "evidence_ref": None,
                                       "target_id": blocks.agent_target("Tessera")})
    assert first != second and counts("private_reports") == (2,)


@pytest.mark.parametrize("dashed_first", [False, True])
def test_uuid_aliases_reuse_a_frozen_request_without_changing_fingerprint(accounts, clock, dashed_first):
    identifier = uuid.uuid4()
    original, alias = ((str(identifier), identifier.hex) if dashed_first
                       else (identifier.hex, str(identifier)))
    options = report_options(accounts[0], target_id=participants.identify(accounts[1])["id"],
                             request_id=original)
    receipt = community.submit_report(**options)
    assert community.lookup_report_retry(accounts[0], alias, options["fingerprint"]) == receipt
    assert community.submit_report(**{**options, "request_id": alias}) == receipt
    saved = rows("private_reports")
    assert len(saved) == 1
    assert saved[0]["request_id"] == identifier.hex
    assert saved[0]["fingerprint"] == options["fingerprint"]
    with pytest.raises(community.ReportConflict):
        community.lookup_report_retry(accounts[0], alias, "e" * 64)


def test_retry_lookup_does_not_enroll_an_unused_reporter_or_take_write_lock(accounts, clock, monkeypatch):
    @contextmanager
    def forbidden():
        raise AssertionError("Readonly receipt lookup must not write.")
        yield

    monkeypatch.setattr(db, "transaction", forbidden)
    assert community.lookup_report_retry(accounts[0], uuid.uuid4().hex, "a" * 64) is None
    assert counts("participants", "participant_credentials") == (0, 0)


def test_concurrent_exact_report_retries_insert_one_case(accounts, clock):
    item = chat(accounts[1])
    options = report_options(accounts[0], item["evidence_ref"])
    barrier = threading.Barrier(8)

    def submit(_):
        barrier.wait()
        return community.submit_report(**options)

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(submit, range(8)))
    assert all(result == results[0] for result in results)
    assert counts("private_reports", "report_actions", "participants") == (1, 0, 2)


def test_receipt_idempotency_expires_without_permanent_tombstone(accounts, clock):
    target = participants.identify(accounts[1])["id"]
    options = report_options(accounts[0], target_id=target, retention_days=1)
    first = community.submit_report(**options)
    community.close_report(first["report_id"], operator="Fixture reviewer")
    clock.now += timedelta(days=1)
    assert community.lookup_report_retry(accounts[0], options["request_id"], options["fingerprint"]) is None
    assert community.show_report(first["report_id"]) is None
    second = community.submit_report(**{**options, "fingerprint": "f" * 64})
    assert first != second and counts("private_reports", "report_actions") == (1, 0)


def test_closed_report_evidence_remains_until_operator_deletes_it(accounts, clock):
    item = chat(accounts[1], text="Deletable evidence")
    receipt = report(accounts[0], item["evidence_ref"])
    community.close_report(receipt["report_id"], operator="Fixture reviewer")
    clock.now += timedelta(days=1)
    shown = community.show_report(receipt["report_id"])
    assert shown["evidence"]["text"] == "Deletable evidence"
    assert counts("private_chat_messages", "private_reports") == (1, 1)
    assert community.status()["retained_chat"] == 1
    removed = community.prune_expired()
    assert removed == {"chat_messages": 0, "reports": 0, "actions": 0, "policies": 0}
    assert community.delete_chat_message(item["evidence_ref"])["deleted"] == 1
    shown = community.show_report(receipt["report_id"])
    assert shown["evidence"] == {"status": "unavailable"}
    assert "Deletable evidence" not in json.dumps(shown)


def until_deleted_chat(key=None, **changes):
    return chat(key, **changes)


def test_until_deleted_chat_has_no_expiry_and_survives_housekeeping(accounts, clock):
    item = until_deleted_chat(accounts[1])
    stored = rows("private_chat_messages")[0]
    assert item["expires_at"] is stored["expires_at"] is stored["retention_days"] is None
    clock.now += timedelta(days=3650)
    assert community.evidence_author(evidence_ref=item["evidence_ref"], world_seed=382)["name"] == "Bea"
    assert community.status()["retained_chat"] == 1
    assert community.prune_expired() == {"chat_messages": 0, "reports": 0, "actions": 0, "policies": 0}
    receipt = report(accounts[0], item["evidence_ref"])
    assert community.show_report(receipt["report_id"])["evidence"]["text"] == "A private line."
    assert rows("private_reports")[0]["evidence_expires_at"] is None
    assert counts("world_mutations") == (0,)


@pytest.mark.parametrize("state", ["open", "acknowledged"])
def test_pending_complaint_holds_case_actions_and_evidence_past_deadlines(accounts, clock, state):
    item = chat(accounts[1])
    receipt = report(accounts[0], item["evidence_ref"])
    if state == "acknowledged":
        community.acknowledge_report(receipt["report_id"], operator="Fixture")
    clock.now += timedelta(days=4)
    assert community.status()["retained_chat"] == 1
    shown = community.show_report(receipt["report_id"])
    assert shown["status"] == state and shown["evidence"]["status"] == "retained"
    assert len(shown["actions"]) == (state == "acknowledged")
    assert community.prune_expired() == {"chat_messages": 0, "reports": 0, "actions": 0, "policies": 0}
    held = community.delete_chat_message(item["evidence_ref"])
    assert held["matched"] == held["held"] == 1 and held["deleted"] == 0
    assert "open or acknowledged report" in held["hold_reason"]
    community.close_report(receipt["report_id"], operator="Fixture")
    assert community.show_report(receipt["report_id"]) is None
    removed = community.prune_expired()
    assert removed["chat_messages"] == 0 and removed["reports"] == 1
    assert removed["actions"] == 1 + (state == "acknowledged")
    assert community.status()["retained_chat"] == 1
    assert community.evidence_author(evidence_ref=item["evidence_ref"], world_seed=382)
    # Closing releases the hold but does not auto-complete the deletion request.
    assert community.delete_chat_message(item["evidence_ref"])["deleted"] == 1


def test_delete_tester_skips_held_lines_and_covers_rotated_keys_and_worlds(accounts, clock):
    held = until_deleted_chat(accounts[1])
    receipt = report(accounts[0], held["evidence_ref"])
    replacement = "nw_" + "c" * 32
    participants.rotate(accounts[1], replacement)
    until_deleted_chat(replacement, world_seed=383)
    until_deleted_chat(accounts[0])
    result = community.delete_tester_chat("Bea")
    assert (result["matched"], result["deleted"], result["held"]) == (2, 1, 1)
    assert result["hold_reason"] and result["backup_copies"]
    assert counts("private_chat_messages", "world_mutations") == (2, 0)
    assert community.show_report(receipt["report_id"])["status"] == "open"
    community.close_report(receipt["report_id"], operator="Fixture")
    assert community.delete_tester_chat("Bea")["deleted"] == 1
    assert community.delete_tester_chat("Bea")["matched"] == 0
    assert counts("private_chat_messages") == (1,)


@pytest.mark.parametrize("evidence", [False, True])
def test_self_report_refused_after_authoritative_target_resolution(accounts, clock, evidence):
    item = until_deleted_chat(accounts[0])
    with pytest.raises(community.CommunityError):
        report(accounts[0], item["evidence_ref"] if evidence else None,
               target_id=None if evidence else item["participant_id"])
    assert counts("private_reports") == (0,)


def test_operator_actions_are_private_append_only_and_share_case_deadline(accounts, clock):
    item = chat(accounts[1])
    receipt = report(accounts[0], item["evidence_ref"])
    report_id = receipt["report_id"]
    deadline = rows("private_reports")[0]["expires_at"]
    ack = community.acknowledge_report(report_id, operator="Reviewer A", note="First assessment\n\x1b[2J")
    clock.now += timedelta(hours=1)
    closed = community.close_report(report_id, operator="Reviewer B", note="Handled independently.")
    assert ack["status"] == "acknowledged" and closed["status"] == "closed"
    shown = community.show_report(report_id)
    assert [entry["action"] for entry in shown["actions"]] == ["acknowledge", "close"]
    assert [entry["operator"] for entry in shown["actions"]] == ["Reviewer A", "Reviewer B"]
    assert all(entry["expires_at"] == deadline for entry in shown["actions"])
    assert shown["expires_at"] == deadline
    with pytest.raises(community.CommunityError):
        community.acknowledge_report(report_id, operator="Reviewer C")
    assert community.list_reports(state="open") == []
    assert community.list_reports(state="closed")[0]["id"] == report_id
    assert counts("world_mutations", "sanctions", "sanction_lifts") == (0, 0, 0)
    clock.now += timedelta(days=3)
    assert community.list_reports() == [] and community.show_report(report_id) is None
    with pytest.raises(community.CommunityError):
        community.close_report(report_id, operator="Reviewer")
    removed = community.prune_expired()
    assert removed == {"chat_messages": 0, "reports": 1, "actions": 2, "policies": 0}
    assert counts("private_chat_messages", "private_reports", "report_actions", "community_policies") == (1, 0, 0, 1)
    assert community.evidence_author(evidence_ref=item["evidence_ref"], world_seed=382)["expires_at"] is None
    community.delete_chat_message(item["evidence_ref"])
    assert community.prune_expired()["policies"] == 1


def test_operator_action_and_state_change_rollback_together(accounts, clock):
    item = chat(accounts[1])
    receipt = report(accounts[0], item["evidence_ref"])
    with db._connection() as conn:
        conn.execute("""CREATE TRIGGER reject_state BEFORE UPDATE ON private_reports
            BEGIN SELECT RAISE(ABORT,'fixture private state error'); END""")
    with pytest.raises(community.CommunityUnavailable):
        community.close_report(receipt["report_id"], operator="Reviewer", note="Private note")
    assert counts("report_actions") == (0,)
    assert community.show_report(receipt["report_id"])["status"] == "open"


def test_policy_snapshots_deduplicate_and_policy_changes_never_expire_existing_chat(accounts, clock):
    document = {"chat": {"enabled": True, "retention_mode": "until_deleted"}, "a": 1, "z": "☃"}
    old = chat(accounts[1], policy_snapshot=json.dumps(document))
    same = chat(accounts[1], policy_snapshot=json.dumps(dict(reversed(list(document.items()))), indent=3))
    assert old["expires_at"] is same["expires_at"] is None and counts("community_policies") == (1,)
    changed = chat(accounts[1], policy_snapshot=json.dumps({**document, "a": 2}))
    assert changed["expires_at"] is None and counts("community_policies") == (2,)
    with pytest.raises(community.CommunityError):
        chat(accounts[1], retention_days=1, retention_mode="days")
    clock.now += timedelta(days=3650)
    assert community.prune_expired() == {"chat_messages": 0, "reports": 0, "actions": 0, "policies": 0}
    assert {item["evidence_ref"] for item in rows("private_chat_messages")} == {
        old["evidence_ref"], same["evidence_ref"], changed["evidence_ref"]}
    community.delete_chat_message(changed["evidence_ref"])
    assert community.prune_expired() == {"chat_messages": 0, "reports": 0, "actions": 0, "policies": 1}
    policy = rows("community_policies")[0]
    assert json.loads(policy["snapshot_json"]) == document
    assert policy["digest"] == hashlib.sha256(policy["snapshot_json"].encode()).hexdigest()


def test_idle_cleanup_and_status_use_no_writer_or_migration(accounts, clock, monkeypatch):
    chat(accounts[0])

    @contextmanager
    def forbidden():
        raise AssertionError("Nothing expired: do not take the SQLite writer.")
        yield

    monkeypatch.setattr(db, "transaction", forbidden)
    monkeypatch.setattr(db, "init_db", lambda: (_ for _ in ()).throw(AssertionError("Readonly call migrated DB.")))
    assert community.prune_expired() == {"chat_messages": 0, "reports": 0, "actions": 0, "policies": 0}
    assert community.status() == {"available": True, "storage_error": False, "retained_chat": 1,
                                  "open_reports": 0, "acknowledged_reports": 0, "closed_reports": 0}


@pytest.mark.parametrize("kind", ["missing", "older_schema", "corrupt"])
def test_status_does_not_create_or_migrate_absent_uninitialized_or_corrupt_storage(clock, kind):
    if kind == "older_schema":
        with sqlite3.connect(db._DB_PATH) as conn:
            conn.execute("CREATE TABLE old_data(value TEXT)")
    elif kind == "corrupt":
        db._DB_PATH.write_text("not a sqlite database")
    before = db._DB_PATH.read_bytes() if db._DB_PATH.exists() else None
    result = community.status()
    assert result["available"] is False and result["storage_error"] is (kind == "corrupt")
    assert all(result[field] is None for field in ("retained_chat", "open_reports", "acknowledged_reports", "closed_reports"))
    assert (db._DB_PATH.read_bytes() if db._DB_PATH.exists() else None) == before


@pytest.mark.parametrize("override", [
    {"retention_days": 1}, {"retention_days": 30}, {"retention_days": 0},
    {"retention_days": True}, {"retention_days": 36501},
    {"policy_snapshot": "[]"}, {"policy_snapshot": '{"a":1,"a":2}'}, {"policy_snapshot": '{"a":NaN}'},
    {"policy_snapshot": '{"a":"' + "x" * 65536 + '"}'}, {"session_id": "short-session"},
    {"world_seed": True}, {"world_seed": 2**63}, {"text": ""}, {"text": "x" * 257},
    {"text": "\ud800"}, {"text": "text\x00text"}, {"node_name": ""}, {"display_name": ""},
    {"retention_mode": []}, {"retention_mode": "forever"},
    {"retention_mode": "days"},
    {"policy_snapshot": '{"chat":{"enabled":true,"retention_days":1}}'},
])
def test_invalid_chat_input_never_collects_or_enrolls(accounts, clock, override):
    with pytest.raises(community.CommunityError):
        chat(accounts[0], **override)
    assert counts("private_chat_messages", "participants", "community_policies") == (0, 0, 0)


@pytest.mark.parametrize("override", [
    {"reason": "not-a-reason"}, {"reason": []}, {"detail": "x" * 2001}, {"detail": None},
    {"request_id": "c1"}, {"fingerprint": "short"}, {"target_id": "Bea"}, {"target_id": "agent:MadeUp"},
    {"target_id": "f" * 32}, {"world_seed": True}, {"retention_days": 0}, {"policy_snapshot": "null"},
])
def test_invalid_report_input_never_creates_reporter_or_case(accounts, clock, override):
    options = report_options(accounts[0], **override)
    with pytest.raises(community.CommunityError):
        community.submit_report(**options)
    assert counts("private_reports", "participants", "community_policies") == (0, 0, 0)


@pytest.mark.parametrize("function,kwargs", [
    (community.list_reports, {"state": []}), (community.list_reports, {"limit": True}),
    (community.list_reports, {"limit": 201}),
])
def test_operator_read_validation_is_bounded(accounts, clock, function, kwargs):
    with pytest.raises(community.CommunityError):
        function(**kwargs)
