"""Executable launch-quality census for an unborn world.

This module inspects generator output directly. It never calls the materialized
store and therefore cannot birth or mutate a persistent world. The launch gate
is intentionally about qualities players can perceive: memorable names, varied
siblings, broad categorical expression, distinct descriptions, and all eleven
scales being present.
"""
from __future__ import annotations

import json
from collections import defaultdict
from itertools import combinations

from multiverse.generator import (
    BREADTH_BY_LEVEL,
    LEVELS,
    NAME_VOCABULARY,
    generate_node_hierarchy,
)
from multiverse.node import SpatialNode

# Properties that materially change the kind of place a player encounters.
# Continuous measurements remain valuable texture, but they do not make two
# otherwise identical choices legible at a glance and therefore do not count
# toward sibling variation.
EXPERIENTIAL_KEYS: dict[str, tuple[str, ...]] = {
    "Multiverse": ("theme", "stability", "membrane"),
    "Universe": ("laws_of_physics", "dominant_faction", "light_temper"),
    "Galaxy": ("shape", "dust"),
    "Planetary System": ("star_type", "habitable_zone", "asteroid_belt"),
    "Planet": ("biome", "inhabited", "sky"),
    "Region": ("terrain", "faction_control", "has_settlement", "weather"),
    "Room": ("has_puzzle", "locked", "lighting", "contains_npc", "air"),
    "Object": ("interactive", "material", "condition", "surface"),
    "Molecule": ("compound_type", "reactive", "geometry"),
    "Atom": ("element", "ionized", "glow"),
    "SubatomicParticle": ("particle_type", "spin", "charge", "tendency"),
}

# Cardinalities of the categorical banks above. Coverage is normalized by the
# smaller of bank size and nodes available at that level, so a three-universe
# world is asked for three distinct laws, not all twelve.
EXPECTED_VARIANTS: dict[str, dict[str, int]] = {
    "Multiverse": {"theme": 5, "stability": 3, "membrane": 12},
    "Universe": {"laws_of_physics": 12, "dominant_faction": 12, "light_temper": 12},
    "Galaxy": {"shape": 10, "dust": 12},
    "Planetary System": {"star_type": 10, "habitable_zone": 2, "asteroid_belt": 2},
    "Planet": {"biome": 15, "inhabited": 2, "sky": 12},
    "Region": {"terrain": 12, "faction_control": 14, "has_settlement": 2, "weather": 14},
    "Room": {"has_puzzle": 2, "locked": 2, "lighting": 4, "contains_npc": 2, "air": 12},
    "Object": {"interactive": 2, "material": 12, "condition": 4, "surface": 12},
    "Molecule": {"compound_type": 10, "reactive": 2, "geometry": 12},
    "Atom": {"element": 10, "ionized": 2, "glow": 12},
    "SubatomicParticle": {"particle_type": 6, "spin": 3, "charge": 3, "tendency": 12},
}

LAUNCH_THRESHOLDS = {
    "readable_name_ratio": 1.0,
    "unique_base_name_ratio": 1.0,
    "unique_aspect_ratio": 0.99,
    "unique_property_ratio": 1.0,
    "sibling_signature_ratio": 0.99,
    "categorical_coverage_ratio": 0.95,
    "branching_coverage_ratio": 0.90,
}


def _walk(root: SpatialNode) -> list[SpatialNode]:
    nodes: list[SpatialNode] = []

    def visit(node: SpatialNode) -> None:
        nodes.append(node)
        for child in node.children:
            visit(child)

    visit(root)
    return nodes


def _signature(node: SpatialNode) -> tuple[object, ...]:
    return tuple(node.properties[key] for key in EXPERIENTIAL_KEYS[node.level])


