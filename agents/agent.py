import hashlib
import random
import time
from dataclasses import dataclass, field
from typing import List, Optional

from multiverse.node import SpatialNode
from agents.behaviors import DEFAULT_DANGER_THRESHOLD, State, transition, should_preserve
from agents.personas import Persona, for_name as _persona_for_name
import causality
from causality import CausalityBus, EventKind


@dataclass
class AgentLog:
    node_name: str
    level: str
    state: State
    action: str
    persona: Optional[str] = None


# Chance an agent's puzzle attempt succeeds, by puzzle difficulty (1–4).
# Agents face the same puzzle the engine would hand a human at that node;
# they don't get free solves — they roll against the difficulty.
_PUZZLE_SUCCESS_BY_DIFFICULTY = {1: 0.75, 2: 0.55, 3: 0.35, 4: 0.2}


@dataclass
class Agent:
    name: str
    danger_threshold: int = DEFAULT_DANGER_THRESHOLD
    state: State = State.IDLE
    log: List[AgentLog] = field(default_factory=list)
    visited: List[str] = field(default_factory=list)
    memory: List[str] = field(default_factory=list)
    bus: Optional[CausalityBus] = None
    persona: Optional[Persona] = None

    def __post_init__(self) -> None:
        if self.persona is None:
            self.persona = _persona_for_name(self.name)

    @property
    def _bus(self) -> CausalityBus:
        return self.bus if self.bus is not None else causality._default

    def _record(self, node: SpatialNode, action: str) -> None:
        self.log.append(AgentLog(
            node_name=node.name,
            level=node.level,
            state=self.state,
            action=action,
            persona=self.persona.name if self.persona else None,
        ))

    def _payload(self, **extra) -> dict:
        """Causal-event payload tagged with this agent's identity + persona."""
        base: dict = {"agent": self.name}
        if self.persona is not None:
            base["persona"] = self.persona.name
        base.update(extra)
        return base

    def _attempt_puzzle(self, node: SpatialNode):
        """Attempt the node's actual puzzle under the same engine humans use.

        The puzzle is derived from the node's identity (the same one a human
        at this node is served), and success is a difficulty-weighted roll
        seeded by (agent, node) so a given agent's outcome at a given node is
        reproducible. Returns (solved, puzzle_name, difficulty).
        """
        from puzzles.generators import build_puzzle
        puzzle = build_puzzle(node)
        digest = hashlib.sha256(
            f"attempt:{self.name}:{node.name}".encode("utf-8")
        ).digest()
        roll = random.Random(int.from_bytes(digest[:8], "big")).random()
        chance = _PUZZLE_SUCCESS_BY_DIFFICULTY.get(puzzle.difficulty, 0.5)
        return roll < chance, puzzle.name, puzzle.difficulty

    def _act(self, node: SpatialNode) -> bool:
        if self.state == State.EXPLORE:
            if should_preserve(node, self.danger_threshold):
                self._record(node, f"withdrew (danger_level={node.properties.get('danger_level')})")
                # Danger travels: an alert cascades up the containing scales
                # (dampened per hop) so a volatile region registers on its
                # planet, system, and beyond.
                self._bus.propagate(node, EventKind.DANGER_ALERT, self._payload(),
                                    direction="up")
                return False
            self._record(node, "explored")
            self._bus.emit(node, EventKind.AGENT_VISIT, self._payload())

        elif self.state == State.INTERACT:
            if node.properties.get("has_puzzle"):
                solved, puzzle_name, difficulty = self._attempt_puzzle(node)
                if solved:
                    self._record(node, f"solved the puzzle ({puzzle_name})")
                    kind = EventKind.PUZZLE_SOLVED
                else:
                    self._record(node, f"failed the puzzle ({puzzle_name})")
                    kind = EventKind.PUZZLE_FAILED
                self._bus.propagate(node, kind, self._payload(
                    puzzle=puzzle_name, difficulty=difficulty))
            else:
                self._record(node, "interacted")
                self._bus.propagate(node, EventKind.AGENT_VISIT, self._payload())

        elif self.state == State.EXIT:
            if should_preserve(node, self.danger_threshold):
                self._record(node, f"withdrew (danger_level={node.properties.get('danger_level')})")
            else:
                self._record(node, "exited")
            return False

        return True

    @property
    def fresh_count(self) -> int:
        """Nodes added to memory during the most recent traverse() call."""
        return len(self.memory) - getattr(self, "_memory_before", 0)

    def traverse(self, node: SpatialNode, max_nodes: int = 50,
                 pace: float = 0.0) -> None:
        """Traverse the hierarchy rooted at `node`.

        `visited` is keyed by node NAME (stable across world rebuilds —
        node ids are per-process UUIDs) and seeded from accumulated memory
        so already-known nodes are naturally skipped. `max_nodes` bounds the
        number of FRESH visits this run, so a well-travelled agent keeps
        exploring new ground instead of exhausting its budget on memories.
        New visits are merged back into memory afterward. `pace` sleeps that
        many seconds between visits — used by the world heartbeat so a
        traversal unfolds over observable time instead of microseconds.
        """
        self.state = State.IDLE
        self.log = []
        self._memory_before = len(self.memory)
        self.visited = list(self.memory)
        self._fresh_budget = max_nodes
        self._fresh_used = 0
        self._pace = pace
        self._traverse(node)
        memory_set = set(self.memory)
        for name in self.visited:
            if name not in memory_set:
                self.memory.append(name)
                memory_set.add(name)

    def _traverse(self, node: SpatialNode) -> None:
        if self._fresh_used >= self._fresh_budget:
            return
        if node.name in self.visited:
            # Known ground: pass through without re-acting or spending fresh
            # budget, but keep exploring beneath it — except where this agent
            # would withdraw anyway.
            if should_preserve(node, self.danger_threshold):
                return
            for child in node.children:
                if self._fresh_used >= self._fresh_budget:
                    break
                self._traverse(child)
            return

        self.visited.append(node.name)
        self._fresh_used += 1
        self.state = transition(self.state, node, self.danger_threshold)
        should_descend = self._act(node)
        if self._pace:
            time.sleep(self._pace)

        if should_descend and self.state != State.EXIT:
            for child in node.children:
                if self._fresh_used >= self._fresh_budget:
                    break
                self._traverse(child)

    def report(self) -> str:
        fresh = self.fresh_count
        prior = len(self.memory) - fresh
        mem_note = f"{fresh} new" + (f" · {prior} previously known" if prior else "")
        persona_tag = f" [{self.persona.name}]" if self.persona else ""
        lines = [f"Agent '{self.name}'{persona_tag} traversal report ({len(self.log)} events · {mem_note}):"]
        for entry in self.log:
            lines.append(f"  [{entry.state.name:9}] {entry.level:20} {entry.node_name:30} → {entry.action}")
        return "\n".join(lines)
