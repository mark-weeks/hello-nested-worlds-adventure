"""World heartbeat — the multiverse moves between requests.

A daemon thread started by `server.run` wakes on an interval, picks a world
(rooms with live players first, then recently visited worlds), and sends a
persona-named agent on a short, PACED traversal wired with the standard
record/ripple/effects handlers plus a live room broadcast. Consequences:

  * The world genuinely runs unattended: agents visit, withdraw from danger,
    attempt puzzles (under the same engine rules as humans), and their
    events persist into node history, ripple pressure, and property
    changes — whether or not anyone is watching.
  * Connected players SEE it live: each fired event broadcasts to the
    seed-room as a `causal_event` (real strength), co-located heartbeat
    agents produce `agent_encounter`, and an `agent_done` closes the run.
  * Traversals are paced (seconds per hop), so ambient motion unfolds over
    observable time instead of microseconds.

Costs nothing per tick: heartbeat agents are FSM-driven — no Anthropic or
fal.ai calls — so ambient life never touches the daily budgets.

Env:
  NESTED_WORLDS_HEARTBEAT=0                 disable entirely
  NESTED_WORLDS_HEARTBEAT_INTERVAL=<secs>   seconds between ticks (default 180)
"""
from __future__ import annotations

import logging
import os
import random
import threading
import time

import persistence
from agents.agent import Agent
from agents.personas import for_name as persona_for_name
from causality import CausalityBus
from causality.wiring import wire_world_handlers
from multiverse.generator import generate_node_hierarchy
from multiverse.node import SpatialNode
from multiverse.utils import (
    apply_property_overrides, apply_ripple_scores, build_distance_map,
)
from server import rooms as _rooms_module
from server.rooms import (
    agent_enter, agent_leave, agent_move, agent_persona, broadcast, get_room,
)

_log = logging.getLogger("nested_worlds.heartbeat")

DISABLE_ENV = "NESTED_WORLDS_HEARTBEAT"
INTERVAL_ENV = "NESTED_WORLDS_HEARTBEAT_INTERVAL"
_DEFAULT_INTERVAL = 180.0
_DEFAULT_MAX_NODES = 10
_DEFAULT_PACE = 1.2  # seconds between hops — motion a watcher can follow

# A recurring cast: the same names return to the same worlds run after run,
# accreting memory (visited ground persists per (name, seed)), so their
# traces read as individuals rather than anonymous noise. Persona follows
# deterministically from the name (agents.personas.for_name).
WANDERER_ROSTER = [
    "Tessera", "Halden", "Mirrorbird", "Sela", "Cartographer-9",
    "Vex", "Aunt Entropy", "The Locksmith",
]


def enabled() -> bool:
    return os.environ.get(DISABLE_ENV, "").strip() != "0"


def interval_seconds() -> float:
    raw = os.environ.get(INTERVAL_ENV, "").strip()
    if not raw:
        return _DEFAULT_INTERVAL
    try:
        return max(10.0, float(raw))
    except ValueError:
        return _DEFAULT_INTERVAL


def _pick_seed(rng: random.Random) -> int:
    """Prefer a world with live players; otherwise a recently visited world;
    otherwise the default seed 42."""
    with _rooms_module._rooms_lock:
        inhabited = [seed for seed, room in _rooms_module._rooms.items()
                     if room.players]
    if inhabited:
        return rng.choice(inhabited)
    worlds = persistence.list_worlds()
    if worlds:
        return worlds[0]["seed"]
    return 42


def _drop_in(root: SpatialNode, rng: random.Random) -> SpatialNode:
    """A random mid-world node to start from — somewhere with ground below."""
    node = root
    hops = rng.randint(1, 5)
    for _ in range(hops):
        if not node.children:
            break
        node = rng.choice(node.children)
    while not node.children and node.parent is not None:
        node = node.parent
    return node


def run_tick(seed: int | None = None, rng: random.Random | None = None,
             max_nodes: int = _DEFAULT_MAX_NODES,
             pace: float = _DEFAULT_PACE) -> dict:
    """One heartbeat: a wandering agent moves through the world, leaving
    persistent traces and live broadcasts. Returns a small summary."""
    rng = rng or random.Random()
    if seed is None:
        seed = _pick_seed(rng)

    agent_name = rng.choice(WANDERER_ROSTER)
    persona = persona_for_name(agent_name)

    root = generate_node_hierarchy(seed=seed)
    apply_ripple_scores(root, persistence.load_ripple_scores(seed))
    apply_property_overrides(root, persistence.load_node_property_overrides(seed))
    target = _drop_in(root, rng)

    room = get_room(seed)
    distance_map = build_distance_map(target)
    agent_enter(room, agent_name, persona=persona.name)

    def live_handler(node, event):
        broadcast(room, {
            "type":     "causal_event",
            "node":     node.name,
            "level":    node.level,
            "kind":     event.kind.name,
            "strength": round(event.strength, 4),
            "depth":    distance_map.get(node.id, 0),
            "origin":   target.name,
            "agent":    agent_name,
            "persona":  persona.name,
        })
        for other_name in agent_move(room, agent_name, node.name):
            broadcast(room, {
                "type":           "agent_encounter",
                "agent1":         agent_name,
                "agent1_persona": persona.name,
                "agent2":         other_name,
                "agent2_persona": agent_persona(room, other_name),
                "node":           node.name,
                "level":          node.level,
            })

    bus = CausalityBus()
    bus.register_handler(live_handler)
    wire_world_handlers(bus, seed)

    agent = Agent(name=agent_name, danger_threshold=7, bus=bus, persona=persona)
    saved = persistence.load_agent_memory(agent_name, seed)
    if saved:
        agent.memory = saved["visited_ids"]

    try:
        agent.traverse(target, max_nodes=max_nodes, pace=pace)
    finally:
        agent_leave(room, agent_name)

    events = [{"node": e.node_name, "level": e.level, "state": e.state.name,
               "action": e.action, "persona": e.persona} for e in agent.log]
    persistence.save_agent_run(agent_name, seed, agent.fresh_count, events)
    persistence.save_agent_memory(agent_name, seed, agent.memory, events[-100:])

    broadcast(room, {"type": "agent_done", "node": target.name,
                     "nodes_visited": agent.fresh_count})
    summary = {"seed": seed, "agent": agent_name, "persona": persona.name,
               "origin": target.name, "fresh": agent.fresh_count}
    _log.info("heartbeat: %(agent)s (%(persona)s) walked %(fresh)d fresh "
              "node(s) from %(origin)s in world %(seed)d", summary)
    return summary


def run_loop(stop: threading.Event) -> None:
    """The daemon loop. One failed tick never kills the heartbeat."""
    _log.info("world heartbeat started (interval %.0fs)", interval_seconds())
    while not stop.wait(interval_seconds()):
        try:
            run_tick()
        except Exception:  # noqa: BLE001 — the world must keep beating
            _log.exception("heartbeat tick failed; continuing")


def start() -> threading.Event:
    """Start the heartbeat thread. Returns the stop event."""
    stop = threading.Event()
    threading.Thread(target=run_loop, args=(stop,), daemon=True,
                     name="world-heartbeat").start()
    return stop
