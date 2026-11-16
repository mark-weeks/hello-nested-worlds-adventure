"""Private chat and operator reports; never part of world history.

Collection callers supply an approved immutable policy and explicit retention.
Chat returns only after commit. Its declared policy may retain it until deletion;
open or acknowledged complaints hold their cited evidence until case closure.
Report retry receipts last only as long as the report itself is retained.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import json
from pathlib import Path
import re
import secrets
import sqlite3
import uuid

import persistence as db
from persistence import blocks, participants

MAX_POLICY_JSON_CHARS = 65536
_REASONS = frozenset(("harassment", "harmful_content", "spam", "other"))
_STATES = frozenset(("open", "acknowledged", "closed"))
_HEX32 = re.compile(r"[0-9a-f]{32}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_TABLES = frozenset(("community_policies", "private_chat_messages", "private_reports", "report_actions",
                     "private_chat_deletions"))
_SUMMARY = ("id", "reporter_participant_id", "world_seed", "target_id", "reason", "status",
            "created_at", "expires_at")
_OPEN_REPORT_HOLD = ("EXISTS (SELECT 1 FROM private_reports r WHERE "
                     "r.evidence_ref=private_chat_messages.evidence_ref "
                     "AND r.status IN ('open','acknowledged'))")
CHAT_RETAINED = f"(expires_at IS NULL OR expires_at>? OR {_OPEN_REPORT_HOLD})"
_REPORT_RETAINED = "(expires_at>? OR status IN ('open','acknowledged'))"


class CommunityError(ValueError):
    pass


class UnknownTester(CommunityError):
    def __init__(self):
        super().__init__("That tester is not registered.")


class AmbiguousTester(CommunityError):
    def __init__(self):
        super().__init__("That tester name is ambiguous; no messages were deleted.")


class EvidenceUnavailable(CommunityError):
    def __init__(self):
        super().__init__("That chat evidence is unavailable. Choose a current traveler or another message.")


class ReportConflict(CommunityError):
    def __init__(self):
        super().__init__("That report request already has different content.")


class CommunityUnavailable(RuntimeError):
    def __init__(self):
        super().__init__("Private community storage is unavailable.")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> datetime:
    value = utc_now()
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise CommunityUnavailable()
    return value.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _database_errors(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (sqlite3.Error, OSError):
            raise CommunityUnavailable() from None
    return wrapped


def _outside_transaction() -> None:
    if db.in_transaction():
        raise CommunityUnavailable()


def _text(value: object, *, maximum: int, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        raise CommunityError("Private community input is invalid.")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise CommunityError("Private community input is invalid.") from None
    if "\x00" in value:
        raise CommunityError("Private community input is invalid.")
    return value


def normalize_uuid(value: object) -> str:
    """Accept lowercase 32-hex or canonical dashed UUIDs; return 32-hex.

    Shared wire/storage validation only: this opens no database and does not
    change the caller's frozen report payload or fingerprint.
    """
    if not isinstance(value, str) or len(value) not in (32, 36):
        raise CommunityError("A server-issued or random request identifier is required.")
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        raise CommunityError("A server-issued or random request identifier is required.") from None
    if value not in (parsed.hex, str(parsed)):
        raise CommunityError("A server-issued or random request identifier is required.")
    return parsed.hex


def _seed(value: object) -> int:
    if type(value) is not int or not -(2**63) <= value < 2**63:
        raise CommunityError("A valid world is required.")
    return value


def _id(value: object) -> str:
    if not isinstance(value, str) or not _HEX32.fullmatch(value):
        raise CommunityError("That private record is unavailable.")
    return value


def _fingerprint(value: object) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise CommunityError("A frozen report fingerprint is required.")
    return value


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CommunityError("An immutable community policy is required.")
        result[key] = value
    return result


def _policy(snapshot: object, days: object, now: datetime, *, until_deleted: bool = False) -> tuple[str, str, str | None]:
    if not (until_deleted and days is None) and (type(days) is not int or not 1 <= days <= 36500):
        raise CommunityError("Explicit community retention days are required.")
    if not isinstance(snapshot, str) or len(snapshot) > MAX_POLICY_JSON_CHARS:
        raise CommunityError("An immutable community policy is required.")
    try:
        parsed = json.loads(snapshot, object_pairs_hook=_unique,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(parsed, dict):
            raise ValueError()
        if until_deleted and parsed.get("chat") != {"enabled": True, "retention_mode": "until_deleted"}:
            raise ValueError()
        canonical = json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(canonical) > MAX_POLICY_JSON_CHARS:
            raise ValueError()
        encoded = canonical.encode("utf-8")
        if len(encoded) > MAX_POLICY_JSON_CHARS:
            raise ValueError()
        expires = None if until_deleted else _stamp(now + timedelta(days=days))
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise CommunityError("An immutable community policy and valid retention are required.") from None
    return hashlib.sha256(encoded).hexdigest(), canonical, expires


def _save_policy(conn, digest: str, snapshot: str, at: str) -> None:
    conn.execute("INSERT INTO community_policies(digest,snapshot_json,created_at) VALUES (?,?,?) "
                 "ON CONFLICT(digest) DO NOTHING", (digest, snapshot, at))


@contextmanager
def _readonly():
    path = Path(db._DB_PATH)
    if not path.is_file():
        raise sqlite3.OperationalError("Community storage is unavailable.")
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("BEGIN")
        yield conn
    finally:
        conn.close()


def _ready(conn) -> bool:
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return _TABLES <= tables


@_database_errors
def append_chat(*, user_key: str | None, session_id: str, world_seed: int, node_name: str,
                text: str, display_name: str, retention_days: int | None, policy_snapshot: str,
                retention_mode: str = "until_deleted") -> dict:
    """Atomically authenticate and commit an operational line before publication."""
    _outside_transaction()
    session = normalize_uuid(session_id)
    seed = _seed(world_seed)
    node = _text(node_name, maximum=1000)
    content = _text(text, maximum=256)
    name = _text(display_name, maximum=1000)
    if retention_mode != "until_deleted" or retention_days is not None:
        raise CommunityError("An explicit chat retention mode is required.")
    reference = secrets.token_hex(16)
    with db.transaction() as conn:
        now = _now()
        at = _stamp(now)
        digest, snapshot, expires = _policy(policy_snapshot, retention_days, now,
                                           until_deleted=True)
        if user_key is not None:
            credential, name = participants.require_live_credential(conn, user_key)
            name = _text(name, maximum=1000)
            participant = participants._ensure(conn, credential)
        else:
            # Registration or invite issuance closes local anonymous collection,
            # including after all keys are revoked. Check inside this write fence.
            gated = conn.execute("SELECT EXISTS(SELECT 1 FROM invite_keys) "
                                 "OR EXISTS(SELECT 1 FROM registration_tokens)").fetchone()[0]
            if gated:
                raise participants.Unauthorized("A current personal invite is required.")
            participant = None
        _save_policy(conn, digest, snapshot, at)
        conn.execute("""INSERT INTO private_chat_messages
            (evidence_ref,world_seed,node_name,participant_id,session_id,name,text,
             created_at,expires_at,retention_days,policy_digest) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (reference, seed, node, participant, session, name, content, at, expires, retention_days, digest))
    return {"evidence_ref": reference, "participant_id": participant, "name": name,
            "at": at, "expires_at": expires}


