"""The materialized world — world-as-data (ADR-006, Option A).

Before this module, the runtime regenerated the world from the content
banks on every request, which made the banks the world's storage medium
and forced the launch freeze: any bank edit renamed nodes and severed all
history keyed on their names. Here the generator runs ONCE per seed, as a
birthing tool; the stored rows become the node's identity; and the banks
govern only the birth of not-yet-born worlds. Editing a bank can never
again touch a world that already exists — pinned by
tests/test_world_store.py::TestBankEditImmunity, the test that made the
freeze obsolete.

Contract mirrored exactly from the generator (equivalence is pinned at
both depths by tests/test_world_store.py):

- `world_tree(seed, max_depth)` ≡ `generate_node_hierarchy(seed, max_depth)`
  at birth: same names, levels, properties, and child order; a shallower
  depth is a true prefix view of the one stored full-depth world.
- `resolve_node_by_name(seed, name)` ≡ the generator's resolver: returns
  the node with its ancestor chain (parent links, no children), or None
  for any forged name — bad suffix, zero digit, step beyond the parent's
  born breadth (the row simply doesn't exist), or a base name that isn't
  what the path was born as.

Births are idempotent and race-safe (persistence.save_world_nodes refuses
to overwrite; a lost birth race defers to the winner's rows). Generation
output is cached per (seed, version) in-process — deterministic, so safe —
which keeps birth cheap for test databases that each birth their own world.
"""
from __future__ import annotations

import json
import threading

import persistence
from multiverse.generator import LEVELS, generate_node_hierarchy
from multiverse.node import SpatialNode

# Version stamp born into every row. Bump when the generator's content or
# structure rules change meaningfully; already-born worlds are unaffected
# (they keep the version they were born under, and are never re-born).
GENERATOR_VERSION = 1

_MAX_DEPTH = len(LEVELS)

# Deterministic generation output, cached per (seed, version) so repeated
# births (one per test database; exactly one ever in production) don't pay
# the full generation walk each time. Rows are immutable tuples.
_birth_rows_lock = threading.Lock()
_birth_rows_cache: dict[tuple[int, int], list[tuple[str, str, str, str, int]]] = {}


def _rows_for_birth(seed: int) -> list[tuple[str, str, str, str, int]]:
    key = (seed, GENERATOR_VERSION)
    with _birth_rows_lock:
        cached = _birth_rows_cache.get(key)
    if cached is not None:
        return cached
    root = generate_node_hierarchy(seed=seed, max_depth=_MAX_DEPTH)
    rows: list[tuple[str, str, str, str, int]] = []

    def walk(node: SpatialNode, path: tuple[int, ...]) -> None:
        # The born breadth is the child count the generator produced; at
        # the leaf level the generator draws but never uses breadth, so
        # the stored value is simply 0 — resolution never consults it
        # (child-row existence is the validation).
        rows.append((
            ".".join(str(i) for i in path),
            node.name,
            node.level,
            json.dumps(node.properties, ensure_ascii=False),
            len(node.children),
        ))
        for i, child in enumerate(node.children, start=1):
            walk(child, path + (i,))

    walk(root, (1,))
    with _birth_rows_lock:
        _birth_rows_cache[key] = rows
    return rows


def birth_world(seed: int) -> int:
    """Birth `seed`'s world into the store if it isn't born yet.

    Returns the number of rows written — 0 when the world already exists
    (a born world is never re-born, whatever the current banks say).
    """
    if persistence.world_is_born(seed):
        return 0
    return persistence.save_world_nodes(seed, _rows_for_birth(seed),
                                        GENERATOR_VERSION)


def ensure_born(seed: int) -> None:
    birth_world(seed)


def _node_from_row(row: tuple[str, str, str, str, int]) -> SpatialNode:
    _path, name, level, props_json, breadth = row
    node = SpatialNode(name=name, level=level,
                       properties=json.loads(props_json))
    node._breadth = breadth  # parity with the generator's resolver
    return node


def world_tree(seed: int = 42, max_depth: int = _MAX_DEPTH) -> SpatialNode:
    """The stored world for `seed`, assembled as a SpatialNode tree.

    Births the world on first visit. `max_depth` is a view: the top
    `max_depth` levels of the one stored full-depth world (prefix-true by
    construction — there is only one world to take a prefix of). A fresh
    tree is assembled per call, matching the old generate-per-request
    lifecycle: callers mutate trees (ripple, overlays) per request.
    """
    if not 1 <= max_depth <= _MAX_DEPTH:
        raise ValueError(
            f"max_depth must be between 1 and {_MAX_DEPTH}, got {max_depth}")
    ensure_born(seed)
    rows = persistence.get_world_nodes(seed, max_depth=max_depth)
    by_path: dict[str, SpatialNode] = {}
    root: SpatialNode | None = None
    for row in rows:
        path = row[0]
        node = _node_from_row(row)
        by_path[path] = node
        parent_path, _, _ = path.rpartition(".")
        if parent_path:
            # Rows arrive ordered by path, so the parent is always present
            # before its children and sibling order (…"N") is ascending.
            by_path[parent_path].add_child(node)
        else:
            root = node
    if root is None:  # pragma: no cover — birth writes the root or nothing
        raise RuntimeError(f"world {seed} has no stored root")
    return root


def root_name(seed: int) -> str:
    ensure_born(seed)
    rows = persistence.get_world_node_chain(seed, ["1"])
    return rows[0][1]


def resolve_node_by_name(seed: int, name: str) -> SpatialNode | None:
    """Resolve a stored node from its name alone — the store's mirror of
    the generator's resolver, same contract, same forgery refusals.

    Names encode their path as a digit suffix, so the ancestor chain is
    the set of path prefixes: one indexed query. Returns the node with
    parent links and no children, or None for anything the world was not
    born with.
    """
    if not name or "-" not in name:
        return None
    _, _, suffix = name.rpartition("-")
    if not suffix.isdigit() or not suffix.startswith("1"):
        return None
    digits = [int(c) for c in suffix]
    if len(digits) > _MAX_DEPTH or any(d < 1 for d in digits):
        return None

    ensure_born(seed)
    prefixes = [".".join(str(d) for d in digits[:i + 1])
                for i in range(len(digits))]
    rows = persistence.get_world_node_chain(seed, prefixes)
    if len(rows) != len(prefixes):
        return None  # some claimed ancestor was never born — forged path
    parent: SpatialNode | None = None
    node: SpatialNode | None = None
    for row in rows:
        node = _node_from_row(row)
        if parent is not None:
            parent.add_child(node)
        parent = node
    if node is None or node.name != name:
        return None  # base name isn't what this path was born as — forged
    return node
