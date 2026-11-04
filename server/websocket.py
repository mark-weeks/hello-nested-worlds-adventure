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

# How long a closing session waits to write its close frame (or the echo of
# the client's): first for the send lock, which a writer blocked in
# ``sendall`` to a client that has stopped reading holds for up to the
# socket's 60 s timeout, then for the frame itself, which a full receive
# window can hold as long. Past this the session shuts the socket down
# instead and sends no close frame; a client that reads nothing would not
# read one either. The shutdown ends the writer's ``sendall`` at once, so
# the departure follows. The sweep gives a refused session's reader the
# same grace before it ends a write the reader is stuck in.
_CLOSE_GRACE_SEC = 1.0


class _Session:
    """One upgraded socket, shared by its reader loop and the credential sweep.

    Only the reader thread writes a close frame or leaves the room. The sweep
    reads the credential, and when it is no longer live sets ``revoked``,
    stops the writer and shuts the socket's read side, which wakes the
    reader; the reader then closes with 1008 and leaves through the normal
    disconnect path, once. A reader still stuck writing to a client that has
    stopped reading a grace period later is released by the sweep shutting
    the socket down (``_CredentialSweep._release_stuck``).
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
        # Set by the sweep, under its lock, when the credential failed, with
        # the monotonic time it did.
        self.revoked = False
        self.revoked_at = 0.0
        # Reader thread only. Set once this session's close frame is
        # written or attempted, or a peer's close is about to be echoed: a
        # session sends at most one close frame.
        self._close_sent = False
        # Set once the socket is shut down in both directions.
        self.shut_down = False

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
        frame (RFC 6455 §5.5.1). Waits at most ``_CLOSE_GRACE_SEC`` for the
        lock and the frame; past that the socket is shut down without one.
        The caller then leaves the loop through the normal disconnect path,
        which removes the player and records the departure once.
        """
        self.player.stop_writer()
        if self._close_sent:
            return
        self._close_sent = True
        if not self._lock_for_close():
            return
        try:
            send_close(self.sock, code)
        except OSError:  # includes the grace running out on a full window
            self.shut_down_socket()
        finally:
            self.player.send_lock.release()

    def peer_closing(self) -> None:
        """``ws_recv``'s ``before_close``: the echo is this session's close.

        Bounded as ``close`` is: the echo, which ``ws_recv`` writes next,
        gets what is left of the grace. If the send lock stays taken the
        socket is shut down instead, and this raises so no echo is tried;
        the reader leaves through its disconnect path.
        """
        self.player.stop_writer()
        self._close_sent = True
        if not self._lock_for_close():
            raise ConnectionAbortedError("WebSocket client is not reading")
        # The writer is stopped: it can only take the lock to see that.
        self.player.send_lock.release()

    def _lock_for_close(self) -> bool:
        """Take the send lock for a close frame within ``_CLOSE_GRACE_SEC``.

        True with the lock held and the socket's timeout cut to the rest of
        the grace: the reader writes nothing after its close frame, so the
        session's idle timer is not needed again. False, with the socket
        shut down, if the lock stayed taken.
        """
        deadline = time.monotonic() + _CLOSE_GRACE_SEC
        if not self.player.send_lock.acquire(timeout=_CLOSE_GRACE_SEC):
            self.shut_down_socket()
            return False
        self.sock.settimeout(max(deadline - time.monotonic(), 0.01))
        return True

    def shut_down_socket(self) -> None:
        """End the socket in both directions, without a close frame.

        Any ``sendall`` on it, the writer's or the reader's, fails at once.
        Called only while the socket is open: by the reader before its
        handler returns, or by the sweep under its lock while the session
        is registered.
        """
        self.shut_down = True
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


class _CredentialSweep:
    """Re-checks every open socket's credential on the server's own schedule.

    A frame re-checks its own socket, but a client that only listens sends
    no frames. One daemon thread per process, started by the first open
    socket and ended when the last one leaves (or by ``stop`` at server
    shutdown), reads each socket's credential once its last successful
    check is ``guard.WS_SWEEP_INTERVAL_SEC`` old: one read per socket per
    interval at most, none while the socket's own frames keep it checked,
    and never one per broadcast. Reads run outside every lock. A failed
    read, or anything raised while checking one session, revokes that
    session (``_sweep``, ``_revoke``); nothing here blocks on a socket, so
    one stalled client cannot delay the sweep of the others. Reads run one
    socket after another, so one slow read delays the checks queued behind
    it.
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
        try:
            while True:
                due = self._next_due(me)
                if due is None:
                    return
                for session in due:
                    self._sweep(session)
        finally:
            # If this thread dies, the next socket starts another, rather
            # than add() trusting a dead thread to sweep it.
            with self._cond:
                if self._thread is me:
                    self._thread = None

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
                wakes = self._release_stuck(now)
                live = [s for s in self._sessions if not s.ending]
                due = [s for s in live if now - s.last_checked >= interval]
                if due:
                    return due
                # Sleep until the next socket is due or a refused session's
                # grace ends. With neither, wait for the readers of ending
                # sockets to discard them.
                wakes += [s.last_checked + interval for s in live]
                self._cond.wait(min(wakes) - now if wakes else None)

    def _release_stuck(self, now: float) -> list[float]:
        """Shut down refused sockets whose reader is stuck writing.

        A refused session's reader normally sends its close frame and lets
        go at once. If it still holds the session a grace period after the
        refusal while the send lock is taken, it is stuck behind or in a
        write to a client that has stopped reading: a pong, the echo of the
        client's close, or its own close frame, queued behind the writer's
        ``sendall`` or blocked on a full receive window. Shutting the read
        side wakes only a read. Shutting both ends those writes, and the
        writer's, so the reader goes on to its departure. A reader waiting
        on anything else, with the send lock free, is looked at again a
        grace period later. Under the sweep lock, so each socket is still
        open. Returns when to look again.
        """
        wakes = []
        for session in self._sessions:
            if not session.revoked or session.shut_down:
                continue
            grace_ends = session.revoked_at + _CLOSE_GRACE_SEC
            if now < grace_ends:
                wakes.append(grace_ends)
            elif session.player.send_lock.locked():
                session.shut_down_socket()
            else:
                wakes.append(now + _CLOSE_GRACE_SEC)
        return wakes

    def _sweep(self, session: _Session) -> None:
        """Check one session. Whatever escapes the check closes that session
        (fail closed) and never ends the thread, so every other socket is
        still swept. Logged by exception class, never with the key."""
        try:
            self._check(session)
        except Exception as exc:  # noqa: BLE001 — fail closed, never a key
            session.logger.error("WebSocket credential sweep failed (%s); "
                                 "closing the session", type(exc).__name__)
            self._revoke(session)

    def _check(self, session: _Session) -> None:
        started = time.monotonic()
        if guard.ws_session_authorized(session.ws_key, session.credentialed):
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
            session.revoked_at = time.monotonic()
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
    reserved_names: frozenset[str],
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
        # Keyless means the gate has never closed, so no player name is
        # registered yet; only the reserved names, by their name_key, and
        # names that are not visible text are refused. Trim, cap, trim
        # again, as `_normalize_client_name` does, so a cap that ends on
        # spaces leaves none in the shown name.
        name = (qs.get("name", ["Anonymous"])[0] or "").strip()[:32].strip() or "Anonymous"
        if not persistence.name_is_visible_text(name):
            # A control or invisible character, or nothing to see: refused
            # as a reserved name is, and as `/register` refuses it.
            request._send_error(persistence.INVISIBLE_NAME_ERROR, 403)
            return
        if persistence.name_key(name) in reserved_names:
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
