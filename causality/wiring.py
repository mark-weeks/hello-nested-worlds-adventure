"""Standard bus wiring: make causal events durable and material.

`wire_world_handlers(bus, seed)` registers the handlers every world-facing
bus should carry:

  1. substance — every fired event lands in `world_mutations` with its
                 strength (node history, consciousness memory, image style
                 signals); when the event materially changes the node, the
                 SAME row carries the property delta and lands atomically
                 with the overlay application. The delta is recomputed
                 against the LIVE overlay under the write lock
                 (persistence.record_substance_transition, ADR-009), so
                 concurrent transitions serialize instead of chronicling
                 stale changes.
  2. ripple    — each fire adds its dampened pressure to the node's
                 persisted `ripple_score`, additively at the DB level so
                 concurrent participants compound rather than overwrite.
                 Deliberately OUTSIDE the atomic transaction: the score is
                 a derived cache, rebuildable from chronicled strengths
                 (persistence.rebuild_ripple_scores).

Producers that own their origin event's attributed chronicle row wire
`record=False` (ripple only) and write that row through the producer
helpers below — `record_origin_event` for event-effect origins,
`record_verb_act` for the scale-verb immediate branch — so the attributed
row, its delta, and the overlay change always commit as one transaction.

Used by the HTTP server (`/agent`, `/observe`, puzzle solves), the world
heartbeat, and the CLI — one wiring, same rules for every participant.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import persistence
from causality import ORIGIN_STRENGTH, CausalEvent, CausalityBus, EventKind

# Matches the accumulation constant in CausalityBus._fire; the authoritative
# copy lives beside the ripple rebuild fold in persistence.
from persistence import RIPPLE_INCREMENT_PER_STRENGTH  # noqa: F401 — re-export

from multiverse.effects import compute_event_effects

if TYPE_CHECKING:
    from multiverse.node import SpatialNode
    from multiverse.verbs import Verb


def _maybe_rearm(seed: int, node_name: str, kind: EventKind,
                 payload: dict) -> None:
    """Decay that materially changes a node whose current puzzle is already
    solved RE-ARMS the puzzle: a PUZZLE_REARM row increments the node's
    puzzle epoch, and the next /puzzle build serves a fresh, renamed,
    unsolved variant. This is the world's renewal loop — entropy doesn't
    just corrode, it re-opens challenges the last cohort finished, so the
    permanent world never runs out of puzzles."""
    if kind not in (EventKind.DANGER_ALERT, EventKind.STRUCTURAL_CHANGE):
        return
    solves = persistence.count_node_mutations(seed, node_name, "PUZZLE_SOLVED")
    rearms = persistence.count_node_mutations(seed, node_name, "PUZZLE_REARM")
    if solves > rearms:
        persistence.record_mutation(
            seed, node_name, "PUZZLE_REARM", None,
            {"trigger": kind.name, "agent": payload.get("agent")})


def make_substance_handler(seed: int):
    """Chronicle each fired event and apply its material consequence.

    One row per fired event, carrying its strength; a material change rides
    the same row as a delta, atomic with the overlay application. The
    transition is recomputed under the serialization lock against the node's
    live overlay — the request-local snapshot only seeds the base state, so
    two concurrent danger alerts from danger 5 chronicle 6 then 7, never 6
    twice. The applied delta is folded back into the in-memory node so the
    rest of the request (later cascade hops, the response) stays coherent.
    """
    def handler(node: "SpatialNode", event: CausalEvent) -> None:
        base = dict(node.properties)

        def compute(live_overlay: dict) -> dict | None:
            current = persistence.json_merge_patch(base, live_overlay)
            return compute_event_effects(current, event.kind, event.strength)

        changed = persistence.record_substance_transition(
            seed, node.name, event.kind.name, None, dict(event.payload),
            compute, strength=event.strength)
        if changed:
            node.properties.update(changed)
            _maybe_rearm(seed, node.name, event.kind, event.payload)
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

    `record=False` wires ripple only: producers that own the origin event
    write its one attributed chronicle row — with the origin strength, and
    with any material delta, atomically — through `record_origin_event` /
    `record_verb_act` BEFORE emitting (POST /act, /puzzle/attempt, the CLI
    equivalents, constellation lighting), so each event lands in the
    chronicle exactly once, attributed, never as a second anonymous copy
    (which also double-counted the art's activity marks). Staged rings
    drained by the pump always record: their hop rows are the only
    chronicle trace those nodes get.
    """
    if record:
        bus.register_handler(make_substance_handler(seed))
    bus.register_handler(make_ripple_handler(seed))
    return bus


def record_origin_event(seed: int, node: "SpatialNode", kind: EventKind,
                        data: dict, *, player_name: str | None = None,
                        actor_identity: str | None = None) -> dict | None:
    """A producer-owned origin event's one canonical chronicle write.

    Under the serialization lock, recomputes the event's material
    consequence (multiverse/effects.py) against the live overlay and lands
    the attributed row — kind, `data`, ORIGIN_STRENGTH, and the delta +
    node_version when material — plus the overlay change, in ONE
    transaction. A crash leaves neither the row nor the change, so a
    canonical solve can never outlive its lost delta. Folds the applied
    delta into the in-memory node and returns it (None if immaterial).
    The caller then emits on a `record=False` bus for ripple + broadcast.
    """
    base = dict(node.properties)

    def compute(live_overlay: dict) -> dict | None:
        current = persistence.json_merge_patch(base, live_overlay)
        return compute_event_effects(current, kind, ORIGIN_STRENGTH)

    changed = persistence.record_substance_transition(
        seed, node.name, kind.name, player_name, data, compute,
        strength=ORIGIN_STRENGTH, actor_identity=actor_identity)
    if changed:
        node.properties.update(changed)
    return changed


def record_verb_act(seed: int, node: "SpatialNode", verb: "Verb",
                    token: str, base_props: dict, act_data: dict, *,
                    player_name: str | None = None,
                    actor_identity: str | None = None) -> dict | None:
    """The scale-verb immediate branch's one canonical chronicle write.

    Verb deltas are transitions of current state (danger falls by one, the
    inscription count increments), so the delta chronicled must be derived
    from the state it applies to: under the serialization lock the verb's
    effect is re-derived against `base_props` (the node's properties BEFORE
    the producer's optimistic apply_verb) merged under the live overlay,
    and the attributed SCALE_ACT row + overlay change land in one
    transaction, stamped ORIGIN_STRENGTH. Folds the authoritative delta
    into the in-memory node and returns it (None if, against live state,
    the verb had nothing left to do — the act row still lands).
    """
    def compute(live_overlay: dict) -> dict | None:
        current = persistence.json_merge_patch(dict(base_props), live_overlay)
        changed, _flavor = verb.effect(
            SimpleNamespace(properties=current, level=node.level), token)
        return changed

    changed = persistence.record_substance_transition(
        seed, node.name, "SCALE_ACT", player_name, act_data, compute,
        strength=ORIGIN_STRENGTH, actor_identity=actor_identity)
    if changed:
        node.properties.update(changed)
    return changed
