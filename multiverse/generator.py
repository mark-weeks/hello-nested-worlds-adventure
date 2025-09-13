# multiverse/generator.py

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

def generate_node_hierarchy(seed: int = 42, depth: int = 10, breadth: int = 2) -> SpatialNode:
    import random
    random.seed(seed)

    def _generate(level_index: int) -> SpatialNode:
        level = LEVELS[level_index]
        name = f"{level}_{random.randint(100, 999)}"
        node = SpatialNode(name=name, level=level)

        if level_index + 1 < depth:
            for _ in range(breadth):
                child = _generate(level_index + 1)
                node.add_child(child)

        return node

    return _generate(0)
