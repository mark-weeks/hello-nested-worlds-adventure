"""Money is reserved before dispatch and never refunded by a process restart."""
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

import pytest

import persistence as db
from persistence import model_spend as spend, participants, sanctions


@pytest.fixture
def clock(monkeypatch):
    clock = SimpleNamespace(now=datetime(2026, 1, 1, 12, tzinfo=timezone.utc))
    monkeypatch.setattr(spend, "utc_now", lambda: clock.now)
    return clock


def reservation_options(key, amount=10, **overrides):
    options = dict(user_key=key, reserved_microusd=amount,
                   global_limit_microusd=100, participant_limit_microusd=50,
                   policy_snapshot='{"policy":"fixture-a"}', task="node",
                   adapter="fixture", endpoint="https://provider.example.test/v1/chat/completions",
                   model="fixture model", retention_days=2)
    options.update(overrides)
    return options


def reserve(key, amount=10, **overrides):
    return spend.reserve(**reservation_options(key, amount, **overrides))


def cold_reserve(options, clock, *, startup=False):
    """A separate interpreter reads the same DB, with no inherited module state."""
    script = """
from datetime import datetime
from pathlib import Path
import json, os
import persistence as db
from persistence import model_spend as spend
db._DB_PATH = Path(os.environ['ENFOLDED_LEDGER_TEST_DB'])
spend.utc_now = lambda: datetime.fromisoformat(os.environ['ENFOLDED_LEDGER_TEST_NOW'])
request = json.loads(os.environ['ENFOLDED_LEDGER_TEST_REQUEST'])
if os.environ['ENFOLDED_LEDGER_TEST_STARTUP'] == '1':
    spend.check_unsettled_on_startup()
try:
    result = {'id': spend.reserve(**request)}
except spend.ModelSpendDenied as exc:
    result = {'denied': type(exc).__name__}
result['status'] = spend.status(user_key=request['user_key'])
print(json.dumps(result))
"""
    env = {**os.environ, "ENFOLDED_LEDGER_TEST_DB": str(db._DB_PATH),
           "ENFOLDED_LEDGER_TEST_NOW": clock.now.isoformat(),
           "ENFOLDED_LEDGER_TEST_STARTUP": "1" if startup else "0",
           "ENFOLDED_LEDGER_TEST_REQUEST": json.dumps(options)}
    result = subprocess.run([sys.executable, "-c", script], env=env,
                            check=True, capture_output=True, text=True, timeout=10)
    return json.loads(result.stdout)


def settle(reservation, actual=None, **overrides):
    options = dict(actual_microusd=actual, usage_json=None, resolved_model=None)
    options.update(overrides)
    return spend.settle(reservation, **options)


def rows():
    db.init_db()
    with db._connection() as conn:
        cursor = conn.execute("""SELECT r.*,p.policy_json FROM model_spend_reservations r
            JOIN model_spend_policies p ON p.digest=r.policy_digest ORDER BY r.created_at,r.id""")
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor]


def row(reservation):
    return next(item for item in rows() if item["id"] == reservation)


def enrolled():
    with db._connection() as conn:
        return tuple(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                     for table in ("participants", "participant_credentials"))


def test_complete_usage_releases_only_the_unused_reservation(accounts, clock):
    rid = reserve(accounts[0], 20)
    before = row(rid)
    assert before["status"] == "reserved" and before["accounted_microusd"] == 20
    assert before["reserved_microusd"] == 20 and before["settled_at"] is None
    usage = '{"input_tokens":4,"output_tokens":1,"cache_read_tokens":null,"cache_write_tokens":0}'
    settle(rid, 7, usage_json=usage, resolved_model="fixture resolved model")
    saved = row(rid)
    assert saved["status"] == "settled" and saved["accounted_microusd"] == 7
    assert saved["reserved_microusd"] == 20
    assert json.loads(saved["usage_json"]) == json.loads(usage)
    assert saved["resolved_model"] == "fixture resolved model"
    assert spend.status(user_key=accounts[0]) == {
        "day": "2026-01-01", "global_accounted_microusd": 7,
        "participant_accounted_microusd": 7, "latched": False,
        "stop_reason": None, "unresolved_reservations": 0, "abandoned_reservations": 0,
        "storage_error": False, "ledger_state": "ready"}
    reserve(accounts[0], 43)  # The refund is reusable, without a second bucket.
    with pytest.raises(spend.ParticipantLimitExceeded):
        reserve(accounts[0], 1)


