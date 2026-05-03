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

    def _act(self, node: SpatialNode) -> bool:
        if self.state == State.EXPLORE:
            if should_preserve(node, self.danger_threshold):
                self._record(node, f"withdrew (danger_level={node.properties.get('danger_level')})")
                self._bus.emit(node, EventKind.DANGER_ALERT, self._payload())
                return False
            self._record(node, "explored")
            self._bus.emit(node, EventKind.AGENT_VISIT, self._payload())

        elif self.state == State.INTERACT:
            has_puzzle = node.properties.get("has_puzzle")
            detail = "interacted with puzzle" if has_puzzle else "interacted"
            self._record(node, detail)
            kind = EventKind.PUZZLE_SOLVED if has_puzzle else EventKind.AGENT_VISIT
            self._bus.propagate(node, kind, self._payload())

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

    def traverse(self, node: SpatialNode, max_nodes: int = 50) -> None:
        """Traverse the hierarchy rooted at `node`.

        visited is seeded from accumulated memory so already-known nodes are
        naturally skipped.  New visits are merged back into memory afterward.
        """
        self.state = State.IDLE
        self.log = []
        self._memory_before = len(self.memory)
        self.visited = list(self.memory)
        self._traverse(node, max_nodes)
        memory_set = set(self.memory)
        for nid in self.visited:
            if nid not in memory_set:
                self.memory.append(nid)
                memory_set.add(nid)

    def _traverse(self, node: SpatialNode, max_nodes: int) -> None:
        if len(self.visited) >= max_nodes:
            return
        if node.id in self.visited:
            return

        self.visited.append(node.id)
        self.state = transition(self.state, node, self.danger_threshold)
        should_descend = self._act(node)

        if should_descend and self.state != State.EXIT:
            for child in node.children:
                if len(self.visited) >= max_nodes:
                    break
                self._traverse(child, max_nodes)

    def report(self) -> str:
        fresh = self.fresh_count
        prior = len(self.memory) - fresh
        mem_note = f"{fresh} new" + (f" · {prior} previously known" if prior else "")
        persona_tag = f" [{self.persona.name}]" if self.persona else ""
        lines = [f"Agent '{self.name}'{persona_tag} traversal report ({len(self.log)} events · {mem_note}):"]
        for entry in self.log:
            lines.append(f"  [{entry.state.name:9}] {entry.level:20} {entry.node_name:30} → {entry.action}")
        return "\n".join(lines)
