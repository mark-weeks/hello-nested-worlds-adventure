"""WebSocket upgrade and per-connection message loop."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
import uuid
from collections.abc import Callable

import persistence
from multiverse import store
from puzzles import gates
from server import guard, moderation
from server.protocol import (
    CLOSE_POLICY_VIOLATION,
    CLOSE_PROTOCOL_ERROR,
    ProtocolError,
    send_close,
    ws_recv,
)
from server.rooms import (
    Player,
    agents_snapshot,
    broadcast,
    get_room,
    snapshot,
)


_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _close_unauthorized(player: Player, sock) -> None:
    """Close a session whose credential is no longer authorized (1008).

    Stops the writer first so queued room traffic does not follow the close
    frame. The caller then leaves the loop through the normal disconnect
    path, which removes the player and records the departure once.
    """
    player.stop_writer()
    try:
        send_close(sock, CLOSE_POLICY_VIOLATION, send_lock=player.send_lock)
    except OSError:
        pass


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
    # Upgraded with a live per-user credential. Such a session lives only as
    # long as that credential does; any other session lives only while the
    # invite gate is open (guard.ws_session_authorized).
    credentialed = registered is not None
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
        # Lifts the plain-HTTP read and write timers (see Handler.setup) and
        # installs this session's idle timer. 60s with no client bytes ends
        # the session. Live browser clients send an application ping inside
        # that window; protocol pings and {"type":"ping"} both run under the
        # same timer. A silent socket — a gone client — still ends here.
        # TimeoutError is an OSError, so it leaves through the handler below.
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

        # Keyed sockets share their buckets with every socket on the same
        # credential; keyless dev sockets get their own.
        move_bucket, chat_bucket = guard.ws_message_buckets(
            ws_key if credentialed else None)

        last_authorized = float("-inf")

        def still_authorized(*, fresh: bool = False) -> bool:
            # A revoked credential or a newly closed gate ends the session.
            # Frames that write nothing (protocol pings and pongs, bad JSON,
            # unknown types, application pings, a rate-limited move or chat)
            # re-check at most once per guard.WS_REAUTH_INTERVAL_SEC: each
            # one resets the idle timer, so an unchecked stream would keep a
            # revoked session subscribed to every room broadcast, but a
            # database read per frame would let one client turn a frame flood
            # into a read flood. A move or chat that passes its throttle
            # re-checks fresh before it writes or broadcasts, so a revoked
            # credential writes nothing; the throttle bounds those reads.
            nonlocal last_authorized
            now = time.monotonic()
            if (not fresh
                    and now - last_authorized < guard.WS_REAUTH_INTERVAL_SEC):
                return True
            if guard.ws_session_authorized(ws_key, credentialed):
                last_authorized = now
                return True
            logger.info("WebSocket session %s closed: no longer authorized",
                        session_id)
            _close_unauthorized(player, sock)
            return False

        try:
            while True:
                # The same throttled check also vets every frame inside an
                # open fragmented message, which ws_recv reads without
                # returning: interleaved pings would otherwise keep a revoked
                # session subscribed.
                payload = ws_recv(sock, send_lock=player.send_lock,
                                  on_frame=still_authorized)
                if payload is None:
                    break
                # Throttled re-check on every frame, before anything else.
                if not still_authorized():
                    break
                if not payload:
                    continue
                try:
                    message = json.loads(payload)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if not isinstance(message, dict):
                    # Valid JSON is not necessarily an object. A list, a
                    # string, a number or null has no type to dispatch on;
                    # ignore it like invalid JSON rather than let .get()
                    # raise into a 500 written onto an upgraded socket.
                    continue
                message_type = message.get("type")
                if message_type == "move":
                    if not move_bucket.allow():
                        continue
                    # Fresh: a move writes a chronicle row and broadcasts.
                    if not still_authorized(fresh=True):
                        break
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
                    # Fresh: a chat writes a chronicle row and broadcasts.
                    if not still_authorized(fresh=True):
                        break
                    # Same rule as /speak: a non-string is not a line. Do not
                    # stringify it, screen it, or write it. The sender hears
                    # the same private refusal; nobody else does.
                    raw_text = message.get("text", "")
                    if not isinstance(raw_text, str):
                        player.send({
                            "type": "chat_declined",
                            "text": "A message is required.",
                        })
                        continue
                    text = raw_text.strip()[:256]
                    if text:
                        verdict = moderation.screen(
                            text, user_key=ws_key or None, surface="chat")
                        if not verdict.allowed:
                            player.send({
                                "type": "chat_declined",
                                "text": moderation.player_line(verdict),
                            })
                            continue
                        # Fresh again: screening can wait on a remote
                        # classifier, and a credential revoked meanwhile
                        # must not publish.
                        if not still_authorized(fresh=True):
                            break
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
                send_close(sock, CLOSE_PROTOCOL_ERROR,
                           send_lock=player.send_lock)
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