def test_zero_is_an_explicit_valid_amount_and_limit(accounts, clock):
    rid = reserve(accounts[0], 0, global_limit_microusd=0, participant_limit_microusd=0)
    settle(rid, 0)
    assert row(rid)["accounted_microusd"] == 0
    assert spend.status(user_key=accounts[0])["participant_accounted_microusd"] == 0


def test_limits_span_policy_route_adapter_and_model_changes(accounts, clock):
    reserve(accounts[0], 30)
    with pytest.raises(spend.ParticipantLimitExceeded):
        reserve(accounts[0], 25, policy_snapshot='{"policy":"fixture-b"}',
                task="moderation", adapter="other", model="other model",
                endpoint="https://another.example.test/chat/completions")
    reserve(accounts[1], 40)
    with pytest.raises(spend.GlobalLimitExceeded):
        reserve(accounts[1], 31, participant_limit_microusd=100)
    with pytest.raises(spend.GlobalLimitExceeded):
        reserve(accounts[0], 0, global_limit_microusd=69)
    with pytest.raises(spend.ParticipantLimitExceeded):
        reserve(accounts[0], 0, participant_limit_microusd=29)
    assert spend.status()["global_accounted_microusd"] == 70


@pytest.mark.parametrize("kind", ["global", "participant"])
def test_budget_refusal_rolls_back_first_use_participant_enrollment(accounts, clock, kind):
    assert enrolled() == (0, 0)
    options = {"global_limit_microusd": 0} if kind == "global" else {"participant_limit_microusd": 0}
    with pytest.raises(spend.ModelSpendDenied):
        reserve(accounts[0], 1, **options)
    assert enrolled() == (0, 0)
    assert rows() == []
    assert db.get_mutations(382) == []


def test_concurrent_reservations_cannot_overspend_global_limit(accounts, clock):
    start = threading.Barrier(8)

    def attempt(index):
        start.wait()
        try:
            return reserve(accounts[index % 2], 7, global_limit_microusd=21,
                           participant_limit_microusd=100,
                           policy_snapshot=json.dumps({"policy": index}))
        except spend.GlobalLimitExceeded:
            return None

    with ThreadPoolExecutor(8) as pool:
        outcomes = list(pool.map(attempt, range(8)))
    assert len([outcome for outcome in outcomes if outcome]) == 3
    assert len(rows()) == 3 and spend.status()["global_accounted_microusd"] == 21


def test_concurrent_same_credential_has_one_stable_participant_and_cap(accounts, clock):
    start = threading.Barrier(8)

    def attempt(_):
        start.wait()
        try:
            return reserve(accounts[0], 4, global_limit_microusd=1000,
                           participant_limit_microusd=10)
        except spend.ParticipantLimitExceeded:
            return None

    with ThreadPoolExecutor(8) as pool:
        outcomes = list(pool.map(attempt, range(8)))
    assert len([outcome for outcome in outcomes if outcome]) == 2
    assert enrolled() == (1, 1)
    assert spend.status(user_key=accounts[0])["participant_accounted_microusd"] == 8


def test_rotation_and_a_cold_process_do_not_reset_an_abandoned_reservation(accounts, clock):
    original = reserve(accounts[0], 40)
    owner = row(original)["participant_id"]
    replacement = "nw_" + "c" * 32
    participants.rotate(accounts[0], replacement)
    assert row(original)["status"] == "reserved"
    cold = cold_reserve(reservation_options(replacement, 11), clock)
    assert cold["denied"] == "ParticipantLimitExceeded"
    assert cold["status"]["participant_accounted_microusd"] == 40
    second = reserve(replacement, 10)
    assert row(second)["participant_id"] == owner
    with pytest.raises(spend.ModelSpendDenied):
        reserve(accounts[0], 0)
    assert spend.status(user_key=replacement)["participant_accounted_microusd"] == 50


