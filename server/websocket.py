"""WebSocket upgrade and per-connection message loop."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import struct
import uuid
from collections.abc import Callable

import persistence
from multiverse import store
from puzzles import gates
from server import guard, moderation
from server.protocol import ProtocolError, _send_frame, ws_recv
from server.rooms import (
    Player,
    agents_snapshot,
    broadcast,
    get_room,
    snapshot,
)


_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def handle_websocket(
    request,
    qs: dict,
    *,
    actor_identity: Callable[[str, str | None], str | None],
    reserved_names: set[str],
    logger: logging.Logger,
) -> None:
    """Upgrade one request and own the socket until its session ends.

    ``request`` provides the ``BaseHTTPRequestHandler`` surface used below
    plus ``Handler._send_error(message, status)`` from ``server.handlers``.
    """
    key = request.headers.get("Sec-WebSocket-Key", "")
    if not key:
        request._send_error("WebSocket upgrade required", 400)
        return

    try:
        seed = guard.world_seed(qs.get("seed", [""])[0])
    except (ValueError, IndexError) as exc:
        request._send_error(str(exc), 400)
        return

    ws_key = guard.supplied_key(request.headers, qs)
    registered = guard.registered_name(ws_key)
    if registered:
        name = registered
    else:
        name = (qs.get("name", ["Anonymous"])[0] or "").strip()[:32] or "Anonymous"
        if name.lower() in reserved_names:
            request._send_error(
                f"'{name}' belongs to the world — choose another name", 403
            )
            return

    ip = guard.client_ip(request.client_address, request.headers)
    if not guard.WS_LIMITER.acquire(ip):
        request._send_error("too many connections", 503)
        return

    try:
        accept = base64.b64encode(
            hashlib.sha1((key + _WS_GUID).encode()).digest()
        ).decode()
        request.send_response(101, "Switching Protocols")
        request.send_header("Upgrade", "websocket")
        request.send_header("Connection", "Upgrade")
        request.send_header("Sec-WebSocket-Accept", accept)
        request.end_headers()
        request.wfile.flush()

        # An upgraded socket is one-shot. Closing HTTP keep-alive also ensures
        # a completed RFC 6455 close handshake ends with TCP FIN.
        request.close_connection = True
        sock = request.connection
        sock.settimeout(60)
        session_id = uuid.uuid4().hex[:8]
        ws_identity = actor_identity(ws_key, name)

        # A reconnect resumes at its validated stored position. Do not re-check
        # a seal here: someone already inside a newly sealed subtree is never
        # imprisoned by it.
        root_name = store.root_name(seed)
        entry_node = root_name
        if ws_key:
            saved = persistence.get_player_position(ws_key)
            if saved and saved.get("seed") == seed and saved.get("node"):
                target = store.resolve_node_by_name(seed, str(saved["node"])[:128])
                if target is not None:
                    entry_node = target.name

        player = Player(
            name=name,
            seed=seed,
            current_node=entry_node,
            session_id=session_id,
            sock=sock,
        )
        player.start_writer()
        room = get_room(seed)
        with room.lock:
            room.players[session_id] = player

        player.send(
            {
                "type": "welcome",
                "session_id": session_id,
                "players": snapshot(room),
                "agents": agents_snapshot(room),
            }
        )
        broadcast(
            room,
            {"type": "player_join", "name": name, "session_id": session_id},
            exclude=session_id,
        )
        persistence.record_mutation(
            seed,
            entry_node,
            "PLAYER_JOIN",
            name,
            {},
            actor_identity=ws_identity,
        )

        move_bucket = guard.TokenBucket(guard.WS_MOVE_RATE, guard.WS_MOVE_BURST)
        chat_bucket = guard.TokenBucket(guard.WS_CHAT_RATE, guard.WS_CHAT_BURST)
        try:
            while True:
                payload = ws_recv(sock, send_lock=player.send_lock)
                if payload is None:
                    break
                if not payload:
                    continue
                try:
                    message = json.loads(payload)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                message_type = message.get("type")
                if message_type == "move":
                    if not move_bucket.allow():
                        continue
                    node_name = str(message.get("node", ""))[:64]
                    target = (
                        store.resolve_node_by_name(seed, node_name)
                        if node_name
                        else None
                    )
                    if target is None:
                        player.send(
                            {
                                "type": "move_denied",
                                "node": node_name,
                                "reason": "no such place",
                            }
                        )
                        continue
                    seal = gates.seal_check(
                        seed, target, current_name=player.current_node
                    )
                    if seal is not None:
                        player.send(
                            {
                                "type": "move_denied",
                                "node": node_name,
                                "reason": "sealed",
                                **seal,
                            }
                        )
                        continue
                    with room.lock:
                        player.current_node = node_name
                    broadcast(
                        room,
                        {
                            "type": "player_move",
                            "name": name,
                            "node": node_name,
                            "session_id": session_id,
                        },
                        exclude=session_id,
                    )
                    persistence.record_mutation(
                        seed,
                        node_name,
                        "PLAYER_MOVE",
                        name,
                        {},
                        actor_identity=ws_identity,
                    )
                elif message_type == "chat":
                    if not chat_bucket.allow():
                        continue
                    text = str(message.get("text", "")).strip()[:256]
                    if text and not moderation.screen(text).allowed:
                        player.send(
                            {"type": "chat_declined", "text": moderation.DECLINE_LINE}
                        )
                        continue
                    if text:
                        broadcast(
                            room,
                            {
                                "type": "chat",
                                "name": name,
                                "text": text,
                                "session_id": session_id,
                            },
                        )
                        persistence.record_mutation(
                            seed,
                            player.current_node or root_name,
                            "PLAYER_CHAT",
                            name,
                            {"text": text},
                            actor_identity=ws_identity,
                        )
                elif message_type == "ping":
                    player.send({"type": "pong"})
        except ProtocolError:
            try:
                _send_frame(
                    sock,
                    0x8,
                    struct.pack(">H", 1002),
                    lock=player.send_lock,
                )
            except OSError:
                pass
        except (OSError, ConnectionResetError, BrokenPipeError):
            pass
        finally:
            player.stop_writer()
            with room.lock:
                room.players.pop(session_id, None)
            broadcast(
                room,
                {"type": "player_leave", "name": name, "session_id": session_id},
            )
            try:
                persistence.record_mutation(
                    seed,
                    player.current_node or root_name,
                    "PLAYER_LEAVE",
                    name,
                    {},
                    actor_identity=ws_identity,
                )
            except Exception:  # noqa: BLE001 — teardown must not raise
                logger.exception("failed to record PLAYER_LEAVE")
    finally:
        guard.WS_LIMITER.release(ip)
