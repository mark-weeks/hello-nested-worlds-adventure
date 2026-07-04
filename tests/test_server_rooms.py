"""Tests for room presence + broadcast in server/rooms.py."""
import json

import pytest

from server.rooms import (
    Player, PuzzleSession, Room, _rooms, _rooms_lock,
    agent_enter, agent_leave, agent_move,
    broadcast, clear_rooms, get_puzzle_session, get_room,
    record_attempt, reset_puzzle_session, snapshot,
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


class TestPuzzleSession:
    """Shared puzzle state for co-op solving inside one room."""

    def test_get_creates_session_on_first_access(self):
        room = get_room(1)
        session = get_puzzle_session(room, "Vault-3", "The Lock")
        assert isinstance(session, PuzzleSession)
        assert session.attempts == 0
        assert session.solver is None

    def test_get_returns_same_instance_for_same_node(self):
        room = get_room(1)
        a = get_puzzle_session(room, "Vault-3", "The Lock")
        b = get_puzzle_session(room, "Vault-3", "The Lock")
        assert a is b

    def test_get_replaces_session_when_puzzle_name_changes(self):
        # World regenerated → different puzzle on the same node name.
        # The cached session must not leak its solver/attempts.
        room = get_room(1)
        a = get_puzzle_session(room, "Vault-3", "Old Puzzle")
        a.attempts = 2
        b = get_puzzle_session(room, "Vault-3", "New Puzzle")
        assert b is not a
        assert b.attempts == 0

    def test_record_attempt_increments_shared_counter(self):
        room = get_room(1)
        record_attempt(room, "Vault-3", "The Lock", "Alice", correct=False)
        record_attempt(room, "Vault-3", "The Lock", "Bob",   correct=False)
        session = get_puzzle_session(room, "Vault-3", "The Lock")
        assert session.attempts == 2
        assert session.contributors == {"Alice", "Bob"}

    def test_record_attempt_marks_solver_on_first_correct(self):
        room = get_room(1)
        _, just_solved_a = record_attempt(room, "V", "P", "Alice", correct=False)
        assert just_solved_a is False
        sess_b, just_solved_b = record_attempt(room, "V", "P", "Bob", correct=True)
        assert just_solved_b is True
        assert sess_b.solver == "Bob"
        assert sess_b.contributors == {"Alice", "Bob"}

    def test_record_attempt_no_op_after_solved(self):
        # A second correct attempt by a third player must not flip solver
        # or increment attempts — the puzzle is already won.
        room = get_room(1)
        record_attempt(room, "V", "P", "Alice", correct=True)
        sess, just_solved = record_attempt(room, "V", "P", "Bob", correct=True)
        assert just_solved is False
        assert sess.solver == "Alice"
        # Bob's name is still credited as a contributor.
        assert sess.contributors == {"Alice", "Bob"}
        assert sess.attempts == 1  # Bob's call did not bump the counter

    def test_record_attempt_handles_anonymous_solver(self):
        # When player_name is None, the solver string is "anonymous" so the
        # /puzzle/attempt response always has a stable, non-null solver.
        room = get_room(1)
        sess, _ = record_attempt(room, "V", "P", None, correct=True)
        assert sess.solver == "anonymous"

    def test_reset_drops_the_session(self):
        room = get_room(1)
        record_attempt(room, "V", "P", "Alice", correct=False)
        reset_puzzle_session(room, "V")
        # The next get_ creates a fresh one.
        sess = get_puzzle_session(room, "V", "P")
        assert sess.attempts == 0
        assert sess.contributors == set()


class TestSolvedStateSurvivesRestart:
    """Co-op session state is per-process RAM, but a solve is a durable fact:
    a fresh room (deploy/restart) must rehydrate solver + contributors from
    the persisted PUZZLE_SOLVED mutation instead of resetting the puzzle."""

    def test_session_rehydrates_from_persisted_solve(self):
        import persistence
        persistence.record_mutation(
            42, "Vault-11", "PUZZLE_SOLVED", "Ada",
            {"puzzle": "The Lock", "contributors": ["Ada", "Bob"]})

        clear_rooms()  # simulate a process restart
        room = get_room(42)
        session, just_solved = record_attempt(
            room, "Vault-11", "The Lock", "Mallory", correct=True)
        assert just_solved is False, "puzzle was already solved before restart"
        assert session.solver == "Ada"
        assert {"Ada", "Bob"} <= session.contributors

    def test_agent_solves_do_not_lock_players_out(self):
        import persistence
        persistence.record_mutation(
            42, "Vault-11", "PUZZLE_SOLVED", None,
            {"puzzle": "The Lock", "agent": "Tessera", "persona": "scholar"})

        clear_rooms()
        room = get_room(42)
        session, just_solved = record_attempt(
            room, "Vault-11", "The Lock", "Ada", correct=True)
        assert just_solved is True, "an ambient agent's solve must not claim the co-op session"
        assert session.solver == "Ada"

    def test_anonymous_human_solve_rehydrates(self):
        import persistence
        persistence.record_mutation(
            42, "Vault-11", "PUZZLE_SOLVED", None,
            {"puzzle": "The Lock", "contributors": []})

        clear_rooms()
        room = get_room(42)
        session, just_solved = record_attempt(
            room, "Vault-11", "The Lock", "Ada", correct=True)
        assert just_solved is False
        assert session.solver == "anonymous"

    def test_different_puzzle_name_is_not_rehydrated(self):
        import persistence
        persistence.record_mutation(
            42, "Vault-11", "PUZZLE_SOLVED", "Ada", {"puzzle": "Old Puzzle"})

        clear_rooms()
        room = get_room(42)
        session, just_solved = record_attempt(
            room, "Vault-11", "New Puzzle", "Bob", correct=True)
        assert just_solved is True
        assert session.solver == "Bob"