def _evidence(conn, reference: object, seed: int, at: str):
    if not isinstance(reference, str) or not _HEX32.fullmatch(reference):
        raise EvidenceUnavailable()
    cursor = conn.execute("""SELECT evidence_ref,world_seed,node_name,participant_id,session_id,name,
        text,created_at,expires_at FROM private_chat_messages
        WHERE evidence_ref=? AND world_seed=? AND """ + CHAT_RETAINED, (reference, seed, at))
    row = cursor.fetchone()
    if row is None:
        raise EvidenceUnavailable()
    return dict(zip((column[0] for column in cursor.description), row))


@_database_errors
def evidence_author(*, evidence_ref: str, world_seed: int) -> dict:
    """Trusted server metadata for a retained line, including disconnected authors."""
    seed = _seed(world_seed)
    with _readonly() as conn:
        item = _evidence(conn, evidence_ref, seed, _stamp(_now()))
    return {key: item[key] for key in ("participant_id", "session_id", "name", "expires_at")}


def _retry(conn, reporter: str | None, request: str, fingerprint: str, at: str) -> dict | None:
    if reporter is None:
        return None
    row = conn.execute("""SELECT id,fingerprint FROM private_reports
        WHERE reporter_participant_id=? AND request_id=? AND """ + _REPORT_RETAINED,
        (reporter, request, at)).fetchone()
    if row is None:
        return None
    if row[1] != fingerprint:
        raise ReportConflict()
    return {"report_id": row[0], "received": True}


