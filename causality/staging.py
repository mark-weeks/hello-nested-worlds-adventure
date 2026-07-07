"""Staged cascades: causality with delay.

A synchronous `propagate()` finishes an eleven-scale cascade in microseconds
— correct, but invisible. Staging spreads the same cascade over observable
time: the origin fires immediately (the solver gets instant feedback), and
each subsequent ring rides the durable `causal_queue`, fired by the causal
pump (server/heartbeat.py) after `NESTED_WORLDS_HOP_DELAY` seconds per hop.
A solve settles its room now, calms its region shortly, and reaches the
galaxy later — and every connected player watches it travel.

Same physics as the synchronous path: per-hop dampening (0.5, matching
`propagate()`'s default), the MIN_STRENGTH floor, and the standard
record/ripple/effects wiring at every hop — the end state of a staged
cascade is identical to a synchronous one; only its arrival times differ.
Hops are durable, so an in-flight cascade survives a restart and finishes
arriving afterwards.
"""
from __future__ import annotations

import os
from typing import Callable

import persistence
from causality import CausalEvent, CausalityBus, EventKind, MIN_STRENGTH
from causality.wiring import wire_world_handlers
from multiverse.generator import generate_node_hierarchy
from multiverse.node import SpatialNode
from multiverse.utils import (
    apply_property_overrides, apply_ripple_scores, find_node,
)

HOP_DELAY_ENV = "NESTED_WORLDS_HOP_DELAY"
_DEFAULT_HOP_DELAY = 12.0

# Matches causality.propagate()'s default so staged and synchronous cascades
# obey the same physics.
STAGED_DAMPENING = 0.5


def hop_delay_seconds() -> float:
    raw = os.environ.get(HOP_DELAY_ENV, "").strip()
    if not raw:
        return _DEFAULT_HOP_DELAY
    try:
        return max(0.0, float(raw))
    except ValueError:
        return _DEFAULT_HOP_DELAY


def stage_cascade(seed: int, origin: SpatialNode, kind: EventKind,
                  payload: dict | None = None,
                  dampening: float = STAGED_DAMPENING) -> int:
    """Schedule the first ring of a cascade around an already-fired origin.

    The caller fires the origin itself (immediate feedback for whoever
    caused it); this enqueues the origin's parent (upward arm) and children
    (downward arms) at FULL strength with the hop counter at 1 — each hop
    dampens itself on arrival under the law of the universe it lands in
    (causality/laws.py), so staged physics match the live bus exactly.
    (Direction inversion is a no-op here: staging always fires both arms,
    and flipping both arms of a both-ways cascade is the same cascade —
    Inverted physics only bites one-armed live propagation.) Returns hops
    enqueued.
    """
    from causality.laws import law_for

    hop_payload = dict(payload or {})
    hop_payload["_origin"] = origin.name
    hop_payload["_origin_level"] = origin.level
    hop_payload["_hop"] = 1
    law = law_for(origin)
    delay = hop_delay_seconds() * (law.delay_scale if law else 1.0)
    enqueued = 0
    if origin.parent is not None:
        persistence.enqueue_causal_hop(
            seed, origin.parent.name, kind.name, 1.0, "up",
            hop_payload, delay)
        enqueued += 1
    for child in origin.children:
        persistence.enqueue_causal_hop(
            seed, child.name, kind.name, 1.0, "down",
            hop_payload, delay)
        enqueued += 1
    return enqueued


# broadcaster: (seed, node, event) -> None — the server passes a room
# broadcast so live players see each hop arrive; None outside the server.
Broadcaster = Callable[[int, SpatialNode, CausalEvent], None]


def drain_due_hops(limit: int = 64,
                   broadcaster: Broadcaster | None = None) -> int:
    """Fire every due hop through the standard wiring; schedule next rings.

    Each fired hop records a mutation, adds ripple pressure, applies material
    effects, and (via `broadcaster`) reaches connected players — exactly what
    a synchronous cascade would have done at this node, just later. Returns
    the number of hops fired.
    """
    rows = persistence.claim_due_causal_hops(limit)
    if not rows:
        return 0

    worlds: dict[int, SpatialNode] = {}
    delay = hop_delay_seconds()
    fired = 0
    for row in rows:
        seed = row["world_seed"]
        if seed not in worlds:
            root = generate_node_hierarchy(seed=seed)
            apply_ripple_scores(root, persistence.load_ripple_scores(seed))
            apply_property_overrides(
                root, persistence.load_node_property_overrides(seed))
            worlds[seed] = root
        node = find_node(worlds[seed], row["node_name"])
        if node is None:
            continue  # world params changed under an in-flight hop; drop it

        payload = row["payload"]
        hop = payload.get("_hop")
        if hop is None:
            # Legacy row (queued before per-hop law physics): its strength
            # is already dampened — fire as-is, continue the old way.
            arrived, tunneled, next_hop_payload = row["strength"], False, payload
            next_strength = row["strength"] * STAGED_DAMPENING
            next_delay = delay
        else:
            # The hop dampens itself on arrival, under the law of the
            # universe it lands IN — staged physics match the live bus.
            from causality.laws import hop_token, law_for
            law = law_for(node)
            origin_name = payload.get("_origin", node.name)
            if law is None:
                factor, tunneled = STAGED_DAMPENING, False
            else:
                token = hop_token(law, origin_name, node.name, hop)
                if law.drops(token):
                    continue  # the thread frays; this arm ends here
                tunneled = law.tunnels(token)
                factor = 1.0 if tunneled else law.dampening(
                    hop, row["direction"], token)
            arrived = row["strength"] * factor
            if arrived < MIN_STRENGTH:
                continue
            next_strength = arrived
            next_hop_payload = dict(payload)
            next_hop_payload["_hop"] = hop + 1
            next_delay = delay * (law.delay_scale if law else 1.0)

        if not tunneled:
            event = CausalEvent(
                kind=EventKind[row["kind"]],
                origin_id=payload.get("_origin", node.name),
                origin_level=payload.get("_origin_level", node.level),
                strength=arrived,
                payload=payload,
            )
            bus = wire_world_handlers(CausalityBus(), seed)
            bus.fire(node, event)
            fired += 1
            if broadcaster is not None:
                broadcaster(seed, node, event)

        # The cascade continues outward in its committed direction.
        if next_strength >= MIN_STRENGTH:
            if row["direction"] == "up" and node.parent is not None:
                persistence.enqueue_causal_hop(
                    seed, node.parent.name, row["kind"], next_strength,
                    "up", next_hop_payload, next_delay)
            elif row["direction"] == "down":
                for child in node.children:
                    persistence.enqueue_causal_hop(
                        seed, child.name, row["kind"], next_strength,
                        "down", next_hop_payload, next_delay)
    return fired
