"""Private participant-owned blocks; no chronicle or credential data is exposed."""
from __future__ import annotations

import re

import persistence as db


def _validate_id(value: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{32}", value) is None:
        raise ValueError("Choose another traveler.")


def agent_target(name: str) -> str | None:
    """Public targeting identity derived only from the server's canonical registry."""
    from agents.identities import canonical
    canonical_name = canonical(name)
    return 'agent:' + canonical_name if canonical_name is not None else None


def _target_agent(target: str) -> str | None:
    if not isinstance(target, str) or not target.startswith('agent:'):
        return None
    name = target[6:]
    return name if agent_target(name) == target else None


def _list(conn, participant: str) -> list[dict]:
    rows = conn.execute("""SELECT b.blocked_id, COALESCE((
        SELECT i.name FROM invite_keys i JOIN participant_credentials c
        ON c.credential_digest=i.key WHERE c.participant_id=b.blocked_id LIMIT 1
        ), 'Unavailable traveler')
        FROM participant_blocks b WHERE b.participant_id=?
        ORDER BY b.created_at,b.blocked_id""", (participant,)).fetchall()
    return [{"id": target, "name": _target_agent(target) or name}
            for target, name in rows]


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
            conn.execute("DELETE FROM participant_blocks WHERE participant_id=? AND blocked_id=?",
                         (participant, target))
        return _list(conn, participant)
