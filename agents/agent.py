from dataclasses import dataclass, field
from typing import List
from multiverse.node import SpatialNode
from agents.behaviors import State, transition, should_avoid


@dataclass
class AgentLog:
    node_name: str
    level: str
    state: State
    action: str


@dataclass
class Agent:
    name: str
    danger_threshold: int = 6
    state: State = State.IDLE
    log: List[AgentLog] = field(default_factory=list)
    visited: List[str] = field(default_factory=list)

    def _record(self, node: SpatialNode, action: str) -> None:
        self.log.append(AgentLog(
            node_name=node.name,
            level=node.level,
            state=self.state,
            action=action,
        ))

    def _act(self, node: SpatialNode) -> bool:
        if self.state == State.EXPLORE:
            if should_avoid(node, self.danger_threshold):
                self._record(node, f"avoided (danger_level={node.properties.get('danger_level')})")
                return False
            self._record(node, "explored")

        elif self.state == State.INTERACT:
            detail = "solved puzzle" if node.properties.get("has_puzzle") else "interacted"
            self._record(node, detail)

        elif self.state == State.EXIT:
            if should_avoid(node, self.danger_threshold):
                self._record(node, f"avoided (danger_level={node.properties.get('danger_level')})")
            else:
                self._record(node, "exited")
            return False

        return True

    def traverse(self, node: SpatialNode, max_nodes: int = 50) -> None:
        """Reset agent state and traverse the hierarchy rooted at `node`."""
        self.state = State.IDLE
        self.log = []
        self.visited = []
        self._traverse(node, max_nodes, depth=0)

    def _traverse(self, node: SpatialNode, max_nodes: int, depth: int) -> None:
        if len(self.visited) >= max_nodes or depth > 500:
            return
        if node.id in self.visited:
            return

        self.visited.append(node.id)
        self.state = transition(self.state, node)
        should_descend = self._act(node)

        if should_descend and self.state != State.EXIT:
            for child in node.children:
                if len(self.visited) >= max_nodes:
                    break
                self._traverse(child, max_nodes, depth + 1)

    def report(self) -> str:
        lines = [f"Agent '{self.name}' traversal report ({len(self.log)} events):"]
        for entry in self.log:
            lines.append(f"  [{entry.state.name:9}] {entry.level:20} {entry.node_name:30} → {entry.action}")
        return "\n".join(lines)
