"""Tests for room presence + broadcast in server/rooms.py."""
import json

import pytest

from server.rooms import (
    Player, Room, _rooms, _rooms_lock,
    agent_enter, agent_leave, agent_move,
    broadcast, get_room, snapshot,
)


class FakeSock:
    """Captures sendall payloads; can be configured to fail."""

    def __init__(self, fail: bool = False):
        self.sent = []
        self.fail = fail

    def sendall(self, data: bytes) -> None:
        if self.fail:
            raise OSError("simulated socket failure")
        self.sent.append(data)


@pytest.fixture(autouse=True)
def isolate_rooms():
    """Each test runs against a clean global room registry."""
    with _rooms_lock:
        _rooms.clear()
    yield
    with _rooms_lock:
        _rooms.clear()


def _add_player(room: Room, sid: str, *, fail: bool = False) -> Player:
    p = Player(name=f"P{sid}", seed=1, current_node="root",
               session_id=sid, sock=FakeSock(fail=fail))
    with room.lock:
        room.players[sid] = p
    return p


class TestGetRoom:
    def test_creates_room_on_first_access(self):
        room = get_room(42)
        assert isinstance(room, Room)
        assert room.players == {}

    def test_returns_same_room_for_same_seed(self):
        assert get_room(42) is get_room(42)

    def test_different_seeds_get_different_rooms(self):
        assert get_room(1) is not get_room(2)


class TestBroadcast:
    def test_sends_to_all_players(self):
        room = get_room(1)
        a = _add_player(room, "a")
        b = _add_player(room, "b")
        broadcast(room, {"type": "hello"})
        assert len(a.sock.sent) == 1
        assert len(b.sock.sent) == 1
        # Frame layout: 0x81 + 1-byte length + JSON payload (length is 16, fits in short form)
        payload_a = a.sock.sent[0][2:].decode()
        assert json.loads(payload_a) == {"type": "hello"}

    def test_excludes_specified_session(self):
        room = get_room(1)
        a = _add_player(room, "a")
        b = _add_player(room, "b")
        broadcast(room, {"type": "hello"}, exclude="a")
        assert a.sock.sent == []
        assert len(b.sock.sent) == 1

    def test_evicts_failing_players(self):
        room = get_room(1)
        good = _add_player(room, "good")
        _add_player(room, "bad", fail=True)
        broadcast(room, {"type": "hello"})
        with room.lock:
            assert "good" in room.players
            assert "bad" not in room.players
        assert len(good.sock.sent) == 1

    def test_empty_room_is_noop(self):
        room = get_room(1)
        broadcast(room, {"type": "hello"})  # must not raise


class TestAgentTracking:
    def test_agent_enter_registers_with_no_position(self):
        room = get_room(1)
        agent_enter(room, "Scout")
        with room.lock:
            assert room.active_agents == {"Scout": ""}

    def test_agent_leave_removes(self):
        room = get_room(1)
        agent_enter(room, "Scout")
        agent_leave(room, "Scout")
        with room.lock:
            assert room.active_agents == {}

    def test_agent_leave_unknown_is_noop(self):
        room = get_room(1)
        agent_leave(room, "NeverEntered")  # must not raise

    def test_agent_move_returns_no_collisions_when_alone(self):
        room = get_room(1)
        agent_enter(room, "Scout")
        assert agent_move(room, "Scout", "Aethon") == []

    def test_agent_move_detects_collision(self):
        room = get_room(1)
        agent_enter(room, "Scout")
        agent_enter(room, "Wanderer")
        agent_move(room, "Scout", "Aethon")
        # Wanderer arrives at the same node Scout is already on
        assert agent_move(room, "Wanderer", "Aethon") == ["Scout"]

    def test_agent_move_does_not_match_self(self):
        room = get_room(1)
        agent_enter(room, "Scout")
        agent_move(room, "Scout", "Aethon")
        # moving Scout to where Scout already is should not yield Scout
        assert agent_move(room, "Scout", "Aethon") == []


class TestSnapshot:
    def test_empty_snapshot(self):
        assert snapshot(get_room(1)) == []

    def test_snapshot_lists_all_players(self):
        room = get_room(1)
        _add_player(room, "a")
        _add_player(room, "b")
        snap = snapshot(room)
        sids = {p["session_id"] for p in snap}
        assert sids == {"a", "b"}
        for p in snap:
            assert set(p.keys()) == {"name", "node", "session_id"}


class TestPlayerSend:
    def test_returns_true_on_success(self):
        sock = FakeSock()
        p = Player(name="X", seed=1, current_node="root", session_id="x", sock=sock)
        assert p.send({"type": "ping"}) is True
        assert len(sock.sent) == 1

    def test_returns_false_on_oserror(self):
        sock = FakeSock(fail=True)
        p = Player(name="X", seed=1, current_node="root", session_id="x", sock=sock)
        assert p.send({"type": "ping"}) is False
