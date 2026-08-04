# multiverse/generator.py
#
# Canonical world generation: every node is a pure function of
# (world seed, path-from-root). Each node derives its own RNG from a
# SHA-256 of (seed, path, domain). Names, properties, and child counts use
# independent deterministic domains — never a shared sequential stream.
# Consequences:
#
#   * PREFIX STABILITY. A tree generated at max_depth=6 is exactly the
#     top of the tree generated at max_depth=11 for the same seed and
#     breadth bounds — same names, same properties, same branching.
#     Every client and endpoint that regenerates "the world" therefore
#     agrees on node identity, and persistence keyed on
#     (seed, node_name) refers to the same place everywhere.
#   * STABLE, READABLE, UNIQUE NAMES. A curated semantic grammar makes the
#     base phrase readable and assigns it injectively within each level. The
#     suffix encodes the node's path
#     (root is "1", its second child "12", that child's first child
#     "121"), so names are unique within a world and identical across
#     rebuilds at any depth. Breadth is capped at 9 so path digits are
#     unambiguous.

import hashlib
import random
from math import gcd
from typing import Callable

from multiverse.node import SpatialNode

DEFAULT_WORLD_SEED = 382

LEVELS = [
    "Multiverse",
    "Universe",
    "Galaxy",
    "Planetary System",
    "Planet",
    "Region",
    "Room",
    "Object",
    "Molecule",
    "Atom",
    "SubatomicParticle",
]

# How many children a node at each level generates (inclusive range, one
# rng.randint draw per node — the draw itself is part of the frozen stream).
# The profile is level-shaped rather than uniform: wide at the cosmic
# shells, where every extra universe or galaxy multiplies the distinctness
# of everything beneath it (uniform 1-3 produced single-universe worlds in
# 88 of 300 seeds — one physics for all existence — and worlds as small as
# 46 nodes); plural rooms, because rooms are the human scale; tapered
# below Object, where uniform breadth spent 88% of the world on the
# least-visited shells. Floors of 2-3 at the top make degenerate worlds
# structurally impossible (minimum world ≈ 2.4k nodes, always 3+
# universes). Part of the FROZEN surface below: changing any range after
# first production deploy deletes and spawns subtrees in every existing
# world. tests/test_continuity_freeze.py pins this profile exactly.
BREADTH_BY_LEVEL: dict[str, tuple[int, int]] = {
    "Multiverse":        (3, 4),
    "Universe":          (3, 4),
    "Galaxy":            (2, 3),
    "Planetary System":  (2, 2),
    "Planet":            (2, 2),
    "Region":            (2, 2),
    "Room":              (1, 2),
    "Object":            (1, 2),
    "Molecule":          (1, 2),
    "Atom":              (1, 2),
    "SubatomicParticle": (1, 2),  # leaf level — drawn, never used
}

# The profile's outer bounds — descriptive, for records like the worlds
# table; the per-level ranges above are what generation actually uses.
BREADTH_ENVELOPE = (min(lo for lo, _ in BREADTH_BY_LEVEL.values()),
                    max(hi for _, hi in BREADTH_BY_LEVEL.values()))

_BIOMES = ["tundra", "jungle", "desert", "ocean", "volcanic", "temperate", "irradiated",
           "mangrove", "glacial", "fungal", "salt flat", "cloud forest",
           "basalt waste", "reef shallows", "grassland"]
_FACTIONS = ["The Conclave", "Iron Veil", "Drifters", "Null Cult", "Reclaimer Order",
             "Lanternwrights", "The Unnumbered", "Verge Assembly", "Saltborn",
             "Chorus of Nine", "Emberkeep", "The Quiet Ledger"]


def _pick(pool: list, rng: random.Random) -> str:
    return rng.choice(pool)


# ── Semantic names (generator v2) ──────────────────────────────────────────
# A launch-world node must have a name a person can read, remember, and repeat.
# Invented syllables failed that bar even when their path suffix made them
# technically unique. V2 names are three curated English words:
#
#     <qualifier> <motif> <level form>-<path>
#
# There are 24 × 24 × 12 = 6,912 phrases per level. The widest possible level
# under BREADTH_BY_LEVEL contains 6,144 nodes. `_path_ordinal` maps every path
# at a level to a different integer, then a seed-and-level-specific affine
# permutation assigns that integer a phrase. Because the multiplier is
# coprime to the name-space size, the mapping is injective: base names are
# guaranteed unique, not merely likely to be unique. Every level has disjoint
# form words, so base names cannot collide across levels either.
#
# These banks govern births only (ADR-006). Editing them changes future births,
# never a materialized world. Such an edit still requires a generator-version
# bump, deliberate golden re-pin, and changelog entry.

