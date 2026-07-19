"""Movement mechanics: validated moves, per-connection throttles, sealed
rooms, and live agent presence — the substrate the travelers panel rides on.
"""
from __future__ import annotations

import base64
import os
import random
import socket
import time

import pytest

import persistence
from multiverse.generator import generate_node_hierarchy
from puzzles.gates import seal_check, sealing_room
from puzzles.generators import build_puzzle
from server import guard, heartbeat
from server.rooms import (
    Player, agent_enter, agent_leave, agent_move, agents_snapshot, clear_rooms,
    get_room,
)
from tests.test_day_one_recording import _ws_connect, _ws_send_json, srv  # noqa: F401
from tests.test_heartbeat import _FakeSock, _decode_frames


@pytest.fixture(autouse=True)
def _zero_hop_delay(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_HOP_DELAY", "0")
    yield


def _walk(n, out):
    out.append(n)
    for c in n.children:
        _walk(c, out)
    return out


def _rooms_by_lock(seed, locked):
    return [n for n in _walk(generate_node_hierarchy(seed=seed), [])
            if n.level == "Room" and bool(n.properties.get("locked")) is locked]


def _recv_frames(sock, want, timeout=3.0, seed_buf=b""):
    """Read unmasked server frames off a real socket until `want(frames)`
    is truthy or the clock runs out; returns all decoded frames."""
    sock.settimeout(0.2)
    buf, frames = seed_buf, _decode_frames(seed_buf)
    if want(frames):
        return frames
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
        except OSError:
            chunk = b""
        if chunk:
            buf += chunk
            frames = _decode_frames(buf)
            if want(frames):
                break
    return frames


def _connect_keep_rest(port, seed, name):
    """Like _ws_connect, but hands back any frame bytes that arrived glued
    to the upgrade response — the welcome frame often races the header read
    and must not be swallowed."""
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall((
        f"GET /ws?seed={seed}&name={name} HTTP/1.1\r\nHost: t\r\n"
        "Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
    ).encode())
    head = b""
    while b"\r\n\r\n" not in head:
        chunk = s.recv(4096)
        if not chunk:
            break
        head += chunk
    _, _, rest = head.partition(b"\r\n\r\n")
    return s, rest


def _human_solve(seed, room_node):
    """Record the human solve that opens `room_node`'s current seal."""
    epoch = persistence.count_node_mutations(seed, room_node.name,
                                             "PUZZLE_REARM")
    puzzle = build_puzzle(room_node, epoch)
    persistence.record_mutation(
        seed, room_node.name, "PUZZLE_SOLVED", "Ada",
        {"puzzle": puzzle.name, "contributors": ["Ada"]},
        actor_identity="ada-id")
    return puzzle


class TestSealGate:
    SEED = 42

    def test_locked_room_is_sealed_until_solved(self):
        room = _rooms_by_lock(self.SEED, locked=True)[0]
        seal = seal_check(self.SEED, room)
        assert seal is not None
        assert seal["sealed_by"] == room.name
        assert seal["keeper"] == room.parent.name
        _human_solve(self.SEED, room)
        assert seal_check(self.SEED, room) is None

    def test_seal_covers_everything_enfolded_beneath(self):
        room = next(r for r in _rooms_by_lock(self.SEED, locked=True)
                    if r.children)
        deep = room.children[0]
        assert sealing_room(deep) is room
        assert seal_check(self.SEED, deep) is not None

    def test_the_seal_never_imprisons(self):
        # A mover already inside the sealed subtree moves freely within it.
        room = next(r for r in _rooms_by_lock(self.SEED, locked=True)
                    if r.children)
        deep = room.children[0]
        assert seal_check(self.SEED, deep, current_name=room.name) is None
        assert seal_check(self.SEED, room, current_name=deep.name) is None

    def test_unlocked_rooms_are_open(self):
        room = _rooms_by_lock(self.SEED, locked=False)[0]
        assert seal_check(self.SEED, room) is None

    def test_renewal_reseals_the_door(self):
        seed = 4301
        room = _rooms_by_lock(seed, locked=True)[0]
        _human_solve(seed, room)
        assert seal_check(seed, room) is None
        # Entropy re-arms the room's puzzle: the epoch advances, the old
        # solve no longer names the current puzzle — the door seals itself.
        persistence.record_mutation(seed, room.name, "PUZZLE_REARM", None,
                                    {"trigger": "DANGER_ALERT"})
        reseal = seal_check(seed, room)
        assert reseal is not None
        assert "Renewal 1" in reseal["puzzle"]

    def test_agent_solves_do_not_open_doors_for_players(self):
        seed = 4302
        room = _rooms_by_lock(seed, locked=True)[0]
        puzzle = build_puzzle(room, 0)
        persistence.record_mutation(
            seed, room.name, "PUZZLE_SOLVED", None,
            {"puzzle": puzzle.name, "agent": "The Locksmith"},
            actor_identity="The Locksmith")
        assert seal_check(seed, room) is not None


class TestMoveValidation:
    def test_phantom_move_is_denied_and_leaves_no_history(self, srv):
        seed = 4310
        s, status = _ws_connect(srv, seed, "Ada")
        assert b"101" in status
        _recv_frames(s, lambda fs: any(f.get("type") == "welcome" for f in fs))
        _ws_send_json(s, {"type": "move", "node": "Fake-99"})
        frames = _recv_frames(
            s, lambda fs: any(f.get("type") == "move_denied" for f in fs))
        denied = [f for f in frames if f.get("type") == "move_denied"]
        assert denied and denied[0]["reason"] == "no such place"
        # Nothing entered the permanent record for the phantom place.
        assert not [m for m in persistence.get_mutations(seed, limit=50)
                    if m["node"] == "Fake-99"]
        s.close()

    def test_valid_move_records_and_broadcasts(self, srv):
        seed = 4311
        target = generate_node_hierarchy(seed=seed, max_depth=2).children[0]
        a, _ = _ws_connect(srv, seed, "Ada")
        b, rest = _connect_keep_rest(srv, seed, "Ben")
        # B must be registered (welcome received) before A moves, or the
        # broadcast can race past an in-flight join and never reach B.
        _recv_frames(b, lambda fs: any(f.get("type") == "welcome"
                                       for f in fs), seed_buf=rest)
        _ws_send_json(a, {"type": "move", "node": target.name})
        frames = _recv_frames(
            b, lambda fs: any(f.get("type") == "player_move" for f in fs),
            timeout=6.0)
        moves = [f for f in frames if f.get("type") == "player_move"]
        assert moves and moves[0]["node"] == target.name
        a.close()
        b.close()

    def test_forged_names_cannot_enter_the_chronicle(self, srv):
        # A name with a REAL path but a wrong base is forged identity —
        # resolution must reject it, same as the HTTP paths do.
        seed = 4312
        real = generate_node_hierarchy(seed=seed, max_depth=2).children[0]
        suffix = real.name.rpartition("-")[2]
        s, _ = _ws_connect(srv, seed, "Ada")
        _ws_send_json(s, {"type": "move", "node": f"Forged-{suffix}"})
        _recv_frames(
            s, lambda fs: any(f.get("type") == "move_denied" for f in fs))
        assert not [m for m in persistence.get_mutations(seed, limit=50)
                    if m["node"].startswith("Forged-")]
        s.close()


class TestMoveThrottle:
    def test_flood_is_capped_at_the_bucket(self, srv):
        seed = 4320
        root = generate_node_hierarchy(seed=seed, max_depth=2)
        a, b = root.children[0], root.children[1 % len(root.children)]
        s, _ = _ws_connect(srv, seed, "Flood")
        for i in range(60):
            _ws_send_json(s, {"type": "move",
                              "node": (a if i % 2 == 0 else b).name})
        time.sleep(1.0)  # let the handler drain
        rows = [m for m in persistence.get_mutations(seed, limit=200)
                if m["type"] == "PLAYER_MOVE"]
        # Burst (20) plus at most a few refilled tokens — never all 60.
        assert guard.WS_MOVE_BURST * 0.5 <= len(rows) <= guard.WS_MOVE_BURST + 8
        s.close()

    def test_bucket_refills(self):
        bucket = guard.TokenBucket(rate=100.0, burst=2)
        assert bucket.allow() and bucket.allow()
        assert not bucket.allow()
        time.sleep(0.03)  # 100/s → ~3 tokens back
        assert bucket.allow()


class TestSealedMovesOverWs:
    def test_sealed_denied_then_solve_then_enter(self, srv):
        seed = 42
        room = _rooms_by_lock(seed, locked=True)[0]
        s, _ = _ws_connect(srv, seed, "Ada")
        _ws_send_json(s, {"type": "move", "node": room.name})
        frames = _recv_frames(
            s, lambda fs: any(f.get("type") == "move_denied" for f in fs))
        denied = [f for f in frames if f.get("type") == "move_denied"]
        assert denied and denied[0]["reason"] == "sealed"
        assert denied[0]["sealed_by"] == room.name
        assert denied[0]["keeper"] == room.parent.name
        assert not [m for m in persistence.get_mutations(seed, limit=50)
                    if m["node"] == room.name and m["type"] == "PLAYER_MOVE"]

        _human_solve(seed, room)
        _ws_send_json(s, {"type": "move", "node": room.name})
        deadline = time.monotonic() + 3.0
        moved = []
        while time.monotonic() < deadline and not moved:
            moved = [m for m in persistence.get_mutations(seed, limit=50)
                     if m["node"] == room.name and m["type"] == "PLAYER_MOVE"]
            time.sleep(0.02)
        assert moved, "the way must open once the key is spoken"
        s.close()


class TestAgentPresence:
    def test_welcome_carries_the_walking_cast(self, srv):
        seed = 4330
        room = get_room(seed)
        agent_enter(room, "Tessera", persona="tender")
        agent_move(room, "Tessera", "Somewhere-11")
        s, rest = _connect_keep_rest(srv, seed, "Ada")
        frames = _recv_frames(
            s, lambda fs: any(f.get("type") == "welcome" for f in fs),
            seed_buf=rest)
        welcome = next(f for f in frames if f.get("type") == "welcome")
        cast = {a["name"]: a for a in welcome.get("agents", [])}
        assert cast["Tessera"]["node"] == "Somewhere-11"
        assert cast["Tessera"]["persona"] == "tender"
        agent_leave(room, "Tessera")
        s.close()

    def test_agent_walks_broadcast_enter_move_leave(self):
        clear_rooms()
        seed = 4331
        room = get_room(seed)
        sock = _FakeSock()
        with room.lock:
            room.players["w"] = Player(name="W", seed=seed, current_node="",
                                       session_id="w", sock=sock)
        heartbeat.run_tick(seed=seed, rng=random.Random(3), pace=0.0)
        kinds = [f.get("type") for f in _decode_frames(sock.raw)]
        assert "agent_enter" in kinds
        assert "agent_move" in kinds
        assert "agent_leave" in kinds
        # Presence state is clean after the walk.
        assert agents_snapshot(room) == []
