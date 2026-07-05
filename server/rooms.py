"""Multiplayer room state for the nested-worlds server.

A room is keyed by world seed; each connected WebSocket player is a `Player`.
Broadcasting handles per-socket failures by evicting dead players.

Sends are decoupled from socket writes: each connected player gets a
dedicated writer thread draining a bounded outbox, so `broadcast` only
enqueues. Without this, broadcast did a blocking `sendall` per player in
sequence — one client with a full TCP window stalled every message to
everyone else in the room. A player whose outbox overflows (they can't
drain OUTBOX_LIMIT pending messages) is marked dead and evicted instead
of ever blocking the room.
"""
from __future__ import annotations

import json
import queue
import threading
from dataclasses import dataclass, field

from server.protocol import ws_send

# Pending messages a client may fall behind before being declared dead.
OUTBOX_LIMIT = 64

_STOP = object()  # outbox sentinel: writer thread exits


@dataclass
class Player:
    name: str
    seed: int
    current_node: str
    session_id: str
    sock: object
    # Serializes all frame writes on this socket — the writer thread's data
    # frames and the reader thread's pong/close echoes (see protocol.ws_recv).
    send_lock: threading.Lock = field(
        default_factory=threading.Lock, compare=False, repr=False)
    outbox: queue.Queue = field(
        default_factory=lambda: queue.Queue(maxsize=OUTBOX_LIMIT),
        compare=False, repr=False)
    _dead: threading.Event = field(
        default_factory=threading.Event, compare=False, repr=False)
    _writer: threading.Thread | None = field(
        default=None, compare=False, repr=False)

    def start_writer(self) -> None:
        """Spawn the dedicated writer thread (called once per connection)."""
        self._writer = threading.Thread(
            target=self._drain, name=f"ws-writer-{self.session_id}", daemon=True)
        self._writer.start()

    def stop_writer(self) -> None:
        """Ask the writer thread to exit; safe to call multiple times."""
        self._dead.set()
        try:
            self.outbox.put_nowait(_STOP)
        except queue.Full:
            pass  # writer is draining; it checks _dead between items

    def _drain(self) -> None:
        while not self._dead.is_set():
            item = self.outbox.get()
            if item is _STOP:
                return
            try:
                ws_send(self.sock, item, send_lock=self.send_lock)
            except OSError:
                self._dead.set()
                return

    def send(self, msg: dict) -> bool:
        """Hand `msg` to this player without blocking the caller.

        With a writer thread running this only enqueues; a full outbox means
        the client has stopped draining, so the player is marked dead and
        False is returned (broadcast evicts on False). Without a writer
        (tests, synchronous contexts) it writes inline as before.
        """
        if self._dead.is_set():
            return False
        data = json.dumps(msg)
        if self._writer is None:
            try:
                ws_send(self.sock, data, send_lock=self.send_lock)
                return True
            except OSError:
                self._dead.set()
                return False
        try:
            self.outbox.put_nowait(data)
            return True
        except queue.Full:
            self._dead.set()
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
    else:
        # Unsolved: the pooled attempt count and contributors are durable
        # facts too (PUZZLE_ATTEMPT rows) — a deploy must not refund the
        # room's spent attempts.
        state = persistence.get_puzzle_attempt_state(
            room.seed, node_name, puzzle_name)
        session.attempts = state["attempts"]
        session.contributors = state["contributors"]
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
