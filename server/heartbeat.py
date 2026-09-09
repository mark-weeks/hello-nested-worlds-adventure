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
import sqlite3
import threading

import persistence
from agents.agent import Agent
from agents.behaviors import State, should_preserve
from agents.personas import for_name as persona_for_name
from agents.roster import profile_for
from causality import CausalityBus, EventKind
from causality.staging import stage_cascade
from causality.delivery import accept_verb, deliver_due
from causality.wiring import wire_world_handlers
from multiverse import store
from multiverse.generator import DEFAULT_WORLD_SEED, LEVELS
from multiverse.node import SpatialNode
from server import guard, rooms as _rooms_module
from server.history import narration_fields, broadcast_history_batch
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
from consciousness import WANDERER_CAST as WANDERER_ROSTER  # noqa: E402


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
    """Stay in the hosted world; local multi-world mode retains old routing."""
    hosted = guard.canonical_seed()
    if hosted is not None:
        return hosted
    with _rooms_module._rooms_lock:
        inhabited = [seed for seed, room in _rooms_module._rooms.items()
                     if room.players]
    if inhabited:
        return rng.choice(inhabited)
    worlds = persistence.list_worlds()
    if worlds:
        return worlds[0]["seed"]
    return DEFAULT_WORLD_SEED


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
                 rng: random.Random, on_event=None, *, node_index=None, attempt=None,
                 on_action=None, chance=True) -> str | None:
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
    from multiverse.verbs import verb_for_level

    if not visited_names or chance and rng.random() > 0.6:
        return None
    nodes = [n for n in ((node_index.get(name) if node_index is not None else find_node(root, name))
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

    def perform(node, operation):
        return attempt(node, "persona", operation) if attempt else operation()

    if persona_name == "destabilizer":
        count = 0
        for node in nodes[:2]:
            kind = (EventKind.STRUCTURAL_CHANGE
                    if "condition" in (node.properties or {})
                    else EventKind.DANGER_ALERT)
            def decay():
                from multiverse.effects import compute_event_effects
                if not compute_event_effects(node.properties, kind, 1.0):
                    return None
                return _ambient_event(seed, node, kind, payload, cascade=True)
            accepted = perform(node, decay)
            if accepted is not None:
                event, _staged = accepted
                count += 1
                if on_action is not None:
                    on_action(node, "destabilized")
                if on_event is not None:
                    on_event(node, event)
        return f"destabilized {count} node(s)" if count else None

    if persona_name in ("tender", "scholar"):
        allowed = None if persona_name == "tender" else (
            "inscribe", "observe", "calibrate")
        for node in nodes:
            verb = verb_for_level(node.level)
            if verb is None or (allowed and verb.name not in allowed):
                continue
            token = f"{agent_name}:{node.name}"
            act_payload = {"verb": verb.name, **payload}
            accepted = perform(node, lambda: accept_verb(
                seed, node, verb, token, act_payload, act_payload,
                actor_identity=agent_name, maturation_actor=agent_name))
            if accepted is None:
                continue
            result, _staged = accepted
            if result["action_status"] != "accepted":
                continue
            if on_action is not None:
                on_action(node, f"{verb.name}ed")
            try:
                broadcast(room, {
                    "type": "scale_act", "node": node.name, "level": node.level,
                    "verb": verb.name, "actor": agent_name,
                    **{key: value for key, value in result.items() if key != "flavor"},
                    **narration_fields(seed, result["event_id"]),
                })
            except Exception:
                _log.exception("committed cast action notice failed")
            return f"{verb.name}ed {node.name}"
    return None


def _ambient_event(seed, node, kind, payload, *, cascade=False):
    """Existing origin event + pressure + optional ring, committed before notice."""
    with persistence.transaction():
        event = wire_world_handlers(CausalityBus(), seed).emit(node, kind, dict(payload))
        event.recorded_id = persistence.latest_event_id(kind.name)
        event.origin_id = node.name
        staged = (stage_cascade(seed, node, kind, payload,
                                source_event_id=event.recorded_id) if cascade else 0)
    return event, staged


def _chain(node):
    while node is not None:
        yield node
        node = node.parent


def _accessible(node, signals, threshold, current_name=None):
    from puzzles.generators import build_puzzle
    for ancestor in _chain(node):
        if ancestor is not node and should_preserve(ancestor, threshold):
            return False
        if ancestor.level == "Room" and ancestor.properties.get("locked"):
            if current_name and current_name.rpartition('-')[2].startswith(ancestor.name.rpartition('-')[2]):
                continue  # already inside: the seal never imprisons
            signal = signals[ancestor.name]
            if build_puzzle(ancestor, signal["epoch"]).name not in signal["solved"]:
                return False
    return True


def _hold_conversation(seed: int, room, node: SpatialNode,
                       agent_a: str, persona_a: str,
                       agent_b: str, persona_b: str) -> None:
    """Two co-located wanderers talk; the exchange persists and broadcasts.

    The meeting ordinal (how many conversations this node has already
    hosted) keys the deterministic exchange, so the same pair meeting at
    the same place twice says something new the second time.
    """
    from agents.banter import compose_exchange

    prior = [h for h in persistence.get_node_history(seed, node.name, limit=50,
                                                  include_narration=False)
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
    rng = rng or random.Random()
    seed = _pick_seed(rng) if seed is None else seed
    # Birth is one-time world initialization, never repeated world evolution.
    store.ensure_born(seed)
    with persistence.agent_work_budget() as budget:
        try:
            result = _run_tick(seed, rng, max_nodes, pace)
        except sqlite3.OperationalError as exc:
            if str(exc) != 'interrupted' or budget['steps'] < budget['limit']:
                raise
            # Earlier commits remain authoritative; never claim zero effects.
            _log.warning('heartbeat SQL work budget exhausted; committed work retained')
            result = {'seed': seed, 'status': 'work_limit', 'fresh': None, 'act': None,
                      'work': {'projection_limited': True, 'interrupted': True}}
        result['work']['sql_steps'] = budget['steps']
        return result


def _run_tick(seed, rng, max_nodes, pace):
    """One heartbeat: a wandering agent moves through the world, leaving
    persistent traces and live broadcasts. Returns a small summary."""
    rng = rng or random.Random()
    if seed is None:
        seed = _pick_seed(rng)

    agent_name = rng.choice(WANDERER_ROSTER)
    persona = persona_for_name(agent_name)
    profile = profile_for(agent_name)

    # max_nodes bounds actual visits; even callers requesting enormous walks
    # cannot exceed this heartbeat's independent inspection/action caps.
    visit_limit = max(0, min(10, int(max_nodes)))
    inspect_limit = min(40, visit_limit * 4)
    root = store.world_tree(seed=seed)
    nodes, stack = [], [root]
    while stack:
        node = stack.pop()
        nodes.append(node)
        stack.extend(reversed(node.children))
    node_index = {node.name: node for node in nodes}
    positions = {node.name: i for i, node in enumerate(nodes)}
    saved = persistence.load_agent_memory(agent_name, seed) or {}
    target = _drop_in(root, rng, profile)
    cursor = saved.get("scan_cursor")
    start = (positions[cursor] + 1) % len(nodes) if cursor in positions else positions[target.name]
    fair = [nodes[(start + i) % len(nodes)] for i in range(min(inspect_limit, len(nodes)))]
    fair_names = {node.name for node in fair}
    known = set(saved.get("visited_ids", []))
    priority_limit = min(2, max(0, visit_limit - 1))
    priority = [node_index[name] for name in persistence.recent_attention_nodes(seed, agent_name)
                if name in known and name in node_index and name not in fair_names][:priority_limit]
    priority_names = {node.name for node in priority}
    candidates = priority + fair[:inspect_limit - len(priority)]
    target = candidates[0] if candidates else target
    related = {n.name: n for candidate in candidates for n in _chain(candidate)}
    # Keep born values separate: a concurrent tombstone must not resurrect a
    # value from the previous overlaid snapshot when admission refreshes it.
    born = {name: dict(node.properties) for name, node in related.items()}
    threshold = profile.danger_threshold if profile is not None else 7
    agent = Agent(name=agent_name, danger_threshold=threshold, persona=persona,
                  world_seed=seed, memory=list(saved.get("visited_ids", [])))
    agent._memory_before = len(agent.memory)
    work = {"inspected": 0, "visited": 0, "puzzle_attempts": 0,
            "persona_attempts": 0, "origin_effects": 0, "initial_hops": 0,
            "hydrated_nodes": len(nodes), "persona_moves": 0, "conversations": 0,
            "projection_limited": False}
    room = get_room(seed)
    companion = None
    act = None
    signals, markers = {}, {}
    persona_candidates = []
    current_name = None
    fair_cursor = cursor

    def refresh(selected):
        overrides = persistence.load_node_property_overrides(seed, list(selected))
        for name, node in selected.items():
            node.properties = persistence.json_merge_patch(born[name], overrides.get(name, {}))
        return persistence.agent_attention_signals(seed, list(selected), seals=True)

    def notice(node, event):
        # Notification/read failures cannot refund a committed opportunity.
        try:
            broadcast(room, {"type": "causal_event", "node": node.name,
                "level": node.level, "kind": event.kind.name,
                "strength": event.strength, "origin": event.origin_id,
                "agent": agent_name, "persona": persona.name,
                "event_id": event.recorded_id, **narration_fields(seed, event.recorded_id)})
        except Exception:
            _log.exception("committed heartbeat notice failed")

    def attempt(node, mode, operation):
        key = "puzzle_attempts" if mode == "puzzle" else "persona_attempts"
        if work[key] >= (2 if mode == "puzzle" else 4):
            return None
        if work["puzzle_attempts"] + work["persona_attempts"] >= 4:
            return None
        # Count admission attempts too, including a race-lost or no-op attempt.
        work[key] += 1
        with persistence.transaction():
            current_signals = refresh({n.name: n for n in _chain(node)})
            state = persistence.load_agent_attention(agent_name, seed, [node.name]).get(node.name, {})
            signal = current_signals[node.name]
            field, value = ("puzzle", signal["epoch"]) if mode == "puzzle" else ("change", signal["change"])
            if (state.get(field, -1) >= value or not _accessible(node, current_signals, threshold, current_name)
                    or should_preserve(node, threshold)):
                return None
            result = operation(signal) if mode == "puzzle" else operation()
            persistence.mark_agent_attention(agent_name, seed, node.name, **{field: value})
        if result is not None:
            first, staged = result
            accepted = not isinstance(first, dict) or first.get("action_status") == "accepted"
            if accepted:
                work["origin_effects"] += 1
                work["initial_hops"] += staged
        return result

    def visit(node, fresh):
        nonlocal current_name, fair_cursor
        if node.name not in priority_names:
            fair_cursor = node.name
        signal = signals[node.name]
        state = markers.get(node.name, {})
        if not _accessible(node, signals, threshold, current_name):
            return False
        danger = should_preserve(node, threshold)
        from multiverse.verbs import verb_for_level
        verb = verb_for_level(node.level)
        persona_eligible = (persona.name in ("tender", "destabilizer") or
                            persona.name == "scholar" and verb is not None and
                            verb.name in ("inscribe", "observe", "calibrate"))
        changed = signal["change"] > state.get("change", -1)
        puzzle_due = (not danger and node.properties.get("has_puzzle") and
                      signal["epoch"] > state.get("puzzle", -1))
        if not (fresh or changed and (persona_eligible or danger) or puzzle_due):
            return False
        # Actual movement is separate from event propagation, and precedes any
        # encounter. The companion is only present for a real visit.
        nonlocal companion
        if not agent.activity_nodes and rng.random() < (0.7 if node.properties.get("contains_npc") else 0.35):
            others = [name for name in WANDERER_ROSTER if name != agent_name]
            if others:
                companion = rng.choice(others)
                companion_persona = persona_for_name(companion)
                agent_enter(room, companion, persona=companion_persona.name)
                agent_move(room, companion, node.name)
        for other in agent_move(room, agent_name, node.name)[:1]:
            other_persona = agent_persona(room, other)
            broadcast(room, {"type": "agent_encounter", "agent1": agent_name,
                "agent1_persona": persona.name, "agent2": other,
                "agent2_persona": other_persona, "node": node.name, "level": node.level})
            if work['conversations'] < 1:
                _hold_conversation(seed, room, node, agent_name, persona.name, other, other_persona)
                work['conversations'] += 1
        current_name = node.name
        agent.state = State.EXPLORE
        if danger:
            agent._record(node, f"withdrew (danger_level={node.properties.get('danger_level')})")
            # Remember observing this unsafe condition without amplifying it.
            persistence.mark_agent_attention(agent_name, seed, node.name, change=signal["change"])
            return True
        agent._record(node, "explored" if fresh else "revisited")
        if persona_eligible and changed:
            persona_candidates.append(node.name)
        if fresh:
            event, _ = _ambient_event(seed, node, EventKind.AGENT_VISIT, agent._payload())
            work["origin_effects"] += 1
            notice(node, event)
        if puzzle_due:
            def puzzle_operation(current):
                solved, puzzle_name, difficulty = agent._attempt_puzzle(node, current["epoch"])
                agent.state = State.INTERACT
                agent._record(node, f"{'solved' if solved else 'failed'} the puzzle ({puzzle_name})")
                return _ambient_event(seed, node, EventKind.PUZZLE_SOLVED if solved else EventKind.PUZZLE_FAILED,
                    agent._payload(puzzle=puzzle_name, difficulty=difficulty), cascade=True)
            outcome = attempt(node, "puzzle", puzzle_operation)
            if outcome is not None:
                notice(node, outcome[0])
        return True

    def acted(node, action):
        nonlocal current_name
        # Choosing an earlier visited place entails an actual return, not
        # movement inferred from a remote consequence. At most two per tick.
        agent_move(room, agent_name, node.name)
        current_name = node.name
        work["persona_moves"] += 1
        agent._record(node, action)

    agent_enter(room, agent_name, persona=persona.name)
    try:
        try:
            signals = refresh(related)
            markers = persistence.load_agent_attention(agent_name, seed, list(related))
            agent.traverse(target, max_nodes=inspect_limit, pace=pace,
                           candidates=candidates, visit=visit, max_visits=visit_limit)
            # Eligibility comes from independently tracked visited places,
            # including familiar ones; the fresh-discovery log is not a queue.
            try:
                act = _persona_act(seed, room, root, agent_name, persona.name,
                    persona_candidates, rng, on_event=notice,
                    node_index=node_index, attempt=attempt, on_action=acted, chance=False)
            except persistence.AttentionReadLimit:
                raise
            except Exception:
                _log.exception("heartbeat persona attempt/notice failed")
        except persistence.AttentionReadLimit:
            work["projection_limited"] = True
            if not getattr(agent, 'inspected', 0) and fair:
                fair_cursor = fair[-1].name
            _log.warning("heartbeat attention projection exhausted its budget")
        events = [{"node": e.node_name, "level": e.level, "state": e.state.name,
                   "action": e.action, "persona": e.persona} for e in agent.log]
        # Discovery is a union even if another run saved memory during ours.
        with persistence.transaction():
            latest = persistence.load_agent_memory(agent_name, seed) or {}
            memory = list(dict.fromkeys(latest.get("visited_ids", []) + agent.memory))
            previous = latest.get("log_entries", [])
            persistence.save_agent_memory(agent_name, seed, memory, (previous + events)[-100:])
            if candidates:
                persistence.save_agent_scan_cursor(agent_name, seed,
                    fair_cursor or fair[-1].name)
        persistence.save_agent_run(agent_name, seed, agent.fresh_count, events)
    finally:
        agent_leave(room, agent_name)
        if companion is not None:
            agent_leave(room, companion)
    work.update(inspected=getattr(agent, "inspected", 0), visited=len(getattr(agent, "activity_nodes", [])))
    broadcast(room, {"type": "agent_done", "node": target.name,
                     "nodes_visited": agent.fresh_count})
    summary = {"seed": seed, "agent": agent_name, "persona": persona.name,
               "origin": target.name, "fresh": agent.fresh_count, "act": act, "work": work}
    _log.info("heartbeat: %s", summary)
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
    _pump_broadcast_batch([(seed, node, event)])


def _pump_broadcast_batch(events) -> None:
    broadcast_history_batch([(seed, {
        "type":     "causal_event",
        "node":     node.name,
        "level":    node.level,
        "kind":     event.kind.name,
        "strength": round(event.strength, 4),
        "origin":   event.origin_id,
        "staged":   True,
        "event_id": event.recorded_id,
    }) for seed, node, event in events],
        lambda seed, message: broadcast(get_room(seed), message))


def drain_matured_verbs(limit: int = 32, world_seed: int | None = None) -> int:
    """Land every planted cosmic-verb change whose time has come.

    Deep time's second half: the property delta finally applies, the
    chronicle gains a SCALE_ACT_MATURED row, and connected players watch
    the change arrive — often long after (and far from) whoever planted
    it. Returns maturations landed.
    """
    return deliver_due(
        "verb_maturation", limit, world_seed, _apply_maturation, None,
        notify_batch=lambda messages: broadcast_history_batch(
            messages, lambda seed, message: broadcast(get_room(seed), message)))


def _apply_maturation(row, notifications):
    seed, node_name = row["world_seed"], row["node_name"]
    resolved = store.resolve_node_by_name(seed, node_name)
    if resolved is None:
        return "missing_node"
    if row["semantics_version"] == 2:
        from multiverse import delayed_v2
        current = persistence.json_merge_patch(
            resolved.properties, persistence.load_node_property_override(seed, node_name))
        changed, outcome = delayed_v2.apply(
            row["verb"], resolved.level, current, row["operation"])
        flavor = delayed_v2.outcome_flavor(row["verb"], outcome)
        data = {"verb": row["verb"], "changed": changed, "outcome": outcome,
                "flavor": flavor, "semantics_version": 2,
                "source_event_id": row["source_event_id"],
                "delivery": {"queue": "verb_maturation", "id": row["id"]}}
        if changed:
            persistence.record_substance_change(
                seed, node_name, "SCALE_ACT_MATURED", row["actor"], data, changed,
                actor_identity=row["actor_identity"])
        else:
            persistence.record_mutation(
                seed, node_name, "SCALE_ACT_MATURED", row["actor"], data,
                actor_identity=row["actor_identity"])
        notifications.append((seed, {
            "type": "scale_act", "node": node_name, "level": resolved.level,
            "verb": row["verb"], "actor": row["actor"] or "someone",
            "changed": changed, "matured": True, "outcome": outcome,
            "flavor": flavor, "work_id": row["id"],
            "event_id": persistence.latest_event_id("SCALE_ACT_MATURED"),
        }))
        return outcome
    if not row["changed"]:
        return "empty_patch"
    persistence.record_substance_change(
        seed, node_name, "SCALE_ACT_MATURED", row["actor"],
        {"verb": row["verb"], "changed": row["changed"],
         "delivery": {"queue": "verb_maturation", "id": row["id"]}},
        row["changed"], actor_identity=row["actor"])
    notifications.append((seed, {
        "type": "scale_act", "node": node_name, "level": resolved.level,
        "verb": row["verb"],
        "actor": row["actor"] or "the slow work of someone",
        "changed": row["changed"], "matured": True,
        "work_id": row["id"],
        "event_id": persistence.latest_event_id("SCALE_ACT_MATURED"),
        "flavor": (f"The {row['verb']} planted here settles at last — "
                   "the change arrives."),
    }))
    return "applied"


def run_pump_loop(stop: threading.Event) -> None:
    from causality import staging
    _log.info("causal pump started (interval %.0fs, hop delay %.0fs)",
              _PUMP_INTERVAL, staging.hop_delay_seconds())
    while not stop.wait(_PUMP_INTERVAL):
        # Match request-time guard semantics: an operator seed change re-aims
        # both durable queue drains on their next tick, without a restart.
        hosted_seed = guard.canonical_seed()
        try:
            staging.drain_due_hops(world_seed=hosted_seed,
                                   broadcaster_batch=_pump_broadcast_batch)
        except Exception:  # noqa: BLE001 — cascades must keep traveling
            _log.exception("causal pump tick failed; continuing")
        try:
            drain_matured_verbs(world_seed=hosted_seed)
        except Exception:  # noqa: BLE001 — planted changes must still land
            _log.exception("verb maturation drain failed; continuing")


def start_pump() -> threading.Event:
    """Start the causal pump thread. Returns the stop event."""
    stop = threading.Event()
    threading.Thread(target=run_pump_loop, args=(stop,), daemon=True,
                     name="causal-pump").start()
    return stop
