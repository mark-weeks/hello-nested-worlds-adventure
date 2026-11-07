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
from contextlib import contextmanager
from dataclasses import dataclass, field

from persistence.blocks import agent_target
from server.block_targets import wire_message
from server.protocol import ws_send

# Pending messages a client may fall behind before being declared dead.
OUTBOX_LIMIT = 64

_STOP = object()  # outbox sentinel: writer thread exits

# Serialize preference writes with connection enrollment. Delivery itself only
# reads each player's immutable preference snapshot; no database read or global
# lock is added to room broadcasts or socket writes.
BLOCKS_LOCK = threading.RLock()
_LIVE_TYPES = frozenset({"chat", "player_join", "player_move", "player_leave",
                         "agent_enter", "agent_move", "agent_leave", "agent_done"})


def _live_agent_ids(message: dict) -> tuple[dict, dict]:
    """Enrich live server envelopes without changing stored events or world effects."""
    kind = message.get('type')
    if kind in ('agent_enter', 'agent_move', 'agent_leave', 'agent_done'):
        target = agent_target(message.get('name'))
        return ({**message, 'participant_id': target} if target else message), {}
    if kind == 'agent_encounter':
        return {**message, 'participant_ids': [target for name in
                    (message.get('agent1'), message.get('agent2'))
                    if (target := agent_target(name))]}, {}
    if kind == 'agent_talk':
        names = {name for name in (message.get('a'), message.get('b'),
                 *(line.get('speaker') for line in message.get('lines', [])))
                 if isinstance(name, str)}
        targets = {name: agent_target(name) for name in names}
        return {**message, 'participant_ids': [target for name in
                    (message.get('a'), message.get('b')) if (target := targets.get(name))],
                'lines': [{**line, 'participant_id': target} if
                          (target := targets.get(line.get('speaker'))) else line
                          for line in message.get('lines', [])]}, targets
    return message, {}


@dataclass(frozen=True)
class _Delivery:
    message: dict
    revision: int
    agent_ids: dict


@dataclass(frozen=True)
class _BlockPolicy:
    blocks: tuple = ()
    ids: frozenset = frozenset()
    revision: int = 0
    blocked_at: dict = field(default_factory=dict)


