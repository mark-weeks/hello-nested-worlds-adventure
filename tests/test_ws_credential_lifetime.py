"""An open WebSocket lives only as long as its authorization.

The upgrade is authorized once. Before this suite's fix, a revoked player's
open socket kept chatting world-wide and moving for as long as the client
pinged, a keyless socket opened before the first mint kept playing after the
gate closed, and up to eight sockets on one credential each had their own
chat and move allowance. Every test here drives a real server socket.
"""
from __future__ import annotations

import json
import struct
import threading
import time
import urllib.error
import urllib.request

import pytest

import persistence
from multiverse.generator import generate_node_hierarchy
from server import guard
from tests.test_day_one_recording import _ws_connect, _ws_send_json
from tests.test_moderation import _read_ws_json_until, _recv_exact

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
    def test_concurrent_sockets_cannot_overdraw_a_shared_bucket(self):
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
