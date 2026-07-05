# multiverse/generator.py
#
# Canonical world generation: every node is a pure function of
# (world seed, path-from-root). Each node derives its own RNG from a
# SHA-256 of (seed, path), and draws its name, properties, and child
# count from that node-local RNG — never from a shared sequential
# stream. Consequences:
#
#   * PREFIX STABILITY. A tree generated at max_depth=6 is exactly the
#     top of the tree generated at max_depth=11 for the same seed and
#     breadth bounds — same names, same properties, same branching.
#     Every client and endpoint that regenerates "the world" therefore
#     agrees on node identity, and persistence keyed on
#     (seed, node_name) refers to the same place everywhere.
#   * STABLE, UNIQUE NAMES. The name suffix encodes the node's path
#     (root is "1", its second child "12", that child's first child
#     "121"), so names are unique within a world and identical across
#     rebuilds at any depth. Breadth is capped at 9 so path digits are
#     unambiguous.

import hashlib
import random
from typing import Callable

from multiverse.node import SpatialNode

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

_BIOMES = ["tundra", "jungle", "desert", "ocean", "volcanic", "temperate", "irradiated"]
_FACTIONS = ["The Conclave", "Iron Veil", "Drifters", "Null Cult", "Reclaimer Order"]


def _pick(pool: list, rng: random.Random) -> str:
    return rng.choice(pool)


# ── Name synthesis ──────────────────────────────────────────────────────────
# Every node's name is synthesized from its own RNG rather than drawn from a
# small pool, so base names essentially never repeat within a world (the
# combinatorial space per level runs from tens of thousands to hundreds of
# thousands). The path suffix stays — it is what makes names canonically
# unique and resolvable in O(depth) — but the base in front of it now belongs
# to that node alone. No bank word may contain "-" (the suffix separator).

_SYL_ROOTS = [
    "vel", "kar", "thal", "mor", "sel", "dra", "ny", "or", "az", "il",
    "ul", "eth", "bel", "cal", "ser", "tor", "hal", "mir", "vor", "quel",
    "ash", "sol", "keth", "yr", "ond", "fen", "gal", "isk", "lum", "ver",
]
_SYL_MIDS = [
    "a", "e", "i", "o", "u", "ar", "en", "ir", "or", "un",
    "al", "em", "is", "ov", "ur", "ae", "ol", "an", "eth", "am",
    "ys", "ex", "ia", "au",
]
_SYL_ENDINGS: dict[str, list[str]] = {
    "Multiverse":        ["on", "aeon", "um", "ael", "os", "yr", "is", "ex", "urne", "ith"],
    "Universe":          ["vast", "ium", "or", "ane", "eth", "ar", "ul", "orne", "ax", "ese"],
    "Galaxy":            ["a", "is", "ara", "eia", "ion", "ova", "yne", "ris", "ella", "ix"],
    "Planetary System":  ["os", "eth", "ara", "ion", "ax", "ir", "one", "ese", "ala", "ur"],
    "Planet":            ["a", "ia", "une", "eth", "ara", "is", "or", "ys", "aia", "en"],
    "Molecule":          ["ine", "ol", "ide", "ane", "ate", "yl", "ose", "ene", "ium", "in"],
    "Atom":              ["ium", "on", "ide", "ine", "um", "is", "yte", "ase", "or", "ite"],
    "SubatomicParticle": ["ino", "on", "ette", "ule", "yon", "ion", "il", "ix", "is", "eon"],
}

