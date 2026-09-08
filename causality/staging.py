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

from copy import copy
import os
from typing import Callable

import persistence
from causality import CausalEvent, CausalityBus, EventKind, MIN_STRENGTH
from causality.delivery import deliver_due
from causality.wiring import wire_world_handlers
from multiverse import store
from multiverse.node import SpatialNode
from multiverse.utils import find_node

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
                  dampening: float = STAGED_DAMPENING, *,
                  source_event_id: int | None = None) -> int:
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
    with persistence.transaction():
        enqueued = 0
        if origin.parent is not None:
            persistence.enqueue_causal_hop(
                seed, origin.parent.name, kind.name, 1.0, "up",
                hop_payload, delay, source_event_id=source_event_id)
            enqueued += 1
        for child in origin.children:
            persistence.enqueue_causal_hop(
                seed, child.name, kind.name, 1.0, "down",
                hop_payload, delay, source_event_id=source_event_id)
            enqueued += 1
        return enqueued



# broadcaster: (seed, node, event) -> None — the server passes a room
# broadcast so live players see each hop arrive; None outside the server.
Broadcaster = Callable[[int, SpatialNode, CausalEvent], None]


def _live_hop_node(root: SpatialNode, seed: int, name: str) -> SpatialNode | None:
    """Copy only the hop's ancestor chain; never mutate the cached born tree.

    Live overlays include the governing Universe's law. Loading this short
    chain under the lock preserves routing and broadcast state after another
    worker's commit, without rebuilding the world or sharing failed effects.
    Children supply immutable topology for continuation scheduling only.
    """
    born = find_node(root, name)
    node = child = None
    while born is not None:
        current = copy(born)
        current.properties = persistence.json_merge_patch(
            born.properties, persistence.load_node_property_override(seed, born.name))
        if child is None:
            node = current
            node.ripple_score = persistence.get_ripple_score(seed, name)
        else:
            child.parent = current
        child, born = current, born.parent
    return node


def _apply_hop(row: dict, notifications: list, root: SpatialNode) -> str:
    """v1 interpreter: same law physics, including pre-law legacy payloads."""
    seed = row["world_seed"]
    node = _live_hop_node(root, seed, row["node_name"])
    if node is None:
        return "missing_node"
    if row["direction"] not in ("up", "down"):
        raise ValueError("invalid causal direction")
    kind = EventKind[row["kind"]]
    payload = row["payload"]
    hop = payload.get("_hop")
    delay = hop_delay_seconds()
    if hop is None:
        arrived, tunneled, next_hop_payload = row["strength"], False, payload
        next_strength = row["strength"] * STAGED_DAMPENING
        next_delay = delay
    else:
        from causality.laws import hop_token, law_for
        law = law_for(node)
        origin_name = payload.get("_origin", node.name)
        if law is None:
            factor, tunneled = STAGED_DAMPENING, False
        else:
            token = hop_token(law, origin_name, node.name, hop)
            if law.drops(token):
                return "law_dropped"
            tunneled = law.tunnels(token)
            factor = 1.0 if tunneled else law.dampening(hop, row["direction"], token)
        arrived = row["strength"] * factor
        if arrived < MIN_STRENGTH:
            return "below_threshold"
        next_strength = arrived
        next_hop_payload = dict(payload)
        next_hop_payload["_hop"] = hop + 1
        next_delay = delay * (law.delay_scale if law else 1.0)

    if not tunneled:
        event = CausalEvent(
            kind=kind, origin_id=payload.get("_origin", node.name),
            origin_level=payload.get("_origin_level", node.level),
            strength=arrived,
            payload={**payload, "delivery": {"queue": "causal_queue", "id": row["id"]}})
        wire_world_handlers(CausalityBus(), seed).fire(node, event)
        event.recorded_id = persistence.latest_event_id(kind.name)
        notifications.append((seed, node, event))

    if next_strength >= MIN_STRENGTH:
        neighbors = ([node.parent] if row["direction"] == "up" and node.parent
                     else node.children if row["direction"] == "down" else [])
        for neighbor in neighbors:
            persistence.enqueue_causal_hop(
                seed, neighbor.name, row["kind"], next_strength,
                row["direction"], next_hop_payload, next_delay,
                parent_id=row["id"], source_event_id=row["source_event_id"])
    return "tunneled" if tunneled else "applied"


def drain_due_hops(limit: int = 64,
                   broadcaster: Broadcaster | None = None,
                   world_seed: int | None = None, *, broadcaster_batch=None) -> int:
    """Deliver a bounded candidate batch; each hop commits independently.

    Lost broadcasts do not retry committed effects. Reconnect/read APIs expose
    the authoritative overlay and chronicle. One bad item cannot lose a batch.
    """
    trees = {}

    def prepare(row):
        seed = row["world_seed"]
        if seed not in trees:
            trees[seed] = store.world_tree(seed=seed)

    return deliver_due(
        "causal_queue", limit, world_seed,
        lambda row, notifications: _apply_hop(row, notifications, trees[row["world_seed"]]),
        broadcaster, prepare=prepare, notify_batch=broadcaster_batch)
