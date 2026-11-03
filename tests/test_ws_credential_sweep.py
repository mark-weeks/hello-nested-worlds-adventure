"""An open WebSocket is re-checked on the server's schedule, not only its own.

Before the credential sweep, a socket's credential was re-checked only when a
client frame arrived. A client that only listened kept receiving every room
broadcast for up to about 72 s after its key was revoked or its player was
sanctioned (the 60 s idle timeout plus the frame deadline). Every test here
drives a real server socket; the sweep interval is shortened so the suite
stays fast.
"""
from __future__ import annotations

import datetime
import json
import logging
import struct
import threading
import time

import pytest

import persistence
from multiverse import store
from persistence import sanctions
from persistence.participants import rotate
from server import guard, protocol, websocket
from server.rooms import broadcast, get_room
from tests.test_day_one_recording import _ws_send_json
from tests.test_server_protocol import _client_frame
from tests.test_ws_credential_lifetime import (
    KEY_A,
    KEY_B,
    _join,
    _read_frame,
    _rows,
    _two_players,
    _until_type,
    _wait_rows,
)

KEY_C = "nw_" + "c" * 32
INTERVAL = 0.2
# One interval plus generous slack for a loaded machine. Without the sweep
# none of these sockets would close before the 60 s idle timeout.
CLOSE_WITHIN = 3.0
SWEEP_THREAD = "ws-credential-sweep"


@pytest.fixture()
def srv():
    from server import _Handler, _ThreadedServer
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()
    thread.join(5)


class _RevokeBeforeDiscard(websocket._CredentialSweep):
    """Holds one session's discard until the sweep has revoked it.

    Forces the order in which a racing reader and the sweep act: the reader
    has already sent (or echoed) its close frame and reached its disconnect
    path, and the sweep revokes the session before the reader lets go of it.
    """

    target: str | None = None
    held: bool | None = None

    def discard(self, session):
        if session.player.session_id == self.target:
            deadline = time.monotonic() + 5.0
            while not session.revoked and time.monotonic() < deadline:
                time.sleep(0.005)
            self.held = session.revoked
        super().discard(session)


class _RecordingSweep(websocket._CredentialSweep):
    """Signals each time the sweep has finished acting on a refusal."""

    def __init__(self):
        super().__init__()
        self.revoke_returned = threading.Event()

    def _revoke(self, session):
        try:
            super()._revoke(session)
        finally:
            self.revoke_returned.set()


@pytest.fixture()
def install_sweep(monkeypatch):
    """Install a sweep of this test's own sockets only, at a short interval.
    Every sweep installed is stopped at teardown."""
    installed = []

    def install(sweep=None, interval=INTERVAL):
        sweep = sweep or websocket._CredentialSweep()
        monkeypatch.setattr(guard, "WS_SWEEP_INTERVAL_SEC", interval)
        monkeypatch.setattr(websocket, "_SWEEP", sweep)
        installed.append(sweep)
        return sweep

    yield install
    for sweep in installed:
        sweep.stop()


@pytest.fixture()
def sweep(install_sweep):
    return install_sweep()


def _frames_until_eof(sock, timeout=CLOSE_WITHIN):
    """Every frame the server sends until it ends the TCP session."""
    sock.settimeout(timeout)
    frames = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            frames.append(_read_frame(sock))
        except ConnectionError:  # EOF (or a reset) after the last frame
            return frames
    raise AssertionError(f"server kept the socket open past {timeout}s")


def _closed_once(frames):
    """The one close frame is the last frame. Return (its code, the JSON
    messages before it)."""
    closes = [i for i, (opcode, _) in enumerate(frames) if opcode == 0x8]
    assert closes == [len(frames) - 1], frames
    payload = frames[-1][1]
    code = struct.unpack(">H", payload[:2])[0] if len(payload) >= 2 else None
    return code, [json.loads(p) for opcode, p in frames[:-1] if opcode == 0x1]


def _leaves_heard(sock, sid):
    """Ping, then return the player_leave frames for `sid` heard before the
    pong. Every earlier broadcast to this socket precedes its pong."""
    _ws_send_json(sock, {"type": "ping"})
    _, heard = _until_type(sock, "pong")
    return [m for m in heard if m.get("type") == "player_leave"
            and m["session_id"] == sid]