def test_missing_revoked_and_sanctioned_credentials_cannot_reserve(accounts, clock):
    for key in ("", "not-an-invite"):
        with pytest.raises(spend.ModelSpendDenied):
            reserve(key)
    assert enrolled() == (0, 0)
    rid = reserve(accounts[0], 10)
    assert db.revoke_invite_key(accounts[0])
    with pytest.raises(spend.ModelSpendDenied):
        reserve(accounts[0])
    ban = sanctions.ban("Bea", "Private fixture reason")
    with pytest.raises(spend.ModelSpendDenied):
        reserve(accounts[1])
    # In-flight work still settles after its author loses access.
    settle(rid, 3)
    assert row(rid)["accounted_microusd"] == 3
    sanctions.lift(ban["id"], "Fixture ended")
    reserve(accounts[1], 1)


def test_unknown_usage_keeps_full_reservation_and_first_settlement_wins(accounts, clock):
    rid = reserve(accounts[0], 20)
    settle(rid, usage_json='{"input_tokens":null}')
    saved = row(rid)
    assert saved["status"] == "uncertain" and saved["accounted_microusd"] == 20
    clock.now += timedelta(hours=1)
    settle(rid, 1, usage_json='{"input_tokens":1}', resolved_model="later model")
    assert row(rid) == saved
    assert spend.status()["global_accounted_microusd"] == 20


def test_concurrent_settlements_choose_one_complete_result_atomically(accounts, clock):
    rid = reserve(accounts[0], 10)
    start = threading.Barrier(2)

    def complete(amount):
        start.wait()
        settle(rid, amount, usage_json=json.dumps({"input_tokens": amount}),
               resolved_model=f"model-{amount}")

    with ThreadPoolExecutor(2) as pool:
        list(pool.map(complete, (2, 8)))
    saved = row(rid)
    assert saved["accounted_microusd"] in {2, 8}
    assert json.loads(saved["usage_json"])["input_tokens"] == saved["accounted_microusd"]
    assert saved["resolved_model"] == f'model-{saved["accounted_microusd"]}'
    settle(rid, 0)
    assert row(rid) == saved


@pytest.mark.parametrize("actual, explicit_anomaly, accounted", [(12, False, 12), (2, True, 10), (None, True, 10)])
def test_anomaly_latches_all_routes_days_and_policies_persistently(accounts, clock,
                                                               actual, explicit_anomaly, accounted):
    rid = reserve(accounts[0], 10)
    settle(rid, actual, anomaly=explicit_anomaly)
    assert row(rid)["status"] == "anomaly"
    assert row(rid)["accounted_microusd"] == accounted
    clock.now += timedelta(days=4)
    cold = cold_reserve(reservation_options(accounts[1], 0,
        policy_snapshot='{"policy":"replacement"}', task="inhabitant",
        participant_limit_microusd=1000), clock)
    assert cold["denied"] == "SpendLatched" and cold["status"]["latched"] is True
    # Denied live attempts still prune expired rows, never the independent latch.
    assert rows() == []
    assert spend.status() == {"day": "2026-01-05", "global_accounted_microusd": 0,
                              "participant_accounted_microusd": None, "latched": True,
                              "stop_reason": "billing_anomaly", "unresolved_reservations": 0,
                              "abandoned_reservations": 0, "storage_error": False,
                              "ledger_state": "ready"}
    assert enrolled() == (1, 1)


def test_aggregate_after_an_overrun_can_exceed_sqlite_int64_without_overflow(accounts, clock):
    limit = spend.SQLITE_MAX
    first = reserve(accounts[0], limit - 1, global_limit_microusd=limit,
                    participant_limit_microusd=limit)
    reserve(accounts[0], 1, global_limit_microusd=limit, participant_limit_microusd=limit)
    settle(first, limit)
    assert spend.status(user_key=accounts[0])["global_accounted_microusd"] == limit + 1
    with pytest.raises(spend.SpendLatched):
        reserve(accounts[1], 0)


