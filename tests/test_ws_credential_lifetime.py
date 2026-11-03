"""An open WebSocket lives only as long as its authorization.

The upgrade is authorized once. Before this suite's fix, a revoked player's
open socket kept chatting world-wide and moving for as long as the client
pinged, a keyless socket opened before the first mint kept playing after the
gate closed, and up to eight sockets on one credential each had their own
chat and move allowance. Every test here drives a real server socket.
"""
from __future__ import annotations

import base64
import json
import os
import re
import socket
import struct
import threading
import time
import urllib.error
import urllib.request

import pytest

import persistence
from multiverse.generator import generate_node_hierarchy
from server import guard, protocol
from server.rooms import get_room
from tests.test_day_one_recording import _ws_connect, _ws_send_json
from tests.test_moderation import _read_ws_json_until, _recv_exact
from tests.test_server_protocol import _client_frame

KEY_A = "nw_" + "a" * 32
KEY_B = "nw_" + "b" * 32


@pytest.fixture()
def srv():
    from server import _Handler, _ThreadedServer
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield port
    server.shutdown()


def _read_frame(sock):
    """One server frame: (opcode, payload). Server frames are unmasked."""
    hdr = _recv_exact(sock, 2)
    length = hdr[1] & 0x7F
    if length == 126:
        length = struct.unpack(">H", _recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", _recv_exact(sock, 8))[0]
    return hdr[0] & 0x0F, _recv_exact(sock, length)


def _until_close(sock, timeout=4.0):
    """Read frames until a close frame. Return (status code, JSON messages
    received before it). Fails if the server never closes."""
    sock.settimeout(timeout)
    seen = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        opcode, payload = _read_frame(sock)
        if opcode == 0x8:
            code = struct.unpack(">H", payload[:2])[0] if len(payload) >= 2 else None
            return code, seen
        if opcode == 0x1:
            seen.append(json.loads(payload))
    raise AssertionError(f"no close frame within {timeout}s")


def _until_eof(sock, timeout=4.0):
    """The server ends the TCP session after its close frame."""
    sock.settimeout(timeout)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if sock.recv(4096) == b"":
                return
        except ConnectionResetError:
            return
    raise AssertionError("server kept the socket open after closing")


def _until_type(sock, msg_type, timeout=4.0):
    """Read text frames until one has `msg_type`; return (it, all before)."""
    sock.settimeout(timeout)
    seen = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        opcode, payload = _read_frame(sock)
        if opcode != 0x1:
            continue
        msg = json.loads(payload)
        if msg.get("type") == msg_type:
            return msg, seen
        seen.append(msg)
    raise AssertionError(f"no {msg_type!r} frame within {timeout}s")


def _join(port, seed, name, key=None):
    sock, status = _ws_connect(port, seed, name, invite_key=key)
    assert b"101" in status, status
    welcome = _read_ws_json_until(sock, "welcome")
    return sock, welcome["session_id"]


def _rows(seed, kind, player=None):
    return [r for r in persistence.get_mutations(seed, limit=1000)
            if r["type"] == kind and (player is None or r["player"] == player)]


def _wait_rows(seed, kind, player, n, timeout=4.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rows = _rows(seed, kind, player)
        if len(rows) >= n:
            return rows
        time.sleep(0.02)
    return _rows(seed, kind, player)


def _two_players(port, seed):
    """Ada on key A and Bea on key B in one room; Bea has seen Ada join."""
    persistence.mint_invite_key(KEY_A, "Ada")
    persistence.mint_invite_key(KEY_B, "Bea")
    bea, _ = _join(port, seed, "x", KEY_B)
    ada, ada_sid = _join(port, seed, "x", KEY_A)
    _until_type(bea, "player_join")
    return ada, ada_sid, bea


class TestRevokedCredentialLosesItsSocket:
    def test_revoked_chat_closes_1008_writes_nothing_and_reaches_nobody(self, srv):
        seed = 2601
        ada, ada_sid, bea = _two_players(srv, seed)
        assert persistence.revoke_invite_key(KEY_A) is True

        _ws_send_json(ada, {"type": "chat", "text": "still here?"})
        code, _ = _until_close(ada)
        assert code == 1008
        _until_eof(ada)

        # Bea hears the departure once and never the line.
        leave, before = _until_type(bea, "player_leave")
        assert leave["session_id"] == ada_sid
        assert not [m for m in before if m.get("type") == "chat"]
        assert _rows(seed, "PLAYER_CHAT") == []
        # The normal disconnect path ran exactly once.
        assert len(_wait_rows(seed, "PLAYER_LEAVE", "Ada", 1)) == 1

        # Control: Bea's live key still speaks, and her line is the first
        # chat she receives (nothing of Ada's was queued ahead of it).
        _ws_send_json(bea, {"type": "chat", "text": "hello"})
        echoed, _ = _until_type(bea, "chat")
        assert echoed["name"] == "Bea" and echoed["text"] == "hello"
        assert [r["player"] for r in _wait_rows(seed, "PLAYER_CHAT", None, 1)] == ["Bea"]
        assert len(_rows(seed, "PLAYER_LEAVE", "Ada")) == 1
        bea.close()

    def test_revoked_move_closes_1008_and_leaves_no_trace(self, srv):
        seed = 2602
        target = generate_node_hierarchy(seed=seed, max_depth=2).children[0]
        ada, ada_sid, bea = _two_players(srv, seed)
        persistence.revoke_invite_key(KEY_A)

        _ws_send_json(ada, {"type": "move", "node": target.name})
        code, _ = _until_close(ada)
        assert code == 1008
        _until_eof(ada)

        leave, before = _until_type(bea, "player_leave")
        assert leave["session_id"] == ada_sid
        assert not [m for m in before if m.get("type") == "player_move"]
        assert _rows(seed, "PLAYER_MOVE") == []
        # Ada never arrived, so she departs from where she stood.
        leaves = _wait_rows(seed, "PLAYER_LEAVE", "Ada", 1)
        assert [r["node"] for r in leaves] != [target.name]

        # Control: the same move is open to a live key.
        _ws_send_json(bea, {"type": "move", "node": target.name})
        assert [r["player"] for r in _wait_rows(seed, "PLAYER_MOVE", None, 1)] == ["Bea"]
        bea.close()

    def test_revoking_the_only_key_closes_its_open_socket(self, srv):
        seed = 2603
        persistence.mint_invite_key(KEY_A, "Ada")
        ada, _ = _join(srv, seed, "x", KEY_A)
        persistence.revoke_invite_key(KEY_A)
        assert persistence.list_invite_keys() == []

        _ws_send_json(ada, {"type": "chat", "text": "anyone?"})
        code, _ = _until_close(ada)
        assert code == 1008
        _until_eof(ada)
        assert _rows(seed, "PLAYER_CHAT") == []
        # The world did not reopen: neither the old key nor no key gets back.
        for key in (KEY_A, None):
            sock, status = _ws_connect(srv, seed, "Ada", invite_key=key)
            sock.close()
            assert b"403" in status, (key, status)

    def test_a_ping_after_revocation_closes_instead_of_ponging(self, srv):
        seed = 2604
        persistence.mint_invite_key(KEY_A, "Ada")
        ada, _ = _join(srv, seed, "x", KEY_A)
        _ws_send_json(ada, {"type": "ping"})
        _until_type(ada, "pong")

        persistence.revoke_invite_key(KEY_A)
        _ws_send_json(ada, {"type": "ping"})
        code, seen = _until_close(ada)
        assert code == 1008
        assert not [m for m in seen if m.get("type") == "pong"]
        _until_eof(ada)

    def test_a_rotated_key_closes_the_socket_it_opened(self, srv):
        from persistence.participants import rotate
        seed = 2605
        persistence.mint_invite_key(KEY_A, "Ada")
        ada, _ = _join(srv, seed, "x", KEY_A)
        rotate(KEY_A, "nw_" + "c" * 32)

        _ws_send_json(ada, {"type": "chat", "text": "old key"})
        assert _until_close(ada)[0] == 1008
        assert _rows(seed, "PLAYER_CHAT") == []

    # Frames that write nothing still reset the 60 s idle timer, so a client
    # that sends only these after revocation would otherwise stay subscribed
    # to every room broadcast (chat text, moves, joins) indefinitely.
    _SILENT_FRAMES = {
        "protocol-ping": _client_frame(b"hb", opcode=0x9),
        "protocol-pong": _client_frame(b"", opcode=0xA),
        "unknown-type": _client_frame(b'{"type": "wave"}'),
        "invalid-json": _client_frame(b"{not json"),
        "non-object-json": _client_frame(b"[1, 2]"),
        "empty-text": _client_frame(b""),
    }

    @pytest.mark.parametrize("kind", sorted(_SILENT_FRAMES))
    def test_a_revoked_socket_cannot_stay_subscribed_on_frames_that_write_nothing(
            self, srv, kind):
        seed = 2640 + sorted(self._SILENT_FRAMES).index(kind)
        ada, ada_sid, bea = _two_players(srv, seed)
        persistence.revoke_invite_key(KEY_A)

        ada.sendall(self._SILENT_FRAMES[kind])
        code, seen = _until_close(ada)
        assert code == 1008, kind
        _until_eof(ada)
        assert not [m for m in seen if m.get("type") == "chat"]

        # The usual single departure, and Bea's later line reaches no one
        # but Bea.
        leave, _ = _until_type(bea, "player_leave")
        assert leave["session_id"] == ada_sid
        assert len(_wait_rows(seed, "PLAYER_LEAVE", "Ada", 1)) == 1
        _ws_send_json(bea, {"type": "chat", "text": "after"})
        _until_type(bea, "chat")
        bea.close()

    def test_a_revoked_socket_with_a_spent_chat_bucket_still_closes(
            self, srv, monkeypatch):
        # A dropped (rate-limited) frame writes nothing, but it must not be a
        # way to keep a revoked session alive and listening either. A
        # near-zero refill keeps the bucket spent for the whole test.
        monkeypatch.setattr(guard, "WS_CHAT_BUCKETS",
                            guard.CredentialBuckets(0.0001, guard.WS_CHAT_BURST))
        seed = 2649
        ada, _, bea = _two_players(srv, seed)
        for i in range(guard.WS_CHAT_BURST):
            _ws_send_json(ada, {"type": "chat", "text": f"line {i}"})
        _ws_send_json(ada, {"type": "ping"})
        _until_type(ada, "pong")
        assert len(_wait_rows(seed, "PLAYER_CHAT", "Ada", guard.WS_CHAT_BURST)) \
            == guard.WS_CHAT_BURST

        persistence.revoke_invite_key(KEY_A)
        _ws_send_json(ada, {"type": "chat", "text": "over the limit"})
        assert _until_close(ada)[0] == 1008
        _until_eof(ada)
        assert len(_rows(seed, "PLAYER_CHAT", "Ada")) == guard.WS_CHAT_BURST
        bea.close()

    def test_a_failing_credential_lookup_closes_the_socket(self, srv, monkeypatch):
        seed = 2606
        persistence.mint_invite_key(KEY_A, "Ada")
        ada, _ = _join(srv, seed, "x", KEY_A)

        def broken(_key):
            raise persistence.sqlite3.OperationalError("database is locked")
        monkeypatch.setattr(persistence, "lookup_invite_key", broken)
        _ws_send_json(ada, {"type": "chat", "text": "during an outage"})
        assert _until_close(ada)[0] == 1008
        assert _rows(seed, "PLAYER_CHAT") == []


class TestKeylessSocketClosesWhenTheGateCloses:
    def test_keyless_socket_closes_on_its_next_frame_after_the_first_mint(self, srv):
        seed = 2611
        loner, _ = _join(srv, seed, "Loner")
        _ws_send_json(loner, {"type": "chat", "text": "open world"})
        assert len(_wait_rows(seed, "PLAYER_CHAT", "Loner", 1)) == 1

        persistence.mint_invite_key(KEY_A, "Ada")
        _ws_send_json(loner, {"type": "chat", "text": "still open?"})
        code, _ = _until_close(loner)
        assert code == 1008
        _until_eof(loner)
        assert [r["data"]["text"] for r in _rows(seed, "PLAYER_CHAT")] == ["open world"]
        assert len(_wait_rows(seed, "PLAYER_LEAVE", "Loner", 1)) == 1

    def test_keyless_socket_closes_after_the_first_registration_invite(self, srv):
        seed = 2612
        loner, _ = _join(srv, seed, "Loner")
        persistence.create_registration_token("nwr_first")
        _ws_send_json(loner, {"type": "ping"})
        code, seen = _until_close(loner)
        assert code == 1008
        assert not [m for m in seen if m.get("type") == "pong"]

    def test_keyless_socket_keeps_playing_while_nothing_was_ever_issued(self, srv):
        seed = 2613
        loner, _ = _join(srv, seed, "Loner")
        for text in ("one", "two"):
            _ws_send_json(loner, {"type": "chat", "text": text})
        _ws_send_json(loner, {"type": "ping"})
        _until_type(loner, "pong")
        assert len(_wait_rows(seed, "PLAYER_CHAT", "Loner", 2)) == 2
        loner.close()


class TestPerCredentialRateLimits:
    def test_two_sockets_on_one_key_share_one_chat_burst(self, srv):
        seed = 2621
        persistence.mint_invite_key(KEY_A, "Ada")
        persistence.mint_invite_key(KEY_B, "Bea")
        first, _ = _join(srv, seed, "x", KEY_A)
        second, _ = _join(srv, seed, "x", KEY_A)
        bea, _ = _join(srv, seed, "x", KEY_B)

        burst = guard.WS_CHAT_BURST
        started = time.monotonic()
        for i in range(burst + 3):
            _ws_send_json(first, {"type": "chat", "text": f"first {i}"})
            _ws_send_json(second, {"type": "chat", "text": f"second {i}"})
        # A pong is sent only after every earlier frame on that socket was
        # handled, so both floods are fully processed once both arrive.
        for sock in (first, second):
            _ws_send_json(sock, {"type": "ping"})
            _until_type(sock, "pong")
        elapsed = time.monotonic() - started
        # The bucket refills at WS_CHAT_RATE; allow what a slow run earned.
        ceiling = burst + int(elapsed * guard.WS_CHAT_RATE)

        ada_rows = _rows(seed, "PLAYER_CHAT", "Ada")
        assert burst <= len(ada_rows) <= ceiling, (len(ada_rows), elapsed)

        # Another key's allowance is untouched by Ada's flood.
        for i in range(burst):
            _ws_send_json(bea, {"type": "chat", "text": f"bea {i}"})
        _ws_send_json(bea, {"type": "ping"})
        _, heard = _until_type(bea, "pong")
        assert len(_wait_rows(seed, "PLAYER_CHAT", "Bea", burst)) == burst
        # Bea's queue is FIFO: every chat broadcast from Ada precedes her pong.
        ada_heard = [m for m in heard if m.get("type") == "chat" and m["name"] == "Ada"]
        assert len(ada_heard) == len(ada_rows)
        for sock in (first, second, bea):
            sock.close()

    def test_keyless_dev_sockets_keep_their_own_buckets(self, srv):
        seed = 2622
        one, _ = _join(srv, seed, "Uno")
        two, _ = _join(srv, seed, "Dos")
        burst = guard.WS_CHAT_BURST
        for i in range(burst):
            _ws_send_json(one, {"type": "chat", "text": f"uno {i}"})
            _ws_send_json(two, {"type": "chat", "text": f"dos {i}"})
        for sock in (one, two):
            _ws_send_json(sock, {"type": "ping"})
            _until_type(sock, "pong")
        assert len(_rows(seed, "PLAYER_CHAT", "Uno")) == burst
        assert len(_rows(seed, "PLAYER_CHAT", "Dos")) == burst
        assert len(guard.WS_CHAT_BUCKETS) == 0
        one.close()
        two.close()

    def test_registry_is_keyed_by_digest_never_the_plaintext(self, srv):
        seed = 2623
        persistence.mint_invite_key(KEY_A, "Ada")
        ada, _ = _join(srv, seed, "x", KEY_A)
        _ws_send_json(ada, {"type": "chat", "text": "hi"})
        _ws_send_json(ada, {"type": "ping"})
        _until_type(ada, "pong")
        keys = list(guard.WS_CHAT_BUCKETS._buckets)
        assert keys == [guard.credential_identity(KEY_A)]
        assert KEY_A not in keys and not any(KEY_A in k for k in keys)
        ada.close()


class TestCredentialBucketsRegistry:
    def test_concurrent_sockets_cannot_overdraw_a_shared_bucket(self, monkeypatch):
        class ContendedBucket(guard.TokenBucket):
            # Widens allow()'s read-modify-write window, so without the
            # registry's lock concurrent sockets read the same balance and
            # all spend it.
            def allow(self):
                tokens = self.tokens
                time.sleep(0.002)
                if tokens >= 1.0:
                    self.tokens = tokens - 1.0
                    return True
                return False

        monkeypatch.setattr(guard, "TokenBucket", ContendedBucket)
        buckets = guard.CredentialBuckets(rate=0.001, burst=5)
        allowed = []
        lock = threading.Lock()
        start = threading.Barrier(8)

        def socket_thread():
            start.wait()
            for _ in range(20):
                ok = buckets.allow("ident")
                with lock:
                    allowed.append(ok)

        threads = [threading.Thread(target=socket_thread) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sum(allowed) == 5

    def test_registry_stays_bounded_without_forgiving_a_spent_bucket(self):
        buckets = guard.CredentialBuckets(rate=0.001, burst=2, max_entries=3)
        assert buckets.allow("spent") and buckets.allow("spent")
        assert not buckets.allow("spent")
        for ident in ("b", "c"):
            buckets.allow(ident)
        assert len(buckets) == 3
        # A fourth identity forces eviction: none of the buckets refilled, so
        # the least recently used goes. "spent" is touched again first.
        assert not buckets.allow("spent")
        buckets.allow("d")
        assert len(buckets) == 3
        assert set(buckets._buckets) == {"spent", "c", "d"}
        assert not buckets.allow("spent")

    def test_refilled_buckets_are_evicted_before_live_ones(self):
        buckets = guard.CredentialBuckets(rate=0.01, burst=2, max_entries=2)
        buckets.allow("idle")
        # Last seen long enough ago to have refilled to its burst (200 s).
        buckets._buckets["idle"].last -= 1000.0
        buckets.allow("busy")
        buckets.allow("busy")
        # Make "idle" the most recently used, so LRU order alone would keep
        # it; only the refill rule can explain its eviction.
        buckets._buckets.move_to_end("idle")
        buckets.allow("new")    # over the bound: the refilled bucket goes
        assert set(buckets._buckets) == {"busy", "new"}
        assert not buckets.allow("busy")


class TestRevocationMidMessage:
    """Revocation lands while a message is still in flight: inside an open
    fragmented message (which `ws_recv` reads without returning), or while
    a chat line waits on moderation screening."""

    @staticmethod
    def _until_close_raw(sock, timeout=4.0):
        """Read frames until close; return (status code, opcodes before it)."""
        sock.settimeout(timeout)
        opcodes = []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            opcode, payload = _read_frame(sock)
            if opcode == 0x8:
                code = (struct.unpack(">H", payload[:2])[0]
                        if len(payload) >= 2 else None)
                return code, opcodes
            opcodes.append(opcode)
        raise AssertionError(f"no close frame within {timeout}s")

    @pytest.mark.parametrize("filler", ["ping", "empty continuation"])
    def test_frames_inside_an_open_fragment_are_still_checked(self, srv, filler):
        seed = 2651 if filler == "ping" else 2652
        ada, ada_sid, bea = _two_players(srv, seed)
        # Open a fragmented chat message and leave it unfinished.
        ada.sendall(_client_frame(b'{"type": "chat", ', fin=False))
        persistence.revoke_invite_key(KEY_A)

        frame = (_client_frame(b"", opcode=0x9) if filler == "ping"
                 else _client_frame(b"", opcode=0x0, fin=False))
        ada.sendall(frame)
        code, opcodes = self._until_close_raw(ada)
        assert code == 1008
        assert 0xA not in opcodes  # the ping was refused, not answered
        _until_eof(ada)

        leave, before = _until_type(bea, "player_leave")
        assert leave["session_id"] == ada_sid
        assert not [m for m in before if m.get("type") == "chat"]
        assert _rows(seed, "PLAYER_CHAT") == []
        bea.close()

    def test_the_frame_that_opens_a_fragmented_message_is_checked(self, srv):
        # The opening fragment is a complete frame that ws_recv reads without
        # returning. Unchecked, it reset the idle timer once more and the
        # session stayed subscribed for another idle period.
        seed = 2655
        ada, ada_sid, bea = _two_players(srv, seed)
        persistence.revoke_invite_key(KEY_A)

        ada.sendall(_client_frame(b'{"type": "chat", ', fin=False))
        code, _ = self._until_close_raw(ada)
        assert code == 1008
        _until_eof(ada)
        leave, _ = _until_type(bea, "player_leave")
        assert leave["session_id"] == ada_sid
        bea.close()

    def test_a_live_key_still_assembles_a_fragmented_chat_across_pings(self, srv):
        seed = 2653
        ada, _, bea = _two_players(srv, seed)
        ada.sendall(_client_frame(b'{"type": "chat", ', fin=False)
                    + _client_frame(b"", opcode=0x9)
                    + _client_frame(b'"text": "in pieces"}', opcode=0x0))
        line, _ = _until_type(bea, "chat")
        assert line["name"] == "Ada" and line["text"] == "in pieces"
        assert [r["player"] for r in _wait_rows(seed, "PLAYER_CHAT", None, 1)] \
            == ["Ada"]
        ada.close()
        bea.close()

    def test_a_key_revoked_while_its_chat_is_screened_publishes_nothing(
            self, srv, monkeypatch):
        from server import moderation
        real_screen = moderation.screen
        entered, release = threading.Event(), threading.Event()

        def slow_screen(*args, **kwargs):
            if kwargs.get("surface") == "chat":
                entered.set()
                assert release.wait(5.0), "test never released the screen"
            return real_screen(*args, **kwargs)

        monkeypatch.setattr(moderation, "screen", slow_screen)
        seed = 2654
        ada, ada_sid, bea = _two_players(srv, seed)
        _ws_send_json(ada, {"type": "chat", "text": "said while judged"})
        assert entered.wait(4.0), "the chat never reached the screen"
        persistence.revoke_invite_key(KEY_A)
        release.set()

        code, _ = _until_close(ada)
        assert code == 1008
        _until_eof(ada)
        leave, before = _until_type(bea, "player_leave")
        assert leave["session_id"] == ada_sid
        assert not [m for m in before if m.get("type") == "chat"]
        assert _rows(seed, "PLAYER_CHAT") == []
        bea.close()


class TestReauthorizationThrottle:
    """The production interval, restored from its test default of zero.

    Frames that write nothing re-check at most once per
    `guard.WS_REAUTH_INTERVAL_SEC`, so a frame flood is not a database-read
    flood. A move or chat that passes its throttle re-checks fresh, so a
    revoked credential still writes nothing inside the interval.
    """

    @staticmethod
    def _count_lookups(monkeypatch):
        calls = []
        real = persistence.lookup_invite_key

        def counting(key):
            calls.append(key)
            return real(key)

        monkeypatch.setattr(persistence, "lookup_invite_key", counting)
        return calls

    def test_a_frame_flood_costs_one_read_per_interval(self, srv, monkeypatch):
        monkeypatch.setattr(guard, "WS_REAUTH_INTERVAL_SEC", 60.0)
        seed = 2631
        persistence.mint_invite_key(KEY_A, "Ada")
        ada, _ = _join(srv, seed, "x", KEY_A)
        calls = self._count_lookups(monkeypatch)

        for _ in range(50):
            ada.sendall(_client_frame(b"not json"))
        for _ in range(25):
            ada.sendall(_client_frame(b"", opcode=0x9))
        _ws_send_json(ada, {"type": "ping"})
        _until_type(ada, "pong")

        # 76 frames, one re-check (the first frame after the upgrade).
        assert len(calls) == 1
        ada.close()

    def test_a_chat_inside_the_interval_is_still_checked_fresh(
            self, srv, monkeypatch):
        monkeypatch.setattr(guard, "WS_REAUTH_INTERVAL_SEC", 60.0)
        seed = 2632
        ada, ada_sid, bea = _two_players(srv, seed)
        # A checked frame starts the interval; the revocation lands inside it.
        _ws_send_json(ada, {"type": "ping"})
        _until_type(ada, "pong")
        persistence.revoke_invite_key(KEY_A)

        _ws_send_json(ada, {"type": "chat", "text": "inside the interval"})
        assert _until_close(ada)[0] == 1008
        _until_eof(ada)
        leave, before = _until_type(bea, "player_leave")
        assert leave["session_id"] == ada_sid
        assert not [m for m in before if m.get("type") == "chat"]
        assert _rows(seed, "PLAYER_CHAT") == []
        bea.close()

    def test_a_move_inside_the_interval_is_still_checked_fresh(
            self, srv, monkeypatch):
        monkeypatch.setattr(guard, "WS_REAUTH_INTERVAL_SEC", 60.0)
        seed = 2633
        target = generate_node_hierarchy(seed=seed, max_depth=2).children[0]
        ada, _, bea = _two_players(srv, seed)
        _ws_send_json(ada, {"type": "ping"})
        _until_type(ada, "pong")
        persistence.revoke_invite_key(KEY_A)

        _ws_send_json(ada, {"type": "move", "node": target.name})
        assert _until_close(ada)[0] == 1008
        _until_eof(ada)
        assert _rows(seed, "PLAYER_MOVE", "Ada") == []
        bea.close()

    def test_a_listening_socket_closes_on_its_first_frame_after_the_interval(
            self, srv, monkeypatch):
        monkeypatch.setattr(guard, "WS_REAUTH_INTERVAL_SEC", 0.5)
        seed = 2634
        ada, _, bea = _two_players(srv, seed)
        _ws_send_json(ada, {"type": "ping"})
        _until_type(ada, "pong")
        persistence.revoke_invite_key(KEY_A)

        # Inside the interval a frame that writes nothing is not re-checked.
        _ws_send_json(ada, {"type": "ping"})
        _until_type(ada, "pong")
        # The first such frame after the interval is, and it ends the session.
        time.sleep(0.6)
        _ws_send_json(ada, {"type": "ping"})
        code, seen = _until_close(ada)
        assert code == 1008
        assert not [m for m in seen if m.get("type") == "pong"]
        _until_eof(ada)
        bea.close()


class TestPlayersRouteRemoved:
    def test_players_answers_like_any_unknown_route_for_an_invited_caller(self, srv):
        persistence.mint_invite_key(KEY_A, "Ada")
        ada, _ = _join(srv, 2631, "x", KEY_A)

        def fetch(path):
            req = urllib.request.Request(
                f"http://127.0.0.1:{srv}{path}",
                headers={guard.BETA_KEY_HEADER: KEY_A})
            try:
                with urllib.request.urlopen(req) as resp:
                    return resp.status, json.loads(resp.read())
            except urllib.error.HTTPError as exc:
                return exc.code, json.loads(exc.read())

        gone = fetch("/players?seed=2631")
        assert gone == fetch("/no-such-route?seed=2631")
        assert gone[0] == 404 and "players" not in gone[1]
        # Keyless callers are still refused at the gate, as for any route.
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"http://127.0.0.1:{srv}/players?seed=2631")
        assert exc.value.code == 403
        ada.close()


def _upgrade_reply(port, path):
    """A raw upgrade request: (status, JSON body), or (101, None) if the
    server upgraded."""
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    try:
        sock.sendall((
            f"GET {path} HTTP/1.1\r\nHost: t\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {base64.b64encode(os.urandom(16)).decode()}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n").encode())
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            assert chunk, data
            data += chunk
        head, _, body = data.partition(b"\r\n\r\n")
        status = int(head.split(b" ", 2)[1])
        if status == 101:
            return status, None
        length = int(re.search(rb"(?im)^content-length:\s*(\d+)", head).group(1))
        while len(body) < length:
            chunk = sock.recv(4096)
            assert chunk, body
            body += chunk
        return status, json.loads(body[:length])
    finally:
        sock.close()


class TestUpgradeRace:
    def test_a_key_revoked_during_the_upgrade_is_refused_before_any_join(
            self, srv, monkeypatch):
        # The gate admits the upgrade on a live key; the key is revoked
        # before the session reads its registered name. Before the fix the
        # session fell into the keyless branch and joined under ?name=,
        # here another player's registered name.
        seed = 2661
        persistence.mint_invite_key(KEY_A, "Ada")
        persistence.mint_invite_key(KEY_B, "Bea")
        bea, _ = _join(srv, seed, "x", KEY_B)
        real = guard.registered_name

        def revoked_meanwhile(supplied):
            if supplied == KEY_A:
                persistence.revoke_invite_key(KEY_A)
            return real(supplied)

        monkeypatch.setattr(guard, "registered_name", revoked_meanwhile)
        raced = _upgrade_reply(srv, f"/ws?seed={seed}&name=Bea&key={KEY_A}")
        # The gate's own refusal of a keyless upgrade, for comparison.
        gate = _upgrade_reply(srv, f"/ws?seed={seed}&name=Bea")
        assert raced == gate == (403, {"error": "forbidden"})

        assert [r["player"] for r in _rows(seed, "PLAYER_JOIN")] == ["Bea"]
        _ws_send_json(bea, {"type": "ping"})
        _, heard = _until_type(bea, "pong")
        assert not [m for m in heard if m.get("type") == "player_join"]
        bea.close()


class TestNoDataFrameAfterClose:
    """Every close the server writes is written after the writer stopped, so
    a queued room broadcast cannot follow it (RFC 6455 §5.5.1)."""

    @pytest.mark.parametrize("cause", ["revoked", "protocol error"])
    def test_the_writer_stops_before_the_server_sends_close(
            self, srv, monkeypatch, cause):
        from server import websocket
        seed = 2671 if cause == "revoked" else 2672
        persistence.mint_invite_key(KEY_A, "Ada")
        ada, ada_sid = _join(srv, seed, "x", KEY_A)
        player = get_room(seed).players[ada_sid]
        calls = []
        real = websocket.send_close

        def recording(sock, code, send_lock=None):
            calls.append((code, player._dead.is_set()))
            real(sock, code, send_lock=send_lock)

        monkeypatch.setattr(websocket, "send_close", recording)
        if cause == "revoked":
            persistence.revoke_invite_key(KEY_A)
            _ws_send_json(ada, {"type": "chat", "text": "after revocation"})
            expected = protocol.CLOSE_POLICY_VIOLATION
        else:
            ada.sendall(_client_frame(b"unmasked", masked=False))
            expected = protocol.CLOSE_PROTOCOL_ERROR
        assert _until_close(ada)[0] == expected
        _until_eof(ada)
        assert calls == [(expected, True)]

    def test_the_writer_stops_before_a_peer_close_is_echoed(
            self, srv, monkeypatch):
        seed = 2673
        persistence.mint_invite_key(KEY_A, "Ada")
        ada, ada_sid = _join(srv, seed, "x", KEY_A)
        player = get_room(seed).players[ada_sid]
        echoes = []
        real = protocol._send_frame

        def recording(sock, opcode, data, lock=None):
            if opcode == 0x8:
                echoes.append(player._dead.is_set())
            real(sock, opcode, data, lock=lock)

        monkeypatch.setattr(protocol, "_send_frame", recording)
        ada.sendall(_client_frame(struct.pack(">H", 1000), opcode=0x8))
        assert _until_close(ada)[0] == 1000
        _until_eof(ada)
        assert echoes == [True]


class TestFrameDeadline:
    """Every authorization check runs on a completed frame, and the 60 s idle
    timer resets on every recv. Once a frame's first byte arrives, the rest
    must arrive within `protocol._FRAME_DEADLINE_SEC`, so a client cannot
    hold one frame open, unchecked and subscribed, by trickling bytes."""

    @staticmethod
    def _nodelay(sock):
        # Small writes leave as separate segments, not coalesced.
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    @staticmethod
    def _frames_until_close(sock, timeout=4.0):
        """(close code, or None if none came; JSON messages before it)."""
        sock.settimeout(timeout)
        seen = []
        deadline = time.monotonic() + timeout
        try:
            while time.monotonic() < deadline:
                opcode, payload = _read_frame(sock)
                if opcode == 0x8:
                    return struct.unpack(">H", payload[:2])[0], seen
                if opcode == 0x1:
                    seen.append(json.loads(payload))
        except TimeoutError:
            pass
        return None, seen

    def test_a_revoked_client_trickling_one_frame_is_closed_at_the_deadline(
            self, srv, monkeypatch):
        monkeypatch.setattr(protocol, "_FRAME_DEADLINE_SEC", 0.5)
        seed = 2691
        ada, ada_sid, bea = _two_players(srv, seed)
        self._nodelay(ada)
        persistence.revoke_invite_key(KEY_A)

        frame = _client_frame(json.dumps({"type": "chat", "text": "x" * 64}).encode())
        sent = [0]
        stop = threading.Event()

        def trickle():
            # One byte every 0.2 s: the idle timer never fires, and the
            # frame (about 18 s of bytes) never completes during the test.
            for byte in frame:
                try:
                    ada.sendall(bytes([byte]))
                except OSError:
                    return
                sent[0] += 1
                if stop.wait(0.2):
                    return

        trickler = threading.Thread(target=trickle, daemon=True)
        trickler.start()
        try:
            # Three deadlines in, another player speaks.
            time.sleep(1.5)
            _ws_send_json(bea, {"type": "chat", "text": "during the trickle"})
            chat, before = _until_type(bea, "chat")
            assert sent[0] < len(frame)
            code, seen = self._frames_until_close(ada)
        finally:
            stop.set()
            trickler.join(timeout=2)

        assert not [m for m in seen if m.get("type") == "chat"]
        assert code == protocol.CLOSE_PROTOCOL_ERROR
        _until_eof(ada)
        # Ada had left before Bea's line was broadcast.
        assert chat["name"] == "Bea"
        assert [m["session_id"] for m in before
                if m.get("type") == "player_leave"] == [ada_sid]
        assert len(_wait_rows(seed, "PLAYER_LEAVE", "Ada", 1)) == 1
        assert _rows(seed, "PLAYER_CHAT", "Ada") == []
        bea.close()

    def test_a_frame_sent_in_quick_chunks_still_arrives(self, srv, monkeypatch):
        monkeypatch.setattr(protocol, "_FRAME_DEADLINE_SEC", 1.0)
        seed = 2692
        ada, _, bea = _two_players(srv, seed)
        self._nodelay(ada)
        frame = _client_frame(json.dumps({"type": "chat", "text": "in chunks"}).encode())
        # Split inside the header, inside the mask key and inside the payload.
        for chunk in (frame[:1], frame[1:4], frame[4:10], frame[10:]):
            ada.sendall(chunk)
            time.sleep(0.05)
        line, _ = _until_type(bea, "chat")
        assert line["name"] == "Ada" and line["text"] == "in chunks"
        assert [r["player"] for r in _wait_rows(seed, "PLAYER_CHAT", None, 1)] \
            == ["Ada"]
        ada.close()
        bea.close()

    def test_the_deadline_is_per_frame_not_per_fragmented_message(
            self, srv, monkeypatch):
        monkeypatch.setattr(protocol, "_FRAME_DEADLINE_SEC", 0.5)
        seed = 2693
        ada, _, bea = _two_players(srv, seed)
        ada.sendall(_client_frame(b'{"type": "chat", ', fin=False))
        time.sleep(1.0)  # two deadlines between the message's two frames
        ada.sendall(_client_frame(b'"text": "between frames"}', opcode=0x0))
        line, _ = _until_type(bea, "chat")
        assert line["name"] == "Ada" and line["text"] == "between frames"
        ada.close()
        bea.close()

    def test_the_wait_before_a_frame_is_still_the_idle_timer(
            self, srv, monkeypatch):
        monkeypatch.setattr(protocol, "_FRAME_DEADLINE_SEC", 0.5)
        seed = 2694
        persistence.mint_invite_key(KEY_A, "Ada")
        ada, _ = _join(srv, seed, "x", KEY_A)
        # A complete frame first: reading it shortens the socket's timeout,
        # which must be back to the idle timer before the next frame.
        _ws_send_json(ada, {"type": "ping"})
        _until_type(ada, "pong")
        time.sleep(1.5)  # silent for three deadlines, well inside 60 s
        _ws_send_json(ada, {"type": "ping"})
        _until_type(ada, "pong")
        ada.close()
