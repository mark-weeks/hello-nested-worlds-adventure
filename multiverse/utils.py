from __future__ import annotations

from multiverse.node import SpatialNode


def node_address(name: str) -> str | None:
    """The path-digit suffix a canonical node name carries ("Hidden Thorn
    Quark-11431112111" → "11431112111") — the node's address, its path from
    the root. None when the name carries no address."""
    base, separator, suffix = (name or "").rpartition("-")
    if separator and base and suffix.isdigit():
        return suffix
    return None


def display_name(name: str) -> str:
    """The readable phrase without its address — the DISPLAY layer only.

    The canonical full name (phrase + address) stays the sole identity
    everywhere data is keyed, sent, or chronicled; this exists so player-
    facing chrome can show "Hidden Thorn Quark" while the address stays one
    gesture away. Mirrors clientlogic.js `displayName` and the puzzle
    layer's `_base_name` reading.
    """
    address = node_address(name)
    if address is None:
        return name or ""
    return name[:-(len(address) + 1)]


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


def build_distance_map(origin: SpatialNode) -> dict[str, int]:
    """Hop distance from `origin` to every node reachable through parent and
    child edges — i.e. the whole tree. Unlike `build_depth_map` (which only
    covers the subtree below its root), ancestors get their true distance,
    so an upward-cascading event is never mislabelled as distance 0."""
    dist: dict[str, int] = {origin.id: 0}
    frontier = [origin]
    while frontier:
        node = frontier.pop()
        d = dist[node.id]
        neighbors = list(node.children)
        if node.parent is not None:
            neighbors.append(node.parent)
        for n in neighbors:
            if n.id not in dist:
                dist[n.id] = d + 1
                frontier.append(n)
    return dist


def apply_property_overrides(root: SpatialNode, overrides: dict[str, dict]) -> None:
    """Merge persisted property overlays (from causal-event effects) onto the
    freshly generated tree, keyed by node name. This is how the world's
    durable evolution survives per-request regeneration."""
    if not overrides:
        return
    changed = overrides.get(root.name)
    if changed:
        root.properties.update(changed)
    for child in root.children:
        apply_property_overrides(child, overrides)


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
