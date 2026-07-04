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

MIN_STRENGTH: float = 0.05
DAMPENING: float = 0.6   # default per-depth attenuation factor


class CausalityBus:
    """Encapsulates handlers and event log for causal events.

    A bus instance is independent of any other.  The module exposes a default
    singleton (``_default``) plus convenience functions that delegate to it,
    so existing call sites work unchanged; the server and interface create
    their own buses for isolated observation runs.
    """

    def __init__(self) -> None:
        self._handlers: list[Handler] = []
        self._event_log: list[tuple[str, CausalEvent]] = []

    def register_handler(self, fn: Handler) -> None:
        self._handlers.append(fn)

    def clear_handlers(self) -> None:
        self._handlers.clear()

    def get_log(self) -> list[tuple[str, CausalEvent]]:
        return list(self._event_log)

    def clear_log(self) -> None:
        self._event_log.clear()

    def emit(self, node: SpatialNode, kind: EventKind,
             payload: dict[str, Any] | None = None) -> CausalEvent:
        """Create a full-strength event at *node* without propagating."""
        event = CausalEvent(
            kind=kind,
            origin_id=node.id,
            origin_level=node.level,
            strength=1.0,
            payload=payload or {},
        )
        self._fire(node, event)
        return event

    def propagate(self, origin: SpatialNode, kind: EventKind,
                  payload: dict[str, Any] | None = None,
                  dampening: float = 0.5,
                  direction: str = "both") -> CausalEvent:
        """Emit at *origin* and cascade across the hierarchy.

        `direction` is one of "down", "up", or "both" (default). Strength
        attenuates by `dampening` at each hop and the cascade halts when
        strength drops below `MIN_STRENGTH`.

        Origin fires exactly once even when direction is "both" — the
        downward and upward cascades only walk away from origin.
        """
        if direction not in ("down", "up", "both"):
            raise ValueError(f"direction must be down|up|both, got {direction!r}")

        event = CausalEvent(
            kind=kind,
            origin_id=origin.id,
            origin_level=origin.level,
            strength=1.0,
            payload=payload or {},
        )
        self._fire(origin, event)

        if direction in ("down", "both"):
            child_event = event.dampen(dampening)
            for child in origin.children:
                self._cascade_down(child, child_event, dampening)

        if direction in ("up", "both") and origin.parent is not None:
            parent_event = event.dampen(dampening)
            self._cascade_up(origin.parent, parent_event, dampening)

        return event

    def _fire(self, node: SpatialNode, event: CausalEvent) -> None:
        self._event_log.append((node.name, event))
        # `ripple_score` is the README's "cumulative causal pressure" field.
        # We accumulate proportional to the event's (already-dampened) strength
        # so deeper-reach events leave a fainter mark, then clamp to 1.0 so a
        # busy node never overflows the [0, 1] contract documented on the field.
        node.ripple_score = min(1.0, node.ripple_score + event.strength * 0.1)
        for handler in self._handlers:
            handler(node, event)

    def _cascade_down(self, node: SpatialNode, event: CausalEvent,
                      dampening: float) -> None:
        if event.strength < MIN_STRENGTH:
            return
        self._fire(node, event)
        child_event = event.dampen(dampening)
        for child in node.children:
            self._cascade_down(child, child_event, dampening)

    def _cascade_up(self, node: SpatialNode, event: CausalEvent,
                    dampening: float) -> None:
        if event.strength < MIN_STRENGTH:
            return
        self._fire(node, event)
        if node.parent is not None:
            parent_event = event.dampen(dampening)
            self._cascade_up(node.parent, parent_event, dampening)


# Default module-level bus.  Most code uses the convenience wrappers below;
# code that needs isolation (per-request observers, tests) should construct
# its own CausalityBus and pass it explicitly.
_default = CausalityBus()


def register_handler(fn: Handler) -> None:
    _default.register_handler(fn)


def clear_handlers() -> None:
    _default.clear_handlers()


def get_log() -> list[tuple[str, CausalEvent]]:
    return _default.get_log()


def clear_log() -> None:
    _default.clear_log()


def emit(node: SpatialNode, kind: EventKind,
         payload: dict[str, Any] | None = None) -> CausalEvent:
    return _default.emit(node, kind, payload)


def propagate(origin: SpatialNode, kind: EventKind,
              payload: dict[str, Any] | None = None,
              dampening: float = 0.5,
              direction: str = "both") -> CausalEvent:
    return _default.propagate(origin, kind, payload, dampening, direction)