NAME_QUALIFIERS = (
    "Amber", "Ashen", "Azure", "Bright", "Broken", "Cedar", "Distant",
    "Elder", "Emberlit", "Fallow", "Glass", "Golden", "Hidden", "Hollow",
    "Iron", "Last", "Lucent", "Mossbound", "Pale", "Quiet", "Silver",
    "Still", "Verdant", "Weathered",
)

NAME_MOTIFS = (
    "Anchor", "Bell", "Bloom", "Cinder", "Compass", "Crown", "Dawn",
    "Echo", "Ember", "Frost", "Garden", "Lantern", "Moon", "Orchard",
    "Pilgrim", "Rain", "Reed", "River", "Salt", "Shadow", "Star", "Tide",
    "Thorn", "Willow",
)

NAME_FORMS: dict[str, tuple[str, ...]] = {
    "Multiverse": (
        "Expanse", "Continuum", "Tapestry", "Totality", "Infinity",
        "Manifold", "Firmament", "Cosmos", "Beyond", "Vastness", "Whole",
        "Horizon",
    ),
    "Universe": (
        "Realm", "Creation", "Sphere", "Dominion", "Province", "Vault",
        "Testament", "Weave", "Dream", "Age", "Canopy", "Volume",
    ),
    "Galaxy": (
        "Spiral", "Wheel", "Stream", "Halo", "Array", "Swarm", "Pinwheel",
        "Cloud", "Riverway", "Archipelago", "Radiance", "Disc",
    ),
    "Planetary System": (
        "Orrery", "Orbit", "Circuit", "Constellation", "Assembly",
        "Choreography", "Clockwork", "Retinue", "Garland", "Procession",
        "Gyre", "Accord",
    ),
    "Planet": (
        "Haven", "Cradle", "Pasture", "Refuge", "Sanctuary", "Hearth",
        "Isle", "Globe", "World", "Eden", "Bastion", "Anchorage",
    ),
    "Region": (
        "Basin", "Reach", "Wilds", "Barrens", "Vale", "Steppe", "Fens",
        "Highlands", "Wastes", "Terraces", "Shallows", "Verge",
    ),
    "Room": (
        "Chamber", "Archive", "Gallery", "Chapel", "Library", "Stair",
        "Undercroft", "Alcove", "Rotunda", "Cistern", "Workshop",
        "Antechamber",
    ),
    "Object": (
        "Obelisk", "Terminal", "Chest", "Mirror", "Mechanism", "Conduit",
        "Astrolabe", "Reliquary", "Beacon", "Loom", "Tablet", "Instrument",
    ),
    "Molecule": (
        "Lattice", "Chain", "Ring", "Helix", "Cluster", "Bond", "Fold",
        "Matrix", "Polymer", "Crystal", "Compound", "Structure",
    ),
    "Atom": (
        "Nucleus", "Shell", "Element", "Isotope", "Orbital", "Core", "Ion",
        "Nuclide", "Kernel", "Center", "Measure", "Quantum",
    ),
    "SubatomicParticle": (
        "Particle", "Wave", "Quark", "Lepton", "Boson", "Neutrino", "Photon",
        "Gluon", "Fermion", "Pulse", "Spark", "Point",
    ),
}

NAME_VOCABULARY = frozenset(
    NAME_QUALIFIERS + NAME_MOTIFS
    + tuple(word for forms in NAME_FORMS.values() for word in forms)
)

_NAME_SPACE = len(NAME_QUALIFIERS) * len(NAME_MOTIFS) * 12

assert set(NAME_FORMS) == set(LEVELS)
assert all(len(forms) == 12 for forms in NAME_FORMS.values())
assert len({word for forms in NAME_FORMS.values() for word in forms}) == 12 * len(LEVELS)
assert not ({word for forms in NAME_FORMS.values() for word in forms}
            & (set(NAME_QUALIFIERS) | set(NAME_MOTIFS)))
