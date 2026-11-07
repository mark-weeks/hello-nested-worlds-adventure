"""Opaque live targeting handles; durable identities never leave this boundary.

Handles are scoped to a viewing participant and this server process. Reconnecting
after a restart fetches fresh handles; the underlying preferences remain durable.
No handle is a participant/profile identifier or a human/agent discriminator.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

_KEY = secrets.token_bytes(32)


def handle(viewer: str, target: str | None) -> str | None:
    if not target:
        return None
    return hmac.new(_KEY, f'{viewer}\0{target}'.encode(), hashlib.sha256).hexdigest()[:32]


def wire_message(viewer: str, message: dict) -> dict:
    """Project identity-bearing live envelopes, leaving historical payloads alone."""
    result = dict(message)
    if 'participant_id' in result:
        result['participant_id'] = handle(viewer, result['participant_id'])
    if 'participant_ids' in result:
        result['participant_ids'] = [handle(viewer, target) for target in result['participant_ids']]
    for collection in ('players', 'agents', 'lines'):
        if collection in result:
            result[collection] = [wire_message(viewer, item) for item in result[collection]]
    if 'blocks' in result:
        result['blocks'] = wire_blocks(viewer, result['blocks'])
    return result


def wire_blocks(viewer: str, rows: list[dict]) -> list[dict]:
    return [{**row, 'id': handle(viewer, row['id'])} for row in rows]


def resolve(viewer: str, token: str) -> str:
    """Resolve only a handle minted for this viewer, never a supplied durable ID.

    Writes are rate-limited. This read includes disconnected participants so an
    already displayed live line remains blockable, and the owner's stored rows
    so retired agent identities remain removable.
    """
    import persistence as db
    from agents.identities import SERVER_IDENTITIES
    from persistence.blocks import agent_target

    if not isinstance(token, str) or len(token) != 32:
        raise ValueError('Choose another traveler.')
    with db._connection() as conn:
        candidates = {row[0] for row in conn.execute('SELECT id FROM participants')}
        candidates.update(row[0] for row in conn.execute(
            'SELECT blocked_id FROM participant_blocks WHERE participant_id=?', (viewer,)))
    candidates.update(target for name in SERVER_IDENTITIES if (target := agent_target(name)))
    for target in candidates:
        if hmac.compare_digest(handle(viewer, target), token):
            return target
    raise ValueError('Choose another traveler.')