def test_settlement_after_midnight_keeps_original_day_and_new_day_has_its_own_cap(accounts, clock):
    clock.now = datetime(2026, 1, 1, 23, 59, tzinfo=timezone.utc)
    rid = reserve(accounts[0], 9, participant_limit_microusd=10)
    clock.now += timedelta(minutes=2)
    settle(rid, 3)
    assert row(rid)["day"] == "2026-01-01"
    assert row(rid)["settled_at"].startswith("2026-01-02T")
    assert spend.status()["global_accounted_microusd"] == 0
    reserve(accounts[0], 9, participant_limit_microusd=10)
    assert spend.status(user_key=accounts[0])["participant_accounted_microusd"] == 9


def test_clock_is_read_after_waiting_for_the_writer_lock(accounts, clock, monkeypatch):
    entered, read_clock = threading.Event(), threading.Event()
    outcome = {}

    def now():
        assert db.in_transaction()
        read_clock.set()
        return clock.now

    monkeypatch.setattr(spend, "utc_now", now)
    writer = db._connect()
    writer.execute("BEGIN IMMEDIATE")

    def wait_for_writer():
        entered.set()
        try:
            outcome["id"] = reserve(accounts[0])
        except BaseException as exc:
            outcome["error"] = exc

    worker = threading.Thread(target=wait_for_writer)
    worker.start()
    try:
        assert entered.wait(1)
        assert not read_clock.wait(0.1)
        clock.now += timedelta(days=1)
    finally:
        writer.rollback()
        writer.close()
    worker.join(5)
    assert not worker.is_alive() and "error" not in outcome
    assert row(outcome["id"])["day"] == "2026-01-02"


def test_retention_belongs_to_each_row_and_reads_settlement_do_not_prune(accounts, clock):
    long_lived = reserve(accounts[0], 3, retention_days=10)
    short_lived = reserve(accounts[0], 3, retention_days=2)
    settle(short_lived, 3)
    clock.now += timedelta(days=3)
    assert spend.status()["global_accounted_microusd"] == 0
    settle(long_lived, 1)
    assert {item["id"] for item in rows()} == {long_lived, short_lived}
    reserve(accounts[0], 1, retention_days=2)
    assert long_lived in {item["id"] for item in rows()}
    assert short_lived not in {item["id"] for item in rows()}
    assert row(long_lived)["retention_days"] == 10


def test_idle_housekeeping_needs_no_key_and_keeps_current_day_and_latch(accounts, clock):
    today = reserve(accounts[0], 0)
    # Force an old deadline to pin the current-day exclusion independently
    # of the normal, validated retention minimum.
    with db.transaction() as conn:
        conn.execute("UPDATE model_spend_reservations SET retain_until=? WHERE id=?",
                     ("2000-01-01T00:00:00.000000Z", today))
    assert spend.prune_expired() == 0 and row(today)["day"] == "2026-01-01"
    expired = reserve(accounts[0], 10)
    settle(expired, 12)
    clock.now += timedelta(days=3)
    assert spend.prune_expired() == 1
    assert [item["id"] for item in rows()] == [today]  # A concurrent in-flight row stays protected.
    assert spend.check_unsettled_on_startup() is True
    assert spend.prune_expired() == 1
    assert rows() == [] and spend.status()["latched"] is True
    assert spend.prune_expired() == 0


@pytest.mark.parametrize("field", ["reserved_microusd", "global_limit_microusd", "participant_limit_microusd"])
@pytest.mark.parametrize("invalid", [True, -1, 1.5, 2**63])
def test_invalid_money_is_refused_before_enrollment(accounts, clock, field, invalid):
    with pytest.raises(spend.ModelSpendDenied):
        reserve(accounts[0], **{field: invalid})
    assert enrolled() == (0, 0) and rows() == []


@pytest.mark.parametrize("invalid", [True, 1, 1.5, 2**63])
def test_invalid_retention_is_refused_without_a_new_account(accounts, clock, invalid):
    with pytest.raises(spend.ModelSpendDenied):
        reserve(accounts[0], retention_days=invalid)
    assert enrolled() == (0, 0) and rows() == []