assert all("-" not in word for word in NAME_VOCABULARY)


# ── Aspect synthesis ────────────────────────────────────────────────────────
# Every node carries an `aspect`: a one-line description belonging to it
# alone, composed from four independent draws (detail × texture × motion ×
# mood ≈ 420k combinations), so repetition within a world is negligible. The
# aspect feeds the node's voice prompt, the UI, and the generative art.

_ASPECT_DETAILS = [
    "light", "salt", "iron", "dust", "frost", "resin", "ash", "static",
    "silver", "smoke", "dew", "grit", "chalk", "oil", "lichen", "amber",
    "soot", "glass", "pollen", "brine", "rust", "wax", "ozone", "shadow",
]
_ASPECT_TEXTURES = [
    "veins of {d} cross it", "a skin of fine {d} holds every touch",
    "it is threaded through with {d}", "old {d} has settled into its seams",
    "a bloom of {d} clings to its edges", "its surface remembers {d}",
    "thin bands of {d} circle it", "flecks of {d} drift over it",
    "it wears a lattice of {d}", "a wash of {d} pools in its hollows",
    "hairline traces of {d} map it", "its grain is shot through with {d}",
    "a film of {d} softens its outline", "ridges of {d} rise along it",
    "it carries a dusting of {d}", "knots of {d} gather at its center",
    "a halo of {d} follows its edge", "seams of {d} open and close in it",
    "its shadow is tinted with {d}", "beads of {d} stand on its surface",
    "a scar of {d} runs its length", "whorls of {d} turn beneath its skin",
    "its edges are stitched with {d}", "a lace of {d} hangs about it",
    "spurs of {d} break its outline", "a sheen of {d} moves when you move",
]
_ASPECT_MOTIONS = [
    "something in it turns over slowly", "it breathes on a long cycle",
    "a faint pulse travels through it", "it leans toward whatever watches it",
    "it settles a little as you arrive", "a tremor crosses it and is gone",
    "it hums below the threshold of hearing", "it gathers itself, then stills",
    "a slow tide moves under its surface", "it flickers at the corner of sight",
    "it holds itself perfectly still", "it sways to no wind you can feel",
    "something inside it keeps time", "it turns a fraction toward the light",
    "a ripple runs its length at intervals", "it tightens when approached",
    "it drifts a hair out of true", "its center never quite stops moving",
    "it exhales when the pressure drops", "a shiver lives in its edges",
    "it counts something, patiently", "it re-forms itself when unobserved",
    "it echoes footsteps back a beat late", "a slow rotation shows in its shadow",
    "it dims and brightens like sleep", "it startles, sometimes, at nothing",
]
_ASPECT_MOODS = [
    "it waits as if listening", "it seems glad of company",
    "it keeps its own counsel", "it is patient the way stone is patient",
    "it wants something it cannot name", "it has forgiven whatever happened here",
    "it remembers being newer", "it is proud, in a quiet way",
    "it distrusts sudden things", "it is tired but unbroken",
    "it hopes, against its nature", "it grieves something small",
    "it is amused by visitors", "it guards more than it shows",
    "it has made peace with the dark", "it is curious and hides it badly",
    "it dislikes being counted", "it dreams shallowly, and often",
    "it is braver than it looks", "it misses a sound it once knew",
    "it tolerates the cold on principle", "it is honest to a fault",
    "it wears its age like a medal", "it is waiting to be asked",
    "it flinches from nothing now", "it keeps one secret well",
]


def _synth_aspect(rng: random.Random) -> str:
    texture = _pick(_ASPECT_TEXTURES, rng).format(d=_pick(_ASPECT_DETAILS, rng))
    motion = _pick(_ASPECT_MOTIONS, rng)
    mood = _pick(_ASPECT_MOODS, rng)
    return f"{texture}; {motion}, and {mood}."


# ── Per-level property generators ──────────────────────────────────────────

def _props_multiverse(rng: random.Random) -> dict:
    return {
        "theme": _pick(["entropy", "expansion", "paradox", "recursion", "stillness"], rng),
        "age_billion_years": round(rng.uniform(1.0, 100.0), 1),
        "stability": _pick(["stable", "fraying", "collapsing"], rng),
        "membrane": _pick(["glassine", "auroral", "umbral", "prismatic", "ashen",
                           "pearled", "hyaline", "smoked", "iridescent", "lucent",
                           "filmed", "crystalline"], rng),
        "hum_period_years": round(rng.uniform(0.9, 990.0), 1),
    }


