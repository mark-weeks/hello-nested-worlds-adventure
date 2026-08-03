"""World mechanics used by HTTP, co-op, and real-time server surfaces.

Keeping these rules outside request dispatch makes constellation completion,
particle entanglement, and canonical node hydration independently readable and
testable without changing their public behavior.
"""
from __future__ import annotations

import persistence
from causality import CausalityBus, EventKind
from causality.staging import stage_cascade
from causality.wiring import wire_world_handlers
from multiverse import store
from multiverse.node import SpatialNode
from puzzles.engine import build_puzzle
from server.rooms import broadcast, get_puzzle_session


CONSTELLATION_LEVELS = {"Galaxy": "systems", "Region": "rooms"}


def constellation_progress(seed: int, container: SpatialNode) -> tuple[int, int]:
    """Return (children with a human solve for the current puzzle, total)."""
    solved = 0
    for child in container.children:
        epoch = persistence.count_node_mutations(seed, child.name, "PUZZLE_REARM")
        puzzle = build_puzzle(child, epoch)
        if persistence.get_puzzle_solve(seed, child.name, puzzle.name):
            solved += 1
    return solved, len(container.children)


def check_constellation(
    seed: int,
    room,
    container: SpatialNode | None,
    solver: str | None,
    actor_identity: str | None,
) -> None:
    """Light a container when all of its current child puzzles are solved."""
    if container is None or container.level not in CONSTELLATION_LEVELS:
        return
    if not container.children:
        return
    if persistence.count_node_mutations(seed, container.name, "CONSTELLATION_COMPLETE"):
        return
    solved, total = constellation_progress(seed, container)
    if solved < total:
        return
    display = solver if solver != "anonymous" else None
    word = CONSTELLATION_LEVELS[container.level]
    persistence.record_mutation(
        seed,
        container.name,
        "CONSTELLATION_COMPLETE",
        display,
        {"children": total, "of": word},
        actor_identity=actor_identity,
    )
    persistence.upsert_node_properties(seed, container.name, {"constellated": True})
    broadcast(
        room,
        {
            "type": "constellation_complete",
            "node": container.name,
            "level": container.level,
            "by": display,
            "children": total,
            "of": word,
        },
    )
    bus = wire_world_handlers(CausalityBus(), seed, record=False)
    bus.emit(container, EventKind.CONSTELLATION_COMPLETE, {"by": display})
    stage_cascade(
        seed,
        container,
        EventKind.CONSTELLATION_COMPLETE,
        {"by": display},
    )


def entangled_twin(node: SpatialNode) -> SpatialNode | None:
    """Return the structurally paired live-entangled particle, if any."""
    if node.level != "SubatomicParticle" or node.parent is None:
        return None
    suffix = node.name.rpartition("-")[2]
    if not suffix or not suffix[-1].isdigit():
        return None
    ordinal = int(suffix[-1])
    twin_suffix = suffix[:-1] + str(
        ordinal + 1 if ordinal % 2 == 1 else ordinal - 1
    )
    twin = next(
        (
            child
            for child in node.parent.children
            if child.name.rpartition("-")[2] == twin_suffix
        ),
        None,
    )
    if twin is None:
        return None
    tendencies = (node.properties.get("tendency"), twin.properties.get("tendency"))
    return twin if "entangled" in tendencies else None


def resolve_entangled_twin(
    seed: int,
    room,
    twin: SpatialNode,
    origin_name: str,
    solver: str | None,
    contributors: list,
    actor_identity: str | None,
) -> None:
    """Resolve an unsolved twin alongside its entangled partner."""
    epoch = persistence.count_node_mutations(seed, twin.name, "PUZZLE_REARM")
    twin_puzzle = build_puzzle(twin, epoch)
    if persistence.get_puzzle_solve(seed, twin.name, twin_puzzle.name):
        return
    display = solver if solver != "anonymous" else None
    persistence.record_mutation(
        seed,
        twin.name,
        "PUZZLE_SOLVED",
        display,
        {
            "puzzle": twin_puzzle.name,
            "contributors": contributors,
            "entangled_with": origin_name,
        },
        actor_identity=actor_identity,
    )
    twin_session = get_puzzle_session(room, twin.name, twin_puzzle.name)
    with room.lock:
        twin_session.solver = solver
        twin_session.contributors |= set(contributors)
    broadcast(
        room,
        {
            "type": "puzzle_solved",
            "node": twin.name,
            "puzzle": twin_puzzle.name,
            "solver": solver,
            "contributors": contributors,
            "entangled_with": origin_name,
        },
    )


def resolve_node(seed: int, node_name: str) -> SpatialNode | None:
    """Resolve and hydrate a client-named node from the authoritative store."""
    if not node_name:
        return None
    node = store.resolve_node_by_name(seed, node_name)
    if node is None:
        return None
    node.ripple_score = persistence.get_ripple_score(seed, node.name)
    overlay = persistence.load_node_property_overrides(seed).get(node.name)
    if overlay:
        node.properties.update(overlay)
    return node
