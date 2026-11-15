"""Completed private erasure survives restore without targeting future chat."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from types import SimpleNamespace
import uuid

import pytest

import persistence as db
from persistence import community, community_deletions

POLICY = '{"chat":{"enabled":true,"retention_mode":"until_deleted"}}'


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr(community, "utc_now", lambda: datetime(2026, 11, 15, 12, tzinfo=timezone.utc))


def chat(key, text="Synthetic private line"):
    return community.append_chat(user_key=key, session_id=uuid.uuid4().hex, world_seed=382,
        node_name="Synthetic room", text=text, display_name="ignored", retention_days=None,
        retention_mode="until_deleted", policy_snapshot=POLICY)


def report(key, item):
    request = uuid.uuid4().hex
    return community.submit_report(user_key=key, request_id=request,
        fingerprint=hashlib.sha256(request.encode()).hexdigest(), world_seed=382,
        target_id=None, evidence_ref=item["evidence_ref"], reason="other", detail="Synthetic complaint",
        retention_days=3, policy_snapshot=POLICY)["report_id"]


def ledger():
    with db._connection() as conn:
        return community_deletions.records_on(conn)


def retained_refs():
    with db._connection() as conn:
        return {row[0] for row in conn.execute("SELECT evidence_ref FROM private_chat_messages")}


@pytest.mark.parametrize("operation", ["one", "tester"])
def test_completed_deletion_is_carried_from_live_db_through_old_backup(accounts, tmp_path, operation):
    item = chat(accounts[0])
    backup = tmp_path / "before-request.db"
    db.backup_to(backup)
    result = (community.delete_chat_message(item["evidence_ref"]) if operation == "one"
              else community.delete_tester_chat("ada"))
    assert result["deleted"] == 1
    proof = ledger()
    assert proof == [(item["evidence_ref"], "2026-11-15T12:00:00.000000Z")]
    db.restore_from(backup)
    assert retained_refs() == set()
    assert ledger() == proof
    assert community.status()["retained_chat"] == 0
    assert db.get_mutations(382) == []


@pytest.mark.parametrize("failed_operation", ["record", "erase"])
def test_erasure_and_proof_roll_back_together(accounts, failed_operation):
    item = chat(accounts[0])
    table, operation = (("private_chat_deletions", "INSERT") if failed_operation == "record"
                        else ("private_chat_messages", "DELETE"))
    with db._connection() as conn:
        conn.execute(f"""CREATE TRIGGER reject_erasure BEFORE {operation} ON {table}
            BEGIN SELECT RAISE(ABORT,'synthetic confidential storage failure'); END""")
    with pytest.raises(community.CommunityUnavailable):
        community.delete_chat_message(item["evidence_ref"])
    assert retained_refs() == {item["evidence_ref"]}
    assert ledger() == []


def test_bulk_proof_excludes_held_rows_and_never_targets_later_messages(accounts):
    held, eligible = chat(accounts[0]), chat(accounts[0])
    case = report(accounts[1], held)
    result = community.delete_tester_chat(" ADA ")
    assert (result["deleted"], result["held"]) == (1, 1)
    assert [row[0] for row in ledger()] == [eligible["evidence_ref"]]
    later = chat(accounts[0])  # Same person and timestamp; a cutoff would erase it.
    community.close_report(case, operator="Synthetic operator")
    assert community_deletions.replay_pending() == 0
    assert retained_refs() == {held["evidence_ref"], later["evidence_ref"]}


def test_completed_proof_overrides_a_backups_stale_open_complaint(accounts, tmp_path):
    item = chat(accounts[0])
    case = report(accounts[1], item)
    backup = tmp_path / "open-case.db"
    db.backup_to(backup)
    community.close_report(case, operator="Synthetic operator")
    assert community.delete_chat_message(item["evidence_ref"])["deleted"] == 1
    db.restore_from(backup)
    restored = community.show_report(case)
    assert restored["status"] == "open"
    assert restored["evidence"] == {"status": "unavailable"}
    assert retained_refs() == set()


def test_lost_store_requires_external_export_before_any_private_restore(accounts, tmp_path, monkeypatch):
    item = chat(accounts[0], text="Text must never enter the deletion record")
    backup, export = tmp_path / "old.db", tmp_path / "private-deletions.json"
    db.backup_to(backup)
    community.delete_chat_message(item["evidence_ref"])
    assert community_deletions.export_to(export)["exported"] == 1
    record = json.loads(export.read_text())
    assert record == {"schema_version": 1, "deletions": [
        {"evidence_ref": item["evidence_ref"], "deleted_at": "2026-11-15T12:00:00.000000Z"}]}
    assert export.stat().st_mode & 0o777 == 0o600
    recovered = tmp_path / "lost-volume" / "worlds.db"
    monkeypatch.setattr(db, "_DB_PATH", recovered)
    with pytest.raises(ValueError, match="separately preserved deletion export"):
        db.restore_from(backup)
    assert not recovered.exists()
    db.restore_from(backup, deletions=export)
    assert retained_refs() == set()
    assert ledger() == [(item["evidence_ref"], "2026-11-15T12:00:00.000000Z")]
    assert recovered.stat().st_mode & 0o777 == 0o600


def test_explicit_empty_export_allows_recovery_when_no_requests_exist(accounts, tmp_path, monkeypatch):
    item = chat(accounts[0])
    backup, export = tmp_path / "old.db", tmp_path / "no-requests.json"
    db.backup_to(backup)
    community_deletions.export_to(export)
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "recovered.db")
    db.restore_from(backup, deletions=export)
    assert retained_refs() == {item["evidence_ref"]}


@pytest.mark.parametrize("payload", [
    '{"schema_version":1,"deletions":[],"message":"forbidden field"}',
    '{"schema_version":1,"schema_version":1,"deletions":[]}',
    '{"schema_version":true,"deletions":[]}',
    '{"schema_version":1,"deletions":[{"evidence_ref":"bad","deleted_at":"2026-11-15"}]}',
    '{"schema_version":1,"deletions":[{"evidence_ref":"' + "a" * 32 + '","deleted_at":"private text"}]}',
    'not JSON',
])
def test_invalid_external_record_never_changes_live_data(accounts, tmp_path, payload):
    item = chat(accounts[0])
    backup, export = tmp_path / "snapshot.db", tmp_path / "invalid.json"
    db.backup_to(backup)
    db.record_mutation(382, "Retained after snapshot", "AGENT_VISIT", None, {})
    export.write_text(payload)
    before = db.get_mutations(382)
    with pytest.raises(community.CommunityError, match="deletion record is invalid"):
        db.restore_from(backup, deletions=export)
    assert db.get_mutations(382) == before
    assert retained_refs() == {item["evidence_ref"]}


def test_schema32_restore_carries_proof_without_migrating_the_candidate(accounts, tmp_path):
    item = chat(accounts[0])
    source = tmp_path / "schema32.db"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE world_mutations(id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE schema_version(version INTEGER PRIMARY KEY)")
        conn.executemany("INSERT INTO schema_version VALUES (?)", [(version,) for version in range(1, 33)])
    community.delete_chat_message(item["evidence_ref"])
    proof = ledger()
    db.restore_from(source)
    with sqlite3.connect(db._DB_PATH) as conn:
        assert conn.execute("SELECT max(version) FROM schema_version").fetchone()[0] == 32
        assert community_deletions.records_on(conn) == proof
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='private_chat_messages'").fetchone() is None


def test_startup_replay_removes_proven_rows_before_normal_reads(accounts):
    item = chat(accounts[0])
    with db._connection() as conn:
        conn.execute("INSERT INTO private_chat_deletions VALUES (?,?)",
                     (item["evidence_ref"], "2026-11-15T12:00:00.000000Z"))
    assert community_deletions.replay_pending() == 1
    assert community_deletions.replay_pending() == 0
    with pytest.raises(community.EvidenceUnavailable):
        community.evidence_author(evidence_ref=item["evidence_ref"], world_seed=382)


def test_server_replays_completed_deletion_before_binding_a_listener(accounts, monkeypatch):
    import server
    from tests.test_community_activation import _quiet_dependencies

    item = chat(accounts[0])
    with db._connection() as conn:
        conn.execute("INSERT INTO private_chat_deletions VALUES (?,?)",
                     (item["evidence_ref"], "2026-11-15T12:00:00.000000Z"))
    events = []
    _quiet_dependencies(monkeypatch, events)

    class Listener:
        def __init__(self, *_args):
            assert retained_refs() == set()
            assert ledger()[0][0] == item["evidence_ref"]
            events.append("bound after reconciliation")

        def serve_forever(self):
            pass

        def server_close(self):
            pass

    monkeypatch.setattr(server, "_ThreadedServer", Listener)
    monkeypatch.setattr(server, "_start_community_retention", lambda: (
        SimpleNamespace(set=lambda: None),
        SimpleNamespace(join=lambda **_kwargs: None, is_alive=lambda: False)))
    server.run(port=0)
    assert "bound after reconciliation" in events