def _watching(sweep, n, timeout=CLOSE_WITHIN):
    """Wait until the sweep watches `n` sockets (a session registers just
    after its welcome frame); return the sweep's thread."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with sweep._cond:
            if len(sweep._sessions) == n:
                return sweep._thread
        time.sleep(0.01)
    raise AssertionError(f"the sweep never watched {n} socket(s)")


def _lookups(monkeypatch):
    """Record (thread name, key, monotonic time) for every credential read."""
    calls = []
    real = persistence.lookup_invite_key

    def counting(key):
        calls.append((threading.current_thread().name, key, time.monotonic()))
        return real(key)

    monkeypatch.setattr(persistence, "lookup_invite_key", counting)
    return calls


def _session_of(sweep, sid, timeout=CLOSE_WITHIN):
    """The sweep's session for the socket `sid`, once the sweep watches it."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with sweep._cond:
            for session in sweep._sessions:
                if session.player.session_id == sid:
                    return session
        time.sleep(0.01)
    raise AssertionError(f"the sweep never watched {sid}")


def _until(condition, what, timeout=CLOSE_WITHIN):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.005)
    raise AssertionError(f"{what} never happened within {timeout}s")


class TestListenOnlySocketIsClosed:
    def test_a_revoked_key_closes_a_socket_that_sends_nothing(self, srv, sweep):
        seed = 2801
        ada, ada_sid, bea = _two_players(srv, seed)
        persistence.revoke_invite_key(KEY_A)
        started = time.monotonic()

        code, _ = _closed_once(_frames_until_eof(ada))
        assert code == protocol.CLOSE_POLICY_VIOLATION
        assert time.monotonic() - started < CLOSE_WITHIN

        # The usual departure, once, and Bea's next line reaches Bea only.
        _ws_send_json(bea, {"type": "chat", "text": "after the close"})
        line, before = _until_type(bea, "chat")
        assert line["name"] == "Bea"
        assert [m["session_id"] for m in before
                if m.get("type") == "player_leave"] == [ada_sid]
        assert _leaves_heard(bea, ada_sid) == []
        assert len(_wait_rows(seed, "PLAYER_LEAVE", "Ada", 1)) == 1
        assert _rows(seed, "PLAYER_CHAT", "Ada") == []
        assert [r["player"] for r in _rows(seed, "PLAYER_CHAT")] == ["Bea"]
        bea.close()

    def test_no_broadcast_reaches_the_socket_once_its_check_failed(
            self, srv, sweep):
        seed = 2802
        ada, ada_sid, bea = _two_players(srv, seed)
        player = get_room(seed).players[ada_sid]
        failed = threading.Event()
        real_stop = player.stop_writer

        def stop_writer():
            real_stop()
            if threading.current_thread().name == SWEEP_THREAD:
                failed.set()

        player.stop_writer = stop_writer
        persistence.revoke_invite_key(KEY_A)
        assert failed.wait(CLOSE_WITHIN), "the sweep never refused the key"

        # Broadcast after the failed check: one through the room directly,
        # one as Bea's chat.
        broadcast(get_room(seed), {"type": "chat", "name": "World",
                                   "text": "after the check", "session_id": "w"})
        _ws_send_json(bea, {"type": "chat", "text": "also after"})
        _until_type(bea, "chat")

        code, heard = _closed_once(_frames_until_eof(ada))
        assert code == protocol.CLOSE_POLICY_VIOLATION
        assert not [m for m in heard if m.get("type") == "chat"]
        bea.close()

    @pytest.mark.parametrize("how", ["suspend", "ban"])
    def test_a_sanction_closes_a_socket_that_sends_nothing(
            self, srv, sweep, how):
        seed = 2803 if how == "suspend" else 2804
        ada, ada_sid, bea = _two_players(srv, seed)
        if how == "suspend":
            sanctions.suspend("Ada", datetime.timedelta(hours=1), "spam")
        else:
            sanctions.ban("Ada", "threats")

        code, _ = _closed_once(_frames_until_eof(ada))
        assert code == protocol.CLOSE_POLICY_VIOLATION
        leave, _ = _until_type(bea, "player_leave")
        assert leave["session_id"] == ada_sid
        assert len(_wait_rows(seed, "PLAYER_LEAVE", "Ada", 1)) == 1
        bea.close()

    def test_a_rotated_key_closes_the_socket_it_opened(self, srv, sweep):
        seed = 2805
        persistence.mint_invite_key(KEY_A, "Ada")
        ada, _ = _join(srv, seed, "x", KEY_A)
        rotate(KEY_A, KEY_C)

        code, _ = _closed_once(_frames_until_eof(ada))
        assert code == protocol.CLOSE_POLICY_VIOLATION
        assert len(_wait_rows(seed, "PLAYER_LEAVE", "Ada", 1)) == 1

    def test_a_revoked_client_holding_a_frame_open_is_closed_by_the_sweep(
            self, srv, sweep, monkeypatch):
        # A frame in progress blocks the reader, which checks only complete
        # frames. The sweep does not wait for it, or for the frame deadline.
        monkeypatch.setattr(protocol, "_FRAME_DEADLINE_SEC", 30.0)
        seed = 2806
        ada, ada_sid, bea = _two_players(srv, seed)
        frame = _client_frame(json.dumps({"type": "chat", "text": "x" * 40}).encode())
        ada.sendall(frame[:3])
        persistence.revoke_invite_key(KEY_A)

        code, _ = _closed_once(_frames_until_eof(ada))
        assert code == protocol.CLOSE_POLICY_VIOLATION  # not the deadline's 1002
        leave, _ = _until_type(bea, "player_leave")
        assert leave["session_id"] == ada_sid
        assert _rows(seed, "PLAYER_CHAT") == []
        bea.close()

    def test_a_failing_read_closes_the_socket_and_logs_no_key(
            self, srv, sweep, monkeypatch, caplog):
        caplog.set_level(logging.INFO)
        seed = 2807
        persistence.mint_invite_key(KEY_A, "Ada")
        ada, _ = _join(srv, seed, "x", KEY_A)

        def broken(_key):
            raise persistence.sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(persistence, "lookup_invite_key", broken)
        code, _ = _closed_once(_frames_until_eof(ada))
        assert code == protocol.CLOSE_POLICY_VIOLATION
        assert len(_wait_rows(seed, "PLAYER_LEAVE", "Ada", 1)) == 1
        logged = "\n".join(f"{r.getMessage()} {r.args!r}" for r in caplog.records)
        assert "OperationalError" in logged
        assert KEY_A not in logged and guard.credential_identity(KEY_A) not in logged

    def test_the_sweep_needs_no_room_lock_to_close_a_socket(self, srv, sweep):
        seed = 2808
        persistence.mint_invite_key(KEY_A, "Ada")
        ada, _ = _join(srv, seed, "x", KEY_A)
        room = get_room(seed)
        with room.lock:
            persistence.revoke_invite_key(KEY_A)
            ada.settimeout(CLOSE_WITHIN)
            opcode, payload = _read_frame(ada)
            while opcode != 0x8:
                opcode, payload = _read_frame(ada)
            assert struct.unpack(">H", payload[:2])[0] == 1008
            # The departure itself waits for the room.
            assert _rows(seed, "PLAYER_LEAVE", "Ada") == []
        assert len(_wait_rows(seed, "PLAYER_LEAVE", "Ada", 1)) == 1