@pytest.mark.parametrize("invalid", [True, -1, 1.5, 2**63])
def test_invalid_settlement_cannot_refund_the_reservation(accounts, clock, invalid):
    rid = reserve(accounts[0])
    before = row(rid)
    with pytest.raises(spend.ModelSpendDenied):
        settle(rid, invalid)
    assert row(rid) == before


@pytest.mark.parametrize("usage", ['{"messages":"private prompt"}', '{"output_tokens":"private reply"}',
                                  '{"input_tokens":true}', '{"cache_read_tokens":-1}',
                                  '{"cache_write_tokens":9223372036854775808}', '[]', 'not-json'])
def test_usage_accepts_only_normalized_numeric_counters(accounts, clock, usage):
    rid = reserve(accounts[0])
    before = row(rid)
    with pytest.raises(spend.ModelSpendDenied) as caught:
        settle(rid, 1, usage_json=usage)
    assert "private" not in str(caught.value)
    assert row(rid) == before


def test_endpoint_secrets_are_not_stored_or_echoed(accounts, clock):
    for endpoint in ("https://secret@provider.example.test/v1", "https://provider.example.test/v1?key=secret",
                     "https://provider.example.test/v1#secret"):
        with pytest.raises(spend.ModelSpendDenied) as caught:
            reserve(accounts[0], endpoint=endpoint)
        assert "secret" not in str(caught.value)
    assert rows() == [] and enrolled() == (0, 0)


def test_records_have_only_metadata_and_stable_owner_not_credentials(accounts, clock):
    rid = reserve(accounts[0])
    saved = row(rid)
    owner = participants.identify(accounts[0])["id"]
    assert saved["participant_id"] == owner
    assert saved["task"] == "node" and saved["adapter"] == "fixture"
    assert saved["requested_model"] == "fixture model"
    assert json.loads(saved["policy_json"]) == {"policy": "fixture-a"}
    serialized = json.dumps(saved)
    assert accounts[0] not in serialized
    assert db._credential_digest(accounts[0]) not in serialized
    assert db.get_mutations(382) == []


def test_status_does_not_enroll_and_nested_accounting_is_refused(accounts, clock):
    assert spend.status(user_key=accounts[0])["participant_accounted_microusd"] == 0
    assert enrolled() == (0, 0)
    rid = reserve(accounts[0])
    before = row(rid)
    with db.transaction():
        with pytest.raises(spend.ModelSpendDenied, match="caller-owned transaction"):
            reserve(accounts[1])
        with pytest.raises(spend.ModelSpendDenied, match="caller-owned transaction"):
            settle(rid, 0)
        with pytest.raises(spend.ModelSpendDenied, match="caller-owned transaction"):
            spend.prune_expired()
    assert row(rid) == before and enrolled() == (1, 1)


def test_unknown_reservation_is_refused_without_accounting_changes(accounts, clock):
    with pytest.raises(spend.ModelSpendDenied, match="unavailable"):
        settle("not-an-existing-reservation", 0)
    assert rows() == [] and enrolled() == (0, 0)


def test_failed_settlement_does_not_refund_or_partly_update_the_reservation(accounts, clock):
    rid = reserve(accounts[0], 10)
    before = row(rid)
    with db.transaction() as conn:
        conn.execute("""CREATE TRIGGER fail_model_settlement BEFORE UPDATE ON model_spend_reservations
            BEGIN SELECT RAISE(ABORT, 'private injected database failure'); END""")
    with pytest.raises(spend.ModelSpendDenied, match="accounting is unavailable") as caught:
        settle(rid, 0, usage_json='{"input_tokens":0}')
    assert "private" not in str(caught.value)
    assert row(rid) == before
    assert spend.status()["global_accounted_microusd"] == 10


def test_failed_insert_rolls_back_first_use_enrollment(accounts, clock):
    with db.transaction() as conn:
        conn.execute("""CREATE TRIGGER fail_model_reserve BEFORE INSERT ON model_spend_reservations
            BEGIN SELECT RAISE(ABORT, 'private injected database failure'); END""")
    with pytest.raises(spend.ModelSpendDenied, match="accounting is unavailable"):
        reserve(accounts[0])
    assert rows() == [] and enrolled() == (0, 0)


