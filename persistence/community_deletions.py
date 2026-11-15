"""Text-free proof of completed chat erasure, carried across world restores.

Only refs actually erased get a record. A record never targets a person's future
messages, and a held line has no record until an operator successfully deletes it.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile

import persistence as db
from persistence import community

TABLE = "private_chat_deletions"
DDL = """CREATE TABLE IF NOT EXISTS private_chat_deletions (
    evidence_ref TEXT PRIMARY KEY NOT NULL CHECK (length(evidence_ref) = 32),
    deleted_at TEXT NOT NULL
)"""


def _invalid() -> community.CommunityError:
    return community.CommunityError("The private chat deletion record is invalid.")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _invalid()
        result[key] = value
    return result


def _validated(records: object) -> list[tuple[str, str]]:
    if not isinstance(records, list):
        raise _invalid()
    result = []
    seen = set()
    for row in records:
        if not isinstance(row, dict) or set(row) != {"evidence_ref", "deleted_at"}:
            raise _invalid()
        reference, at = row["evidence_ref"], row["deleted_at"]
        if not isinstance(reference, str) or not community._HEX32.fullmatch(reference) or reference in seen:
            raise _invalid()
        if not isinstance(at, str):
            raise _invalid()
        try:
            moment = datetime.fromisoformat(at.replace("Z", "+00:00"))
            if moment.tzinfo is None or moment.utcoffset() != timezone.utc.utcoffset(moment):
                raise _invalid()
            if community._stamp(moment) != at:
                raise _invalid()
        except (ValueError, OverflowError):
            raise _invalid() from None
        seen.add(reference)
        result.append((reference, at))
    return result


def records_on(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Read without migrations; pre-schema33 snapshots simply have no ledger."""
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone() is None:
        return []
    rows = conn.execute("SELECT evidence_ref,deleted_at FROM private_chat_deletions ORDER BY evidence_ref").fetchall()
    return _validated([{"evidence_ref": row[0], "deleted_at": row[1]} for row in rows])


def merge_on(conn: sqlite3.Connection, records: list[tuple[str, str]]) -> None:
    conn.execute(DDL)
    conn.executemany("""INSERT INTO private_chat_deletions(evidence_ref,deleted_at) VALUES (?,?)
        ON CONFLICT(evidence_ref) DO UPDATE SET deleted_at=min(deleted_at,excluded.deleted_at)""", records)


def replay_on(conn: sqlite3.Connection) -> int:
    """Apply completed erasure, including over a backup's stale complaint state."""
    records_on(conn)  # Corrupt proof must fail closed before any row changes.
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='private_chat_messages'").fetchone() is None:
        return 0
    return conn.execute("""DELETE FROM private_chat_messages WHERE evidence_ref IN
        (SELECT evidence_ref FROM private_chat_deletions)""").rowcount


def read_export(path: str | Path) -> list[tuple[str, str]]:
    """Validate the complete operator record before a restore changes live data."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique,
                              parse_constant=lambda _: (_ for _ in ()).throw(_invalid()))
        if (not isinstance(document, dict) or set(document) != {"schema_version", "deletions"}
                or type(document["schema_version"]) is not int or document["schema_version"] != 1):
            raise _invalid()
        return _validated(document["deletions"])
    except community.CommunityError:
        raise
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        raise _invalid() from None


def _require_ledger(conn) -> None:
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone() is None:
        raise community.CommunityUnavailable()


@community._database_errors
def export_to(path: str | Path) -> dict:
    """Atomically export a private operator record with mode 0600 without opening a new DB."""
    community._outside_transaction()
    with community._readonly() as conn:
        _require_ledger(conn)
        records = records_on(conn)
    target = Path(path).expanduser()
    if target.resolve() == Path(db._DB_PATH).resolve():
        raise _invalid()
    document = {"schema_version": 1, "deletions": [
        {"evidence_ref": reference, "deleted_at": at} for reference, at in records]}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                         prefix=".chat-deletions-", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(document, stream, ensure_ascii=True, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        target.chmod(0o600)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"exported": len(records), "path": str(target)}


@community._database_errors
def replay_from(path: str | Path) -> dict:
    """Reconcile a separately preserved operator record into an existing DB."""
    community._outside_transaction()
    records = read_export(path)
    with community._readonly() as conn:
        _require_ledger(conn)
    # Do not migrate an older restored database just to replay its carried
    # ledger. Its next normal init will apply additive migration 0033.
    with db._connection() as conn:
        merge_on(conn, records)
        deleted = replay_on(conn)
    return {"recorded": len(records), "deleted": deleted}


@community._database_errors
def replay_pending() -> int:
    """Startup reconciliation before a listener; idle work takes no writer."""
    community._outside_transaction()
    with community._readonly() as conn:
        _require_ledger(conn)
        records_on(conn)
        pending = conn.execute("""SELECT 1 FROM private_chat_messages c JOIN private_chat_deletions d
            ON d.evidence_ref=c.evidence_ref LIMIT 1""").fetchone()
    if pending is None:
        return 0
    with db.transaction() as conn:
        return replay_on(conn)