class TestKeylessSocket:
    @pytest.mark.parametrize("issue", ["mint", "invite"])
    def test_a_quiet_keyless_socket_closes_once_the_first_credential_exists(
            self, srv, sweep, issue):
        seed = 2811 if issue == "mint" else 2812
        loner, _ = _join(srv, seed, "Loner")
        # The gate is open: several sweeps pass and the socket still plays.
        time.sleep(INTERVAL * 4)
        _ws_send_json(loner, {"type": "ping"})
        _until_type(loner, "pong")

        if issue == "mint":
            persistence.mint_invite_key(KEY_A, "Ada")
        else:
            persistence.create_registration_token("nwr_first")
        code, _ = _closed_once(_frames_until_eof(loner))
        assert code == protocol.CLOSE_POLICY_VIOLATION
        assert len(_wait_rows(seed, "PLAYER_LEAVE", "Loner", 1)) == 1


class TestLiveKeyAndCost:
    def test_a_live_key_stays_open_at_one_read_per_interval(
            self, srv, sweep, monkeypatch):
        seed = 2821
        ada, _, bea = _two_players(srv, seed)
        reads = _lookups(monkeypatch)
        time.sleep(INTERVAL * 5)

        # Still subscribed: Bea's line arrives, and Ada's ping is answered.
        _ws_send_json(bea, {"type": "chat", "text": "still there?"})
        line, _ = _until_type(ada, "chat")
        assert line["text"] == "still there?"
        _ws_send_json(ada, {"type": "ping"})
        _until_type(ada, "pong")

        swept = [t for name, key, t in reads
                 if name == SWEEP_THREAD and key == KEY_A]
        assert len(swept) >= 2, reads
        # One read per interval; a quarter of it is slack for thread
        # scheduling between the sweep's clock and this recorder's.
        gaps = [b - a for a, b in zip(swept, swept[1:])]
        assert min(gaps) >= INTERVAL * 0.75, gaps
        ada.close()
        bea.close()

    def test_broadcasts_cost_no_credential_reads(
            self, srv, install_sweep, monkeypatch):
        install_sweep(interval=0.5)
        seed = 2822
        persistence.mint_invite_key(KEY_A, "Ada")
        ada, _ = _join(srv, seed, "x", KEY_A)
        reads = _lookups(monkeypatch)

        started = time.monotonic()
        for i in range(40):
            broadcast(get_room(seed), {"type": "chat", "name": "World",
                                       "text": f"line {i}", "session_id": "w"})
        heard = 0
        ada.settimeout(CLOSE_WITHIN)
        while heard < 40:
            opcode, payload = _read_frame(ada)
            if opcode == 0x1 and json.loads(payload).get("type") == "chat":
                heard += 1
        window = time.monotonic() - started

        during = [t for _, key, t in reads if key == KEY_A and t >= started]
        assert len(during) <= window / 0.5 + 1, (len(during), window)
        ada.close()


