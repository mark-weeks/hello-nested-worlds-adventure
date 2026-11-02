"""Owner sanctions: suspend a player for a set time, ban, or lift either.

Beta checklist G5. A sanction is keyed to a participant (migration 0021),
not to a credential, and while it is active every credential of that
participant is not live: `persistence.lookup_invite_key` and
`participants.identify` both refuse it (`persistence._UNSANCTIONED`). The
player meets the same invite-gate 403 as a revoked key, an open WebSocket
closes with 1008 at its next frame, and no reason is disclosed. When the
suspension expires or the sanction is lifted, the same credential works
again and resolves to the same participant, journal and profile intact.

Unlike `invite revoke`, nothing here burns the name or the credential.

Insert-only, like `persistence.pin_world_meta`: this module offers no
update and no delete. A sanction ends at its expiry or by a lift row.
Nothing here writes to `world_mutations`. Reasons are private operator data:
returned to the operator's CLI, never logged, never sent to a client. They
do enter every backup of the database.

Operator-only: called from `python main.py sanction ...`. There is no HTTP
surface.
"""
from __future__ import annotations

import datetime
import logging
from typing import Any

import persistence as db
from persistence import participants

_log = logging.getLogger("nested_worlds.sanctions")

KINDS = ("suspension", "ban")
MAX_REASON_CHARS = 500
# A longer exclusion is a ban, which is lifted explicitly.
MAX_SUSPENSION = datetime.timedelta(days=365)
MIN_SUSPENSION = datetime.timedelta(minutes=1)

_ROW = """SELECT s.id, s.participant_id, s.kind, s.reason, s.created_at,
       s.expires_at, l.reason, l.lifted_at,
       CASE WHEN l.sanction_id IS NOT NULL THEN 'lifted'
            WHEN {active} THEN 'active'
            ELSE 'expired' END,
       (SELECT i.name FROM participant_credentials c
          JOIN invite_keys i ON i.key = c.credential_digest
         WHERE c.participant_id = s.participant_id
         ORDER BY i.revoked_at IS NULL DESC LIMIT 1)
  FROM sanctions s LEFT JOIN sanction_lifts l ON l.sanction_id = s.id"""


def _select(where: str = "") -> str:
    return _ROW.format(active=db._SANCTION_ACTIVE) + (f" WHERE {where}" if where else "")


def _as_dict(row) -> dict[str, Any]:
    return {
        "id": row[0], "participant": row[1], "kind": row[2], "reason": row[3],
        "created_at": row[4], "expires_at": row[5], "lift_reason": row[6],
        "lifted_at": row[7], "status": row[8], "name": row[9],
    }


def _clean_reason(reason: Any) -> str:
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("A reason is required and must not be empty.")
    reason = reason.strip()
    if len(reason) > MAX_REASON_CHARS:
        raise ValueError(f"A reason may contain up to {MAX_REASON_CHARS} characters.")
    return reason


def _resolve_on(conn, target: str) -> dict[str, Any]:
    """{'id', 'name'} for a registered name or a participant id.

    Names match case- and whitespace-insensitively, the same comparison as
    name uniqueness (migration 0011), and a revoked key's name still
    resolves. A registered player who has never made an authenticated read
    has no participant row yet; one is created with `participants._ensure`
    semantics, keyed by the credential's digest, so the sanction and every
    later read agree on who the player is. An argument that names one
    player and is another player's id is refused as ambiguous.
    """
    if not isinstance(target, str) or not target.strip():
        raise ValueError("Name a registered player or a participant id.")
    target = target.strip()
    named = conn.execute(
        "SELECT key, name FROM invite_keys WHERE lower(trim(name)) = ?",
        (db._normalize_invite_name(target),)).fetchone()
    by_id = conn.execute(
        "SELECT id FROM participants WHERE id = ?", (target,)).fetchone()
    if named is not None:
        participant = participants._ensure(conn, named[0])
        if by_id is not None and by_id[0] != participant:
            raise ValueError(f"{target!r} is both a player's name and another "
                             "player's participant id; nothing changed.")
        return {"id": participant, "name": named[1]}
    if by_id is not None:
        name = conn.execute(
            """SELECT i.name FROM participant_credentials c
               JOIN invite_keys i ON i.key = c.credential_digest
               WHERE c.participant_id = ?
               ORDER BY i.revoked_at IS NULL DESC LIMIT 1""",
            (by_id[0],)).fetchone()
        return {"id": by_id[0], "name": name[0] if name else None}
    raise ValueError(f"No registered player or participant matches {target!r}.")