@_database_errors
def lookup_report_retry(user_key: str, request_id: str, fingerprint: str) -> dict | None:
    """Authenticate and recover a retained receipt before transient target lookup."""
    request, frozen = normalize_uuid(request_id), _fingerprint(fingerprint)
    with _readonly() as conn:
        credential, _ = participants.require_live_credential(conn, user_key)
        row = conn.execute("SELECT participant_id FROM participant_credentials WHERE credential_digest=?",
                           (credential,)).fetchone()
        return _retry(conn, row[0] if row else None, request, frozen, _stamp(_now()))


def _target(conn, target: object) -> str:
    if blocks._target_agent(target):
        return target
    target = _id(target)
    if not conn.execute("SELECT 1 FROM participants WHERE id=?", (target,)).fetchone():
        raise CommunityError("Choose a current traveler or retained chat evidence.")
    return target


@_database_errors
def submit_report(*, user_key: str, request_id: str, fingerprint: str, world_seed: int,
                  target_id: str | None, evidence_ref: str | None, reason: str, detail: str,
                  retention_days: int, policy_snapshot: str) -> dict:
    """Submit with trusted resolved target; a retained retry precedes evidence checks."""
    _outside_transaction()
    request, frozen = normalize_uuid(request_id), _fingerprint(fingerprint)
    seed = _seed(world_seed)
    with db.transaction() as conn:
        now = _now()
        at = _stamp(now)
        credential, _ = participants.require_live_credential(conn, user_key)
        reporter = participants._ensure(conn, credential)
        previous = _retry(conn, reporter, request, frozen, at)
        if previous:
            return previous
        # Idempotency is retention-bounded. Remove an expired conflicting receipt
        # together with its actions before accepting this request as a new case.
        expired = conn.execute("SELECT id FROM private_reports WHERE reporter_participant_id=? "
                               "AND request_id=?", (reporter, request)).fetchone()
        if expired:
            conn.execute("DELETE FROM report_actions WHERE report_id=?", expired)
            conn.execute("DELETE FROM private_reports WHERE id=?", expired)
        if not isinstance(reason, str) or reason not in _REASONS:
            raise CommunityError("Choose an available report reason.")
        explanation = _text(detail, maximum=2000, empty=True)
        digest, snapshot, expires = _policy(policy_snapshot, retention_days, now)
        target = _target(conn, target_id) if target_id is not None else None
        evidence = _evidence(conn, evidence_ref, seed, at) if evidence_ref is not None else None
        if evidence:
            if target is not None and target != evidence["participant_id"]:
                raise EvidenceUnavailable()
            target = evidence["participant_id"]
        if target == reporter:
            raise CommunityError("Choose another traveler to report.")
        if target is None and evidence is None:
            raise CommunityError("Choose a current traveler or retained chat evidence.")
        _save_policy(conn, digest, snapshot, at)
        report_id = secrets.token_hex(16)
        conn.execute("""INSERT INTO private_reports
            (id,reporter_participant_id,request_id,fingerprint,world_seed,target_id,target_session_id,
             reason,detail,evidence_ref,evidence_expires_at,status,created_at,expires_at,retention_days,policy_digest)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,'open',?,?,?,?)""",
            (report_id, reporter, request, frozen, seed, target, evidence["session_id"] if evidence else None,
             reason, explanation, evidence_ref, evidence["expires_at"] if evidence else None,
             at, expires, retention_days, digest))
    return {"report_id": report_id, "received": True}


@_database_errors
def list_reports(*, state: str | None = None, limit: int = 50) -> list[dict]:
    if state is not None and (not isinstance(state, str) or state not in _STATES):
        raise CommunityError("Choose an available report state.")
    if type(limit) is not int or not 1 <= limit <= 200:
        raise CommunityError("Choose a report limit between 1 and 200.")
    with _readonly() as conn:
        query = "SELECT " + ",".join(_SUMMARY) + " FROM private_reports WHERE " + _REPORT_RETAINED
        values = [_stamp(_now())]
        if state is not None:
            query += " AND status=?"
            values.append(state)
        rows = conn.execute(query + " ORDER BY created_at,id LIMIT ?", (*values, limit)).fetchall()
    return [dict(zip(_SUMMARY, row)) for row in rows]