def _props_universe(rng: random.Random) -> dict:
    return {
        "laws_of_physics": _pick(["Newtonian", "Quantum", "Fractal", "Inverted",
                                  "Probabilistic", "Recursive", "Viscous",
                                  "Crystalline", "Tidal", "Threadbare",
                                  "Palindromic", "Slow light"], rng),
        "dark_matter_ratio": round(rng.uniform(0.1, 0.9), 2),
        "dominant_faction": _pick(_FACTIONS, rng),
        "light_temper": _pick(["honeyed", "clinical", "wine dark", "brittle", "syrup slow",
                               "granular", "silvered", "feverish", "muted", "glacial",
                               "molten", "papery"], rng),
        "vacuum_hum_hz": round(rng.uniform(0.11, 40.0), 2),
    }


def _props_galaxy(rng: random.Random) -> dict:
    return {
        "star_density": rng.randint(50, 500),
        "shape": _pick(["spiral", "elliptical", "irregular", "ring", "barred spiral",
                        "lenticular", "shell", "tidal plume", "double core",
                        "threadwork"], rng),
        "black_hole_mass_solar": rng.randint(100_000, 10_000_000),
        "dust": _pick(["rose gray", "verdigris", "charcoal", "opaline", "sulfur",
                       "lavender", "carbon black", "honeyed", "spectral blue",
                       "burnt umber", "chalk white", "petrol"], rng),
        "drift_kmps": round(rng.uniform(80.0, 620.0), 1),
    }


def _props_planetary_system(rng: random.Random) -> dict:
    return {
        "star_type": _pick(["yellow dwarf", "red dwarf", "white dwarf", "binary",
                            "neutron star", "blue giant", "pulsar", "carbon star",
                            "brown dwarf", "cepheid variable"], rng),
        "planet_count": rng.randint(1, 12),
        "habitable_zone": rng.choice([True, False]),
        "asteroid_belt": rng.choice([True, False]),
        "resonance": f"{rng.randint(1, 9)}:{rng.randint(2, 12)}",
        "ecliptic_tilt_deg": round(rng.uniform(0.0, 28.0), 1),
    }


def _props_planet(rng: random.Random) -> dict:
    inhabited = rng.choice([True, False])
    return {
        "gravity": round(rng.uniform(0.1, 3.5), 2),
        "biome": _pick(_BIOMES, rng),
        "inhabited": inhabited,
        # Population is coherent with habitation: uninhabited worlds are
        # empty, inhabited ones carry at least a settlement's worth.
        "population": rng.randint(10_000, 10_000_000_000) if inhabited else 0,
        "moons": rng.randint(0, 8),
        "sky": _pick(["milk white", "storm green", "rust red", "violet banded",
                      "colorless", "aurora laced", "sodium orange", "ink dark",
                      "pearl gray", "cyan streaked", "bruised", "gold hazed"], rng),
        "day_length_hours": round(rng.uniform(6.0, 90.0), 1),
    }


def _props_region(rng: random.Random) -> dict:
    return {
        "danger_level": rng.randint(1, 10),
        "terrain": _pick(["ruins", "wilderness", "urban", "underground", "floating",
                          "terraced", "drowned", "petrified", "shifting dunes",
                          "crystal fields", "overgrown", "cliffbound"], rng),
        "faction_control": _pick(_FACTIONS + ["contested", "none"], rng),
        "has_settlement": rng.choice([True, False]),
        "weather": _pick(["dry lightning", "slow drizzle", "ground fog", "heat shimmer",
                          "ash fall", "still air", "crosswinds", "freezing mist",
                          "electric haze", "warm rain", "dust devils", "long dusk",
                          "glass frost", "low cloud"], rng),
        "extent_km": round(rng.uniform(3.0, 900.0), 1),
    }