def resolve(target: str) -> dict[str, Any]:
    """Resolve a registered name or participant id; see `_resolve_on`."""
    with db.transaction() as conn:
        return _resolve_on(conn, target)


def _record(target: str, kind: str, reason: str,
            seconds: int | None) -> dict[str, Any]:
    reason = _clean_reason(reason)
    with db.transaction() as conn:
        who = _resolve_on(conn, target)
        if kind == "ban":
            cur = conn.execute(
                f"""INSERT INTO sanctions (participant_id, kind, reason, created_at)
                    VALUES (?, 'ban', ?, {db._NOW})""",
                (who["id"], reason))
        else:
            # One statement, so created_at and expires_at read the same 'now'.
            cur = conn.execute(
                f"""INSERT INTO sanctions
                        (participant_id, kind, reason, created_at, expires_at)
                    VALUES (?, 'suspension', ?, {db._NOW}, datetime({db._NOW}, ?))""",
                (who["id"], reason, f"+{seconds} seconds"))
        row = conn.execute(_select("s.id = ?"), (cur.lastrowid,)).fetchone()
    # Sanction id and kind only: never the reason, the name or a credential.
    _log.info("sanction %d recorded (%s)", row[0], kind)
    return _as_dict(row)


def suspend(target: str, duration: datetime.timedelta, reason: str) -> dict[str, Any]:
    """Suspend a player from now for `duration` (1 minute to 365 days).

    Returns the recorded sanction. Effective on the player's next request
    or socket frame. Raises ValueError, writing nothing, for an unknown
    player, an empty reason, or a duration out of range.
    """
    if not isinstance(duration, datetime.timedelta):
        raise ValueError("A suspension needs a duration.")
    if not MIN_SUSPENSION <= duration <= MAX_SUSPENSION:
        raise ValueError("A suspension lasts from 1 minute to 365 days; "
                         "use a ban for longer.")
    return _record(target, "suspension", reason, int(duration.total_seconds()))


def ban(target: str, reason: str) -> dict[str, Any]:
    """Ban a player until the ban is lifted. Returns the recorded sanction.

    Unlike `invite revoke`, a ban keeps the name and the credential: lifting
    it restores the same participant. Raises ValueError, writing nothing,
    for an unknown player or an empty reason.
    """
    return _record(target, "ban", reason, None)


def lift(sanction_id: int, reason: str) -> dict[str, Any]:
    """End an active sanction early, with a reason. Returns the sanction.

    Refuses (ValueError, nothing written) an unknown id, a sanction already
    lifted, and a suspension that has already expired. At most one lift
    exists per sanction; the sanction row itself is never changed.
    """
    reason = _clean_reason(reason)
    if isinstance(sanction_id, bool) or not isinstance(sanction_id, int):
        raise ValueError("A sanction id is a whole number.")
    with db.transaction() as conn:
        row = conn.execute(_select("s.id = ?"), (sanction_id,)).fetchone()
        if row is None:
            raise ValueError(f"No sanction has id {sanction_id}.")
        found = _as_dict(row)
        if found["status"] == "lifted":
            raise ValueError(f"Sanction {sanction_id} was already lifted at "
                             f"{found['lifted_at']}; nothing changed.")
        if found["status"] == "expired":
            raise ValueError(f"Sanction {sanction_id} already ended at "
                             f"{found['expires_at']}; nothing to lift.")
        conn.execute(
            f"""INSERT INTO sanction_lifts (sanction_id, reason, lifted_at)
                VALUES (?, ?, {db._NOW})""", (sanction_id, reason))
        row = conn.execute(_select("s.id = ?"), (sanction_id,)).fetchone()
    _log.info("sanction %d lifted", sanction_id)
    return _as_dict(row)


def active_sanctions(participant_id: str) -> list[dict[str, Any]]:
    """The participant's active sanctions, newest first (empty when none)."""
    db.init_db()
    with db._connection() as conn:
        rows = conn.execute(
            _select(f"s.participant_id = ? AND {db._SANCTION_ACTIVE}")
            + " ORDER BY s.id DESC", (participant_id,)).fetchall()
    return [_as_dict(r) for r in rows]


def is_sanctioned(participant_id: str) -> bool:
    """True while the participant holds any active sanction."""
    return bool(active_sanctions(participant_id))


def list_sanctions(include_all: bool = False) -> list[dict[str, Any]]:
    """Sanctions newest first: active ones, or with `include_all` every one,
    lifted and expired included, with each lift's reason and time."""
    db.init_db()
    with db._connection() as conn:
        where = "" if include_all else db._SANCTION_ACTIVE
        rows = conn.execute(_select(where) + " ORDER BY s.id DESC").fetchall()
    return [_as_dict(r) for r in rows]
