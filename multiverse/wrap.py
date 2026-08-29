"""The wrap passage — the hierarchy closes into a loop (ADR-008).

Traversal layer ONLY. Descending below ANY SubatomicParticle surfaces at
the Multiverse root (every part enfolds the whole — a property of matter,
not of one special place); ascending beyond the root lands at ONE hinge
particle, the same monument for every participant. Parent/child links are
never mutated to express the loop: everything that walks `node.parent`
expecting a finite chain (`causality.laws.law_for`, `puzzles.gates
.sealing_room`, the lineage puzzle families, `__repr__`) is untouched by
construction, and causality does not wrap — cascades still terminate at
the root and at leaves.

The hinge is chosen ONCE per world by `_select_hinge` — a pure function
of (seed, world as born): it reads only the stored `world_nodes` rows, so
a fresh install of the same seed selects the same particle, and no
wall-clock or entropy enters the choice. The selection is constrained to
a fully unsealed lineage (no locked Room among the hinge's ancestors) as
a LIVENESS invariant: a root-side traveler arrives from outside every
seal on that lineage, so a sealed hinge would ship the loop dead in one
direction — on seed 382, 706 of 1,505 particles (46.9%) sit beneath a
locked Room and are ineligible. Among the eligible, worthiness prefers
the particles that already speak the loop's own physics — an entangled
or recurring tendency, a superposed spin, high coherence — so the
monument's born character carries its role.

At first selection the hinge is pinned immutably in `world_meta`, and
from then on THE STORED HINGE IS THE HINGE — mirroring the store's
born-row-is-identity rule. Nothing in application code may re-select or
rewrite it: once crossings, lore, and player memory attach to the hinge,
an edited selector must not silently move the monument (pinned by
tests/test_wrap_passage.py::TestSelectorEditImmunity). Changing a pinned
hinge is an ADR-level continuity decision.
"""
from __future__ import annotations

import hashlib
import json

import persistence
from multiverse.node import SpatialNode

HINGE_META_KEY = "wrap_hinge"

# Authored surfaces of the crossing — the world's voice, never
# mechanism-speak (the fiction covenant). Both clients speak these same
# lines; the first crossing in a session gets the full line.
DESCENT_LINE = (
    "You lean into the particle, and the particle does not end. It opens — "
    "and the whole of everything is already there, enfolded, the way it "
    "always was."
)
ASCENT_LINE = (
    "You pass beyond the last membrane. There is no outside. There is a "
    "particle — and everything you just left is inside it."
)

# Passage labels — what the affordance says before the step is taken.
DESCENT_PASSAGE = "the way inward opens onto the whole"
ASCENT_PASSAGE = "the way beyond narrows to a single particle"


def wraps_inward(node: SpatialNode) -> bool:
    """Does descending below `node` surface at the Multiverse root?"""
    return node.level == "SubatomicParticle"


def wraps_outward(node: SpatialNode) -> bool:
    """Does ascending beyond `node` land at the hinge particle?"""
    return node.level == "Multiverse"


# Worthiness weights, tuned before the first pinning (never after — the
# pin, not this function, is the hinge's identity from then on). On seed
# 382 the rule lands on Hidden Thorn Quark-11431112111: entangled,
# superposed, coherence 0.988, its Room ancestor unlocked.
_TENDENCY_BONUS = 1.0    # entangled / recurring: the loop's own vocabulary
_SPIN_BONUS = 0.5        # superposed: both directions at once


def _worthiness(properties: dict) -> float:
    score = float(properties.get("coherence") or 0.0)
    if properties.get("tendency") in ("entangled", "recurring"):
        score += _TENDENCY_BONUS
    if properties.get("spin") == "superposed":
        score += _SPIN_BONUS
    return score


def _tiebreak(seed: int, path: str) -> str:
    return hashlib.sha256(f"wrap-hinge-v1:{seed}:{path}".encode("utf-8")).hexdigest()


def _select_hinge(seed: int) -> str:
    """The seed-pure selection: the worthiest particle on an unsealed
    lineage, from the world AS BORN. Runs once per world, at pin time.

    Reads only stored rows — never the banks, never the clock — so the
    same born world always yields the same name, whenever and wherever
    the selection first runs.
    """
    from multiverse import store

    store.ensure_born(seed)
    rows = persistence.get_world_nodes(seed)
    locked_room_paths = [
        path for path, _name, level, props_json, _b in rows
        if level == "Room" and json.loads(props_json).get("locked")
    ]
    candidates = []
    for path, name, level, props_json, _breadth in rows:
        if level != "SubatomicParticle":
            continue
        if any(path.startswith(room_path + ".") for room_path in locked_room_paths):
            continue  # liveness: no seal may stand between root and hinge
        candidates.append((path, name, json.loads(props_json)))
    if not candidates:
        # Structurally near-impossible (every Room in the world locked);
        # a world that cannot satisfy the liveness invariant must be loud,
        # not quietly pinned dead.
        raise RuntimeError(f"world {seed} has no unsealed particle lineage")
    best_path, best_name, _ = min(
        candidates,
        key=lambda c: (-_worthiness(c[2]), _tiebreak(seed, c[0])),
    )
    return best_name


def hinge_name(seed: int) -> str:
    """The world's hinge particle name — pinned at first ask, stored forever.

    The pin is write-once and race-safe (`persistence.pin_world_meta`):
    concurrent first askers converge on one durable value, and from then
    on the stored name is returned without consulting the selector at all.
    """
    pinned = persistence.get_world_meta(seed, HINGE_META_KEY)
    if pinned is not None:
        return pinned
    return persistence.pin_world_meta(seed, HINGE_META_KEY, _select_hinge(seed))


def is_hinge(seed: int, node_name: str) -> bool:
    return node_name == hinge_name(seed)
