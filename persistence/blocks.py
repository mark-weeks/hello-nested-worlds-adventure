"""Private participant-owned blocks; no chronicle or credential data is exposed."""
from __future__ import annotations

import re

import persistence as db


def _validate_id(value: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{32}", value) is None:
        raise ValueError("Choose another traveler.")


def agent_target(name: str) -> str | None:
    """Internal targeting identity derived only from the server's canonical registry."""
    from agents.identities import canonical
    canonical_name = canonical(name)
    return 'agent:' + canonical_name if canonical_name is not None else None


def _target_agent(target: str) -> str | None:
    if not isinstance(target, str) or not target.startswith('agent:'):
        return None
    name = target[6:]
    return name if agent_target(name) == target else None


def current_target(target: str) -> str:
    """The target a stored row names today.

    A cast member's block is stored under the name it had when the block was
    made. A rename rewrites no row, so a row under a retired name
    (``agents.identities.RETIRED_IDENTITIES``) is read as the member's
    current target: the block keeps working and shows the current name.
    """
    from agents.identities import RETIRED_IDENTITIES
    if isinstance(target, str) and target.startswith('agent:'):
        renamed = agent_target(RETIRED_IDENTITIES.get(target[6:]))
        if renamed is not None:
            return renamed
    return target


def _stored_targets(target: str) -> list[str]:
    """Every spelling a row for this target may be stored under."""
    from agents.identities import RETIRED_IDENTITIES
    return [target, *('agent:' + old for old in RETIRED_IDENTITIES
                      if current_target('agent:' + old) == target)]


def _list(conn, participant: str) -> list[dict]:
    rows = conn.execute("""SELECT b.blocked_id, COALESCE((
        SELECT i.name FROM invite_keys i JOIN participant_credentials c
        ON c.credential_digest=i.key WHERE c.participant_id=b.blocked_id
        ORDER BY c.created_at DESC,c.rowid DESC LIMIT 1
        ), 'Unavailable traveler')
        FROM participant_blocks b WHERE b.participant_id=?
        ORDER BY b.created_at,b.blocked_id""", (participant,)).fetchall()
    # One entry per current target: a row under a retired name and a newer
    # row under the current one are the same block.
    listed = {}
    for stored, name in rows:
        target = current_target(stored)
        listed.setdefault(target, {"id": target, "name": _target_agent(target) or name})
    return list(listed.values())


def list_blocks(participant: str) -> list[dict]:
    _validate_id(participant)
    db.init_db()
    with db._connection() as conn:
        return _list(conn, participant)


def set_block(participant: str, target: str, blocked: bool) -> list[dict]:
    """The authenticated caller supplies participant; the body supplies only target.

    Idempotent retries change no world rows. Foreign keys are not enabled on
    every connection, so validate both identities under the writer fence.
    """
    _validate_id(participant)
    if not isinstance(target, str) or participant == target or not isinstance(blocked, bool):
        raise ValueError("Choose another traveler and whether to block them.")
    with db.transaction() as conn:
        owner_exists = conn.execute("SELECT 1 FROM participants WHERE id=?",
                                    (participant,)).fetchone()
        if not owner_exists:
            raise ValueError("Choose another traveler.")
        if blocked:
            agent = _target_agent(target)
            if not agent:
                _validate_id(target)
            target_exists = agent or conn.execute("SELECT 1 FROM participants WHERE id=?",
                                                 (target,)).fetchone()
            if not target_exists:
                raise ValueError("Choose another traveler.")
            conn.execute("""INSERT INTO participant_blocks(participant_id,blocked_id)
                VALUES (?,?) ON CONFLICT DO NOTHING""", (participant, target))
        else:
            # Unblocking removes the row under every name the target has had.
            for stored in _stored_targets(target):
                conn.execute("DELETE FROM participant_blocks WHERE participant_id=? AND blocked_id=?",
                             (participant, stored))
        return _list(conn, participant)