class TestOneCloseOneLeave:
    """The reader loop and the sweep can both find a session unauthorized at
    the same moment. The session still sends one close frame and leaves
    once."""

    def test_a_failing_frame_and_a_failing_sweep_at_once(
            self, srv, install_sweep, monkeypatch):
        sweep = install_sweep(_RevokeBeforeDiscard())
        seed = 2831
        ada, ada_sid, bea = _two_players(srv, seed)
        sweep.target = ada_sid
        together = threading.Barrier(2, timeout=5.0)
        callers = []
        real = guard.ws_session_authorized

        def refused_together(ws_key, credentialed):
            if ws_key != KEY_A:
                return real(ws_key, credentialed)
            callers.append(threading.current_thread().name)
            together.wait()
            return False

        monkeypatch.setattr(guard, "ws_session_authorized", refused_together)
        sent = []
        real_close = websocket.send_close

        def recording(sock, code, send_lock=None):
            sent.append(code)
            real_close(sock, code, send_lock=send_lock)

        monkeypatch.setattr(websocket, "send_close", recording)

        _ws_send_json(ada, {"type": "ping"})
        code, heard = _closed_once(_frames_until_eof(ada))
        assert code == protocol.CLOSE_POLICY_VIOLATION
        assert not [m for m in heard if m.get("type") == "pong"]
        assert callers.count(SWEEP_THREAD) == 1 and len(callers) == 2
        assert sweep.held is True  # the sweep revoked before the reader let go
        assert sent == [protocol.CLOSE_POLICY_VIOLATION]
        assert len(_wait_rows(seed, "PLAYER_LEAVE", "Ada", 1)) == 1
        leave, _ = _until_type(bea, "player_leave")
        assert leave["session_id"] == ada_sid
        assert _leaves_heard(bea, ada_sid) == []
        assert len(_rows(seed, "PLAYER_LEAVE", "Ada")) == 1
        bea.close()

    def test_a_peer_close_while_the_sweep_refuses(
            self, srv, install_sweep, monkeypatch):
        sweep = install_sweep(_RevokeBeforeDiscard())
        seed = 2832
        ada, ada_sid, bea = _two_players(srv, seed)
        sweep.target = ada_sid
        reading, refuse = threading.Event(), threading.Event()
        real = guard.ws_session_authorized

        def held_then_refused(ws_key, credentialed):
            if ws_key != KEY_A or threading.current_thread().name != SWEEP_THREAD:
                return real(ws_key, credentialed)
            reading.set()
            assert refuse.wait(5.0)
            return False

        monkeypatch.setattr(guard, "ws_session_authorized", held_then_refused)
        assert reading.wait(CLOSE_WITHIN), "the sweep never read Ada's key"
        ada.sendall(_client_frame(struct.pack(">H", 1000), opcode=0x8))
        ada.settimeout(CLOSE_WITHIN)
        assert _read_frame(ada) == (0x8, struct.pack(">H", 1000))  # the echo
        refuse.set()

        # Revoked while the reader was leaving: no second close frame.
        assert _frames_until_eof(ada) == []
        assert sweep.held is True
        assert len(_wait_rows(seed, "PLAYER_LEAVE", "Ada", 1)) == 1
        leave, _ = _until_type(bea, "player_leave")
        assert leave["session_id"] == ada_sid
        assert _leaves_heard(bea, ada_sid) == []
        bea.close()


