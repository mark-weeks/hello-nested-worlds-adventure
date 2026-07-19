"""Causal events change world substance — and the change persists.

Covers multiverse/effects.py (event → property deltas), causality/wiring.py
(the standard record/ripple/effects bus wiring), the additive persisted
ripple increment, the property overlay round-trip through a world rebuild,
and the origin-relative distance map used for truthful broadcast depths.
"""
from __future__ import annotations

import pytest

import persistence
from causality import CausalEvent, CausalityBus, EventKind
from causality.wiring import wire_world_handlers
from multiverse.effects import EFFECT_THRESHOLD, apply_event_effects
from multiverse.node import SpatialNode
from multiverse.utils import (
    apply_property_overrides, build_distance_map, find_node,
)
from multiverse.generator import generate_node_hierarchy


def _event(kind, strength=1.0):
    return CausalEvent(kind=kind, origin_id="x", origin_level="Room",
                       strength=strength)


class TestApplyEventEffects:
    def test_below_threshold_changes_nothing(self):
        node = SpatialNode("R", "Region", properties={"danger_level": 5})
        out = apply_event_effects(node, _event(EventKind.DANGER_ALERT,
                                               strength=EFFECT_THRESHOLD - 0.01))
        assert out is None
        assert node.properties["danger_level"] == 5

    def test_danger_alert_raises_danger(self):
        node = SpatialNode("R", "Region", properties={"danger_level": 5})
        out = apply_event_effects(node, _event(EventKind.DANGER_ALERT))
        assert out == {"danger_level": 6}
        assert node.properties["danger_level"] == 6

    def test_danger_alert_caps_at_ten(self):
        node = SpatialNode("R", "Region", properties={"danger_level": 10})
        assert apply_event_effects(node, _event(EventKind.DANGER_ALERT)) is None

    def test_danger_alert_disturbs_nodes_without_danger(self):
        node = SpatialNode("P", "Planet", properties={"biome": "ocean"})
        out = apply_event_effects(node, _event(EventKind.DANGER_ALERT))
        assert out == {"disturbed": True}

    def test_puzzle_solved_stabilizes_and_calms(self):
        node = SpatialNode("R", "Region", properties={"danger_level": 7})
        out = apply_event_effects(node, _event(EventKind.PUZZLE_SOLVED))
        assert out["stabilized"] is True
        assert out["danger_level"] == 6

    def test_danger_floor_is_one(self):
        node = SpatialNode("R", "Region", properties={"danger_level": 1})
        out = apply_event_effects(node, _event(EventKind.PUZZLE_SOLVED))
        assert "danger_level" not in out

    def test_new_unrest_clears_stabilized(self):
        node = SpatialNode("R", "Region",
                           properties={"danger_level": 3, "stabilized": True})
        out = apply_event_effects(node, _event(EventKind.DANGER_ALERT))
        assert out["stabilized"] is False

    def test_structural_change_degrades_condition(self):
        node = SpatialNode("O", "Object", properties={"condition": "pristine"})
        assert apply_event_effects(node, _event(EventKind.STRUCTURAL_CHANGE)) == \
            {"condition": "worn"}
        assert apply_event_effects(node, _event(EventKind.STRUCTURAL_CHANGE)) == \
            {"condition": "damaged"}
        assert apply_event_effects(node, _event(EventKind.STRUCTURAL_CHANGE)) == \
            {"condition": "corrupted"}
        # Fully corrupted matter has nowhere further to fall.
        assert apply_event_effects(node, _event(EventKind.STRUCTURAL_CHANGE)) is None

    def test_agent_visit_changes_nothing(self):
        node = SpatialNode("R", "Room", properties={"lighting": "dim"})
        assert apply_event_effects(node, _event(EventKind.AGENT_VISIT)) is None


class TestWiredBusPersistence:
    def _tree(self):
        region = SpatialNode("Region-A", "Region", properties={"danger_level": 5})
        room = SpatialNode("Room-A", "Room", properties={"has_puzzle": True})
        region.add_child(room)
        return region, room

    def test_solve_cascade_persists_material_change(self):
        region, room = self._tree()
        bus = wire_world_handlers(CausalityBus(), seed=99)
        bus.propagate(room, EventKind.PUZZLE_SOLVED, {"puzzle": "The Lock"})

        # The origin room stabilized; the parent region calmed via the
        # dampened upward hop (0.5 ≥ effect threshold).
        overrides = persistence.load_node_property_overrides(99)
        assert overrides["Room-A"]["stabilized"] is True
        assert overrides["Region-A"]["danger_level"] == 4

        # Mutations recorded for both fires; ripple accrued additively.
        history = persistence.get_node_history(99, "Room-A")
        assert any(h["type"] == "PUZZLE_SOLVED" for h in history)
        assert persistence.get_ripple_score(99, "Room-A") == pytest.approx(0.1)
        assert persistence.get_ripple_score(99, "Region-A") == pytest.approx(0.05)

    def test_overlay_survives_world_rebuild(self):
        # Fire an effect against the canonical world, then rebuild the tree
        # and confirm the changed property is hydrated back on.
        root = generate_node_hierarchy(seed=98, max_depth=6)
        region = None

        def pick(n):
            nonlocal region
            if region is None and n.level == "Region":
                region = n
            for c in n.children:
                pick(c)

        pick(root)
        assert region is not None
        before = region.properties["danger_level"]
        bus = wire_world_handlers(CausalityBus(), seed=98)
        bus.emit(region, EventKind.DANGER_ALERT)

        rebuilt = generate_node_hierarchy(seed=98, max_depth=6)
        apply_property_overrides(
            rebuilt, persistence.load_node_property_overrides(98))
        twin = find_node(rebuilt, region.name)
        expected = min(10, before + 1)
        assert twin.properties["danger_level"] == expected

    def test_ripple_increment_is_additive_and_clamped(self):
        persistence.increment_ripple_score(97, "N", 0.4)
        persistence.increment_ripple_score(97, "N", 0.4)
        assert persistence.get_ripple_score(97, "N") == pytest.approx(0.8)
        persistence.increment_ripple_score(97, "N", 0.4)
        assert persistence.get_ripple_score(97, "N") == pytest.approx(1.0)


class TestDistanceMap:
    def test_ancestors_get_true_distance(self):
        root = SpatialNode("Root", "Planet")
        mid = SpatialNode("Mid", "Region")
        leaf = SpatialNode("Leaf", "Room")
        root.add_child(mid)
        mid.add_child(leaf)

        dist = build_distance_map(leaf)
        assert dist[leaf.id] == 0
        assert dist[mid.id] == 1
        assert dist[root.id] == 2  # not 0 — the old subtree map's blind spot

    def test_covers_siblings_through_parent(self):
        root = SpatialNode("Root", "Planet")
        a = SpatialNode("A", "Region")
        b = SpatialNode("B", "Region")
        root.add_child(a)
        root.add_child(b)
        dist = build_distance_map(a)
        assert dist[b.id] == 2  # a → root → b


class TestWorldAge:
    def test_created_at_survives_revisits(self):
        persistence.save_world(55, 10, 6, 1, 3)
        # Backdate the row, then save again — created_at must not reset.
        with persistence._connect() as conn:
            conn.execute(
                "UPDATE worlds SET created_at = '2020-01-01 00:00:00' WHERE seed = 55")
        persistence.save_world(55, 12, 6, 1, 3)
        rows = {w["seed"]: w for w in persistence.list_worlds()}
        assert rows[55]["created_at"] == "2020-01-01 00:00:00"
        assert rows[55]["node_count"] == 12
