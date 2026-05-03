from __future__ import annotations

from multiverse.node import SpatialNode


def count_nodes(node: SpatialNode) -> int:
    return 1 + sum(count_nodes(c) for c in node.children)


def find_node(root: SpatialNode, name: str) -> SpatialNode | None:
    if root.name == name:
        return root
    for child in root.children:
        found = find_node(child, name)
        if found:
            return found
    return None


def build_depth_map(node: SpatialNode, depth: int = 0,
                    result: dict | None = None) -> dict[str, int]:
    if result is None:
        result = {}
    result[node.id] = depth
    for child in node.children:
        build_depth_map(child, depth + 1, result)
    return result


def apply_ripple_scores(root: SpatialNode, scores: dict[str, float]) -> None:
    """Hydrate ripple_score on every node in *root* present in *scores*.

    Names are unique within a generated tree (the generator's index counter
    is global across levels), so keying by name is safe. Nodes absent from
    the map keep their default 0.0.
    """
    if not scores:
        return
    score = scores.get(root.name)
    if score is not None:
        root.ripple_score = score
    for child in root.children:
        apply_ripple_scores(child, scores)
