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
from agents.roster import profile_for
from causality import CausalityBus, EventKind
from causality.staging import stage_cascade
from causality.wiring import wire_world_handlers
from multiverse.generator import LEVELS, generate_node_hierarchy
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
# traces read as individuals rather than anonymous noise. Each name carries
# a trait sheet (agents/roster.py) — deliberate persona, home scales, a
# personal danger threshold, a banter tic — that this module reads so the
# regulars behave like individuals. The name list itself lives in
# consciousness (a leaf module) because the cached bibles teach every node
# voice to recognize these names as returning regulars.
from consciousness import WANDERER_CAST as WANDERER_ROSTER


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


def _drop_in(root: SpatialNode, rng: random.Random,
             profile=None) -> SpatialNode:
    """A random mid-world node to start from — somewhere with ground below.

    Cast regulars gravitate home: most drop-ins aim the walk at one of the
    agent's home levels (Marginalia sinks to Molecules, Aunt Entropy stays
    among the cosmic shells), the rest ramble shallow like anyone else. On
    the way down, children flagged ``contains_npc`` pull the walk toward
    them — inhabited rooms actually receive visitors.
    """
    hops = rng.randint(1, 5)
    if profile is not None and profile.home_levels and rng.random() < 0.6:
        home_depths = [LEVELS.index(lvl) for lvl in profile.home_levels
                       if lvl in LEVELS]
        if home_depths:
            hops = rng.choice(home_depths)
    node = root
    for _ in range(hops):
        if not node.children:
            break
        peopled = [c for c in node.children
                   if (c.properties or {}).get("contains_npc")]
        if peopled and rng.random() < 0.5:
            node = rng.choice(peopled)
        else:
            node = rng.choice(node.children)
    while not node.children and node.parent is not None:
        node = node.parent
    return node


def _persona_act(seed: int, room, root: SpatialNode, agent_name: str,
                 persona_name: str, visited_names: list[str],
                 rng: random.Random, bus: CausalityBus) -> str | None:
    """After a traversal, the wanderer acts on the world by temperament.

    This is the world's living entropy loop: DESTABILIZERS emit real decay
    (STRUCTURAL_CHANGE on matter, DANGER_ALERT elsewhere — the events the
    restorative verbs exist to answer, and the trigger that re-arms solved
    puzzles); TENDERS perform the visited node's own verb (ward, mend,
    attune…), pushing back; SCHOLARS document (inscribe / observe /
    calibrate). Wanderers only pass through. Every act rides the standard
    causal rails with agent attribution. Returns a summary string or None.
    """
    from multiverse.utils import find_node
    from multiverse.verbs import apply_verb, verb_for_level

    if rng.random() > 0.6 or not visited_names:
        return None
    nodes = [n for n in (find_node(root, name)
                         for name in rng.sample(visited_names,
                                                min(4, len(visited_names))))
             if n is not None]
    # A regular reaches for their signature act first: nodes whose level
    # verb matches the profile's favored verb move to the front, so The
    # Locksmith inscribes and Bellhollow wards whenever the ground allows.
    profile = profile_for(agent_name)
    if profile is not None and profile.favored_verb:
        nodes.sort(key=lambda n: (verb_for_level(n.level) is None
                                  or verb_for_level(n.level).name
                                  != profile.favored_verb))
    payload = {"agent": agent_name, "persona": persona_name}

    if persona_name == "destabilizer":
        for node in nodes[:2]:
            kind = (EventKind.STRUCTURAL_CHANGE
                    if "condition" in (node.properties or {})
                    else EventKind.DANGER_ALERT)
            bus.emit(node, kind, dict(payload))
            stage_cascade(seed, node, kind, dict(payload))
        return f"destabilized {min(2, len(nodes))} node(s)"

    if persona_name in ("tender", "scholar"):
        allowed = None if persona_name == "tender" else (
            "inscribe", "observe", "calibrate")
        for node in nodes:
            verb = verb_for_level(node.level)
            if verb is None or (allowed and verb.name not in allowed):
                continue
            changed, flavor = apply_verb(node, verb,
                                         token=f"{agent_name}:{node.name}")
            if not changed:
                continue
            persistence.upsert_node_properties(seed, node.name, changed)
            persistence.record_mutation(
                seed, node.name, "SCALE_ACT", None,
                {"verb": verb.name, "changed": changed, **payload},
                actor_identity=agent_name)
            broadcast(room, {
                "type": "scale_act", "node": node.name, "level": node.level,
                "verb": verb.name, "actor": agent_name,
                "changed": changed, "flavor": flavor,
            })
            act_payload = {"verb": verb.name, **payload}
            act_bus = wire_world_handlers(CausalityBus(), seed, record=False)
            act_bus.emit(node, EventKind.SCALE_ACT, act_payload)
            stage_cascade(seed, node, EventKind.SCALE_ACT, act_payload)
            return f"{verb.name}ed {node.name}"
    return None