class TestSweepVerdictEndsTheSession:
    """Once the sweep refuses a session, the session is over, whatever the
    reader does next, and the sweep touches nothing once the reader has let
    go of the session."""

    @pytest.mark.parametrize("queued", ["move", "malformed"])
    def test_frames_queued_behind_a_failed_check_are_not_acted_on(
            self, srv, sweep, monkeypatch, queued):
        # The sweep's read fails (fail closed) while the reader's own reads
        # still pass, and the client has a frame queued behind one the
        # reader is still checking. A queued move is neither written nor
        # broadcast, and a queued malformed frame does not turn the policy
        # close into a protocol error (1002).
        seed = 2814 if queued == "move" else 2815
        ada, ada_sid, bea = _two_players(srv, seed)
        session = _session_of(sweep, ada_sid)
        reader_held, release_reader = threading.Event(), threading.Event()
        sweep_fails = threading.Event()
        real = persistence.lookup_invite_key

        def lookup(key):
            if key == KEY_A:
                if threading.current_thread().name == SWEEP_THREAD:
                    if sweep_fails.is_set():
                        raise persistence.sqlite3.OperationalError("disk I/O error")
                elif not release_reader.is_set():
                    reader_held.set()
                    assert release_reader.wait(5.0)
            return real(key)

        monkeypatch.setattr(persistence, "lookup_invite_key", lookup)
        _ws_send_json(ada, {"type": "ping"})
        assert reader_held.wait(CLOSE_WITHIN), "the reader never checked the ping"
        if queued == "move":
            _ws_send_json(ada, {"type": "move", "node": store.root_name(seed)})
        else:
            ada.sendall(bytes([0x81, 0x02]) + b"{}")  # unmasked: a protocol error
        sweep_fails.set()
        _until(lambda: session.revoked, "the sweep's refusal")
        release_reader.set()

        code, heard = _closed_once(_frames_until_eof(ada))
        assert code == protocol.CLOSE_POLICY_VIOLATION
        assert not [m for m in heard if m.get("type") == "pong"]
        leave, before = _until_type(bea, "player_leave")
        assert leave["session_id"] == ada_sid
        assert not [m for m in before if m.get("type") == "player_move"]
        assert _rows(seed, "PLAYER_MOVE", "Ada") == []
        assert len(_wait_rows(seed, "PLAYER_LEAVE", "Ada", 1)) == 1
        bea.close()

    @pytest.mark.parametrize("action,refusal", [
        ("move", "revoked"), ("chat", "revoked"), ("move", "read_error")])
    def test_a_refusal_during_the_actions_own_check_wins(
            self, srv, sweep, monkeypatch, action, refusal):
        # The reader is inside the last fresh read before a move or chat is
        # written (for chat, the one after screening) when the sweep refuses
        # the session: its own read already sees the key revoked, or fails
        # closed on a read error. The reader's read began earlier and
        # passes; the sweep's verdict must still win, so nothing is written
        # or broadcast and the session ends with the one policy close.
        seed = {("move", "revoked"): 2816, ("chat", "revoked"): 2817,
                ("move", "read_error"): 2818}[(action, refusal)]
        # Throttled re-checks never read again after the first frame, so
        # the reader's next read is the action's own fresh check.
        monkeypatch.setattr(guard, "WS_REAUTH_INTERVAL_SEC", 3600.0)
        ada, ada_sid, bea = _two_players(srv, seed)
        session = _session_of(sweep, ada_sid)
        _ws_send_json(ada, {"type": "ping"})  # the one throttled read
        _until_type(ada, "pong")
        armed, reader_held = threading.Event(), threading.Event()
        release_reader, sweep_refuses = threading.Event(), threading.Event()
        hold_read = 1 if action == "move" else 2  # chat: before and after screening
        reader_reads = []
        real = persistence.lookup_invite_key

        def lookup(key):
            if key == KEY_A:
                if threading.current_thread().name == SWEEP_THREAD:
                    if sweep_refuses.is_set():
                        if refusal == "read_error":
                            raise persistence.sqlite3.OperationalError(
                                "disk I/O error")
                        return None  # the sweep's read sees it revoked
                elif armed.is_set():
                    reader_reads.append(key)
                    if len(reader_reads) == hold_read:
                        reader_held.set()
                        assert release_reader.wait(5.0)
            return real(key)

        monkeypatch.setattr(persistence, "lookup_invite_key", lookup)
        armed.set()
        if action == "move":
            _ws_send_json(ada, {"type": "move", "node": store.root_name(seed)})
        else:
            _ws_send_json(ada, {"type": "chat", "text": "one last word"})
        assert reader_held.wait(CLOSE_WITHIN), "the reader never ran its fresh check"
        sweep_refuses.set()
        _until(lambda: session.revoked, "the sweep's refusal")
        release_reader.set()

        code, _ = _closed_once(_frames_until_eof(ada))
        assert code == protocol.CLOSE_POLICY_VIOLATION
        leave, before = _until_type(bea, "player_leave")
        assert leave["session_id"] == ada_sid
        assert not [m for m in before
                    if m.get("type") in ("player_move", "chat")]
        assert _rows(seed, "PLAYER_MOVE", "Ada") == []
        assert _rows(seed, "PLAYER_CHAT", "Ada") == []
        assert len(_wait_rows(seed, "PLAYER_LEAVE", "Ada", 1)) == 1
        bea.close()

    def test_a_refusal_after_the_reader_let_go_touches_nothing(
            self, srv, install_sweep, monkeypatch, caplog):
        # The sweep is reading when the client closes, and its refusal lands
        # after the reader has left. The sweep does not act on a session its
        # reader let go of: no shutdown of a socket that may be closed and
        # its descriptor reused, and no second account of the departure.
        caplog.set_level(logging.INFO)
        sweep = install_sweep(_RecordingSweep())
        seed = 2816
        ada, ada_sid, bea = _two_players(srv, seed)
        session = _session_of(sweep, ada_sid)
        reading, refuse = threading.Event(), threading.Event()
        real = guard.ws_session_authorized

        def held_then_refused(ws_key, credentialed):
            if ws_key != KEY_A or threading.current_thread().name != SWEEP_THREAD:
                return real(ws_key, credentialed)
            reading.set()
            assert refuse.wait(5.0)
            return False

        monkeypatch.setattr(guard, "ws_session_authorized", held_then_refused)
        assert reading.wait(CLOSE_WITHIN), "the sweep never read Ada's key"
        ada.sendall(_client_frame(struct.pack(">H", 1000), opcode=0x8))
        assert _closed_once(_frames_until_eof(ada))[0] == 1000  # Ada's echo
        _until(lambda: session not in sweep._sessions, "the reader letting go")
        refuse.set()
        assert sweep.revoke_returned.wait(CLOSE_WITHIN)

        assert session.revoked is False
        assert not [r for r in caplog.records
                    if r.threadName == SWEEP_THREAD and ada_sid in r.getMessage()]
        assert len(_wait_rows(seed, "PLAYER_LEAVE", "Ada", 1)) == 1
        bea.close()

    def test_an_error_escaping_the_check_closes_and_the_sweep_goes_on(
            self, srv, sweep, monkeypatch, caplog):
        # guard.ws_session_authorized catches its own read errors today; the
        # sweep does not depend on that. Anything its check raises ends that
        # session, is logged by exception class and never with the key, and
        # leaves the same thread sweeping every other socket.
        caplog.set_level(logging.INFO)
        seed = 2817
        ada, _, bea = _two_players(srv, seed)
        thread = _watching(sweep, 2)
        real = guard.ws_session_authorized

        def raising(ws_key, credentialed):
            if ws_key == KEY_A and threading.current_thread().name == SWEEP_THREAD:
                raise RuntimeError(f"no answer for {ws_key}")
            return real(ws_key, credentialed)

        monkeypatch.setattr(guard, "ws_session_authorized", raising)
        assert _closed_once(_frames_until_eof(ada))[0] == 1008
        assert len(_wait_rows(seed, "PLAYER_LEAVE", "Ada", 1)) == 1
        logged = "\n".join(f"{r.getMessage()} {r.args!r}" for r in caplog.records)
        assert "RuntimeError" in logged
        assert KEY_A not in logged and guard.credential_identity(KEY_A) not in logged

        time.sleep(INTERVAL * 3)  # Bea's live key passes several sweeps
        assert thread.is_alive() and sweep._thread is thread
        persistence.revoke_invite_key(KEY_B)
        assert _closed_once(_frames_until_eof(bea))[0] == 1008