@dataclass
class Player:
    name: str
    seed: int
    current_node: str
    session_id: str
    sock: object
    participant_id: str | None = None
    _block_policy: _BlockPolicy = field(default_factory=_BlockPolicy, repr=False)
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

    @property
    def blocks(self):
        return self._block_policy.blocks

    @property
    def blocked_ids(self):
        return self._block_policy.ids

    def set_blocks(self, blocks: list[dict]) -> None:
        """Publish one immutable policy snapshot, remembering queued-message fences."""
        policy = self._block_policy
        revision = policy.revision + 1
        ids = frozenset(b["id"] for b in blocks)
        revisions = dict(policy.blocked_at)
        for target in ids - policy.ids:
            revisions[target] = revision
        self._block_policy = _BlockPolicy(
            tuple(dict(b) for b in blocks), ids, revision, revisions)

    def _visible(self, message: dict, revision: int, agent_ids: dict) -> dict | None:
        policy = self._block_policy
        target = message.get("participant_id")
        kind = message.get("type")

        def hidden(target):
            return target in policy.ids or policy.blocked_at.get(target, 0) > revision

        if kind in _LIVE_TYPES and target:
            # A block also discards pre-block queued traffic after an unblock.
            if hidden(target):
                return None
        if kind == 'agent_encounter' and any(hidden(p) for p in message['participant_ids']):
            return None
        if kind == 'agent_talk':
            pair_hidden = any(hidden(p) for p in message['participant_ids'])
            lines = [line for line in message['lines']
                     if not hidden(line.get('participant_id'))
                     and (line.get('speaker') or not pair_hidden)]
            if not lines:
                return None
            message = {**message, 'lines': lines,
                       'participant_ids': [p for p in message['participant_ids'] if not hidden(p)]}
            for key in ('a', 'b'):
                if hidden(agent_ids.get(message.get(key))):
                    message.pop(key, None)
        if kind in ("welcome", "blocks_changed"):
            message = {**message,
                       "players": [p for p in message.get("players", [])
                                   if p.get("participant_id") not in policy.ids],
                       "agents": [a for a in message.get("agents", [])
                                  if a.get('participant_id') not in policy.ids]}
            if kind == "welcome":
                message["blocks"] = list(policy.blocks)
        return message

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
                with self.send_lock:
                    # Re-checked under the lock: a session that closes its
                    # socket marks the player dead before writing the close
                    # frame under this same lock (`stop_writer`, then
                    # `protocol.send_close`), so no data frame dequeued in
                    # the meantime can follow the close frame (RFC 6455
                    # §5.5.1).
                    if self._dead.is_set():
                        return
                    if isinstance(item, _Delivery):
                        visible = self._visible(item.message, item.revision, item.agent_ids)
                        if visible is None:
                            continue
                        item = json.dumps(wire_message(self.participant_id or self.session_id, visible))
                    ws_send(self.sock, item)
            except OSError:
                self._dead.set()
                return

    def send(self, msg: dict, *, _agent_ids: dict | None = None) -> bool:
        """Hand `msg` to this player without blocking the caller.

        With a writer thread running this only enqueues; a full outbox means
        the client has stopped draining, so the player is marked dead and
        False is returned (broadcast evicts on False). Without a writer
        (tests, synchronous contexts) it writes inline as before.
        """
        if self._dead.is_set():
            return False
        if _agent_ids is None:
            msg, _agent_ids = _live_agent_ids(msg)
        revision = self._block_policy.revision
        visible = self._visible(msg, revision, _agent_ids)
        if visible is None:
            return True
        if self._writer is None:
            try:
                ws_send(self.sock, json.dumps(wire_message(
                    self.participant_id or self.session_id, visible)), send_lock=self.send_lock)
                return True
            except OSError:
                self._dead.set()
                return False
        try:
            self.outbox.put_nowait(_Delivery(visible, revision, _agent_ids))
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
    # Acceptance owns the room lock across its DB transaction and calls the
    # existing session helpers, which acquire the same lock themselves.
    lock: threading.RLock = field(default_factory=threading.RLock, compare=False, repr=False)
    # One live `/observe` walk at a time: every walk carries the server's one
    # reserved `Observer` presence, so overlapping walks would overwrite its
    # position and one walk's leave would end the other's presence.
    observer_lock: threading.Lock = field(default_factory=threading.Lock, compare=False, repr=False)


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
    state = persistence.get_puzzle_attempt_state(room.seed, node_name, puzzle_name)
    session.attempts = state["attempts"]
    solve = persistence.get_puzzle_solve(room.seed, node_name, puzzle_name)
    if solve:
        session.solver = solve["solver"]
        session.contributors = set(solve["contributors"])
    else:
        # Unsolved: the pooled attempt count and contributors are durable
        # facts too (PUZZLE_ATTEMPT rows) — a deploy must not refund the
        # room's spent attempts.
        session.contributors = state["contributors"]
    room.puzzle_sessions[node_name] = session
    return session


def broadcast(room: Room, msg: dict, exclude: str | None = None) -> None:
    with room.lock:
        targets = list(room.players.items())
    failed = []
    msg, agent_ids = _live_agent_ids(msg)
    for sid, player in targets:
        if sid == exclude:
            continue
        if not player.send(msg, _agent_ids=agent_ids):
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
    # Agent presence is first-class, like player presence: connected
    # clients keep a live travelers roster, so the cast is visible (and
    # followable) between the causal events their walks emit.
    broadcast(room, {"type": "agent_enter", "name": name, "persona": persona})


def agent_move(room: Room, name: str, node: str) -> list[str]:
    """Update agent position; return names of agents already at the same node."""
    with room.lock:
        room.active_agents[name] = node
        others = [n for n, pos in room.active_agents.items()
                  if pos == node and n != name]
    broadcast(room, {"type": "agent_move", "name": name, "node": node})
    return others


def agent_leave(room: Room, name: str) -> None:
    with room.lock:
        room.active_agents.pop(name, None)
        room.agent_personas.pop(name, None)
    broadcast(room, {"type": "agent_leave", "name": name})


def agent_persona(room: Room, name: str) -> str | None:
    """Look up the recorded persona for an active agent, if any."""
    with room.lock:
        return room.agent_personas.get(name)


def snapshot(room: Room, viewer: Player | None = None) -> list[dict]:
    with room.lock:
        return [{"name": p.name, "node": p.current_node, "session_id": p.session_id,
                 **({"participant_id": p.participant_id} if p.participant_id else {})}
                for p in room.players.values()
                if viewer is None or p.participant_id not in viewer.blocked_ids]


