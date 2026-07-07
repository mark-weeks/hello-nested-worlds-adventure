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
    SCALE_ACT = auto()       # a scale-native verb (multiverse/verbs.py)


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

    def fire(self, node: SpatialNode, event: CausalEvent) -> None:
        """Fire a pre-built event at *node* as-is (strength preserved).

        Used by staged cascades (causality/staging.py), where a hop built
        earlier — already dampened — arrives at its node after a delay and
        must fire without being reset to full strength.
        """
        self._fire(node, event)

    def propagate(self, origin: SpatialNode, kind: EventKind,
                  payload: dict[str, Any] | None = None,
                  dampening: float = 0.5,
                  direction: str = "both") -> CausalEvent:
        """Emit at *origin* and cascade across the hierarchy.

        `direction` is one of "down", "up", or "both" (default). Strength
        attenuates at each hop and the cascade halts when strength drops
        below `MIN_STRENGTH`.

        The physics of the walk come from the containing universe's law
        (causality/laws.py): dampening pattern, direction inversion,
        tunneling, drops. Where no universe holds the origin (the
        Multiverse root, synthetic trees), the caller's `dampening`
        applies uniformly — the pre-law contract, byte for byte. The law
        consulted at each hop is the law of the node the hop lands in, so
        a cascade crossing a universe boundary changes physics there.

        Origin fires exactly once even when direction is "both" — the
        downward and upward cascades only walk away from origin.
        """
        if direction not in ("down", "up", "both"):
            raise ValueError(f"direction must be down|up|both, got {direction!r}")

        from causality.laws import law_for

        event = CausalEvent(
            kind=kind,
            origin_id=origin.id,
            origin_level=origin.level,
            strength=1.0,
            payload=payload or {},
        )
        self._fire(origin, event)

        arms = {"down": ["down"], "up": ["up"], "both": ["down", "up"]}[direction]
        law = law_for(origin)
        if law is not None and law.flip:
            arms = [{"down": "up", "up": "down"}[a] for a in arms]

        for arm in arms:
            if arm == "down":
                for child in origin.children:
                    self._walk(child, event, "down", hop=1,
                               origin_name=origin.name, fallback=dampening)
            elif origin.parent is not None:
                self._walk(origin.parent, event, "up", hop=1,
                           origin_name=origin.name, fallback=dampening)

        return event

    def _walk(self, node: SpatialNode, prior: CausalEvent, arm: str,
              hop: int, origin_name: str, fallback: float) -> None:
        """One cascade step onto `node`: dampen by the local law (or the
        caller's fallback), maybe tunnel through, maybe drop, fire, and
        continue outward along the same arm."""
        from causality.laws import hop_token, law_for

        law = law_for(node)
        if law is None:
            factor, tunneled = fallback, False
        else:
            token = hop_token(law, origin_name, node.name, hop)
            if law.drops(token):
                return  # the thread frays; the cascade ends here
            tunneled = law.tunnels(token)
            factor = 1.0 if tunneled else law.dampening(hop, arm, token)
        event = prior.dampen(factor)
        if event.strength < MIN_STRENGTH:
            return
        if not tunneled:
            self._fire(node, event)
        if arm == "down":
            for child in node.children:
                self._walk(child, event, "down", hop + 1, origin_name, fallback)
        elif node.parent is not None:
            self._walk(node.parent, event, "up", hop + 1, origin_name, fallback)

    def _fire(self, node: SpatialNode, event: CausalEvent) -> None:
        self._event_log.append((node.name, event))
        # `ripple_score` is the README's "cumulative causal pressure" field.
        # We accumulate proportional to the event's (already-dampened) strength
        # so deeper-reach events leave a fainter mark, then clamp to 1.0 so a
        # busy node never overflows the [0, 1] contract documented on the field.
        node.ripple_score = min(1.0, node.ripple_score + event.strength * 0.1)
        for handler in self._handlers:
            handler(node, event)


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