@_database_errors
def show_report(report_id: str) -> dict | None:
    case = _id(report_id)
    at = _stamp(_now())
    with _readonly() as conn:
        cursor = conn.execute("SELECT * FROM private_reports WHERE id=? AND " + _REPORT_RETAINED, (case, at))
        row = cursor.fetchone()
        if row is None:
            return None
        result = dict(zip((column[0] for column in cursor.description), row))
        actions = conn.execute("""SELECT id,action,operator,note,created_at,expires_at FROM report_actions
            WHERE report_id=? AND (expires_at>? OR ? IN ('open','acknowledged'))
            ORDER BY created_at,rowid""", (case, at, result["status"])).fetchall()
        result["actions"] = [dict(zip(("id", "action", "operator", "note", "created_at", "expires_at"), row))
                             for row in actions]
        result["evidence"] = {"status": "none"}
        if result["evidence_ref"] is not None:
            try:
                evidence = _evidence(conn, result["evidence_ref"], result["world_seed"], at)
            except EvidenceUnavailable:
                result["evidence"] = {"status": "unavailable"}
            else:
                result["evidence"] = {"status": "retained", **evidence}
    return result


def _action(report_id: str, *, operator: str, note: str, action: str, state: str) -> dict:
    _outside_transaction()
    case = _id(report_id)
    label = _text(operator, maximum=80)
    annotation = _text(note, maximum=2000, empty=True)
    with db.transaction() as conn:
        at = _stamp(_now())
        row = conn.execute("SELECT status,expires_at FROM private_reports WHERE id=? AND " + _REPORT_RETAINED,
                           (case, at)).fetchone()
        if row is None:
            raise CommunityError("That private report is unavailable.")
        if row[0] == "closed" and state != "closed":
            raise CommunityError("That private report is already closed.")
        action_id = secrets.token_hex(16)
        conn.execute("""INSERT INTO report_actions
            (id,report_id,action,operator,note,created_at,expires_at) VALUES (?,?,?,?,?,?,?)""",
            (action_id, case, action, label, annotation, at, row[1]))
        conn.execute("UPDATE private_reports SET status=? WHERE id=?", (state, case))
    return {"report_id": case, "status": state, "action_id": action_id}


@_database_errors
def acknowledge_report(report_id: str, *, operator: str, note: str = "") -> dict:
    return _action(report_id, operator=operator, note=note, action="acknowledge", state="acknowledged")


@_database_errors
def close_report(report_id: str, *, operator: str, note: str = "") -> dict:
    return _action(report_id, operator=operator, note=note, action="close", state="closed")


def _delete_chat(conn, predicate: str, values: tuple) -> dict:
    selected = conn.execute("SELECT COUNT(*) FROM private_chat_messages WHERE " + predicate,
                            values).fetchone()[0]
    held = conn.execute("SELECT COUNT(*) FROM private_chat_messages WHERE " + predicate
                        + " AND " + _OPEN_REPORT_HOLD, values).fetchone()[0]
    conn.execute("INSERT INTO private_chat_deletions(evidence_ref,deleted_at) "
                 "SELECT evidence_ref,? FROM private_chat_messages WHERE " + predicate
                 + " AND NOT " + _OPEN_REPORT_HOLD
                 + " ON CONFLICT(evidence_ref) DO NOTHING", (_stamp(_now()), *values))
    deleted = conn.execute("DELETE FROM private_chat_messages WHERE " + predicate
                           + " AND NOT " + _OPEN_REPORT_HOLD, values).rowcount
    return {"matched": selected, "deleted": deleted, "held": held,
            "hold_reason": "Cited by an open or acknowledged report; close the report before deletion." if held else None,
            "backup_copies": "Removed when those backups are deleted."}


def _require_deletion_store() -> None:
    # Unlike db.transaction(), this preflight neither creates nor migrates.
    with _readonly() as conn:
        if not _ready(conn):
            raise CommunityUnavailable()