def test_startup_scan_precedes_live_reserves_and_does_not_stop_normal_concurrency(accounts, clock):
    assert spend.check_unsettled_on_startup() is False
    first = reserve(accounts[0], 10)
    second = reserve(accounts[1], 10)
    current = spend.status()
    assert current["latched"] is False and current["unresolved_reservations"] == 2
    assert current["abandoned_reservations"] == 0
    settle(first, 4)
    settle(second, None)
    assert spend.status()["unresolved_reservations"] == 0
    assert spend.status()["latched"] is False


def test_failed_settlement_persists_stop_even_if_reservation_updates_fail(accounts, clock):
    rid = reserve(accounts[0], 10)
    with db.transaction() as conn:
        conn.execute("""CREATE TRIGGER reject_settlement BEFORE UPDATE ON model_spend_reservations
            BEGIN SELECT RAISE(ABORT, 'private injected storage detail'); END""")
    with pytest.raises(spend.ModelSpendDenied):
        settle(rid, 1)
    spend.mark_settlement_fault(rid)
    current = spend.status()
    assert current["latched"] is True and current["stop_reason"] == "accounting_fault"
    assert current["unresolved_reservations"] == 1 and current["abandoned_reservations"] == 0
    assert row(rid)["accounted_microusd"] == 10
    cold = cold_reserve(reservation_options(accounts[1], 0), clock)
    assert cold["denied"] == "SpendLatched"
    assert "private" not in json.dumps(cold)


def test_unavailable_fault_storage_leaves_pending_row_for_a_durable_startup_stop(accounts, clock, monkeypatch):
    rid = reserve(accounts[0], 10)

    @contextmanager
    def unavailable():
        raise sqlite3.OperationalError("private storage detail")
        yield  # pragma: no cover

    with monkeypatch.context() as patch:
        patch.setattr(db, "transaction", unavailable)
        with pytest.raises(spend.ModelSpendDenied):
            spend.mark_settlement_fault(rid)
    assert spend.status()["latched"] is False
    assert row(rid)["accounted_microusd"] == 10
    clock.now += timedelta(days=4)
    assert spend.prune_expired() == 0  # Expiry cannot erase the only crash evidence.
    assert row(rid)["status"] == "reserved"
    cold = cold_reserve(reservation_options(accounts[1], 0), clock, startup=True)
    assert cold["denied"] == "SpendLatched"
    assert cold["status"]["stop_reason"] == "unsettled_startup"
    assert rows() == []  # Expired records may go only after the independent stop commits.
    assert spend.status()["latched"] is True


def test_startup_marks_previous_pending_rows_without_refund_or_silent_resumption(accounts, clock):
    rid = reserve(accounts[0], 10)
    cold = cold_reserve(reservation_options(accounts[1], 0), clock, startup=True)
    assert cold["denied"] == "SpendLatched"
    assert cold["status"]["unresolved_reservations"] == 1
    assert cold["status"]["abandoned_reservations"] == 1
    saved = row(rid)
    assert saved["status"] == "reserved" and saved["accounted_microusd"] == 10
    assert saved["abandoned_at"] is not None
    with pytest.raises(spend.ModelSpendDenied, match="reconciliation"):
        settle(rid, 0)
    assert row(rid) == saved
    assert spend.check_unsettled_on_startup() is True


def test_canonical_policy_snapshots_are_deduplicated_and_not_repeated_in_reservations(accounts, clock):
    policy = {"policy": "海の灯り", "nested": {"b": 2, "a": 1}}
    first = reserve(accounts[0], 1, policy_snapshot=json.dumps(policy, ensure_ascii=True))
    second = reserve(accounts[1], 1, policy_snapshot=json.dumps(policy, ensure_ascii=False, sort_keys=True, indent=2))
    canonical = json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert row(first)["policy_digest"] == row(second)["policy_digest"] == digest
    with db._connection() as conn:
        assert conn.execute("SELECT digest,policy_json FROM model_spend_policies").fetchall() == [(digest, canonical)]
        assert "policy_json" not in {column[1] for column in conn.execute("PRAGMA table_info(model_spend_reservations)")}
    with pytest.raises(spend.GlobalLimitExceeded):
        reserve(accounts[0], 1, policy_snapshot='{"policy":"refused"}', global_limit_microusd=0)
    with db._connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM model_spend_policies").fetchone()[0] == 1


