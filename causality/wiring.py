"""Standard bus wiring: make causal events durable and material.

`wire_world_handlers(bus, seed)` registers the two handlers every
world-facing bus should carry, in order:

  1. substance — every fired event lands in `world_mutations` with its
                 strength (node history, consciousness memory, image style
                 signals), and when the event materially changes the node
                 (multiverse/effects.py) the SAME row carries the property
                 delta and lands atomically with the overlay application
                 (persistence.record_substance_change, ADR-009).
  2. ripple    — each fire adds its dampened pressure to the node's
                 persisted `ripple_score`, additively at the DB level so
                 concurrent participants compound rather than overwrite.
                 Deliberately OUTSIDE the atomic transaction: the score is
                 a derived cache, rebuildable from chronicled strengths
                 (persistence.rebuild_ripple_scores).

Used by the HTTP server (`/agent`, `/observe`, puzzle solves), the world
heartbeat, and the CLI — one wiring, same rules for every participant.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import persistence
from causality import CausalEvent, CausalityBus

# Matches the accumulation constant in CausalityBus._fire; the authoritative
# copy lives beside the ripple rebuild fold in persistence.
from persistence import RIPPLE_INCREMENT_PER_STRENGTH  # noqa: F401 — re-export

from multiverse.effects import apply_event_effects

if TYPE_CHECKING:
    from multiverse.node import SpatialNode


def make_substance_handler(seed: int, record: bool = True):
    """Chronicle each fired event and apply its material consequence.

    One fired event carries strength on exactly ONE chronicle row — that is
    what makes the persisted ripple_score a pure fold of the record:

    * record=True — every event appends a row with its kind, payload, and
      strength; a material change rides the same row as a delta, atomic
      with the overlay application.
    * record=False — the producer already wrote the event's attributed
      origin row (stamped with `causality.ORIGIN_STRENGTH`); this handler
      writes nothing for an immaterial event. A material consequence still
      must be chronicled atomically with its application, so it lands as an
      EVENT_EFFECT row carrying the triggering kind and the delta — with no
      strength of its own, because the strength already rides the
      producer's row.

    Decay that materially changes a node whose current puzzle is already
    solved also RE-ARMS the puzzle: a PUZZLE_REARM row increments the
    node's puzzle epoch, and the next /puzzle build serves a fresh,
    renamed, unsolved variant. This is the world's renewal loop — entropy
    doesn't just corrode, it re-opens challenges the last cohort finished,
    so the permanent world never runs out of puzzles.
    """
    from causality import EventKind

    def handler(node: "SpatialNode", event: CausalEvent) -> None:
        changed = apply_event_effects(node, event)
        if record:
            if changed:
                persistence.record_substance_change(
                    seed, node.name, event.kind.name, None,
                    dict(event.payload), changed, strength=event.strength)
            else:
                persistence.record_mutation(
                    seed, node.name, event.kind.name, None,
                    dict(event.payload), strength=event.strength)
        elif changed:
            persistence.record_substance_change(
                seed, node.name, "EVENT_EFFECT", None,
                {"kind": event.kind.name, **event.payload}, changed)
        if changed and event.kind in (EventKind.DANGER_ALERT,
                                      EventKind.STRUCTURAL_CHANGE):
            solves = persistence.count_node_mutations(
                seed, node.name, "PUZZLE_SOLVED")
            rearms = persistence.count_node_mutations(
                seed, node.name, "PUZZLE_REARM")
            if solves > rearms:
                persistence.record_mutation(
                    seed, node.name, "PUZZLE_REARM", None,
                    {"trigger": event.kind.name,
                     "agent": event.payload.get("agent")})
    return handler


def make_ripple_handler(seed: int):
    """Persist each fire's ripple contribution as an atomic increment."""
    def handler(node: "SpatialNode", event: CausalEvent) -> None:
        persistence.increment_ripple_score(
            seed, node.name, event.strength * RIPPLE_INCREMENT_PER_STRENGTH
        )
    return handler


def wire_world_handlers(bus: CausalityBus, seed: int,
                        record: bool = True) -> CausalityBus:
    """Register the standard substance + ripple handlers on `bus`.

    `record=False` marks a producer-owned origin: producers that write
    their own attributed row for the origin event (POST /act,
    /puzzle/attempt, the CLI equivalents, constellation lighting) pass
    False so each event lands in the chronicle exactly once — with
    attribution and the origin strength — instead of twice (one
    attributed, one anonymous, which also double-counted the art's
    activity marks). The substance handler still chronicles any material
    consequence of such an event (as EVENT_EFFECT — see
    make_substance_handler). Staged rings drained by the pump always
    record: their hop rows are the only chronicle trace those nodes get.
    """
    bus.register_handler(make_substance_handler(seed, record))
    bus.register_handler(make_ripple_handler(seed))
    return bus
