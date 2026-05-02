# multiverse/generator.py

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
    return {
        "gravity": round(rng.uniform(0.1, 3.5), 2),
        "biome": _pick(_BIOMES, rng),
        "inhabited": rng.choice([True, False]),
        "population": rng.randint(0, 10_000_000_000) if rng.random() > 0.4 else 0,
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


def _props_atom(rng: random.Random) -> dict:
    return {
        "element": _pick(["H", "C", "O", "N", "Fe", "Au", "Si", "Xe", "Pb", "U"], rng),
        "ionized": rng.choice([True, False]),
        "atomic_number": rng.randint(1, 118),
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
}


def _generate_name(level: str, index: int, rng: random.Random) -> str:
    pool = _NAME_POOLS.get(level)
    if pool:
        return f"{_pick(pool, rng)}-{index}"
    suffixes = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
    return f"{level}-{_pick(suffixes, rng)}-{index}"


def generate_node_hierarchy(seed: int = 42, max_depth: int = 11, min_breadth: int = 1, max_breadth: int = 3) -> SpatialNode:
    if min_breadth > max_breadth:
        raise ValueError(f"min_breadth ({min_breadth}) must not exceed max_breadth ({max_breadth})")
    if not 1 <= max_depth <= len(LEVELS):
        raise ValueError(f"max_depth must be between 1 and {len(LEVELS)}, got {max_depth}")
    rng = random.Random(seed)
    next_index = 0

    def generate(level_index: int) -> SpatialNode:
        nonlocal next_index
        next_index += 1
        level = LEVELS[level_index]
        name = _generate_name(level, next_index, rng)
        properties = generate_properties(level, rng)
        node = SpatialNode(name=name, level=level, properties=properties)

        if level_index + 1 < max_depth:
            breadth = rng.randint(min_breadth, max_breadth)
            for _ in range(breadth):
                node.add_child(generate(level_index + 1))

        return node

    return generate(0)
