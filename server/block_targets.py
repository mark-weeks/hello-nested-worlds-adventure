"""Opaque live targeting handles; durable identities never leave this boundary.

Handles are scoped to a viewing participant and this server process. Reconnecting
after a restart fetches fresh handles; the underlying preferences remain durable.
No handle is a participant/profile identifier or a human/agent discriminator.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from collections import OrderedDict

_KEY = secrets.token_bytes(32)
_HANDLE_LIMIT = 4096
_HANDLES: OrderedDict[tuple[str, str], str] = OrderedDict()
_HANDLE_LOCK = threading.Lock()


def _token(viewer: str, target: str) -> str:
    return hmac.new(_KEY, f'{viewer}\0{target}'.encode(), hashlib.sha256).hexdigest()[:32]


def handle(viewer: str, target: str | None) -> str | None:
    if not target:
        return None
    token = _token(viewer, target)
    with _HANDLE_LOCK:
        key = (viewer, token)
        _HANDLES[key] = target
        _HANDLES.move_to_end(key)
        while len(_HANDLES) > _HANDLE_LIMIT:
            _HANDLES.popitem(last=False)
    return token


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

    Recently displayed handles include disconnected travelers without scanning
    every historical participant. The bounded cache is process-local; after an
    eviction, live travelers and the owner's saved blocks can still be resolved.
    Stored rows keep offline/retired targets removable after reconnect/restart.
    """
    import persistence as db
    from agents.identities import SERVER_IDENTITIES
    from persistence.blocks import agent_target
    from server.rooms import _rooms, _rooms_lock

    if (not isinstance(token, str) or len(token) != 32
            or any(char not in '0123456789abcdef' for char in token)):
        raise ValueError('Choose another traveler.')
    with _HANDLE_LOCK:
        key = (viewer, token)
        target = _HANDLES.get(key)
        if target is not None:
            # A process restart replaces both the key and the cache. Rechecking
            # also prevents a stale cache from accepting a replaced runtime key.
            if hmac.compare_digest(_token(viewer, target), token):
                _HANDLES.move_to_end(key)
                return target
            _HANDLES.pop(key)
    with db._connection() as conn:
        candidates = {row[0] for row in conn.execute(
            'SELECT blocked_id FROM participant_blocks WHERE participant_id=?', (viewer,))}
    with _rooms_lock:
        rooms = list(_rooms.values())
    for room in rooms:
        with room.lock:
            candidates.update(player.participant_id for player in room.players.values()
                              if player.participant_id is not None)
    candidates.update(target for name in SERVER_IDENTITIES if (target := agent_target(name)))
    for target in candidates:
        if hmac.compare_digest(_token(viewer, target), token):
            handle(viewer, target)
            return target
    raise ValueError('Choose another traveler.')
