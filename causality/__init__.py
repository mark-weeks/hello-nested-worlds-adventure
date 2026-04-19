from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from multiverse.node import SpatialNode


class EventKind(Enum):
    PUZZLE_SOLVED = auto()
    PUZZLE_FAILED = auto()
    AGENT_VISIT = auto()
    DANGER_ALERT = auto()
    STRUCTURAL_CHANGE = auto()


@dataclass
class CausalEvent:
    kind: EventKind
    origin_id: str
    origin_level: str
    strength: float          # 0.0–1.0; attenuates with propagation depth
    payload: dict[str, Any] = field(default_factory=dict)

    def dampen(self, factor: float) -> CausalEvent:
        """Return a copy with strength reduced by factor."""
        return CausalEvent(
            kind=self.kind,
            origin_id=self.origin_id,
            origin_level=self.origin_level,
            strength=self.strength * factor,
            payload=dict(self.payload),
        )


# Signature: (node: SpatialNode, event: CausalEvent) -> None
Handler = Callable[["SpatialNode", CausalEvent], None]

_MIN_STRENGTH: float = 0.05
_handlers: list[Handler] = []
_event_log: list[tuple[str, CausalEvent]] = []


def register_handler(fn: Handler) -> None:
    """Register a callback invoked for every causal event that reaches a node."""
    _handlers.append(fn)


def clear_handlers() -> None:
    _handlers.clear()


def get_log() -> list[tuple[str, CausalEvent]]:
    """Return a snapshot of all (node_name, event) pairs recorded so far."""
    return list(_event_log)


def clear_log() -> None:
    _event_log.clear()


def emit(node: SpatialNode, kind: EventKind, payload: dict[str, Any] | None = None) -> CausalEvent:
    """Create a full-strength event at *node* without propagating to children."""
    event = CausalEvent(
        kind=kind,
        origin_id=node.id,
        origin_level=node.level,
        strength=1.0,
        payload=payload or {},
    )
    _fire(node, event)
    return event


def propagate(
    origin: SpatialNode,
    kind: EventKind,
    payload: dict[str, Any] | None = None,
    dampening: float = 0.5,
) -> CausalEvent:
    """Emit an event at *origin* at full strength, then cascade it downward
    through all descendants.  Strength is multiplied by *dampening* at each
    additional depth level; propagation halts when strength < _MIN_STRENGTH.
    """
    event = CausalEvent(
        kind=kind,
        origin_id=origin.id,
        origin_level=origin.level,
        strength=1.0,
        payload=payload or {},
    )
    _cascade(origin, event, dampening)
    return event


def _fire(node: SpatialNode, event: CausalEvent) -> None:
    _event_log.append((node.name, event))
    for handler in _handlers:
        handler(node, event)


def _cascade(node: SpatialNode, event: CausalEvent, dampening: float) -> None:
    if event.strength < _MIN_STRENGTH:
        return
    _fire(node, event)
    child_event = event.dampen(dampening)
    for child in node.children:
        _cascade(child, child_event, dampening)
