# multiverse/node.py

class SpatialNode:
    def __init__(self, name: str, level: str, children: list = None):
        self.name = name
        self.level = level  # e.g. "Room", "Planet", etc.
        self.children = children or []

    def add_child(self, node: "SpatialNode"):
        self.children.append(node)

    def __repr__(self, depth=0):
        indent = "  " * depth
        repr_str = f"{indent}{self.level}: {self.name}\n"
        for child in self.children:
            repr_str += child.__repr__(depth + 1)
        return repr_str
