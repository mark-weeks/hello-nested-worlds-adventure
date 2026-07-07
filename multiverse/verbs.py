"""Scale-native verbs — the one thing you can only do at each scale.

Every level of the hierarchy has exactly one verb, and each verb is the
restorative / creative counterpart to the decay events in
`multiverse/effects.py`: STRUCTURAL_CHANGE corrodes objects, `mend`
repairs them; DANGER_ALERT roughens regions, `ward` calms them; the
world drifts toward entropy on its own and players push back one scale
at a time. That asymmetry is the point — you can only tend the world at
the scale you're standing in.

`apply_verb(node, verb, rng_token)` mutates `node.properties` in place
and returns `(changed, flavor)` — the property delta to persist (None
when the verb had nothing left to do) and a one-line in-fiction result.
It is called from the SCALE_ACT branch of `apply_event_effects`, so verb
consequences ride the standard causal rails: recorded in the chronicle,
rippled, persisted as a property overlay, staged across scales.

Determinism: verbs that need a "random" outcome (observe collapsing a
superposed spin) derive it from `rng_token`, a caller-supplied string
(actor + node), hashed — same world, same actor, same moment shape, same
collapse. No wall-clock, no global RNG.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from multiverse.node import SpatialNode


# ── Deep time ────────────────────────────────────────────────────────────────
# The cosmic scales answer on cosmic clocks: a verb performed at these
# levels records its act immediately, but the property change MATURES —
# it rides the durable verb_maturation queue and lands later, so kindling
# a galaxy is planting, not doing. The scale multiplier exists for tests
# and impatient operators; 0 makes every verb instant again.

MATURATION_ENV = "NESTED_WORLDS_MATURATION_SCALE"
MATURATION_SECONDS: dict[str, float] = {
    "Multiverse":        1800.0,
    "Universe":           900.0,
    "Galaxy":             300.0,
    "Planetary System":   120.0,
}


def maturation_seconds(level: str) -> float:
    """How long this level's verb takes to settle (0 = instant)."""
    base = MATURATION_SECONDS.get(level, 0.0)
    raw = os.environ.get(MATURATION_ENV, "").strip()
    if raw:
        try:
            return base * max(0.0, float(raw))
        except ValueError:
            pass
    return base


def maturation_note(seconds: float) -> str:
    """The in-fiction suffix for a planted (not yet landed) change."""
    if seconds >= 3600:
        span = f"{seconds / 3600:.0f} hour(s)"
    elif seconds >= 60:
        span = f"{seconds / 60:.0f} minute(s)"
    else:
        span = f"{seconds:.0f} second(s)"
    return (f" …but nothing at this scale is sudden: the change is still "
            f"traveling, and will settle in about {span}.")

_CONDITION_REPAIR = {
    "corrupted": "damaged",
    "damaged": "worn",
    "worn": "pristine",
    "pristine": "pristine",
}

_STABILITY_REPAIR = {
    "collapsing": "fraying",
    "fraying": "stable",
    "stable": "stable",
}


def _det_choice(token: str, options: list) -> Any:
    """Deterministic pick from options, keyed on the caller's token."""
    digest = hashlib.sha256(token.encode()).digest()
    return options[digest[0] % len(options)]


@dataclass(frozen=True)
class Verb:
    name: str            # imperative, what the player clicks
    level: str           # the only level it works at
    tagline: str         # UI hint: what it does, in-fiction
    effect: Callable[["SpatialNode", str], tuple[dict[str, Any] | None, str]]


def _attune(node: "SpatialNode", token: str):
    props = node.properties
    changed: dict[str, Any] = {}
    stability = props.get("stability")
    if stability in _STABILITY_REPAIR and _STABILITY_REPAIR[stability] != stability:
        changed["stability"] = _STABILITY_REPAIR[stability]
    if not props.get("attuned"):
        changed["attuned"] = True
    if not changed:
        return None, "The membranes are already in phase. The hum holds."
    state = changed.get("stability", stability)
    return changed, f"The membranes shiver into phase. The weave is {state}."


