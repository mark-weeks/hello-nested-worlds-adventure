from __future__ import annotations
import uuid
from typing import Any


class SpatialNode:
    def __init__(
        self,
        name: str,
        level: str,
        children: list[SpatialNode] | None = None,
        properties: dict[str, Any] | None = None,
    ) -> None:
        self.id: str = str(uuid.uuid4())
        self.name = name
        self.level = level
        self.children: list[SpatialNode] = []
        self.properties: dict[str, Any] = properties or {}
        # Upward link, set by `add_child` on the parent. None at the root.
        # Held as a weak-ish reference (plain attribute) — we never recurse
        # into it from `__repr__` or `_node_to_dict`, so no cycles in
        # serialization paths.
        self.parent: SpatialNode | None = None
        # Runtime state — mutated as the world evolves; not included in repr
        # so that deterministic generation tests are unaffected.
        self.ripple_score: float = 0.0        # 0.0–1.0 cumulative causal pressure

        # Children passed at construction need their parent set; do this via
        # `add_child` so the linkage is consistent with later additions.
        for child in (children or []):
            self.add_child(child)

    def add_child(self, node: SpatialNode) -> None:
        node.parent = self
        self.children.append(node)

    def __repr__(self, depth: int = 0) -> str:
        indent = "  " * depth
        props = ", ".join(f"{k}: {v}" for k, v in self.properties.items())
        repr_str = f"{indent}{self.level}: {self.name} [{props}]\n"
        for child in self.children:
            repr_str += child.__repr__(depth + 1)
        return repr_str
