from dataclasses import dataclass, field
from typing import List, Optional
from multiverse.node import SpatialNode
from agents.behaviors import DEFAULT_DANGER_THRESHOLD, State, transition, should_preserve
import causality
from causality import CausalityBus, EventKind


@dataclass
class AgentLog:
    node_name: str
    level: str
    state: State
    action: str


@dataclass
class Agent:
    name: str
    danger_threshold: int = DEFAULT_DANGER_THRESHOLD
    state: State = State.IDLE
    log: List[AgentLog] = field(default_factory=list)
    visited: List[str] = field(default_factory=list)
    bus: Optional[CausalityBus] = None

    @property
    def _bus(self) -> CausalityBus:
        return self.bus if self.bus is not None else causality._default

    def _record(self, node: SpatialNode, action: str) -> None:
        self.log.append(AgentLog(
            node_name=node.name,
            level=node.level,
            state=self.state,
            action=action,
        ))

    def _act(self, node: SpatialNode) -> bool:
        if self.state == State.EXPLORE:
            if should_preserve(node, self.danger_threshold):
                self._record(node, f"withdrew (danger_level={node.properties.get('danger_level')})")
                self._bus.emit(node, EventKind.DANGER_ALERT, {"agent": self.name})
                return False
            self._record(node, "explored")
            self._bus.emit(node, EventKind.AGENT_VISIT, {"agent": self.name})

        elif self.state == State.INTERACT:
            has_puzzle = node.properties.get("has_puzzle")
            detail = "interacted with puzzle" if has_puzzle else "interacted"
            self._record(node, detail)
            kind = EventKind.PUZZLE_SOLVED if has_puzzle else EventKind.AGENT_VISIT
            self._bus.propagate(node, kind, {"agent": self.name})

        elif self.state == State.EXIT:
            if should_preserve(node, self.danger_threshold):
                self._record(node, f"withdrew (danger_level={node.properties.get('danger_level')})")
            else:
                self._record(node, "exited")
            return False

        return True

    def traverse(self, node: SpatialNode, max_nodes: int = 50) -> None:
        """Reset agent state and traverse the hierarchy rooted at `node`."""
        self.state = State.IDLE
        self.log = []
        self.visited = []
        self._traverse(node, max_nodes)

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
        lines = [f"Agent '{self.name}' traversal report ({len(self.log)} events):"]
        for entry in self.log:
            lines.append(f"  [{entry.state.name:9}] {entry.level:20} {entry.node_name:30} → {entry.action}")
        return "\n".join(lines)