def _hold_conversation(seed: int, room, node: SpatialNode,
                       agent_a: str, persona_a: str,
                       agent_b: str, persona_b: str) -> None:
    """Two co-located wanderers talk; the exchange persists and broadcasts.

    The meeting ordinal (how many conversations this node has already
    hosted) keys the deterministic exchange, so the same pair meeting at
    the same place twice says something new the second time.
    """
    from agents.banter import compose_exchange

    prior = [h for h in persistence.get_node_history(seed, node.name, limit=50)
             if h["type"] == "AGENT_TALK"]
    lines = compose_exchange(seed, node, agent_a, persona_a,
                             agent_b, persona_b, ordinal=len(prior))
    persistence.record_mutation(
        seed, node.name, "AGENT_TALK", None,
        {"a": agent_a, "a_persona": persona_a,
         "b": agent_b, "b_persona": persona_b,
         "lines": lines},
    )
    broadcast(room, {
        "type":  "agent_talk",
        "node":  node.name,
        "level": node.level,
        "a":     agent_a,
        "b":     agent_b,
        "lines": lines,
    })


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
    profile = profile_for(agent_name)

    root = generate_node_hierarchy(seed=seed)
    apply_ripple_scores(root, persistence.load_ripple_scores(seed))
    apply_property_overrides(root, persistence.load_node_property_overrides(seed))
    target = _drop_in(root, rng, profile)

    room = get_room(seed)
    distance_map = build_distance_map(target)
    agent_enter(room, agent_name, persona=persona.name)

    # Roughly a third of ticks are social: a second wanderer is already
    # loitering where the walker drops in, so the two actually MEET — an
    # encounter broadcast plus a persisted conversation — instead of the
    # cast only ever walking the world alone. Ground flagged contains_npc
    # is where someone is usually home: meetings there are twice as likely.
    companion = None
    social_p = 0.7 if (target.properties or {}).get("contains_npc") else 0.35
    if rng.random() < social_p:
        others = [n for n in WANDERER_ROSTER if n != agent_name]
        companion = rng.choice(others)
        companion_persona = persona_for_name(companion)
        agent_enter(room, companion, persona=companion_persona.name)
        agent_move(room, companion, target.name)

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
            other_persona = agent_persona(room, other_name)
            broadcast(room, {
                "type":           "agent_encounter",
                "agent1":         agent_name,
                "agent1_persona": persona.name,
                "agent2":         other_name,
                "agent2_persona": other_persona,
                "node":           node.name,
                "level":          node.level,
            })
            # The meeting is a conversation, not just a proximity ping:
            # a deterministic in-character exchange (zero API cost) that
            # persists into node history — players who arrive later find
            # the transcript, and the node's voice can allude to it.
            _hold_conversation(seed, room, node, agent_name, persona.name,
                               other_name, other_persona)

    bus = CausalityBus()
    bus.register_handler(live_handler)
    wire_world_handlers(bus, seed)

    # Courage is character: each regular withdraws at their own threshold
    # (Aunt Entropy walks into anything; The Locksmith turns back early).
    threshold = profile.danger_threshold if profile is not None else 7
    agent = Agent(name=agent_name, danger_threshold=threshold, bus=bus,
                  persona=persona)
    saved = persistence.load_agent_memory(agent_name, seed)
    if saved:
        agent.memory = saved["visited_ids"]

    act = None
    try:
        agent.traverse(target, max_nodes=max_nodes, pace=pace)
        events = [{"node": e.node_name, "level": e.level, "state": e.state.name,
                   "action": e.action, "persona": e.persona} for e in agent.log]
        persistence.save_agent_run(agent_name, seed, agent.fresh_count, events)
        persistence.save_agent_memory(agent_name, seed, agent.memory,
                                      events[-100:])

        # The wanderer acts on the world by temperament — the living entropy
        # (destabilizers) and tending (tenders/scholars) loop. This runs
        # BEFORE agent_leave: a destabilizer's decay events replay through
        # live_handler, whose agent_move would otherwise re-register the
        # walker after departure and leave a ghost in room.active_agents.
        act = _persona_act(seed, room, root, agent_name, persona.name,
                           [e["node"] for e in events], rng, bus)
    finally:
        agent_leave(room, agent_name)
        if companion is not None:
            agent_leave(room, companion)

    broadcast(room, {"type": "agent_done", "node": target.name,
                     "nodes_visited": agent.fresh_count})
    summary = {"seed": seed, "agent": agent_name, "persona": persona.name,
               "origin": target.name, "fresh": agent.fresh_count,
               "act": act}
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


# ── The causal pump ─────────────────────────────────────────────────────────
# Staged cascades (causality/staging.py) put each ring of a strong event on
# the durable causal_queue; this pump fires due hops every few seconds and
# broadcasts each arrival to the seed-room, so consequences visibly travel
# outward instead of completing invisibly inside one request.

PUMP_DISABLE_ENV = "NESTED_WORLDS_CAUSAL_PUMP"
_PUMP_INTERVAL = 5.0


def pump_enabled() -> bool:
    return os.environ.get(PUMP_DISABLE_ENV, "").strip() != "0"


def _pump_broadcaster(seed, node, event) -> None:
    broadcast(get_room(seed), {
        "type":     "causal_event",
        "node":     node.name,
        "level":    node.level,
        "kind":     event.kind.name,
        "strength": round(event.strength, 4),
        "origin":   event.origin_id,
        "staged":   True,
    })


def run_pump_loop(stop: threading.Event) -> None:
    from causality import staging
    _log.info("causal pump started (interval %.0fs, hop delay %.0fs)",
              _PUMP_INTERVAL, staging.hop_delay_seconds())
    while not stop.wait(_PUMP_INTERVAL):
        try:
            staging.drain_due_hops(broadcaster=_pump_broadcaster)
        except Exception:  # noqa: BLE001 — cascades must keep traveling
            _log.exception("causal pump tick failed; continuing")


def start_pump() -> threading.Event:
    """Start the causal pump thread. Returns the stop event."""
    stop = threading.Event()
    threading.Thread(target=run_pump_loop, args=(stop,), daemon=True,
                     name="causal-pump").start()
    return stop
