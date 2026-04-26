from __future__ import annotations

from multiverse.node import SpatialNode


def _count_nodes(node: SpatialNode) -> int:
    return 1 + sum(_count_nodes(c) for c in node.children)


def _find_node(root: SpatialNode, name: str) -> SpatialNode | None:
    if root.name == name:
        return root
    for child in root.children:
        found = _find_node(child, name)
        if found:
            return found
    return None


def _build_depth_map(node: SpatialNode, depth: int = 0,
                     result: dict | None = None) -> dict[str, int]:
    if result is None:
        result = {}
    result[node.id] = depth
    for child in node.children:
        _build_depth_map(child, depth + 1, result)
    return result