def audit_world(seed: int) -> dict:
    """Return player-facing quality metrics and pass/fail findings for seed."""
    root = generate_node_hierarchy(seed=seed, max_depth=len(LEVELS))
    nodes = _walk(root)
    by_level: dict[str, list[SpatialNode]] = defaultdict(list)
    for node in nodes:
        by_level[node.level].append(node)

    bases = [node.name.rsplit("-", 1)[0] for node in nodes]
    readable = [
        all(word in NAME_VOCABULARY for word in base.split())
        for base in bases
    ]
    aspects = [node.properties.get("aspect") for node in nodes]
    property_fingerprints = [
        json.dumps(node.properties, ensure_ascii=False, sort_keys=True)
        for node in nodes
    ]

    sibling_pairs = 0
    distinct_sibling_pairs = 0
    for parent in nodes:
        for left, right in combinations(parent.children, 2):
            sibling_pairs += 1
            distinct_sibling_pairs += _signature(left) != _signature(right)

    coverage_samples: list[float] = []
    for level, keys in EXPECTED_VARIANTS.items():
        level_nodes = by_level[level]
        for key, bank_size in keys.items():
            observed = len({node.properties[key] for node in level_nodes})
            coverage_samples.append(observed / min(len(level_nodes), bank_size))

    branching_samples: list[float] = []
    branching_by_level: dict[str, list[int]] = {}
    for level in LEVELS[:-1]:
        lo, hi = BREADTH_BY_LEVEL[level]
        # One root cannot demonstrate a distribution; fixed-width levels have
        # no distribution to demonstrate. Every other variable level does.
        if lo == hi or len(by_level[level]) < 3:
            continue
        observed = sorted({len(node.children) for node in by_level[level]})
        branching_by_level[level] = observed
        branching_samples.append(
            len(set(observed) & set(range(lo, hi + 1))) / (hi - lo + 1)
        )

    metrics = {
        "readable_name_ratio": sum(readable) / len(readable),
        "unique_base_name_ratio": len(set(bases)) / len(bases),
        "unique_aspect_ratio": len(set(aspects)) / len(aspects),
        "unique_property_ratio": (
            len(set(property_fingerprints)) / len(property_fingerprints)
        ),
        "sibling_signature_ratio": (
            distinct_sibling_pairs / sibling_pairs if sibling_pairs else 1.0
        ),
        "categorical_coverage_ratio": (
            sum(coverage_samples) / len(coverage_samples)
        ),
        "branching_coverage_ratio": (
            sum(branching_samples) / len(branching_samples)
            if branching_samples else 1.0
        ),
    }
    failures = [
        f"{key}={metrics[key]:.4f} below {minimum:.4f}"
        for key, minimum in LAUNCH_THRESHOLDS.items()
        if metrics[key] < minimum
    ]
    missing_levels = [level for level in LEVELS if not by_level[level]]
    if missing_levels:
        failures.append(f"missing levels: {', '.join(missing_levels)}")
    if not 2_000 <= len(nodes) <= 20_000:
        failures.append(f"node_count={len(nodes)} outside launch envelope 2000..20000")

    # A weighted comparison score ranks seeds that all pass the hard gate.
    # Names are invariantly perfect under v2, so candidate selection emphasizes
    # the variation metrics where seeds can meaningfully differ.
    comparison_score = 100 * (
        0.35 * metrics["sibling_signature_ratio"]
        + 0.35 * metrics["categorical_coverage_ratio"]
        + 0.15 * metrics["branching_coverage_ratio"]
        + 0.10 * metrics["unique_aspect_ratio"]
        + 0.05 * metrics["unique_property_ratio"]
    )

    return {
        "seed": seed,
        "passed": not failures,
        "failures": failures,
        "comparison_score": round(comparison_score, 4),
        "node_count": len(nodes),
        "level_counts": {level: len(by_level[level]) for level in LEVELS},
        "branching_by_level": branching_by_level,
        "metrics": {key: round(value, 6) for key, value in metrics.items()},
        "sample_names": [node.name for node in nodes[:11]],
    }
