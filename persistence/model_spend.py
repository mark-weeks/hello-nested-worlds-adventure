"""Durable model USD reservations; no prompts, replies or credentials belong here.

Callers supply a validated policy snapshot and a verified worst-case cost before
dispatch. A non-None actual amount means the caller has complete, priced usage;
otherwise the original reservation stays fully accounted. Failed or abandoned
requests never acquire a refund by restarting the process.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
from urllib.parse import urlsplit

import persistence as db
from persistence import participants


SQLITE_MAX = (1 << 63) - 1
MAX_POLICY_JSON_CHARS = 65536
_USAGE_FIELDS = frozenset({"input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"})
_STOP_REASONS = frozenset({"billing_anomaly", "accounting_fault", "unsettled_startup"})
_TABLES = frozenset({"model_spend_reservations", "model_spend_policies", "model_spend_latch"})
_EXPIRED = """day < ? AND retain_until < ? AND
    (status <> 'reserved' OR (abandoned_at IS NOT NULL AND
        EXISTS (SELECT 1 FROM model_spend_latch WHERE singleton=1)))"""


class ModelSpendDenied(ValueError):
    """No dispatch is authorized by a refused or invalid reservation."""


BudgetDenied = ModelSpendDenied


class GlobalLimitExceeded(ModelSpendDenied):
    pass


class ParticipantLimitExceeded(ModelSpendDenied):
    pass


class SpendLatched(ModelSpendDenied):
    pass


def _database_errors(operation):
    @wraps(operation)
    def checked(*args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except sqlite3.Error:
            raise ModelSpendDenied("Model accounting is unavailable.") from None
    return checked


def utc_now() -> datetime:
    """The UTC clock seam; read only after the reservation acquires its lock."""
    return datetime.now(timezone.utc)


def _now() -> datetime:
    value = utc_now()
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ModelSpendDenied("A timezone-aware model accounting clock is required.")
    return value.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _integer(value, *, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value <= SQLITE_MAX:
        raise ModelSpendDenied("Model accounting requires bounded nonnegative integers.")
    return value


def _metadata(value, *, maximum: int = 2048) -> str:
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ModelSpendDenied("Model accounting metadata is invalid.")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ModelSpendDenied("Model accounting metadata is invalid.") from None
    return value


def _object_json(value, *, usage: bool = False) -> str:
    try:
        if not isinstance(value, str) or len(value) > MAX_POLICY_JSON_CHARS:
            raise ValueError
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError
        if usage:
            if set(parsed) - _USAGE_FIELDS:
                raise ValueError
            for count in parsed.values():
                if count is not None:
                    _integer(count)
        result = json.dumps(parsed, sort_keys=True, ensure_ascii=False,
                            separators=(",", ":"), allow_nan=False)
        result.encode("utf-8")
        return result
    except (TypeError, ValueError, UnicodeError):
        raise ModelSpendDenied("Model accounting JSON is invalid.") from None


def _outside_transaction() -> None:
    if db.in_transaction():
        raise ModelSpendDenied("Model accounting cannot join a caller-owned transaction.")


def _live_digest(conn, key: str) -> str:
    try:
        return participants.require_live_credential(conn, key)[0]
    except participants.Unauthorized:
        raise ModelSpendDenied("A current personal invite is required.") from None


def _totals(conn, day: str, participant_id: str | None) -> tuple[int, int]:
    # An anomalous settlement can raise the combined total above SQLite's
    # signed integer range. Python sums remain exact; SQLite SUM can overflow.
    rows = conn.execute("""SELECT participant_id,accounted_microusd
        FROM model_spend_reservations WHERE day=?""", (day,)).fetchall()
    return (sum(row[1] for row in rows),
            sum(row[1] for row in rows if row[0] == participant_id))


def _prune(conn, now: datetime) -> int:
    removed = conn.execute("DELETE FROM model_spend_reservations WHERE " + _EXPIRED,
                           (now.date().isoformat(), _stamp(now))).rowcount
    conn.execute("""DELETE FROM model_spend_policies WHERE NOT EXISTS
        (SELECT 1 FROM model_spend_reservations WHERE policy_digest=model_spend_policies.digest)""")
    return removed


@contextmanager
def _readonly():
    path = Path(db._DB_PATH)
    if not path.is_file():
        raise sqlite3.OperationalError("Accounting database is unavailable.")
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("BEGIN")
        yield conn
    finally:
        conn.close()


def _latch(conn, timestamp: str, reason: str) -> None:
    conn.execute("""INSERT INTO model_spend_latch(singleton,latched_at,reason)
        VALUES (1,?,?) ON CONFLICT(singleton) DO NOTHING""", (timestamp, reason))


@_database_errors
def check_unsettled_on_startup() -> bool:
    """Run once before this controlled process reserves anything.

    One controlled process per SQLite DB is supported. Pending rows from an
    earlier process (or a second process sharing this DB) require operator
    reconciliation; they are not mistaken for this process's concurrent calls.
    """
    _outside_transaction()
    with db.transaction() as conn:
        if conn.execute("SELECT 1 FROM model_spend_reservations WHERE status='reserved' LIMIT 1").fetchone():
            timestamp = _stamp(_now())
            _latch(conn, timestamp, "unsettled_startup")
            conn.execute("""UPDATE model_spend_reservations SET abandoned_at=COALESCE(abandoned_at,?)
                WHERE status='reserved'""", (timestamp,))
        return conn.execute("SELECT 1 FROM model_spend_latch WHERE singleton=1").fetchone() is not None


@_database_errors
def mark_settlement_fault(reservation_id: str) -> None:
    """Persist a stop after settlement fails; retain the original full charge.

    If storage itself is unavailable this can fail too. The reservation stays
    protected from pruning and the next process's startup scan refuses dispatch.
    """
    _outside_transaction()
    _metadata(reservation_id, maximum=128)
    with db.transaction() as conn:
        timestamp = _stamp(_now())
        _latch(conn, timestamp, "accounting_fault")
        # A table-specific write fault must not roll back the independent stop.
        # An unmarked row remains protected until startup can reconcile it.
        conn.execute("SAVEPOINT model_spend_abandon")
        try:
            conn.execute("""UPDATE model_spend_reservations SET abandoned_at=COALESCE(abandoned_at,?)
                WHERE id=? AND status='reserved'""", (timestamp, reservation_id))
        except sqlite3.Error:
            conn.execute("ROLLBACK TO model_spend_abandon")
        conn.execute("RELEASE model_spend_abandon")


@_database_errors
def prune_expired() -> int:
    """Housekeeping needs no dispatch or live key; each row owns its deadline."""
    _outside_transaction()
    if not Path(db._DB_PATH).is_file():
        return 0
    # Do not acquire the single writer every minute when there is no work.
    now = _now()
    with _readonly() as conn:
        expired = conn.execute("SELECT 1 FROM model_spend_reservations WHERE " + _EXPIRED + " LIMIT 1",
                               (now.date().isoformat(), _stamp(now))).fetchone()
        orphan = conn.execute("""SELECT 1 FROM model_spend_policies WHERE NOT EXISTS
            (SELECT 1 FROM model_spend_reservations WHERE policy_digest=model_spend_policies.digest) LIMIT 1""").fetchone()
    if not expired and not orphan:
        return 0
    with db.transaction() as conn:
        return _prune(conn, _now())


@_database_errors
def reserve(*, user_key: str, reserved_microusd: int,
            global_limit_microusd: int, participant_limit_microusd: int,
            policy_snapshot: str, task: str, adapter: str, endpoint: str,
            model: str, retention_days: int) -> str:
    """Reserve atomically across every policy/route for this UTC day and person.

    Expiry cleanup is committed on a denied live reservation attempt too. A
    savepoint rolls back first-use enrollment and the reservation itself when
    a limit refuses it; it never rolls back the persistent anomaly latch.
    """
    _outside_transaction()
    amount = _integer(reserved_microusd)
    global_limit = _integer(global_limit_microusd)
    participant_limit = _integer(participant_limit_microusd)
    retention = _integer(retention_days, minimum=2)
    policy = _object_json(policy_snapshot)
    policy_digest = hashlib.sha256(policy.encode("utf-8")).hexdigest()
    task = _metadata(task)
    adapter = _metadata(adapter)
    endpoint = _metadata(endpoint)
    model = _metadata(model)
    try:
        url = urlsplit(endpoint)
        if (url.scheme not in {"http", "https"} or not url.hostname
                or url.username is not None or url.password is not None
                or url.query or url.fragment):
            raise ValueError
        url.port
    except ValueError:
        raise ModelSpendDenied("Model accounting endpoint metadata is invalid.") from None
    refusal = None
    reservation_id = secrets.token_hex(16)
    with db.transaction() as conn:
        digest = _live_digest(conn, user_key)
        now = _now()
        day, timestamp = now.date().isoformat(), _stamp(now)
        try:
            retain_until = _stamp(now + timedelta(days=retention))
        except (OverflowError, ValueError):
            raise ModelSpendDenied("Model accounting retention is outside the supported date range.") from None
        _prune(conn, now)
        if conn.execute("SELECT 1 FROM model_spend_latch WHERE singleton=1").fetchone():
            refusal = SpendLatched("Model dispatch is closed after a billing anomaly.")
        else:
            conn.execute("SAVEPOINT model_spend_enrollment")
            participant_id = participants._ensure(conn, digest)
            global_spent, participant_spent = _totals(conn, day, participant_id)
            if global_spent + amount > global_limit:
                refusal = GlobalLimitExceeded("The global model allowance is exhausted.")
            elif participant_spent + amount > participant_limit:
                refusal = ParticipantLimitExceeded("The participant model allowance is exhausted.")
            if refusal:
                conn.execute("ROLLBACK TO model_spend_enrollment")
            else:
                conn.execute("""INSERT INTO model_spend_policies(digest,policy_json,created_at)
                    VALUES (?,?,?) ON CONFLICT(digest) DO NOTHING""", (policy_digest, policy, timestamp))
                stored = conn.execute("SELECT policy_json FROM model_spend_policies WHERE digest=?",
                                      (policy_digest,)).fetchone()[0]
                if stored != policy:
                    raise ModelSpendDenied("The model policy accounting record is inconsistent.")
                conn.execute("""INSERT INTO model_spend_reservations
                    (id,day,participant_id,task,adapter,endpoint,requested_model,policy_digest,
                     reserved_microusd,accounted_microusd,status,created_at,retention_days,retain_until)
                    VALUES (?,?,?,?,?,?,?,?,?,?,'reserved',?,?,?)""",
                    (reservation_id, day, participant_id, task, adapter, endpoint, model,
                     policy_digest, amount, amount, timestamp, retention, retain_until))
            conn.execute("RELEASE model_spend_enrollment")
    if refusal:
        raise refusal
    return reservation_id


@_database_errors
def settle(reservation_id: str, *, actual_microusd: int | None,
           usage_json: str | None, resolved_model: str | None,
           anomaly: bool = False) -> None:
    """Settle once on the original day; uncertainty never releases money."""
    _outside_transaction()
    _metadata(reservation_id, maximum=128)
    if actual_microusd is not None:
        _integer(actual_microusd)
    if type(anomaly) is not bool:
        raise ModelSpendDenied("The model accounting anomaly flag must be boolean.")
    usage = _object_json(usage_json, usage=True) if usage_json is not None else None
    resolved = _metadata(resolved_model) if resolved_model is not None else None
    with db.transaction() as conn:
        row = conn.execute("""SELECT reserved_microusd,status,abandoned_at
            FROM model_spend_reservations WHERE id=?""", (reservation_id,)).fetchone()
        if row is None:
            raise ModelSpendDenied("The model reservation is unavailable.")
        reserved, current_status, abandoned_at = row
        if current_status != "reserved":
            return
        if abandoned_at is not None:
            raise ModelSpendDenied("The model reservation requires accounting reconciliation.")
        timestamp = _stamp(_now())
        anomalous = anomaly or (actual_microusd is not None and actual_microusd > reserved)
        if anomalous:
            accounted, status = max(reserved, actual_microusd or 0), "anomaly"
            _latch(conn, timestamp, "billing_anomaly")
        elif actual_microusd is None:
            accounted, status = reserved, "uncertain"
        else:
            accounted, status = actual_microusd, "settled"
        conn.execute("""UPDATE model_spend_reservations SET accounted_microusd=?,
            status=?,usage_json=?,resolved_model=?,settled_at=? WHERE id=?""",
            (accounted, status, usage, resolved, timestamp, reservation_id))


def status(*, user_key: str | None = None) -> dict:
    """Inspect committed accounting without creating, migrating or changing it."""
    day = _now().date().isoformat()
    result = {"day": day, "global_accounted_microusd": None,
              "participant_accounted_microusd": None, "latched": None,
              "stop_reason": None, "unresolved_reservations": None,
              "abandoned_reservations": None, "storage_error": False, "ledger_state": "absent"}
    try:
        if not Path(db._DB_PATH).exists():
            return result
        with _readonly() as conn:
            present = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not _TABLES <= present:
                version = (conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
                           if "schema_version" in present else None)
                if not _TABLES & present and (version is None or version < 32):
                    return {**result, "ledger_state": "uninitialized"}
                raise sqlite3.OperationalError("Accounting schema is unavailable.")
            participant_id = None
            if user_key is not None:
                digest = _live_digest(conn, user_key)
                row = conn.execute("""SELECT participant_id FROM participant_credentials
                    WHERE credential_digest=?""", (digest,)).fetchone()
                participant_id = row[0] if row else None
            global_spent, participant_spent = _totals(conn, day, participant_id)
            latch = conn.execute("SELECT reason FROM model_spend_latch WHERE singleton=1").fetchone()
            unresolved, abandoned = conn.execute("""SELECT COUNT(*),COUNT(abandoned_at)
                FROM model_spend_reservations WHERE status='reserved'""").fetchone()
            return {**result, "global_accounted_microusd": global_spent,
                    "participant_accounted_microusd": participant_spent if user_key is not None else None,
                    "latched": latch is not None,
                    "stop_reason": (latch[0] if latch[0] in _STOP_REASONS else "accounting_fault") if latch else None,
                    "unresolved_reservations": unresolved, "abandoned_reservations": abandoned,
                    "ledger_state": "ready"}
    except (OSError, sqlite3.Error):
        return {**result, "ledger_state": "unavailable", "storage_error": True}