# Constructed places (Region / Room / Object) read better as "<Word> <Noun>".
# The first word is either a synthesized proper name (huge space) or a fused
# material word; the noun is level-flavored.
_FUSE_A = [
    "ember", "salt", "iron", "ash", "moss", "frost", "night", "amber",
    "hollow", "star", "bone", "rust", "dusk", "cinder", "glass", "storm",
    "silver", "thorn", "wax", "shade", "tide", "root", "smoke", "pale",
    "cold", "deep", "still", "bright", "murk", "loam",
]
_FUSE_B = [
    "glass", "fall", "reach", "veil", "gate", "wark", "mere", "fell",
    "light", "shard", "spire", "hold", "cross", "song", "bloom", "drift",
    "brand", "coil", "marsh", "vane", "crest", "well", "moor", "grain",
    "forge", "ridge", "haven", "lock", "quarry", "vault",
]
_PLACE_NOUNS: dict[str, list[str]] = {
    "Region": [
        "Fields", "Mire", "Peaks", "Hollow", "Expanse", "Wilds", "Barrens",
        "Reaches", "Steppe", "Fens", "Highlands", "Wastes", "Terraces",
        "Shallows", "Bluffs", "Warrens", "Downs", "Flats", "Verge", "Maze",
        "Cradle", "Scar", "Basin", "Crossing",
    ],
    "Room": [
        "Antechamber", "Vault", "Observatory", "Sanctum", "Archive", "Gallery",
        "Cell", "Atrium", "Workshop", "Chapel", "Cistern", "Library", "Stair",
        "Refectory", "Solar", "Oubliette", "Loft", "Passage", "Chamber",
        "Undercroft", "Scriptorium", "Landing", "Alcove", "Rotunda",
    ],
    "Object": [
        "Obelisk", "Terminal", "Chest", "Mirror", "Mechanism", "Conduit",
        "Astrolabe", "Reliquary", "Lantern", "Loom", "Bell", "Tablet",
        "Orrery", "Casket", "Prism", "Anchor", "Idol", "Compass", "Chalice",
        "Engine", "Key", "Seal", "Hourglass", "Stone",
    ],
}


def _synth_proper(rng: random.Random, level: str) -> str:
    """A synthesized proper name in the level's phonetic flavor.

    Always at least one mid syllable: with zero mids the space collapses to
    roots × endings (300 combos) and base names start colliding in a single
    world. With 1–2 mids the space is ≈180k per level.
    """
    root = _pick(_SYL_ROOTS, rng)
    mids = "".join(_pick(_SYL_MIDS, rng) for _ in range(rng.randint(1, 2)))
    ending = _pick(_SYL_ENDINGS.get(level, _SYL_ENDINGS["Planet"]), rng)
    return (root + mids + ending).capitalize()


def _synth_base_name(level: str, rng: random.Random) -> str:
    if level in _PLACE_NOUNS:
        noun = _pick(_PLACE_NOUNS[level], rng)
        if rng.random() < 0.55:
            first = _synth_proper(rng, "Planet")
        else:
            first = (_pick(_FUSE_A, rng) + _pick(_FUSE_B, rng)).capitalize()
        return f"{first} {noun}"
    return _synth_proper(rng, level)


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
        "laws_of_physics": _pick(["Newtonian", "Quantum", "Fractal", "Inverted", "Probabilistic"], rng),
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
        "shape": _pick(["spiral", "elliptical", "irregular", "ring"], rng),
        "black_hole_mass_solar": rng.randint(100_000, 10_000_000),
        "dust": _pick(["rose gray", "verdigris", "charcoal", "opaline", "sulfur",
                       "lavender", "carbon black", "honeyed", "spectral blue",
                       "burnt umber", "chalk white", "petrol"], rng),
        "drift_kmps": round(rng.uniform(80.0, 620.0), 1),
    }


def _props_planetary_system(rng: random.Random) -> dict:
    return {
        "star_type": _pick(["yellow dwarf", "red dwarf", "white dwarf", "binary", "neutron star"], rng),
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
        "terrain": _pick(["ruins", "wilderness", "urban", "underground", "floating"], rng),
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
        "material": _pick(["stone", "metal", "crystal", "wood", "energy", "bone"], rng),
        "condition": _pick(["pristine", "worn", "damaged", "corrupted"], rng),
        "weight_kg": round(rng.uniform(0.01, 500.0), 2),
        "surface": _pick(["mirror smooth", "hatch marked", "pitted", "engraved",
                          "wax sealed", "riveted", "chased with filigree", "burnt",
                          "lacquered", "rough hewn", "worm eaten", "polished by hands"], rng),
        "age_years": rng.randint(3, 90_000),
    }


