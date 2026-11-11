"""Durable model USD reservations; no prompts, replies or credentials belong here.

Callers supply a validated policy snapshot and a verified worst-case cost before
dispatch. A non-None actual amount means the caller has complete, priced usage;
otherwise the original reservation stays fully accounted. Failed or abandoned
requests never acquire a refund by restarting the process.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import wraps
import json
import secrets
import sqlite3
from urllib.parse import urlsplit

import persistence as db
from persistence import participants


SQLITE_MAX = (1 << 63) - 1
_USAGE_FIELDS = frozenset({"input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"})


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
        if not isinstance(value, str) or len(value) > 65536:
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
    return conn.execute("""DELETE FROM model_spend_reservations
        WHERE day < ? AND retain_until < ?""",
        (now.date().isoformat(), _stamp(now))).rowcount


@_database_errors
def prune_expired() -> int:
    """Housekeeping needs no dispatch or live key; each row owns its deadline."""
    _outside_transaction()
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
                conn.execute("""INSERT INTO model_spend_reservations
                    (id,day,participant_id,task,adapter,endpoint,requested_model,policy_json,
                     reserved_microusd,accounted_microusd,status,created_at,retention_days,retain_until)
                    VALUES (?,?,?,?,?,?,?,?,?,?,'reserved',?,?,?)""",
                    (reservation_id, day, participant_id, task, adapter, endpoint, model,
                     policy, amount, amount, timestamp, retention, retain_until))
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
        row = conn.execute("""SELECT reserved_microusd,status
            FROM model_spend_reservations WHERE id=?""", (reservation_id,)).fetchone()
        if row is None:
            raise ModelSpendDenied("The model reservation is unavailable.")
        reserved, current_status = row
        if current_status != "reserved":
            return
        timestamp = _stamp(_now())
        anomalous = anomaly or (actual_microusd is not None and actual_microusd > reserved)
        if anomalous:
            accounted, status = max(reserved, actual_microusd or 0), "anomaly"
            conn.execute("""INSERT INTO model_spend_latch(singleton,latched_at,reason)
                VALUES (1,?,'billing_anomaly') ON CONFLICT(singleton) DO NOTHING""", (timestamp,))
        elif actual_microusd is None:
            accounted, status = reserved, "uncertain"
        else:
            accounted, status = actual_microusd, "settled"
        conn.execute("""UPDATE model_spend_reservations SET accounted_microusd=?,
            status=?,usage_json=?,resolved_model=?,settled_at=? WHERE id=?""",
            (accounted, status, usage, resolved, timestamp, reservation_id))


@_database_errors
def status(*, user_key: str | None = None) -> dict:
    """Read totals without enrollment, reservations, settlement or expiry cleanup."""
    db.init_db()
    day = _now().date().isoformat()
    with db._connection() as conn:
        participant_id = None
        if user_key is not None:
            digest = _live_digest(conn, user_key)
            row = conn.execute("""SELECT participant_id FROM participant_credentials
                WHERE credential_digest=?""", (digest,)).fetchone()
            participant_id = row[0] if row else None
        global_spent, participant_spent = _totals(conn, day, participant_id)
        latched = conn.execute("SELECT 1 FROM model_spend_latch WHERE singleton=1").fetchone() is not None
    return {"day": day, "global_accounted_microusd": global_spent,
            "participant_accounted_microusd": participant_spent if user_key is not None else None,
            "latched": latched}
