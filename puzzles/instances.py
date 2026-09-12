"""Durable first-use puzzle content. Pure generators still describe future instances."""
from dataclasses import asdict
import json

from persistence import puzzle_content
from puzzles import generators
from puzzles.types import Puzzle, PuzzleKind

DEFINITION_VERSION = 1


def _decode(version, blob):
    if version != 1:
        raise ValueError("This question needs a compatible interpreter.")
    data = json.loads(blob)
    data["kind"] = PuzzleKind[data["kind"]]
    return Puzzle(**data)


def get_puzzle(seed, node, epoch=0):
    row = puzzle_content.read(seed, node.name, epoch)
    if row:
        return _decode(row[0], row[1])
    candidate = generators.build_puzzle(node, epoch)
    data = asdict(candidate)
    data["kind"] = candidate.kind.name
    data.pop("result")
    data.pop("attempts")
    evidence = []
    ancestor = node
    while ancestor is not None:
        evidence.append({"node": ancestor.name, "level": ancestor.level,
                         "properties": ancestor.properties})
        ancestor = ancestor.parent
    row = puzzle_content.pin(seed, node.name, epoch, DEFINITION_VERSION, data, evidence)
    return _decode(row[0], row[1])


def evidence(seed, node_name, epoch):
    row = puzzle_content.read(seed, node_name, epoch)
    return json.loads(row[2]) if row else []
