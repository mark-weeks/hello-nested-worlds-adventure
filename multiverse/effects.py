"""Causal events change the world's substance.

`apply_event_effects(node, event)` mutates `node.properties` in place
according to the event kind and (dampened) strength, and returns the dict
of properties that changed — or None when the event has no material effect
here. Callers persist the returned delta (see `causality.wiring`) so the
change survives the per-request world rebuild and every participant sees it.

Effects are deliberately small, legible, and bounded:

  PUZZLE_SOLVED      — the place settles: `stabilized: True`; if the node
                       carries a `danger_level`, it drops by 1 (floor 1).
                       A solved room puzzle therefore calms its region via
                       the first upward hop of the cascade.
  DANGER_ALERT       — the place roughens: `danger_level` rises by 1
                       (cap 10) where present, else `disturbed: True`.
  STRUCTURAL_CHANGE  — matter degrades: `condition` steps
                       pristine → worn → damaged → corrupted where present,
                       else `fractured: True`.
  SCALE_ACT          — no material change HERE: a scale-native verb's
                       property delta is applied exactly once, by the
                       producer (`multiverse/verbs.apply_verb`), because the
                       producer owns the flavor line. The cascade still
                       carries the act outward as ripple and history — you
                       mend the object you're holding; the molecule inside
                       it only feels the tremor.
  PUZZLE_FAILED /    — no material change (they still accrete in history
  AGENT_VISIT          and ripple pressure).

Only events at or above `EFFECT_THRESHOLD` strength change anything, so a
cascade's material reach is its origin plus roughly one hop — distant
echoes are felt (ripple, history) but do not rewrite distant places.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from multiverse.node import SpatialNode
    from causality import CausalEvent, EventKind

EFFECT_THRESHOLD: float = 0.3

_CONDITION_DECAY = {
    "pristine": "worn",
    "worn": "damaged",
    "damaged": "corrupted",
    "corrupted": "corrupted",
}

MAX_DANGER = 10
MIN_DANGER = 1


def compute_event_effects(props: dict[str, Any], kind: "EventKind",
                          strength: float) -> dict[str, Any] | None:
    """The pure transition: the material consequence an event of `kind` at
    `strength` has against the property state `props`. Returns the changed
    properties, or None if nothing changes. Pure over its inputs — the
    atomic write API calls this under its serialization lock against the
    LIVE overlay (ADR-009), so it must not read anything else."""
    from causality import EventKind

    if strength < EFFECT_THRESHOLD:
        return None

    changed: dict[str, Any] = {}

    if kind == EventKind.PUZZLE_SOLVED:
        if not props.get("stabilized"):
            changed["stabilized"] = True
        if isinstance(props.get("danger_level"), int) and props["danger_level"] > MIN_DANGER:
            changed["danger_level"] = props["danger_level"] - 1

    elif kind == EventKind.DANGER_ALERT:
        if isinstance(props.get("danger_level"), int):
            if props["danger_level"] < MAX_DANGER:
                changed["danger_level"] = props["danger_level"] + 1
        elif not props.get("disturbed"):
            changed["disturbed"] = True
        # Fresh unrest unsettles a previously stabilized place.
        if props.get("stabilized"):
            changed["stabilized"] = False

    elif kind == EventKind.STRUCTURAL_CHANGE:
        condition = props.get("condition")
        if condition in _CONDITION_DECAY:
            nxt = _CONDITION_DECAY[condition]
            if nxt != condition:
                changed["condition"] = nxt
        elif not props.get("fractured"):
            changed["fractured"] = True

    if not changed:
        return None
    return changed


def apply_event_effects(node: "SpatialNode", event: "CausalEvent") -> dict[str, Any] | None:
    """Apply `event`'s material consequence to `node` IN MEMORY. Returns the
    changed properties, or None if nothing changed. Persistence goes through
    the atomic write API, which recomputes the transition against the live
    overlay under its lock — this in-place form only keeps a request-local
    tree coherent (and serves the effects unit tests)."""
    changed = compute_event_effects(node.properties, event.kind, event.strength)
    if changed:
        node.properties.update(changed)
    return changed
