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

_MULTIVERSE_NAMES = ["Aethon", "Vorrex", "Nullspace", "Cascade", "Ouroboros"]
_UNIVERSE_NAMES = ["Aldric", "Solvane", "Mireth", "Cerulean", "Thornvast"]
_GALAXY_NAMES = ["Vela", "Cygnus", "Andromeda", "Sable Arm", "Ember Drift"]
_PLANETARY_SYSTEM_NAMES = ["Ardent Prime", "Vethara", "Keleth", "Auric", "Thorngate", "Solweave", "Kaelos"]
_PLANET_NAMES = ["Kethara", "Droven", "Islune", "Pyreth", "Solmara", "Ashveil", "Quelris"]
_REGION_NAMES = ["Ashfields", "The Mire", "Crystalpeak", "Undergate", "Verdant Hollow"]
_ROOM_NAMES = ["Antechamber", "Vault", "Observatory", "Engine Room", "Sanctum", "The Pit", "Archive"]
_OBJECT_NAMES = ["Obelisk", "Terminal", "Chest", "Mirror", "Mechanism", "Rune Stone", "Conduit"]
_MOLECULE_NAMES = ["Helix", "Lattice", "Chiral Bloom", "Catalyst Knot", "Isomer", "Polymer Strand", "Reagent"]
_ATOM_NAMES = ["Ferrum Core", "Aurum Mote", "Xenon Whisper", "Carbon Seed", "Hydrogen Sigh", "Ion Veil"]
_SUBATOMIC_NAMES = ["Quark Flicker", "Neutrino Ghost", "Photon Grain", "Spin Fragment", "Gluon Knot", "Muon Trace"]
_BIOMES = ["tundra", "jungle", "desert", "ocean", "volcanic", "temperate", "irradiated"]
_FACTIONS = ["The Conclave", "Iron Veil", "Drifters", "Null Cult", "Reclaimer Order"]


def _pick(pool: list, rng: random.Random) -> str:
    return rng.choice(pool)


# ── Per-level property generators ──────────────────────────────────────────

def _props_multiverse(rng: random.Random) -> dict:
    return {
        "theme": _pick(["entropy", "expansion", "paradox", "recursion", "stillness"], rng),
        "age_billion_years": round(rng.uniform(1.0, 100.0), 1),
        "stability": _pick(["stable", "fraying", "collapsing"], rng),
    }


def _props_universe(rng: random.Random) -> dict:
    return {
        "laws_of_physics": _pick(["Newtonian", "Quantum", "Fractal", "Inverted", "Probabilistic"], rng),
        "dark_matter_ratio": round(rng.uniform(0.1, 0.9), 2),
        "dominant_faction": _pick(_FACTIONS, rng),
    }


def _props_galaxy(rng: random.Random) -> dict:
    return {
        "star_density": rng.randint(50, 500),
        "shape": _pick(["spiral", "elliptical", "irregular", "ring"], rng),
        "black_hole_mass_solar": rng.randint(100_000, 10_000_000),
    }


def _props_planetary_system(rng: random.Random) -> dict:
    return {
        "star_type": _pick(["yellow dwarf", "red dwarf", "white dwarf", "binary", "neutron star"], rng),
        "planet_count": rng.randint(1, 12),
        "habitable_zone": rng.choice([True, False]),
        "asteroid_belt": rng.choice([True, False]),
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
    }


def _props_region(rng: random.Random) -> dict:
    return {
        "danger_level": rng.randint(1, 10),
        "terrain": _pick(["ruins", "wilderness", "urban", "underground", "floating"], rng),
        "faction_control": _pick(_FACTIONS + ["contested", "none"], rng),
        "has_settlement": rng.choice([True, False]),
    }


def _props_room(rng: random.Random) -> dict:
    return {
        "has_puzzle": rng.choice([True, False]),
        "locked": rng.choice([True, False]),
        "lighting": _pick(["bright", "dim", "dark", "flickering"], rng),
        "exits": rng.randint(1, 4),
        "contains_npc": rng.choice([True, False]),
    }


def _props_object(rng: random.Random) -> dict:
    return {
        "interactive": rng.choice([True, False]),
        "material": _pick(["stone", "metal", "crystal", "wood", "energy", "bone"], rng),
        "condition": _pick(["pristine", "worn", "damaged", "corrupted"], rng),
        "weight_kg": round(rng.uniform(0.01, 500.0), 2),
    }


def _props_molecule(rng: random.Random) -> dict:
    return {
        "compound_type": _pick(["organic", "inorganic", "synthetic", "exotic"], rng),
        "bond_count": rng.randint(1, 12),
        "reactive": rng.choice([True, False]),
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
    }


def _props_subatomic(rng: random.Random) -> dict:
    return {
        "particle_type": _pick(["proton", "neutron", "electron", "quark", "neutrino", "photon"], rng),
        "spin": _pick(["up", "down", "superposed"], rng),
        "charge": _pick([-1, 0, 1], rng),
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
    return gen(rng) if gen else {}


_NAME_POOLS = {
    "Multiverse": _MULTIVERSE_NAMES,
    "Universe": _UNIVERSE_NAMES,
    "Galaxy": _GALAXY_NAMES,
    "Planetary System": _PLANETARY_SYSTEM_NAMES,
    "Planet": _PLANET_NAMES,
    "Region": _REGION_NAMES,
    "Room": _ROOM_NAMES,
    "Object": _OBJECT_NAMES,
    "Molecule": _MOLECULE_NAMES,
    "Atom": _ATOM_NAMES,
    "SubatomicParticle": _SUBATOMIC_NAMES,
}


def _path_suffix(path: tuple[int, ...]) -> str:
    """Digit-string form of the node's path. Unique within a world because
    every component is a single digit (breadth ≤ 9 is enforced)."""
    return "".join(str(i) for i in path)


def _generate_name(level: str, path: tuple[int, ...], rng: random.Random) -> str:
    pool = _NAME_POOLS.get(level)
    base = _pick(pool, rng) if pool else level
    return f"{base}-{_path_suffix(path)}"


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
