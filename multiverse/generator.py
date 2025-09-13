# multiverse/generator.py

import random
from multiverse.node import SpatialNode

LEVELS = [
    "Multiverse",
    "Universe",
    "Galaxy",
    "Planet",
    "Region",
    "Room",
    "Object",
    "Molecule",
    "Atom",
    "SubatomicParticle"
]

def generate_properties(level: str) -> dict:
    templates = {
        "Multiverse": {"theme": random.choice(["entropy", "expansion", "paradox"])},
        "Universe": {"laws_of_physics": random.choice(["Newtonian", "Quantum", "Fractal"])},
        "Galaxy": {"star_density": random.randint(50, 200)},
        "Planet": {"gravity": round(random.uniform(0.5, 2.0), 2), "inhabited": random.choice([True, False])},
        "Region": {"danger_level": random.randint(1, 10)},
        "Room": {"has_puzzle": random.choice([True, False]), "locked": random.choice([True, False])},
        "Object": {"interactive": random.choice([True, False])},
        "Molecule": {"compound_type": random.choice(["organic", "inorganic"])},
        "Atom": {"element": random.choice(["H", "C", "O", "N", "Fe"])},
        "SubatomicParticle": {"particle_type": random.choice(["proton", "neutron", "electron"])},
    }
    return templates.get(level, {})

def generate_node_hierarchy(seed: int = 42, depth: int = 10, breadth: int = 2) -> SpatialNode:
    random.seed(seed)

    def _generate(level_index: int) -> SpatialNode:
        level = LEVELS[level_index]
        name = f"{level}_{random.randint(100, 999)}"
        properties = generate_properties(level)
        node = SpatialNode(name=name, level=level, properties=properties)

        if level_index + 1 < depth:
            for _ in range(breadth):
                child = _generate(level_index + 1)
                node.add_child(child)

        return node

    return _generate(0)
