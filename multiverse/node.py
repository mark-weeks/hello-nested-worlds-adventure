class SpatialNode:
    def __init__(self, name: str, level: str, children: list = None, properties: dict = None):
        self.name = name
        self.level = level
        self.children = children or []
        self.properties = properties or {}

    def add_child(self, node: "SpatialNode"):
        self.children.append(node)

    def __repr__(self, depth=0):
        indent = "  " * depth
        props = ", ".join(f"{k}: {v}" for k, v in self.properties.items())
        repr_str = f"{indent}{self.level}: {self.name} [{props}]\n"
        for child in self.children:
            repr_str += child.__repr__(depth + 1)
        return repr_str
