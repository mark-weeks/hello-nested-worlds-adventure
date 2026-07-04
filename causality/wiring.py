"""Standard bus wiring: make causal events durable and material.

`wire_world_handlers(bus, seed)` registers the three handlers every
world-facing bus should carry, in order:

  1. record   — every fired event lands in `world_mutations` (node history,
                consciousness memory, image style signals).
  2. ripple   — each fire adds its dampened pressure to the node's persisted
                `ripple_score`, additively at the DB level so concurrent
                participants compound rather than overwrite.
  3. effects  — strong-enough events change node substance
                (multiverse/effects.py) and the delta persists as a property
                overlay, applied on top of generation at every rebuild.

Used by the HTTP server (`/agent`, `/observe`, puzzle solves), the world
heartbeat, and the CLI — one wiring, same rules for every participant.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import persistence
from causality import CausalEvent, CausalityBus
from multiverse.effects import apply_event_effects

if TYPE_CHECKING:
    from multiverse.node import SpatialNode

# Matches the accumulation constant in CausalityBus._fire.
RIPPLE_INCREMENT_PER_STRENGTH = 0.1


def make_record_handler(seed: int):
    """Persist each fired causal event into world_mutations.

    Agent-emitted events carry the agent name in `event.payload["agent"]`;
    the player_name slot is reserved for humans, so it stays None here.
    """
    def handler(node: "SpatialNode", event: CausalEvent) -> None:
        persistence.record_mutation(
            seed, node.name, event.kind.name, None, dict(event.payload)
        )
    return handler


def make_ripple_handler(seed: int):
    """Persist each fire's ripple contribution as an atomic increment."""
    def handler(node: "SpatialNode", event: CausalEvent) -> None:
        persistence.increment_ripple_score(
            seed, node.name, event.strength * RIPPLE_INCREMENT_PER_STRENGTH
        )
    return handler


def make_effects_handler(seed: int):
    """Apply and persist the event's material consequence, if any."""
    def handler(node: "SpatialNode", event: CausalEvent) -> None:
        changed = apply_event_effects(node, event)
        if changed:
            persistence.upsert_node_properties(seed, node.name, changed)
    return handler


def wire_world_handlers(bus: CausalityBus, seed: int) -> CausalityBus:
    """Register the standard record + ripple + effects handlers on `bus`."""
    bus.register_handler(make_record_handler(seed))
    bus.register_handler(make_ripple_handler(seed))
    bus.register_handler(make_effects_handler(seed))
    return bus
