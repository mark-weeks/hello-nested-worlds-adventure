"""Executable puzzle-ecology census for an unborn world.

The launch world is persistent: once puzzles have been solved, changing their
generated identity would strand durable history.  This audit therefore runs on
generator output before birth and turns experiential variety into a release
gate.  It measures the balance of mechanics, not just whether individual
puzzles are technically solvable.
"""
from __future__ import annotations

from collections import Counter

from multiverse.generator import DEFAULT_WORLD_SEED, LEVELS, generate_node_hierarchy
from multiverse.node import SpatialNode
from puzzles.generators import build_puzzle
from puzzles.types import Puzzle, PuzzleKind


DECODE_KINDS = {
    PuzzleKind.ANAGRAM,
    PuzzleKind.CIPHER,
    PuzzleKind.PATTERN,
}

WORLD_READING_FAMILIES = {
    "ancestral_compass",
    "bond",
    "enfold",
    "keeper_witness",
    "lineage",
    "sealed_lock",
}

MINIMUMS = {
    "world_reading_family_ratio": 0.55,
    "unique_prompt_ratio": 0.99,
    "unique_answer_ratio": 0.45,
    "family_count": 9,
    "kind_count": 7,
}

MAXIMUMS = {
    "decode_family_ratio": 0.50,
    "largest_family_ratio": 0.25,
}


def puzzle_family(puzzle: Puzzle) -> str:
    """Return the stable mechanic family represented by a puzzle."""
    name = puzzle.name
    if name.startswith("The Keeper Witness"):
        return "keeper_witness"
    if name.startswith("The Ancestral Compass"):
        return "ancestral_compass"
    if name.startswith("The Sealed"):
        return "sealed_lock"
    if name.startswith("The Lineage Sigil"):
        return "lineage"
    if name.startswith("The Bond"):
        return "bond"
    if name.startswith(("The Enfolding Count", "The Depth Within", "The Fold Ordinal")):
        return "enfold"
    if "Jumbled" in name:
        return "anagram"
    if name.endswith(" Inscription"):
        return "cipher"
    if name.endswith(" Progression"):
        return "numeric_pattern"
    return "handwritten"


def _walk(root: SpatialNode) -> list[SpatialNode]:
    nodes: list[SpatialNode] = []
    stack = [root]
    while stack:
        node = stack.pop()
        nodes.append(node)
        stack.extend(reversed(node.children))
    return nodes


def audit_puzzles(seed: int = DEFAULT_WORLD_SEED) -> dict:
    """Return mechanic-balance metrics and pass/fail findings for ``seed``."""
    root = generate_node_hierarchy(seed=seed, max_depth=len(LEVELS))
    puzzles = [build_puzzle(node) for node in _walk(root)]
    total = len(puzzles)
    family_counts = Counter(puzzle_family(puzzle) for puzzle in puzzles)
    kind_counts = Counter(puzzle.kind.name for puzzle in puzzles)
    decode_count = sum(puzzle.kind in DECODE_KINDS for puzzle in puzzles)
    world_reading_count = sum(
        puzzle_family(puzzle) in WORLD_READING_FAMILIES
        for puzzle in puzzles
    )

    metrics: dict[str, float | int] = {
        "decode_family_ratio": decode_count / total,
        "world_reading_family_ratio": world_reading_count / total,
        "unique_prompt_ratio": len({puzzle.prompt for puzzle in puzzles}) / total,
        "unique_answer_ratio": len({puzzle.answer for puzzle in puzzles}) / total,
        "largest_family_ratio": max(family_counts.values()) / total,
        "family_count": len(family_counts),
        "kind_count": len(kind_counts),
    }
    failures = [
        f"{key}={metrics[key]:.4f} below {minimum:.4f}"
        for key, minimum in MINIMUMS.items()
        if metrics[key] < minimum
    ]
    failures.extend(
        f"{key}={metrics[key]:.4f} above {maximum:.4f}"
        for key, maximum in MAXIMUMS.items()
        if metrics[key] > maximum
    )

    return {
        "seed": seed,
        "passed": not failures,
        "failures": failures,
        "puzzle_count": total,
        "family_counts": dict(family_counts.most_common()),
        "kind_counts": dict(kind_counts.most_common()),
        "metrics": {
            key: round(value, 6) if isinstance(value, float) else value
            for key, value in metrics.items()
        },
    }