def _props_molecule(rng: random.Random) -> dict:
    return {
        "compound_type": _pick(["organic", "inorganic", "synthetic", "exotic"], rng),
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


def _generate_name(level: str, path: tuple[int, ...], rng: random.Random) -> str:
    return f"{_synth_base_name(level, rng)}-{_path_suffix(path)}"


def _node_seed(seed: int, path: tuple[int, ...]) -> int:
    digest = hashlib.sha256(
        f"{seed}:{'.'.join(str(i) for i in path)}".encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:8], "big")


# Path digits must stay single-digit for name uniqueness (see _path_suffix).
MAX_GENERATOR_BREADTH = 9


def resolve_node_by_name(seed: int, name: str,
                         min_breadth: int = 1, max_breadth: int = 3) -> SpatialNode | None:
    """Resolve a node from its name alone, without generating the tree.

    Names encode their path ("Vault-1231" sits at path 1→2→3→1), so the
    node — and its ancestor chain, with parent links — can be regenerated
    in O(depth). Returns None when the name doesn't correspond to a real
    node in this world: bad suffix, out-of-range step, level mismatch, or a
    base name that doesn't match what the path actually generates (so a
    client cannot forge "Fake-11" into existence).

    The returned node carries no children; it is for identity, properties,
    and ancestry — use `generate_node_hierarchy` when structure is needed.
    """
    if not name or "-" not in name:
        return None
    _, _, suffix = name.rpartition("-")
    if not suffix.isdigit() or not suffix.startswith("1"):
        return None
    path_digits = [int(c) for c in suffix]
    if len(path_digits) > len(LEVELS):
        return None

    parent: SpatialNode | None = None
    node: SpatialNode | None = None
    path: tuple[int, ...] = ()
    for depth_index, step in enumerate(path_digits):
        if step < 1:
            return None  # children are numbered from 1; path digit 0 is forged
        path = path + (step,)
        rng = random.Random(_node_seed(seed, path))
        level = LEVELS[depth_index]
        node_name = _generate_name(level, path, rng)
        properties = generate_properties(level, rng)
        breadth = rng.randint(min_breadth, max_breadth)
        node = SpatialNode(name=node_name, level=level, properties=properties)
        node._breadth = breadth  # how many children this node would generate
        if parent is not None:
            # The claimed step must be a child that actually exists.
            if step > getattr(parent, "_breadth", 0):
                return None
            parent.add_child(node)
        parent = node

    if node is None or node.name != name:
        return None
    return node


def generate_node_hierarchy(seed: int = 42, max_depth: int = 11, min_breadth: int = 1, max_breadth: int = 3) -> SpatialNode:
    if min_breadth > max_breadth:
        raise ValueError(f"min_breadth ({min_breadth}) must not exceed max_breadth ({max_breadth})")
    if not 1 <= max_depth <= len(LEVELS):
        raise ValueError(f"max_depth must be between 1 and {len(LEVELS)}, got {max_depth}")
    if max_breadth > MAX_GENERATOR_BREADTH:
        raise ValueError(f"max_breadth must be at most {MAX_GENERATOR_BREADTH}, got {max_breadth}")

    def generate(level_index: int, path: tuple[int, ...]) -> SpatialNode:
        # A node-local RNG: nothing about this node depends on siblings,
        # ancestors' subtrees, or the requested max_depth — only on
        # (seed, path). Draw order (name, properties, breadth) is fixed.
        rng = random.Random(_node_seed(seed, path))
        level = LEVELS[level_index]
        name = _generate_name(level, path, rng)
        properties = generate_properties(level, rng)
        node = SpatialNode(name=name, level=level, properties=properties)

        breadth = rng.randint(min_breadth, max_breadth)
        if level_index + 1 < max_depth:
            for i in range(1, breadth + 1):
                node.add_child(generate(level_index + 1, path + (i,)))

        return node

    return generate(0, (1,))
