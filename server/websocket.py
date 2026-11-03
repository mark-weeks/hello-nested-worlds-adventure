"""WebSocket upgrade, per-connection message loop and credential sweep."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import socket
import threading
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


class _Session:
    """One upgraded socket, shared by its reader loop and the credential sweep.

    Only the reader thread writes a close frame or leaves the room. The sweep
    reads the credential, and when it is no longer live sets ``revoked``,
    stops the writer and shuts the socket's read side, which wakes the
    reader; the reader then closes with 1008 and leaves through the normal
    disconnect path, once.
    """

    def __init__(self, player: Player, sock, ws_key: str, credentialed: bool,
                 checked_at: float, logger: logging.Logger) -> None:
        self.player = player
        self.sock = sock
        self.ws_key = ws_key
        self.credentialed = credentialed
        self.logger = logger
        # Monotonic time of the last check that found this session
        # authorized: the upgrade, a frame's re-check or a sweep.
        self.last_checked = checked_at
        # Set by the sweep, under its lock, when the credential failed.
        self.revoked = False
        # Set, under the send lock, once a close frame is written or a peer's
        # close is about to be echoed: a session sends one close frame.
        self._close_sent = False

    def checked(self, at: float) -> None:
        if at > self.last_checked:
            self.last_checked = at

    @property
    def ending(self) -> bool:
        """Revoked by the sweep, or its close frame already sent."""
        return self.revoked or self._close_sent

    def close(self, code: int) -> None:
        """Send this session's close frame, unless one was already sent.

        Stops the writer first, and writes under the send lock that every
        data frame takes, so queued room traffic never follows the close
        frame (RFC 6455 §5.5.1). The caller then leaves the loop through the
        normal disconnect path, which removes the player and records the
        departure once.
        """
        self.player.stop_writer()
        with self.player.send_lock:
            if self._close_sent:
                return
            self._close_sent = True
            try:
                send_close(self.sock, code)
            except OSError:
                pass

    def peer_closing(self) -> None:
        """``ws_recv``'s ``before_close``: the echo is this session's close."""
        self.player.stop_writer()
        with self.player.send_lock:
            self._close_sent = True


class _CredentialSweep:
    """Re-checks every open socket's credential on the server's own schedule.

    A frame re-checks its own socket, but a client that only listens sends
    no frames. One daemon thread per process, started by the first open
    socket and ended when the last one leaves (or by ``stop`` at server
    shutdown), reads each socket's credential once its last successful
    check is ``guard.WS_SWEEP_INTERVAL_SEC`` old: one read per socket per
    interval at most, none while the socket's own frames keep it checked,
    and never one per broadcast. Reads run outside every lock. A failed or
    erroring read revokes the session (``_revoke``); nothing here blocks on
    a socket, so one stalled client cannot delay the sweep of the others.
    """

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._sessions: set[_Session] = set()
        self._thread: threading.Thread | None = None

    def add(self, session: _Session) -> None:
        with self._cond:
            self._sessions.add(session)
            if self._thread is None:
                thread = threading.Thread(
                    target=self._run, name="ws-credential-sweep", daemon=True)
                thread.start()  # it waits for this lock before it looks
                self._thread = thread
            else:
                self._cond.notify_all()  # re-read the interval

    def discard(self, session: _Session) -> None:
        """Called by the reader before its socket can close."""
        with self._cond:
            self._sessions.discard(session)
            self._cond.notify_all()

    def stop(self) -> None:
        """End the sweep thread at server shutdown. A later socket starts
        another."""
        with self._cond:
            self._thread = None
            self._cond.notify_all()

    def _run(self) -> None:
        me = threading.current_thread()
        while True:
            due = self._next_due(me)
            if due is None:
                return
            for session in due:
                self._check(session)

    def _next_due(self, me: threading.Thread) -> list[_Session] | None:
        """Wait until some open socket is due. None ends this thread."""
        with self._cond:
            while True:
                if self._thread is not me:
                    return None
                if not self._sessions:
                    self._thread = None
                    return None
                interval = guard.WS_SWEEP_INTERVAL_SEC
                now = time.monotonic()
                live = [s for s in self._sessions if not s.ending]
                due = [s for s in live if now - s.last_checked >= interval]
                if due:
                    return due
                # Sleep until the next socket is due. With only ending
                # sockets left, wait for their readers to discard them.
                timeout = (min(s.last_checked for s in live) + interval - now
                           if live else None)
                self._cond.wait(timeout)

    def _check(self, session: _Session) -> None:
        started = time.monotonic()
        try:
            authorized = guard.ws_session_authorized(
                session.ws_key, session.credentialed)
        except Exception as exc:  # noqa: BLE001 — fail closed, never a key
            session.logger.error("WebSocket credential sweep failed (%s); "
                                 "closing the session", type(exc).__name__)
            authorized = False
        if authorized:
            session.checked(started)
        else:
            self._revoke(session)

    def _revoke(self, session: _Session) -> None:
        """Stop the writer and wake the reader, which closes with 1008.

        Under the sweep lock, so the socket is still open: the reader
        discards its session under the same lock before the socket closes.
        Neither call blocks.
        """
        with self._cond:
            if session not in self._sessions or session.revoked:
                return
            session.revoked = True
            session.player.stop_writer()
            try:
                session.sock.shutdown(socket.SHUT_RD)
            except OSError:
                pass
        session.logger.info("WebSocket session %s closed: no longer "
                            "authorized", session.player.session_id)


_SWEEP = _CredentialSweep()


def stop_credential_sweep() -> None:
    """Server shutdown: end the credential sweep thread."""
    _SWEEP.stop()


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
    # Taken before the reads that authorize this upgrade: the credential
    # sweep's first check of this socket falls due one interval later.
    authorized_at = time.monotonic()
    registered = guard.registered_name(ws_key)
    if registered is None and guard.invite_gate_active():
        # The gate admitted this request, but its credential was revoked (or
        # the gate closed) before the name was read. Refuse as the gate does,
        # before any row or broadcast, rather than join under ?name=.
        request._send_error("forbidden", 403)
        return
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
        # Once a frame starts, protocol._FRAME_DEADLINE_SEC bounds the rest
        # of it; a frame past that is a ProtocolError (close 1002).
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
        session = _Session(player, sock, ws_key, credentialed,
                           authorized_at, logger)

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
            # A session the credential sweep revoked is over, whatever frame
            # was still being read when it did.
            nonlocal last_authorized
            if session.revoked:
                session.close(CLOSE_POLICY_VIOLATION)
                return False
            now = time.monotonic()
            if (not fresh
                    and now - last_authorized < guard.WS_REAUTH_INTERVAL_SEC):
                return True
            if guard.ws_session_authorized(ws_key, credentialed):
                # The sweep may have refused this session while that read
                # ran (its own read saw the revocation, or failed closed).
                # Its verdict wins: a pass that started earlier is stale.
                if session.revoked:
                    session.close(CLOSE_POLICY_VIOLATION)
                    return False
                last_authorized = now
                session.checked(now)
                return True
            logger.info("WebSocket session %s closed: no longer authorized",
                        session_id)
            session.close(CLOSE_POLICY_VIOLATION)
            return False

        # The sweep this session joins is the one it leaves, even if the
        # module's sweep is replaced meanwhile (tests install their own).
        sweep = _SWEEP
        try:
            # From here a socket that sends nothing is still re-checked; the
            # finally below discards it before the socket can close.
            sweep.add(session)
            while True:
                # The same throttled check also vets the frame that opens a
                # fragmented message and every frame inside it, which
                # ws_recv reads without returning: an opening fragment or
                # interleaved pings would otherwise keep a revoked session
                # subscribed.
                # before_close stops the writer before the peer's close is
                # echoed, so no queued data frame follows the echo, and
                # marks the echo as this session's one close frame.
                payload = ws_recv(sock, send_lock=player.send_lock,
                                  on_frame=still_authorized,
                                  before_close=session.peer_closing)
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
            # Writer first (_Session.close): no queued data frame may follow
            # the close frame. A session the sweep already ended closes with
            # 1008 whatever bytes the client had queued behind its last
            # check: its credential, not its framing, ended it.
            session.close(CLOSE_POLICY_VIOLATION if session.revoked
                          else CLOSE_PROTOCOL_ERROR)
        except (OSError, ConnectionResetError, BrokenPipeError):
            # Includes the end of input after the credential sweep shut the
            # read side; the close frame for that is sent below.
            pass
        finally:
            sweep.discard(session)
            if session.revoked:
                # The sweep revoked this session while the reader waited.
                # A no-op if a close frame was already sent.
                session.close(CLOSE_POLICY_VIOLATION)
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
