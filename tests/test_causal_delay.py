"""Staged cascades: causality with delay.

The origin of a strong event fires immediately; every subsequent ring rides
the durable causal_queue and is fired by the pump after a per-hop delay —
same physics (dampening, MIN_STRENGTH floor, record/ripple/effects wiring),
different arrival times. These tests drive the queue directly with a zero
hop delay so the full cascade can be walked deterministically.
"""
from __future__ import annotations

import json
import threading
import urllib.request

import pytest

import persistence
from causality import CausalityBus, EventKind, MIN_STRENGTH
from causality.staging import (
    STAGED_DAMPENING, drain_due_hops, hop_delay_seconds, stage_cascade,
)
from causality.wiring import wire_world_handlers
from multiverse.generator import generate_node_hierarchy
from multiverse.node import SpatialNode


@pytest.fixture(autouse=True)
def _zero_hop_delay(monkeypatch):
    monkeypatch.setenv("NESTED_WORLDS_HOP_DELAY", "0")
    yield


def _tree():
    region = SpatialNode("Region-A", "Region", properties={"danger_level": 6})
    room = SpatialNode("Room-A", "Room", properties={"has_puzzle": True})
    obj = SpatialNode("Obelisk-A", "Object", properties={"condition": "worn"})
    region.add_child(room)
    room.add_child(obj)
    return region, room, obj


class TestStageCascade:
    def test_first_ring_is_enqueued_not_fired(self):
        region, room, obj = _tree()
        n = stage_cascade(31, room, EventKind.PUZZLE_SOLVED, {"puzzle": "P"})
        assert n == 2  # parent (up) + one child (down)
        assert persistence.pending_causal_hops(31) == 2
        # Nothing has fired yet: no mutations at the neighbors.
        assert persistence.get_node_history(31, "Region-A") == []
        assert persistence.get_node_history(31, "Obelisk-A") == []

    def test_hop_delay_env(self, monkeypatch):
        monkeypatch.setenv("NESTED_WORLDS_HOP_DELAY", "45")
        assert hop_delay_seconds() == 45.0
        monkeypatch.setenv("NESTED_WORLDS_HOP_DELAY", "bogus")
        assert hop_delay_seconds() == 12.0


class TestDrain:
    def _canonical_room(self, seed):
        """A canonical Room node with both a parent and children."""
        root = generate_node_hierarchy(seed=seed)
        stack = [root]
        while stack:
            n = stack.pop()
            if n.level == "Room" and n.children:
                return n
            stack.extend(n.children)
        pytest.skip("no mid-world Room in this seed")

    def test_due_hops_fire_with_wiring_and_chain_onward(self):
        seed = 33
        room = self._canonical_room(seed)
        parent_name = room.parent.name

        stage_cascade(seed, room, EventKind.PUZZLE_SOLVED, {"puzzle": "P"})
        first_ring = persistence.pending_causal_hops(seed)
        assert first_ring >= 1

        fired = drain_due_hops()
        assert fired == first_ring

        # The parent hop fired through the full wiring: mutation recorded,
        # ripple accrued at the dampened strength, material effect applied.
        history = [h["type"] for h in persistence.get_node_history(seed, parent_name)]
        assert "PUZZLE_SOLVED" in history
        assert persistence.get_ripple_score(seed, parent_name) == pytest.approx(
            STAGED_DAMPENING * 0.1)
        overlay = persistence.load_node_property_overrides(seed)
        assert overlay.get(parent_name, {}).get("stabilized") is True

        # And the cascade chained: the NEXT ring is now queued (0.25 ≥ floor).
        assert persistence.pending_causal_hops(seed) > 0

    def test_full_cascade_matches_synchronous_reach(self):
        # Walking the queue to exhaustion must visit exactly the nodes a
        # synchronous propagate() would have, at the same strengths.
        region, room, obj = _tree()

        sync_bus = CausalityBus()
        sync_bus.propagate(room, EventKind.PUZZLE_SOLVED, {"puzzle": "P"},
                           dampening=STAGED_DAMPENING)
        sync_reach = {name: ev.strength for name, ev in sync_bus.get_log()}

        # Staged: fire origin, then drain rings until dry. Nodes here are
        # synthetic (not canonical), so drain against a stub world resolver —
        # instead, rebuild the same synthetic tree names via a custom drain:
        # use the canonical-world drain path only for canonical nodes; for
        # this equivalence test, walk the queue manually.
        seed = 34
        staged_reach = {"Room-A": 1.0}
        stage_cascade(seed, room, EventKind.PUZZLE_SOLVED, {"puzzle": "P"})
        nodes_by_name = {"Region-A": region, "Room-A": room, "Obelisk-A": obj}
        while True:
            rows = persistence.claim_due_causal_hops()
            if not rows:
                break
            for row in rows:
                node = nodes_by_name[row["node_name"]]
                staged_reach[node.name] = row["strength"]
                nxt = row["strength"] * STAGED_DAMPENING
                if nxt >= MIN_STRENGTH:
                    if row["direction"] == "up" and node.parent is not None:
                        persistence.enqueue_causal_hop(
                            seed, node.parent.name, row["kind"], nxt, "up",
                            row["payload"], 0)
                    elif row["direction"] == "down":
                        for child in node.children:
                            persistence.enqueue_causal_hop(
                                seed, child.name, row["kind"], nxt, "down",
                                row["payload"], 0)

        assert staged_reach == pytest.approx(sync_reach)

    def test_drain_broadcasts_each_arrival(self):
        seed = 35
        room = self._canonical_room(seed)
        stage_cascade(seed, room, EventKind.PUZZLE_SOLVED, {"puzzle": "P"})
        seen = []
        drain_due_hops(broadcaster=lambda s, node, ev: seen.append(
            (s, node.name, round(ev.strength, 4))))
        assert seen, "live players must see hops arrive"
        assert all(s == seed for s, _, _ in seen)
        assert all(strength == pytest.approx(0.5) for _, _, strength in seen)

    def test_vanished_node_hops_are_dropped_harmlessly(self):
        persistence.enqueue_causal_hop(
            36, "Never-Existed-99", "PUZZLE_SOLVED", 0.5, "up", {}, 0)
        assert drain_due_hops() == 0
        assert persistence.pending_causal_hops(36) == 0


class TestSolveStagesOverHTTP:
    def test_solve_fires_origin_now_and_queues_the_rest(self):
        from server import _Handler, _ThreadedServer
        from puzzles.generators import build_puzzle

        server = _ThreadedServer(("127.0.0.1", 0), _Handler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            root = generate_node_hierarchy(seed=42, max_depth=6)
            target = root.children[0]  # has parent and children
            answer = build_puzzle(target).answer
            body = json.dumps({"seed": 42, "depth": 6, "node_name": target.name,
                               "answer": answer, "player_name": "Ada"}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/puzzle/attempt", data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
            assert data["correct"] is True

            # Origin fired immediately…
            origin_types = [h["type"] for h in
                            persistence.get_node_history(42, target.name)]
            assert "PUZZLE_SOLVED" in origin_types
            # …but the neighbors have not been touched yet: their hops are
            # in flight on the queue.
            assert persistence.pending_causal_hops(42) >= 2
            parent_types = [h["type"] for h in
                            persistence.get_node_history(42, root.name)]
            assert "PUZZLE_SOLVED" not in parent_types

            # The pump delivers them (hop delay is 0 in this test).
            drain_due_hops()
            parent_types = [h["type"] for h in
                            persistence.get_node_history(42, root.name)]
            assert "PUZZLE_SOLVED" in parent_types
        finally:
            server.shutdown()
