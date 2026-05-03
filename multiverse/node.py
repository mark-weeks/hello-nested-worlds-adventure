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
        self.children: list[SpatialNode] = children or []
        self.properties: dict[str, Any] = properties or {}
        # Runtime state — mutated as the world evolves; not included in repr
        # so that deterministic generation tests are unaffected.
        self.ripple_score: float = 0.0        # 0.0–1.0 cumulative causal pressure
        self.interaction_summary: str = ""    # "conflict", "cooperation", etc.

    def add_child(self, node: SpatialNode) -> None:
        self.children.append(node)

    def __repr__(self, depth: int = 0) -> str:
        indent = "  " * depth
        props = ", ".join(f"{k}: {v}" for k, v in self.properties.items())
        repr_str = f"{indent}{self.level}: {self.name} [{props}]\n"
        for child in self.children:
            repr_str += child.__repr__(depth + 1)
        return repr_str
