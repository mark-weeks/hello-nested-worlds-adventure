"""Multiplayer room state for the nested-worlds server.

A room is keyed by world seed; each connected WebSocket player is a `Player`.
Broadcasting handles per-socket failures by evicting dead players.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field

from server.protocol import ws_send


@dataclass
class Player:
    name: str
    seed: int
    current_node: str
    session_id: str
    sock: object
    _lock: threading.Lock = field(default_factory=threading.Lock, compare=False, repr=False)

    def send(self, msg: dict) -> bool:
        try:
            with self._lock:
                ws_send(self.sock, json.dumps(msg))
            return True
        except OSError:
            return False


@dataclass
class PuzzleSession:
    """Shared per-(seed, node) puzzle state across all players in a room.

    Attempts pool — every player guessing at the same puzzle increments the
    same counter, every contributor's name is recorded, and once any one
    player guesses correctly the puzzle is marked solved for everyone in
    the room. This is the in-product mechanism behind the game-design.md
    "Optional cooperation when players share goals" line.
    """
    puzzle_name: str
    attempts: int = 0
    contributors: set = field(default_factory=set)  # player names who attempted
    solver: str | None = None  # first correct attempter; None until solved


@dataclass
class Room:
    seed: int = 0
    players: dict = field(default_factory=dict)   # session_id → Player
    active_agents: dict = field(default_factory=dict)  # agent_name → current_node
    agent_personas: dict = field(default_factory=dict)  # agent_name → persona name
    puzzle_sessions: dict = field(default_factory=dict)  # node_name → PuzzleSession
    lock: threading.Lock = field(default_factory=threading.Lock, compare=False, repr=False)


_rooms: dict[int, Room] = {}
_rooms_lock = threading.Lock()


def get_room(seed: int) -> Room:
    with _rooms_lock:
        if seed not in _rooms:
            _rooms[seed] = Room(seed=seed)
        return _rooms[seed]


def _new_session(room: Room, node_name: str, puzzle_name: str) -> PuzzleSession:
    """Create a session, rehydrating solved-state from persistence.

    Session state is per-process memory, but solves are durable facts in
    `world_mutations` — without this, every deploy silently reset solved
    puzzles against a history that says they're solved. Caller holds
    `room.lock`.
    """
    import persistence
    session = PuzzleSession(puzzle_name=puzzle_name)
    solve = persistence.get_puzzle_solve(room.seed, node_name, puzzle_name)
    if solve:
        session.solver = solve["solver"]
        session.contributors = set(solve["contributors"])
    room.puzzle_sessions[node_name] = session
    return session


def broadcast(room: Room, msg: dict, exclude: str | None = None) -> None:
    with room.lock:
        targets = list(room.players.items())
    failed = []
    for sid, player in targets:
        if sid == exclude:
            continue
        if not player.send(msg):
            failed.append(sid)
    if failed:
        with room.lock:
            for sid in failed:
                room.players.pop(sid, None)


def agent_enter(room: Room, name: str, persona: str | None = None) -> None:
    with room.lock:
        room.active_agents[name] = ""
        if persona is not None:
            room.agent_personas[name] = persona


def agent_move(room: Room, name: str, node: str) -> list[str]:
    """Update agent position; return names of agents already at the same node."""
    with room.lock:
        room.active_agents[name] = node
        return [n for n, pos in room.active_agents.items() if pos == node and n != name]


def agent_leave(room: Room, name: str) -> None:
    with room.lock:
        room.active_agents.pop(name, None)
        room.agent_personas.pop(name, None)


def agent_persona(room: Room, name: str) -> str | None:
    """Look up the recorded persona for an active agent, if any."""
    with room.lock:
        return room.agent_personas.get(name)


def snapshot(room: Room) -> list[dict]:
    with room.lock:
        return [{"name": p.name, "node": p.current_node, "session_id": p.session_id}
                for p in room.players.values()]


# ── Puzzle sessions (co-op state) ───────────────────────────────────────────


def get_puzzle_session(room: Room, node_name: str, puzzle_name: str) -> PuzzleSession:
    """Fetch (or create) the shared puzzle session for `node_name` in `room`.

    The session carries across attempts by different players; all callers
    must hold `room.lock` themselves while mutating session fields, since
    the room lock is the single guard for room state.
    """
    with room.lock:
        existing = room.puzzle_sessions.get(node_name)
        if existing is not None and existing.puzzle_name == puzzle_name:
            return existing
        # New node, or the puzzle name changed (e.g. world regenerated with
        # a different seed and the cached session no longer applies).
        return _new_session(room, node_name, puzzle_name)


def record_attempt(room: Room, node_name: str, puzzle_name: str,
                    player_name: str | None, correct: bool,
                    ) -> tuple[PuzzleSession, bool]:
    """Atomically increment the attempt counter and (if correct) claim solver.

    Returns (session, just_solved) — `just_solved` is True only on the call
    that flipped solver from None, so the caller can broadcast exactly once.
    No-ops once the puzzle is already solved.
    """
    with room.lock:
        session = room.puzzle_sessions.get(node_name)
        if session is None or session.puzzle_name != puzzle_name:
            session = _new_session(room, node_name, puzzle_name)

        if session.solver is not None:
            # Already solved by someone — record the contributor anyway, but
            # don't increment attempts or re-claim solver.
            if player_name:
                session.contributors.add(player_name)
            return session, False

        session.attempts += 1
        if player_name:
            session.contributors.add(player_name)
        just_solved = False
        if correct:
            session.solver = player_name or "anonymous"
            just_solved = True
        return session, just_solved


def reset_puzzle_session(room: Room, node_name: str) -> None:
    """Drop the cached session for `node_name`, if any."""
    with room.lock:
        room.puzzle_sessions.pop(node_name, None)


def clear_rooms() -> None:
    """Clear the global room registry. Test-only helper."""
    with _rooms_lock:
        _rooms.clear()
