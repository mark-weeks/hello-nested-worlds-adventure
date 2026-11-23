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
  at birth: same names, levels, properties, child order, addresses and
  keys; a shallower depth is a true prefix view of the one stored
  full-depth world.
- `resolve_node_by_name(seed, name)` resolves identity only from born rows,
  by exact match on the stored name: the node carries its ancestor chain
  (parent links, no children), or None for any name the world was not born
  with. No position is read out of a name (ADR-041).
- Every node the store builds carries `address` (its stored path in digits
  form) and `key` (multiverse/naming.py). The key follows the generator
  version the world was BORN under, read from its rows: a world born under
  version 2 or earlier keeps its stored name as its key.

Births are idempotent and race-safe (persistence.save_world_nodes refuses
to overwrite; a lost birth race defers to the winner's rows). Generation
output is cached per (seed, version) in-process — deterministic, so safe —
which keeps birth cheap for test databases that each birth their own world.
"""
from __future__ import annotations

import json
import threading

import persistence
from multiverse.generator import DEFAULT_WORLD_SEED, LEVELS, generate_node_hierarchy
from multiverse.naming import (
    LEGACY_NAME_VERSION, digits_of, dotted_of, key_for, legacy_address,
)
from multiverse.node import SpatialNode

# Version stamp born into every row. Bump when the generator's content or
# structure rules change meaningfully; already-born worlds are unaffected
# (they keep the version they were born under, and are never re-born).
# Version 3 (ADR-041): a born name is its three words; the path digits that
# version 2 appended are the node's address, not part of its name.
GENERATOR_VERSION = 3

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
    _check_birth_names(seed, rows)
    with _birth_rows_lock:
        _birth_rows_cache[key] = rows
    return rows


def _check_birth_names(seed: int,
                       rows: list[tuple[str, str, str, str, int]]) -> None:
    """Refuse to birth a world whose names break ADR-041, loudly.

    D2: no name may repeat within a world. `persistence.save_world_nodes`
    repeats this check for every writer; it is made here too so a generator
    defect is reported before any row is cached. D1: no name may end in
    "-<digits>", the shape of a version-2 name, which display code strips.
    """
    seen: set[str] = set()
    for _path, name, _level, _props, _breadth in rows:
        if name in seen:
            raise ValueError(
                f"world {seed} cannot be born: the name {name!r} is given "
                "to more than one node")
        seen.add(name)
        if GENERATOR_VERSION > LEGACY_NAME_VERSION and legacy_address(name):
            raise ValueError(
                f"world {seed} cannot be born: the name {name!r} ends in "
                "appended digits")


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


def generator_version(seed: int) -> int:
    """The generator version `seed`'s world was born under.

    Read from the stored rows on each call, never cached: the value decides
    the key of every node, and a process may open more than one database.
    """
    ensure_born(seed)
    version = persistence.world_generator_version(seed)
    if version is None:  # pragma: no cover — birth writes the root or nothing
        raise RuntimeError(f"world {seed} has no stored root")
    return version


def _node_from_row(row: tuple[str, str, str, str, int],
                   version: int) -> SpatialNode:
    path, name, level, props_json, breadth = row
    node = SpatialNode(name=name, level=level,
                       properties=json.loads(props_json))
    node._breadth = breadth  # parity with the generator's resolver
    # ADR-041: the address is the stored path; the key follows the version
    # the world was born under (a version-2 name already is its key).
    node.address = digits_of(path)
    node.key = key_for(name, node.address, version)
    return node


def world_tree(seed: int = DEFAULT_WORLD_SEED,
               max_depth: int = _MAX_DEPTH) -> SpatialNode:
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
    version = generator_version(seed)
    rows = persistence.get_world_nodes(seed, max_depth=max_depth)
    by_path: dict[str, SpatialNode] = {}
    root: SpatialNode | None = None
    for row in rows:
        path = row[0]
        node = _node_from_row(row, version)
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


def _chain(seed: int, path: str, version: int) -> SpatialNode | None:
    """The stored node at dot-joined `path` with its ancestor chain (parent
    links, no children), or None when any step of the path was never born."""
    steps = path.split(".")
    prefixes = [".".join(steps[:i + 1]) for i in range(len(steps))]
    rows = persistence.get_world_node_chain(seed, prefixes)
    if len(rows) != len(prefixes):
        return None
    parent: SpatialNode | None = None
    node: SpatialNode | None = None
    for row in rows:
        node = _node_from_row(row, version)
        if parent is not None:
            parent.add_child(node)
        parent = node
    return node


def resolve_node_by_name(seed: int, name: str) -> SpatialNode | None:
    """Resolve a stored node from its name alone.

    One indexed lookup finds the name's stored path (names are unique
    within a world, migration 0034); a second loads the ancestor chain,
    which is the set of path prefixes. Returns the node with parent links
    and no children, or None for any name the world was not born with.
    The same lookup serves a world born under generator version 2, whose
    stored names end in their path digits: nothing is parsed out of a name.
    """
    if not name or not isinstance(name, str):
        return None
    ensure_born(seed)
    found = persistence.get_world_node_address(seed, name)
    if found is None:
        return None
    path, version = found
    return _chain(seed, path, version)


def node_at(seed: int, address: str) -> SpatialNode | None:
    """The stored node at `address` (digits or dot-joined form) with its
    ancestor chain, or None when nothing was born there. For code that holds
    a position and needs the name the world stores for it."""
    digits = digits_of(address) if isinstance(address, str) else ""
    if (not digits.isdigit() or not digits.startswith("1") or "0" in digits
            or len(digits) > _MAX_DEPTH):
        return None
    return _chain(seed, dotted_of(digits), generator_version(seed))


def address_of(seed: int, name: str) -> str | None:
    """The address (digits form) of the node born with this name, or None.
    For callers that hold only a stored name and must send its address."""
    if not name or not isinstance(name, str):
        return None
    ensure_born(seed)
    found = persistence.get_world_node_address(seed, name)
    return digits_of(found[0]) if found else None


def key_of(seed: int, name: str) -> str | None:
    """The identity key of the node born with this name, or None."""
    if not name or not isinstance(name, str):
        return None
    ensure_born(seed)
    found = persistence.get_world_node_address(seed, name)
    if found is None:
        return None
    path, version = found
    return key_for(name, digits_of(path), version)