class TestSweepThread:
    @staticmethod
    def _peer_close(sock):
        sock.sendall(_client_frame(struct.pack(">H", 1000), opcode=0x8))
        _frames_until_eof(sock)

    def test_one_thread_starts_with_the_first_socket_and_ends_with_the_last(
            self, srv, sweep):
        assert sweep._thread is None
        persistence.mint_invite_key(KEY_A, "Ada")
        persistence.mint_invite_key(KEY_B, "Bea")
        ada, _ = _join(srv, 2841, "x", KEY_A)
        thread = _watching(sweep, 1)
        assert thread is not None and thread.is_alive()
        assert thread.name == SWEEP_THREAD
        bea, _ = _join(srv, 2841, "x", KEY_B)
        assert _watching(sweep, 2) is thread  # one thread for every socket

        self._peer_close(ada)
        assert thread.is_alive()  # Bea is still open
        self._peer_close(bea)
        thread.join(CLOSE_WITHIN)
        assert not thread.is_alive() and sweep._thread is None

        # The next socket starts a new thread that still sweeps.
        again, _ = _join(srv, 2841, "x", KEY_A)
        restarted = _watching(sweep, 1)
        assert restarted is not None and restarted is not thread
        persistence.revoke_invite_key(KEY_A)
        assert _closed_once(_frames_until_eof(again))[0] == 1008

    def test_a_socket_leaves_the_sweep_it_joined(self, srv, install_sweep):
        # Tests replace the module's sweep between sockets. A socket still
        # leaves the sweep that watches it, so no sweep keeps a session, or
        # a thread, for a socket that has gone.
        first = install_sweep()
        persistence.mint_invite_key(KEY_A, "Ada")
        ada, _ = _join(srv, 2843, "x", KEY_A)
        thread = _watching(first, 1)
        install_sweep()  # another sweep takes the module's place
        self._peer_close(ada)
        thread.join(CLOSE_WITHIN)
        assert not thread.is_alive()
        assert first._sessions == set() and first._thread is None

    def test_server_shutdown_stops_the_sweep(self, srv, sweep, monkeypatch):
        import server
        from consciousness import model_check
        from server import heartbeat

        persistence.mint_invite_key(KEY_A, "Ada")
        ada, _ = _join(srv, 2842, "x", KEY_A)
        thread = _watching(sweep, 1)
        assert thread is not None and thread.is_alive()

        class StopsAtOnce(server._ThreadedServer):
            def serve_forever(self, poll_interval=0.5):
                raise KeyboardInterrupt

        monkeypatch.setattr(server, "_ThreadedServer", StopsAtOnce)
        monkeypatch.setattr(server.observability, "setup", lambda: None)
        monkeypatch.setattr(server.guard, "canonical_seed", lambda: None)
        monkeypatch.setattr(model_check, "enforce_model_configuration", lambda: None)
        monkeypatch.setattr(server, "model_banner", lambda: [])
        monkeypatch.setattr(heartbeat, "enabled", lambda: False)
        monkeypatch.setattr(heartbeat, "pump_enabled", lambda: False)
        monkeypatch.setattr(server.signal, "signal", lambda *args: None)
        server.run(host="127.0.0.1", port=0)

        thread.join(CLOSE_WITHIN)
        assert not thread.is_alive() and sweep._thread is None
        ada.close()