def test_shared_policy_survives_until_its_last_reservation_expires(accounts, clock):
    short = reserve(accounts[0], 1, retention_days=2)
    long = reserve(accounts[1], 1, retention_days=10)
    settle(short, 1)
    settle(long, 1)
    clock.now += timedelta(days=3)
    assert spend.prune_expired() == 1
    assert [item["id"] for item in rows()] == [long]
    with db._connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM model_spend_policies").fetchone()[0] == 1
    clock.now += timedelta(days=8)
    assert spend.prune_expired() == 1 and rows() == []
    with db._connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM model_spend_policies").fetchone()[0] == 0


def test_idle_prune_does_not_wait_for_the_writer_when_nothing_can_expire(accounts, clock):
    reserve(accounts[0], 1)
    writer = db._connect()
    writer.execute("BEGIN IMMEDIATE")
    outcome = {}

    def prune():
        try:
            outcome["removed"] = spend.prune_expired()
        except BaseException as exc:
            outcome["error"] = exc

    worker = threading.Thread(target=prune)
    worker.start()
    try:
        worker.join(1)
        assert not worker.is_alive(), "An idle prune waited on the single writer."
        assert outcome == {"removed": 0}
    finally:
        writer.rollback()
        writer.close()
        worker.join(5)


def test_idle_prune_removes_orphan_policy_rows_without_any_reservation(accounts, clock):
    rid = reserve(accounts[0], 1)
    settle(rid, 1)
    with db.transaction() as conn:
        conn.execute("DELETE FROM model_spend_reservations WHERE id=?", (rid,))
    assert spend.prune_expired() == 0
    with db._connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM model_spend_policies").fetchone()[0] == 0


def test_status_of_absent_database_is_read_only_and_not_a_storage_outage(clock):
    path = db._DB_PATH
    assert not path.exists()
    current = spend.status()
    assert current["ledger_state"] == "absent" and current["storage_error"] is False
    assert current["global_accounted_microusd"] is None and current["latched"] is None
    assert not path.exists()


def test_status_does_not_migrate_a_readable_older_database(clock):
    with sqlite3.connect(db._DB_PATH) as conn:
        conn.executescript("""CREATE TABLE schema_version(version INTEGER PRIMARY KEY);
            INSERT INTO schema_version VALUES (31);
            CREATE TABLE retained(value TEXT);
            INSERT INTO retained VALUES ('leave this unchanged');""")
    before = db._DB_PATH.read_bytes()
    current = spend.status()
    assert current["ledger_state"] == "uninitialized" and current["storage_error"] is False
    assert current["global_accounted_microusd"] is None
    assert db._DB_PATH.read_bytes() == before
    with sqlite3.connect(db._DB_PATH) as conn:
        assert conn.execute("SELECT version FROM schema_version").fetchall() == [(31,)]
        assert conn.execute("SELECT name FROM sqlite_master WHERE name LIKE 'model_spend%'").fetchall() == []


def test_status_reports_corrupt_or_partial_accounting_without_private_error_text(clock):
    db._DB_PATH.write_bytes(b"private corrupt database contents")
    current = spend.status()
    assert current["ledger_state"] == "unavailable" and current["storage_error"] is True
    assert current["latched"] is None and "private" not in json.dumps(current)
    db._DB_PATH.unlink()
    with sqlite3.connect(db._DB_PATH) as conn:
        conn.executescript("CREATE TABLE model_spend_latch(singleton INTEGER PRIMARY KEY, reason TEXT);")
    current = spend.status()
    assert current["ledger_state"] == "unavailable" and current["storage_error"] is True


def test_status_reports_missing_tables_in_schema_32_as_storage_failure(clock):
    with sqlite3.connect(db._DB_PATH) as conn:
        conn.executescript("CREATE TABLE schema_version(version INTEGER); INSERT INTO schema_version VALUES(32);")
    current = spend.status()
    assert current["ledger_state"] == "unavailable" and current["storage_error"] is True
