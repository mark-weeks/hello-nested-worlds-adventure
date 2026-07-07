"""Sealed passages — the LOCK puzzle's fiction made mechanical.

A locked Room's puzzle promises "speak its weather, and the way opens";
this module is where the way is actually shut. Entry into a locked Room
(or anything enfolded beneath it) requires the room's CURRENT puzzle to be
solved. The rules, chosen deliberately:

- The unlock is WORLD-level: puzzle solves are already shared per world
  (co-op pooled sessions, chronicle solve-state), so one traveler speaking
  the key opens the door for everyone, forever — until the world's entropy
  re-arms the room's puzzle (a renewal epoch), which re-seals it.
- The seal keeps others OUT; it never imprisons. A mover already inside
  the sealed subtree may move freely within and beneath it (and can always
  leave — outward moves land outside the subtree, which is never gated by
  this room).
- The check reads SOLVE STATE, never the `locked` property. Clearing
  `locked` through the persisted overlay would silently change which
  puzzle family build_puzzle serves and orphan the room's solved-state —
  the property stays generated-forever; the gate is state, not mutation.
- The puzzle is built exactly the way the serving path builds it: same
  renewal epoch, same property overlay applied, so the name the gate
  checks is the name the solve was recorded under.

Shared by the WS move handler and the CLI's descend command, so every
client meets the same doors.
"""
from __future__ import annotations

import persistence
from multiverse.node import SpatialNode
from puzzles.generators import build_puzzle


def _path_suffix(name: str) -> str:
    """The path digits a node name carries ("Vault-1121" → "1121")."""
    return name.rpartition("-")[2]


def sealing_room(node: SpatialNode) -> SpatialNode | None:
    """The nearest locked Room at-or-above `node`, or None.

    Only the GENERATED `locked` value matters; the overlay never writes
    this key (see module docstring), so the resolver's clean properties
    are authoritative.
    """
    n = node
    while n is not None:
        if n.level == "Room" and n.properties.get("locked"):
            return n
        n = n.parent
    return None


def _overlaid(seed: int, node: SpatialNode) -> None:
    """Fold the persisted property overlay into `node` (and its parent) in
    place, so build_puzzle sees the same node the serving path serves —
    a divergent view could yield a differently-named puzzle and a door
    that no recorded solve can open."""
    overrides = persistence.load_node_property_overrides(seed)
    for n in (node, node.parent):
        if n is not None and n.name in overrides:
            n.properties.update(overrides[n.name])


def seal_check(seed: int, target: SpatialNode,
               current_name: str | None = None) -> dict | None:
    """Is entering `target` barred by an unsolved LOCK?

    Returns None when the way is open: no locked room encloses the target,
    the mover is already inside the sealed subtree, or the sealing room's
    current puzzle is solved. Otherwise a payload naming the seal — the
    room, its keeper (the parent, where the key is readable), and the
    puzzle that opens it.
    """
    room = sealing_room(target)
    if room is None:
        return None
    room_path = _path_suffix(room.name)
    if current_name and _path_suffix(current_name).startswith(room_path):
        return None  # already inside — the seal never imprisons
    _overlaid(seed, room)
    epoch = persistence.count_node_mutations(seed, room.name, "PUZZLE_REARM")
    puzzle = build_puzzle(room, epoch)
    if persistence.get_puzzle_solve(seed, room.name, puzzle.name):
        return None
    return {
        "sealed_by": room.name,
        "keeper": room.parent.name if room.parent is not None else None,
        "puzzle": puzzle.name,
        "prompt": puzzle.prompt,
    }