def sync_blocks(participant: str, blocks: list[dict]) -> None:
    """Called under BLOCKS_LOCK after commit; only the owner's tabs are notified.

    A writer rechecks queued live speech/presence just before starting its frame.
    A frame whose transmission has already begun cannot be taken back.
    Slow sockets never hold this preference lock or delay another player.
    """
    with _rooms_lock:
        rooms = list(_rooms.values())
    for room in rooms:
        with room.lock:
            players = snapshot(room)
            agents = agents_snapshot(room)
            for player in room.players.values():
                if player.participant_id == participant:
                    player.set_blocks(blocks)
                    player.send({"type": "blocks_changed", "blocks": blocks,
                                 "players": players, "agents": agents})


def agents_snapshot(room: Room, viewer: Player | None = None) -> list[dict]:
    """The cast members currently walking this world, with positions —
    the agent half of the travelers roster the welcome payload carries."""
    with room.lock:
        return [{"name": n, "node": pos,
                 "persona": room.agent_personas.get(n), 'participant_id': target}
                for n, pos in room.active_agents.items()
                for target in (agent_target(n),)
                if viewer is None or target not in viewer.blocked_ids]


# ── Puzzle sessions (co-op state) ───────────────────────────────────────────


def refresh_puzzle_session(room: Room, node_name: str, puzzle_name: str) -> PuzzleSession:
    """Refresh durable facts, retaining local credit only for the same solve.

    Post-solve visitors are credited in this process without new history rows.
    A refresh must preserve that credit, but never a solver absent from the DB.
    """
    with room.lock:
        previous = room.puzzle_sessions.get(node_name)
        session = _new_session(room, node_name, puzzle_name)
        if (previous is not None and previous.puzzle_name == puzzle_name
                and session.solver is not None and previous.solver == session.solver):
            session.attempts = max(session.attempts, previous.attempts)
            session.contributors |= previous.contributors
        return session


class PuzzleRenewed(ValueError):
    pass


def will_store_guess(room: Room, seed: int, node_name: str, puzzle_name: str,
                     expected_epoch: int) -> bool:
    """True when an incorrect guess would be written for this question.

    The room lock makes a solve or renewal that has already committed
    visible before the caller spends a screen. The screen stays outside
    the lock; ``puzzle_attempt`` checks the epoch and the solved state
    again. Holding the lock across the classifier would stall the room.
    """
    import persistence
    with room.lock:
        current = persistence.count_rearms_by_node(seed, node_name).get(node_name, 0)
        if current != expected_epoch:
            return False
        session = room.puzzle_sessions.get(node_name)
        if (session is not None and session.puzzle_name == puzzle_name
                and session.solver is not None):
            return False
        return persistence.get_puzzle_solve(seed, node_name, puzzle_name) is None


@contextmanager
def puzzle_attempt(room: Room, node_name: str, puzzle_name: str,
                   player_name: str | None, correct: bool, *, expected_epoch: int | None = None):
    """Own refresh, serialization and rollback of an accepted puzzle attempt.

    The caller writes history/effects inside this scope. Unsolved sessions are
    refreshed under the writer lock to see other processes' commits. The epoch check and new solve share the writer lock; already-solved reads remain read-only.
    """
    import persistence
    with room.lock:
        session = refresh_puzzle_session(room, node_name, puzzle_name)
        if session.solver is not None:
            # A solved read has no durable effect to fence. It may return the
            # state at this read instant without taking the world writer lock.
            if expected_epoch is not None and persistence.count_rearms_by_node(room.seed, node_name).get(node_name, 0) != expected_epoch:
                raise PuzzleRenewed("This question has renewed. Reopen it before answering.")
            yield record_attempt(room, node_name, puzzle_name, player_name, correct)
            return
        try:
            with persistence.transaction():
                if expected_epoch is not None and persistence.count_rearms_by_node(room.seed, node_name).get(node_name, 0) != expected_epoch:
                    raise PuzzleRenewed("This question has renewed. Reopen it before answering.")
                refresh_puzzle_session(room, node_name, puzzle_name)
                yield record_attempt(room, node_name, puzzle_name, player_name, correct)
        except BaseException:
            reset_puzzle_session(room, node_name)
            raise


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