def _props_room(rng: random.Random) -> dict:
    return {
        "has_puzzle": rng.choice([True, False]),
        "locked": rng.choice([True, False]),
        "lighting": _pick(["bright", "dim", "dark", "flickering"], rng),
        "exits": rng.randint(1, 4),
        "contains_npc": rng.choice([True, False]),
        "air": _pick(["dry and papery", "cool and mineral", "warm and close",
                      "sharp with ozone", "sweet with decay", "faintly saline",
                      "dust laden", "resin scented", "metallic", "damp and green",
                      "smoke tinged", "perfectly still"], rng),
        "ceiling_m": round(rng.uniform(1.9, 40.0), 1),
    }


def _props_object(rng: random.Random) -> dict:
    return {
        "interactive": rng.choice([True, False]),
        "material": _pick(["stone", "metal", "crystal", "wood", "energy", "bone",
                           "glass", "amber", "chitin", "woven light", "cold iron",
                           "pressed ash"], rng),
        "condition": _pick(["pristine", "worn", "damaged", "corrupted"], rng),
        "weight_kg": round(rng.uniform(0.01, 500.0), 2),
        "surface": _pick(["mirror smooth", "hatch marked", "pitted", "engraved",
                          "wax sealed", "riveted", "chased with filigree", "burnt",
                          "lacquered", "rough hewn", "worm eaten", "polished by hands"], rng),
        "age_years": rng.randint(3, 90_000),
    }


def _props_molecule(rng: random.Random) -> dict:
    return {
        "compound_type": _pick(["organic", "inorganic", "synthetic", "exotic",
                                "metastable", "prebiotic", "self-repairing",
                                "photoreactive", "cryogenic", "resonant"], rng),
        "bond_count": rng.randint(1, 12),
        "reactive": rng.choice([True, False]),
        "geometry": _pick(["helical", "planar ring", "cage", "branched chain",
                           "lattice", "folded sheet", "twisted ladder", "star",
                           "interlocked rings", "spiral", "dendritic", "knotted"], rng),
        "mass_amu": round(rng.uniform(16.0, 4000.0), 1),
    }


# Element symbol and atomic number are drawn together so an atom is
# physically coherent (Au is 79, not a random 1–118 roll).
_ELEMENTS = [
    ("H", 1), ("C", 6), ("N", 7), ("O", 8), ("Si", 14),
    ("Fe", 26), ("Xe", 54), ("Au", 79), ("Pb", 82), ("U", 92),
]


def _props_atom(rng: random.Random) -> dict:
    symbol, number = rng.choice(_ELEMENTS)
    return {
        "element": symbol,
        "ionized": rng.choice([True, False]),
        "atomic_number": number,
        "glow": _pick(["faint violet", "sodium yellow", "arc white", "ember red",
                       "sea green", "ultraviolet", "candle warm", "steel blue",
                       "phosphor", "rose", "acid green", "colorless"], rng),
        "resonance_nm": round(rng.uniform(180.0, 780.0), 1),
    }


def _props_subatomic(rng: random.Random) -> dict:
    return {
        "particle_type": _pick(["proton", "neutron", "electron", "quark", "neutrino", "photon"], rng),
        "spin": _pick(["up", "down", "superposed"], rng),
        "charge": _pick([-1, 0, 1], rng),
        "tendency": _pick(["evasive", "gregarious", "solitary", "oscillating",
                           "clinging", "fugitive", "punctual", "erratic",
                           "recurring", "borrowed", "entangled", "shy"], rng),
        "coherence": round(rng.uniform(0.001, 0.999), 3),
    }


_LEVEL_GENERATORS: dict[str, Callable[[random.Random], dict]] = {
    "Multiverse":        _props_multiverse,
    "Universe":          _props_universe,
    "Galaxy":            _props_galaxy,
    "Planetary System":  _props_planetary_system,
    "Planet":            _props_planet,
    "Region":            _props_region,
    "Room":              _props_room,
    "Object":            _props_object,
    "Molecule":          _props_molecule,
    "Atom":              _props_atom,
    "SubatomicParticle": _props_subatomic,
}


def generate_properties(level: str, rng: random.Random) -> dict:
    gen = _LEVEL_GENERATORS.get(level)
    props = gen(rng) if gen else {}
    # The aspect: a one-line description belonging to this node alone
    # (≈420k combinations), feeding its voice, its art, and the UI.
    props["aspect"] = _synth_aspect(rng)
    return props


def _path_suffix(path: tuple[int, ...]) -> str:
    """Digit-string form of the node's path. Unique within a world because
    every component is a single digit (breadth ≤ 9 is enforced)."""
    return "".join(str(i) for i in path)