def _calibrate(node: "SpatialNode", token: str):
    props = node.properties
    ratio = props.get("dark_matter_ratio")
    changed: dict[str, Any] = {}
    if isinstance(ratio, (int, float)) and abs(ratio - 0.5) > 0.01:
        step = 0.05 if ratio < 0.5 else -0.05
        new = round(min(max(ratio + step, 0.0), 1.0), 2)
        if abs(new - 0.5) < abs(ratio - 0.5):
            changed["dark_matter_ratio"] = new
    if not props.get("calibrated"):
        changed["calibrated"] = True
    if not changed:
        return None, "The constants sit exactly where you would have put them."
    return changed, (
        "You lean on the constants until the vacuum stops arguing. "
        f"Dark matter settles at {changed.get('dark_matter_ratio', ratio)}."
    )


def _kindle(node: "SpatialNode", token: str):
    props = node.properties
    density = props.get("star_density")
    changed: dict[str, Any] = {}
    if isinstance(density, int) and density < 999:
        changed["star_density"] = min(999, density + max(1, density // 20))
    if not props.get("kindled"):
        changed["kindled"] = True
    if not changed:
        return None, "The galaxy is already burning as bright as it can."
    return changed, (
        f"New stars catch along the dust lanes — {changed.get('star_density', density)} "
        "points of light where there were fewer."
    )


def _align(node: "SpatialNode", token: str):
    props = node.properties
    tilt = props.get("ecliptic_tilt_deg")
    changed: dict[str, Any] = {}
    if isinstance(tilt, (int, float)) and tilt > 0.05:
        changed["ecliptic_tilt_deg"] = round(tilt * 0.9, 1)
    if not props.get("aligned"):
        changed["aligned"] = True
    if not changed:
        return None, "The orbits already move like clockwork. Nothing to correct."
    return changed, (
        "You nudge the resonance and the orbits close ranks — the ecliptic "
        f"flattens to {changed.get('ecliptic_tilt_deg', tilt)}°."
    )


def _seed(node: "SpatialNode", token: str):
    props = node.properties
    changed: dict[str, Any] = {}
    if not props.get("inhabited"):
        changed["inhabited"] = True
        changed["population"] = 10_000
        flavor = ("Something stirs in the shallows. Ten thousand small lives "
                  "begin keeping time with the tides.")
    else:
        pop = props.get("population")
        if isinstance(pop, int) and pop > 0:
            changed["population"] = pop + max(1, pop // 50)
            flavor = (f"The seeded ground answers. Population swells to "
                      f"{changed['population']:,}.")
        else:
            flavor = "Life here needs no more seeding."
    if not props.get("seeded"):
        changed["seeded"] = True
    if not changed:
        return None, flavor
    return changed, flavor


def _ward(node: "SpatialNode", token: str):
    props = node.properties
    danger = props.get("danger_level")
    changed: dict[str, Any] = {}
    if isinstance(danger, int) and danger > 1:
        changed["danger_level"] = danger - 1
    if not props.get("warded"):
        changed["warded"] = True
    if not changed:
        return None, "The ward lines are already drawn and holding."
    return changed, (
        "You walk the boundary and set the ward. The air eases — danger "
        f"falls to {changed.get('danger_level', danger)}."
    )


def _inscribe(node: "SpatialNode", token: str):
    props = node.properties
    count = props.get("inscriptions", 0)
    count = count if isinstance(count, int) else 0
    changed = {"inscriptions": count + 1}
    n = count + 1
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return changed, (
        f"You cut a line into the wall — the {n}{suffix} inscription this room "
        "has carried. Whoever comes next will read it."
    )


def _mend(node: "SpatialNode", token: str):
    props = node.properties
    condition = props.get("condition")
    changed: dict[str, Any] = {}
    if condition in _CONDITION_REPAIR and _CONDITION_REPAIR[condition] != condition:
        changed["condition"] = _CONDITION_REPAIR[condition]
    if props.get("fractured"):
        changed["fractured"] = False
    if not changed:
        return None, "Your hands find nothing to fix. It is already whole."
    state = changed.get("condition", condition)
    return changed, f"You work the damage backward. The material settles: {state}."


def _catalyze(node: "SpatialNode", token: str):
    props = node.properties
    bonds = props.get("bond_count")
    changed: dict[str, Any] = {}
    if isinstance(bonds, int) and bonds < 12:
        changed["bond_count"] = bonds + 1
    if not props.get("catalyzed"):
        changed["catalyzed"] = True
    if not changed:
        return None, "The lattice is saturated — no bond left to form."
    return changed, (
        f"The reaction takes. A new bond snaps into place — "
        f"{changed.get('bond_count', bonds)} now hold the shape."
    )


def _excite(node: "SpatialNode", token: str):
    props = node.properties
    changed: dict[str, Any] = {}
    if not props.get("ionized"):
        changed["ionized"] = True
    nm = props.get("resonance_nm")
    if isinstance(nm, (int, float)) and nm > 180.0:
        changed["resonance_nm"] = round(max(180.0, nm * 0.95), 1)
    if not changed:
        return None, "The electrons are already as high as they go."
    return changed, (
        "You pump the shell and the atom brightens, resonance shifting "
        f"blueward to {changed.get('resonance_nm', nm)} nm."
    )


def _observe(node: "SpatialNode", token: str):
    props = node.properties
    changed: dict[str, Any] = {}
    if props.get("spin") == "superposed":
        changed["spin"] = _det_choice(token, ["up", "down"])
    coherence = props.get("coherence")
    if isinstance(coherence, (int, float)) and coherence < 0.999:
        changed["coherence"] = round(min(0.999, coherence + 0.1), 3)
    if not props.get("observed"):
        changed["observed"] = True
    if not changed:
        return None, "It has been watched so long it no longer flinches."
    if "spin" in changed:
        flavor = (f"The particle feels itself being watched. The superposition "
                  f"folds: spin {changed['spin']}.")
    else:
        flavor = "Under your attention the waveform firms and holds."
    return changed, flavor


VERBS: dict[str, Verb] = {
    v.level: v for v in [
        Verb("attune",    "Multiverse",        "Bring the membranes into phase; repair fraying reality.", _attune),
        Verb("calibrate", "Universe",          "Nudge the physical constants toward balance.",            _calibrate),
        Verb("kindle",    "Galaxy",            "Ignite new stars along the dust lanes.",                  _kindle),
        Verb("align",     "Planetary System",  "Flatten the ecliptic; bring the orbits into resonance.",  _align),
        Verb("seed",      "Planet",            "Wake life on a barren world, or swell it where it holds.", _seed),
        Verb("ward",      "Region",            "Walk the boundary and lower the danger.",                 _ward),
        Verb("inscribe",  "Room",              "Cut a permanent mark for whoever comes next.",            _inscribe),
        Verb("mend",      "Object",            "Work the damage backward toward pristine.",               _mend),
        Verb("catalyze",  "Molecule",          "Coax a new bond into the lattice.",                       _catalyze),
        Verb("excite",    "Atom",              "Pump the shell; shift the glow blueward.",                _excite),
        Verb("observe",   "SubatomicParticle", "Collapse a superposed spin by watching it.",              _observe),
    ]
}

VERBS_BY_NAME: dict[str, Verb] = {v.name: v for v in VERBS.values()}


def verb_for_level(level: str) -> Verb | None:
    return VERBS.get(level)


def apply_verb(node: "SpatialNode", verb: Verb,
               token: str = "") -> tuple[dict[str, Any] | None, str]:
    """Apply *verb* to *node* (must match the node's level).

    Returns (changed, flavor): the property delta to persist (None if the
    verb had nothing left to do) and the in-fiction result line. Mutates
    node.properties in place when there is a change.
    """
    if verb.level != node.level:
        raise ValueError(f"{verb.name} only works at {verb.level}, not {node.level}")
    changed, flavor = verb.effect(node, token)
    if changed:
        node.properties.update(changed)
        # Weave the node's own character into the moment: the first clause
        # of its aspect makes the same verb read differently at every node.
        aspect = node.properties.get("aspect")
        if isinstance(aspect, str) and ";" in aspect:
            clause = aspect.split(";")[0].strip().rstrip(".")
            if clause:
                flavor = f"{flavor} {clause[0].upper()}{clause[1:]}."
    return changed, flavor