@_database_errors
def delete_chat_message(evidence_ref: str) -> dict:
    """Operator-only erasure of one line; no history write or forced case closure."""
    _outside_transaction()
    reference = _id(evidence_ref)
    _require_deletion_store()
    with db.transaction() as conn:
        return _delete_chat(conn, "evidence_ref=?", (reference,))


@_database_errors
def delete_tester_chat(tester: str) -> dict:
    """Erase one tester's eligible lines across credential rotation and worlds."""
    _outside_transaction()
    name = _text(tester, maximum=1000)
    _require_deletion_store()
    with db.transaction() as conn:
        matches = [digest for digest, registered in conn.execute("SELECT key,name FROM invite_keys")
                   if db.name_key(registered) == db.name_key(name)]
        if not matches:
            raise UnknownTester()
        if len(matches) != 1:
            raise AmbiguousTester()
        owner = conn.execute("SELECT participant_id FROM participant_credentials WHERE credential_digest=?",
                             (matches[0],)).fetchone()
        if owner is None:
            return {**_delete_chat(conn, "0", ()), "note": "No retained messages for this tester."}
        return _delete_chat(conn, "participant_id=?", (owner[0],))


def _prune(conn, at: str) -> dict:
    actions = conn.execute("DELETE FROM report_actions WHERE expires_at<=? AND report_id IN "
                           "(SELECT id FROM private_reports WHERE status='closed')", (at,)).rowcount
    reports = conn.execute("DELETE FROM private_reports WHERE expires_at<=? AND status='closed'", (at,)).rowcount
    messages = conn.execute("DELETE FROM private_chat_messages WHERE expires_at<=? AND NOT "
                            + _OPEN_REPORT_HOLD, (at,)).rowcount
    policies = conn.execute("""DELETE FROM community_policies WHERE NOT EXISTS
        (SELECT 1 FROM private_chat_messages WHERE policy_digest=community_policies.digest)
        AND NOT EXISTS (SELECT 1 FROM private_reports WHERE policy_digest=community_policies.digest)""").rowcount
    return {"chat_messages": messages, "reports": reports, "actions": actions, "policies": policies}


@_database_errors
def prune_expired() -> dict:
    """Independent housekeeping; no writes or migrations when there is no work."""
    _outside_transaction()
    empty = {"chat_messages": 0, "reports": 0, "actions": 0, "policies": 0}
    if not Path(db._DB_PATH).is_file():
        return empty
    at = _stamp(_now())
    with _readonly() as conn:
        if not _ready(conn):
            return empty
        expired = (conn.execute("SELECT 1 FROM private_chat_messages WHERE expires_at<=? AND NOT "
                                + _OPEN_REPORT_HOLD + " LIMIT 1", (at,)).fetchone()
                   or conn.execute("SELECT 1 FROM private_reports WHERE expires_at<=? AND status='closed' LIMIT 1",
                                   (at,)).fetchone())
        orphan = conn.execute("""SELECT 1 FROM community_policies WHERE NOT EXISTS
            (SELECT 1 FROM private_chat_messages WHERE policy_digest=community_policies.digest)
            AND NOT EXISTS (SELECT 1 FROM private_reports WHERE policy_digest=community_policies.digest) LIMIT 1""").fetchone()
    if not expired and not orphan:
        return empty
    with db.transaction() as conn:
        return _prune(conn, _stamp(_now()))


def status() -> dict:
    """Read-only operator metadata; absent schema never creates or migrates a DB."""
    result = {"available": False, "storage_error": False, "retained_chat": None,
              "open_reports": None, "acknowledged_reports": None, "closed_reports": None}
    try:
        if not Path(db._DB_PATH).exists():
            return result
        at = _stamp(_now())
        with _readonly() as conn:
            if not _ready(conn):
                return result
            result["retained_chat"] = conn.execute(
                "SELECT COUNT(*) FROM private_chat_messages WHERE " + CHAT_RETAINED, (at,)).fetchone()[0]
            counts = dict(conn.execute("SELECT status,COUNT(*) FROM private_reports WHERE "
                                       + _REPORT_RETAINED + " GROUP BY status", (at,)))
            for state in _STATES:
                result[state + "_reports"] = counts.get(state, 0)
        result["available"] = True
    except (sqlite3.Error, OSError, CommunityUnavailable):
        result["storage_error"] = True
    return result