def _path_ordinal(level: str, path: tuple[int, ...]) -> int:
    """Return this path's unique zero-based slot within its level.

    Mixed-radix widths use each parent's maximum possible breadth, so paths
    remain unique even when some earlier parent happened to birth fewer
    children. The unused slots are intentional; they keep the mapping stable
    across different realized shapes.
    """
    level_index = LEVELS.index(level)
    if len(path) != level_index + 1 or not path or path[0] != 1:
        raise ValueError(f"path {path!r} does not identify a {level}")

    ordinal = 0
    for parent_index, component in enumerate(path[1:]):
        width = BREADTH_BY_LEVEL[LEVELS[parent_index]][1]
        if not 1 <= component <= width:
            raise ValueError(
                f"path component {component} exceeds {LEVELS[parent_index]} "
                f"maximum breadth {width}"
            )
        ordinal = ordinal * width + component - 1
    if ordinal >= _NAME_SPACE:
        raise ValueError(
            f"name space exhausted at {level}: ordinal {ordinal} >= {_NAME_SPACE}"
        )
    return ordinal


def _name_permutation(seed: int, level: str) -> tuple[int, int]:
    """Return an affine-permutation offset and coprime step for this level."""
    digest = hashlib.sha256(f"name-v2:{seed}:{level}".encode("utf-8")).digest()
    offset = int.from_bytes(digest[:8], "big") % _NAME_SPACE
    step = int.from_bytes(digest[8:16], "big") % _NAME_SPACE or 1
    while gcd(step, _NAME_SPACE) != 1:
        step = (step + 1) % _NAME_SPACE or 1
    return offset, step


def _generate_name(level: str, path: tuple[int, ...], seed: int) -> str:
    ordinal = _path_ordinal(level, path)
    offset, step = _name_permutation(seed, level)
    code = (offset + step * ordinal) % _NAME_SPACE

    forms = NAME_FORMS[level]
    form_count = len(forms)
    motif_stride = len(NAME_MOTIFS) * form_count
    qualifier = NAME_QUALIFIERS[code // motif_stride]
    remainder = code % motif_stride
    motif = NAME_MOTIFS[remainder // form_count]
    form = forms[remainder % form_count]
    return f"{qualifier} {motif} {form}-{_path_suffix(path)}"


def _node_seed(seed: int, path: tuple[int, ...], domain: str) -> int:
    digest = hashlib.sha256(
        f"generator-v2:{domain}:{seed}:"
        f"{'.'.join(str(i) for i in path)}".encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:8], "big")


# Path digits must stay single-digit for name uniqueness (see _path_suffix).
MAX_GENERATOR_BREADTH = 9


def generate_node_hierarchy(seed: int = DEFAULT_WORLD_SEED,
                            max_depth: int = 11) -> SpatialNode:
    """Generate the canonical world for `seed` down to `max_depth`.

    The world's shape is not a caller input: every node draws its child
    count from BREADTH_BY_LEVEL, so the same seed is the same world in
    every client, every request, and every process — the property the
    entire persistence layer keys on. A shallower `max_depth` yields a
    truthful prefix of the full world (each node depends only on
    (seed, path), never on how deep the caller asked to look).
    """
    if not 1 <= max_depth <= len(LEVELS):
        raise ValueError(f"max_depth must be between 1 and {len(LEVELS)}, got {max_depth}")

    def generate(level_index: int, path: tuple[int, ...]) -> SpatialNode:
        # Domain-separated node-local RNGs: editing the name grammar cannot
        # reshuffle properties or structure in a future generator revision,
        # and editing a property bank cannot shift a breadth draw through
        # random.choice() rejection sampling.
        level = LEVELS[level_index]
        name = _generate_name(level, path, seed)
        property_rng = random.Random(_node_seed(seed, path, "properties"))
        breadth_rng = random.Random(_node_seed(seed, path, "breadth"))
        properties = generate_properties(level, property_rng)
        node = SpatialNode(name=name, level=level, properties=properties)

        breadth = breadth_rng.randint(*BREADTH_BY_LEVEL[level])
        if level_index + 1 < max_depth:
            for i in range(1, breadth + 1):
                node.add_child(generate(level_index + 1, path + (i,)))

        return node

    return generate(0, (1,))
