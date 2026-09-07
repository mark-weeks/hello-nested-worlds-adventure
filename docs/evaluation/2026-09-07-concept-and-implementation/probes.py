"""Bounded Enfolded evaluation probes; only disposable databases are touched.

Run with Python 3.11 from any directory; the repository is located from this
file. No database argument is accepted. These characterize current behavior,
not a production-time forecast or regression expectations for the defects.
"""
from __future__ import annotations

import json
import os
import random
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import persistence
from agents.agent import Agent
from causality import CausalityBus, EventKind
from causality.staging import drain_due_hops, stage_cascade
from causality.wiring import record_verb_act, wire_world_handlers
from multiverse import store
from multiverse.verbs import apply_verb, verb_for_level
from server import heartbeat


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def count_rows(table):
    # table names below are internal constants, never supplied by a player.
    with persistence._connect() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def fresh_db(directory, name):
    persistence._DB_PATH = Path(directory) / f"{name}.db"
    persistence.init_db()
    return store.world_tree(382)


def run():
    result = {}
    with (
        tempfile.TemporaryDirectory(prefix="enfolded-probes-") as directory,
        patch.dict(os.environ, {"NESTED_WORLDS_HOP_DELAY": "0"}),
        # fresh_db switches this path per probe; restore the caller's path
        # on exit, including failure, without ever opening that database.
        patch.object(persistence, "_DB_PATH", Path(directory) / "initial.db"),
        patch("server.rooms._rooms", {}),
    ):
        root = fresh_db(directory, "cast")
        nodes = list(walk(root))
        names = [node.name for node in nodes]
        # A constructed terminal memory state, not an elapsed-time simulation.
        for name in heartbeat.WANDERER_ROSTER:
            persistence.save_agent_memory(name, 382, names, [])
        summaries = [heartbeat.run_tick(382, random.Random(i), pace=0)
                     for i in range(12)]
        result["fully_explored_cast"] = {
            "world_nodes": len(nodes), "cast_size": len(heartbeat.WANDERER_ROSTER),
            "ticks": len(summaries),
            "fresh_visits": sum(s["fresh"] for s in summaries),
            "persona_acts": sum(s["act"] is not None for s in summaries),
            "chronicle_rows": count_rows("world_mutations"),
        }
        object_node = next(n for n in nodes if n.level == "Object")
        bus = CausalityBus()
        agent = Agent("RevisitProbe", bus=bus)
        object_node.properties["condition"] = "corrupted"
        # This illustrates the cast probe's same known-name skip branch:
        # condition is not consulted there, so no change detector is tested.
        # Keep the entire subtree known, with a nonzero fresh-visit budget.
        agent.memory = [n.name for n in walk(object_node)]
        agent.traverse(object_node, max_nodes=10)
        result["known_changed_subtree"] = {
            "traversal_events": len(agent.log), "causal_events": len(bus.get_log()),
        }

        root = fresh_db(directory, "queue")
        persistence.enqueue_causal_hop(382, root.name, "DANGER_ALERT", 1.0,
                                       "up", {}, 0)
        before = count_rows("causal_queue")
        with patch("causality.staging.store.world_tree",
                   side_effect=RuntimeError("injected failure after claim")):
            try:
                drain_due_hops()
            except RuntimeError:
                pass
        result["causal_claim_failure"] = {
            "queued_before": before, "queued_after_failure": count_rows("causal_queue"),
            "chronicle_rows_after_failure": count_rows("world_mutations"),
            "retry_fired": drain_due_hops(),
        }
        persistence.enqueue_verb_maturation(382, root.name, "attune",
                                             {"attuned": True}, "Probe", 0)
        with patch("server.heartbeat.persistence.record_substance_change",
                   side_effect=RuntimeError("injected write failure")):
            try:
                heartbeat.drain_matured_verbs()
            except RuntimeError:
                pass
        result["maturation_claim_failure"] = {
            "queued_after_failure": count_rows("verb_maturation"),
            "chronicle_rows_after_failure": count_rows("world_mutations"),
            "retry_landed": heartbeat.drain_matured_verbs(),
        }

        root = fresh_db(directory, "maturation")
        galaxy = next(n for n in walk(root) if n.level == "Galaxy"
                      and n.properties["star_density"] < 900)
        born_density = galaxy.properties["star_density"]
        verb = verb_for_level("Galaxy")
        # Exercise queue landing directly, bypassing the /act handler and its
        # guards. A handler fix that refuses/coalesces overlapping requests
        # need not change this output; it needs its own endpoint regression test.
        for _ in range(2):
            snapshot = store.resolve_node_by_name(382, galaxy.name)
            changed, _ = apply_verb(snapshot, verb)
            persistence.enqueue_verb_maturation(382, galaxy.name, verb.name,
                                                changed, "Probe", 0)
        landed = heartbeat.drain_matured_verbs()
        overlay = persistence.load_node_property_overrides(382)[galaxy.name]
        sequential = store.resolve_node_by_name(382, galaxy.name)
        for _ in range(2):
            apply_verb(sequential, verb)
        result["two_pending_kindles"] = {
            "born_density": born_density, "maturations_landed": landed,
            "final_density": overlay["star_density"],
            "sequential_two_action_density": sequential.properties["star_density"],
        }

        root = fresh_db(directory, "mend")
        obj = next(n for n in walk(root) if n.level == "Object"
                   and n.properties.get("condition") in ("damaged", "worn", "corrupted"))
        base = dict(obj.properties)
        verb = verb_for_level("Object")
        record_verb_act(382, obj, verb, "Probe", base,
                        {"verb": verb.name}, player_name="Probe")
        bus = wire_world_handlers(CausalityBus(), 382, record=False)
        bus.emit(obj, EventKind.SCALE_ACT, {"verb": verb.name})
        stage_cascade(382, obj, EventKind.SCALE_ACT, {"verb": verb.name})
        fired = 0
        for _ in range(64):
            if not count_rows("causal_queue"):
                break
            fired += drain_due_hops()
        if count_rows("causal_queue"):
            raise RuntimeError("mend cascade did not drain within 64 iterations")
        overlays = persistence.load_node_property_overrides(382)
        result["mend_consequences"] = {
            "node": obj.name, "condition_before": base["condition"],
            "condition_after": overlays[obj.name]["condition"],
            "propagated_events": fired,
            "nodes_with_material_property_changes": sum(bool(v) for v in overlays.values()),
            "chronicle_rows": count_rows("world_mutations"),
        }

    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
