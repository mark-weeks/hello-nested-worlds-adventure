"""Durable first-use puzzle content. Pure generators still describe future instances."""
from copy import copy
from dataclasses import asdict
import json

import persistence
from persistence import puzzle_content
from multiverse import store
from multiverse.utils import apply_property_patch
from puzzles import generators
from puzzles.types import Puzzle, PuzzleKind

DEFINITION_VERSION = 1


def _decode(version, blob):
    if version != 1:
        raise ValueError("This question needs a compatible interpreter.")
    data = json.loads(blob)
    data["kind"] = PuzzleKind[data["kind"]]
    return Puzzle(**data)


def _live_node(seed, node):
    # Re-read born values for canonical nodes so stale, already-overlaid callers
    # cannot resurrect deleted properties. Synthetic local fixtures keep their tree.
    if persistence.world_is_born(seed):
        node = store.resolve_node_by_name(seed, node.name) or node
    chain = []
    while node is not None:
        chain.append(copy(node))
        node = node.parent
    overrides = persistence.load_node_property_overrides(seed, [n.name for n in chain])
    for index, node in enumerate(chain):
        node.parent = chain[index + 1] if index + 1 < len(chain) else None
        node.properties = apply_property_patch(node.properties, overrides.get(node.name, {}))
    return chain[0]


def peek_puzzle(seed, node, epoch=0):
    """Resolve a name for progress checks without opening a future question."""
    row = puzzle_content.read(seed, node.name, epoch)
    return _decode(row[0], row[1]) if row else generators.build_puzzle(_live_node(seed, node), epoch)


def get_puzzle(seed, node, epoch=0):
    row = puzzle_content.read(seed, node.name, epoch)
    if row:
        return _decode(row[0], row[1])
    # Snapshot current properties and pin the definition in the same write
    # transaction, including every ancestor used as public question evidence.
    with persistence.transaction():
        row = puzzle_content.read(seed, node.name, epoch)
        if row:
            return _decode(row[0], row[1])
        live = _live_node(seed, node)
        candidate = generators.build_puzzle(live, epoch)
        data = asdict(candidate)
        data['kind'] = candidate.kind.name
        data.pop('result')
        data.pop('attempts')
        observations = []
        ancestor = live
        while ancestor is not None:
            observations.append({'node': ancestor.name, 'level': ancestor.level,
                                 'properties': ancestor.properties})
            ancestor = ancestor.parent
        row = puzzle_content.pin(seed, node.name, epoch, DEFINITION_VERSION, data, observations)
        return _decode(row[0], row[1])


def evidence(seed, node_name, epoch):
    row = puzzle_content.read(seed, node_name, epoch)
    return json.loads(row[2]) if row else []
