"""Chronicled deltas (ADR-009): every substance write chronicles its delta.

The four contract families the ADR names:

  * injected-failure   — a crash mid-write leaves neither the chronicle row
                         nor the overlay change (atomicity, not detection).
  * concurrent-writer  — writers on one node serialize into distinct
                         versions, and the fold reproduces the final overlay.
  * fold-equals-overlay — state folded from chronicled deltas in per-node
                         version order equals the live overlay, across every
                         routed writer surface.
  * ripple-equals-fold — the persisted ripple_score is a pure fold of
                         chronicled strengths (× RIPPLE_INCREMENT_PER_STRENGTH,
                         capped at 1.0): each fired event carries strength on
                         exactly one row, and drift repairs by rebuild.

Plus the semantics the fold depends on: RFC 7396 merge patches (null
deletes), Python fold parity with SQLite's json_patch, and the version
cursor reproducing intermediate states.
"""
from __future__ import annotations

import json
import threading
import urllib.request

import pytest

import persistence
from causality import ORIGIN_STRENGTH, CausalityBus, EventKind
from causality.wiring import wire_world_handlers
from multiverse.generator import generate_node_hierarchy
from multiverse.node import SpatialNode
from multiverse.verbs import maturation_seconds, verb_for_level
from server import heartbeat


def _tree(seed_props: dict | None = None):
    region = SpatialNode("Region-A", "Region",
                         properties={"danger_level": 5})
    room = SpatialNode("Room-A", "Room",
                       properties=dict(seed_props or {"has_puzzle": True}))
    region.add_child(room)
    return region, room


class TestAtomicWriteAPI:
    def test_one_write_lands_row_overlay_and_version_together(self):
        version = persistence.record_substance_change(
            7101, "Vault-1", "SCALE_ACT", "Ada",
            {"verb": "mend", "changed": {"condition": "pristine"}},
            {"condition": "pristine"},
            strength=1.0, actor_identity="ada-key")
        assert version == 1
        rows = persistence.get_substance_deltas(7101, "Vault-1")
        assert len(rows) == 1
        assert rows[0]["type"] == "SCALE_ACT"
        assert rows[0]["version"] == 1
        assert rows[0]["strength"] == pytest.approx(1.0)
        assert rows[0]["delta"] == {"condition": "pristine"}
        overlay = persistence.load_node_property_overrides(7101)
        assert overlay["Vault-1"] == {"condition": "pristine"}

    def test_versions_are_per_node_monotonic(self):
        v1 = persistence.record_substance_change(
            7102, "N-1", "SCALE_ACT", None, {}, {"a": 1})
        v2 = persistence.record_substance_change(
            7102, "N-1", "SCALE_ACT", None, {}, {"b": 2})
        other = persistence.record_substance_change(
            7102, "N-2", "SCALE_ACT", None, {}, {"a": 1})
        assert (v1, v2) == (1, 2)
        assert other == 1  # versions count per node, not per world

    def test_empty_delta_is_refused(self):
        with pytest.raises(ValueError):
            persistence.record_substance_change(
                7103, "N", "SCALE_ACT", None, {}, {})


class TestInjectedFailure:
    def test_crash_mid_write_leaves_neither_half(self):
        seed = 7110
        persistence.record_substance_change(
            seed, "N", "SCALE_ACT", None, {}, {"before": True})

        def _boom(conn, world_seed, node_name, changed):
            raise RuntimeError("injected: crash between chronicle and overlay")

        # A dedicated MonkeyPatch instance: pytest's function-scoped
        # `monkeypatch` fixture is shared with conftest's DB isolation, and
        # undoing it mid-test would point reads at the real home DB.
        mp = pytest.MonkeyPatch()
        mp.setattr(persistence, "_apply_overlay_patch", _boom)
        try:
            with pytest.raises(RuntimeError):
                persistence.record_substance_change(
                    seed, "N", "SCALE_ACT", None, {}, {"after": True})
        finally:
            mp.undo()

        # Neither the chronicle row nor the overlay change survived.
        rows = persistence.get_substance_deltas(seed, "N")
        assert [r["delta"] for r in rows] == [{"before": True}]
        assert persistence.load_node_property_overrides(seed)["N"] == {
            "before": True}
        # And the fold still equals the overlay — no half-event to diverge on.
        assert persistence.fold_node_properties(seed, "N") == {"before": True}
        # The next write allocates the version the failed write never took.
        assert persistence.record_substance_change(
            seed, "N", "SCALE_ACT", None, {}, {"after": True}) == 2


class TestConcurrentWriters:
    def test_writers_on_one_node_serialize_into_distinct_versions(self):
        seed, node, writers = 7120, "Contested-1", 8
        persistence.init_db()
        barrier = threading.Barrier(writers)
        versions: list[int] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def write(i: int) -> None:
            try:
                barrier.wait()
                v = persistence.record_substance_change(
                    seed, node, "SCALE_ACT", None, {"i": i}, {f"k{i}": i})
                with lock:
                    versions.append(v)
            except Exception as exc:  # noqa: BLE001 — collected for assertion
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=write, args=(i,))
                   for i in range(writers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert sorted(versions) == list(range(1, writers + 1))
        # The fold in version order reproduces the final overlay exactly.
        overlay = persistence.load_node_property_overrides(seed)[node]
        assert persistence.fold_node_properties(seed, node) == overlay
        assert overlay == {f"k{i}": i for i in range(writers)}


class TestFoldEqualsOverlay:
    def test_recorded_cascade_folds_to_overlay(self):
        # record=True: the event's chronicle row carries its delta and
        # strength; origin and the dampened upward hop both change matter.
        seed = 7130
        region, room = _tree()
        bus = wire_world_handlers(CausalityBus(), seed)
        bus.propagate(room, EventKind.PUZZLE_SOLVED, {"puzzle": "The Lock"})

        overlay = persistence.load_node_property_overrides(seed)
        for name in ("Room-A", "Region-A"):
            assert persistence.fold_node_properties(seed, name) == overlay[name]
        room_rows = persistence.get_substance_deltas(seed, "Room-A")
        assert room_rows[0]["type"] == "PUZZLE_SOLVED"
        assert room_rows[0]["strength"] == pytest.approx(1.0)
        region_rows = persistence.get_substance_deltas(seed, "Region-A")
        assert region_rows[0]["delta"] == {"stabilized": True,
                                           "danger_level": 4}
        assert region_rows[0]["strength"] == pytest.approx(0.5)

    def test_producer_owned_origin_chronicles_its_effect(self):
        # record=False: the producer's attributed row carries the strength;
        # the material consequence lands as an EVENT_EFFECT delta row —
        # atomic with the overlay, carrying no strength of its own.
        seed = 7131
        _, room = _tree()
        persistence.record_mutation(
            seed, room.name, "PUZZLE_SOLVED", "Ada", {"puzzle": "The Lock"},
            actor_identity="ada-key", strength=ORIGIN_STRENGTH)
        bus = wire_world_handlers(CausalityBus(), seed, record=False)
        bus.emit(room, EventKind.PUZZLE_SOLVED, {"puzzle": "The Lock"})

        rows = persistence.get_substance_deltas(seed, room.name)
        assert len(rows) == 1
        assert rows[0]["type"] == "EVENT_EFFECT"
        assert rows[0]["delta"] == {"stabilized": True}
        assert rows[0]["strength"] is None
        assert rows[0]["version"] == 1
        overlay = persistence.load_node_property_overrides(seed)
        assert persistence.fold_node_properties(seed, room.name) == \
            overlay[room.name]
        # Exactly one chronicle row carries the fired event's strength.
        history = persistence.get_node_history(seed, room.name, limit=10)
        assert len(history) == 2  # attributed solve + its EVENT_EFFECT

    def test_maturation_drain_chronicles_the_landing_delta(self):
        seed = 7132
        persistence.enqueue_verb_maturation(
            seed, "Galaxy-X", "kindle", {"kindled": True}, "Ada", 0)
        assert heartbeat.drain_matured_verbs(world_seed=seed) == 1

        rows = persistence.get_substance_deltas(seed, "Galaxy-X")
        assert len(rows) == 1
        assert rows[0]["type"] == "SCALE_ACT_MATURED"
        assert rows[0]["delta"] == {"kindled": True}
        assert rows[0]["strength"] is None  # landing fires no causal event
        overlay = persistence.load_node_property_overrides(seed)
        assert persistence.fold_node_properties(seed, "Galaxy-X") == \
            overlay["Galaxy-X"] == {"kindled": True}

    def test_act_endpoint_writes_one_atomic_scale_act_row(self):
        # The HTTP immediate branch: SCALE_ACT row = delta + strength +
        # version, and the overlay change, in one write.
        from server import _Handler, _ThreadedServer
        seed = 7133
        root = generate_node_hierarchy(seed=seed, max_depth=6)

        def find_instant(n):
            if (verb_for_level(n.level) is not None
                    and maturation_seconds(n.level) == 0):
                return n
            for c in n.children:
                hit = find_instant(c)
                if hit is not None:
                    return hit
            return None

        target = find_instant(root)
        assert target is not None
        server = _ThreadedServer(("127.0.0.1", 0), _Handler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            body = json.dumps({"seed": seed, "depth": 6,
                               "node_name": target.name,
                               "player_name": "Ada"}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/act", data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
            assert data["changed"]
        finally:
            server.shutdown()

        rows = persistence.get_substance_deltas(seed, target.name)
        assert len(rows) == 1
        assert rows[0]["type"] == "SCALE_ACT"
        assert rows[0]["version"] == 1
        assert rows[0]["strength"] == pytest.approx(ORIGIN_STRENGTH)
        overlay = persistence.load_node_property_overrides(seed)
        assert rows[0]["delta"] == overlay[target.name]
        assert persistence.fold_node_properties(seed, target.name) == \
            overlay[target.name]

    def test_constellation_lighting_chronicles_its_delta(self):
        from puzzles.engine import build_puzzle
        from server.rooms import get_room
        from server.world_mechanics import check_constellation
        seed = 7134
        region = SpatialNode("Region-C", "Region", properties={})
        rooms = [SpatialNode(f"Room-C{i}", "Room",
                             properties={"has_puzzle": True})
                 for i in (1, 2)]
        for r in rooms:
            region.add_child(r)
            puzzle = build_puzzle(r, 0)
            persistence.record_mutation(
                seed, r.name, "PUZZLE_SOLVED", "Ada",
                {"puzzle": puzzle.name}, actor_identity="ada-key",
                strength=ORIGIN_STRENGTH)

        check_constellation(seed, get_room(seed), region, "Ada", "ada-key")

        rows = persistence.get_substance_deltas(seed, region.name)
        assert len(rows) == 1
        assert rows[0]["type"] == "CONSTELLATION_COMPLETE"
        assert rows[0]["delta"] == {"constellated": True}
        assert rows[0]["strength"] == pytest.approx(ORIGIN_STRENGTH)
        overlay = persistence.load_node_property_overrides(seed)
        assert persistence.fold_node_properties(seed, region.name) == \
            overlay[region.name] == {"constellated": True}


class TestRippleEqualsFold:
    def test_live_scores_equal_the_rebuilt_fold(self):
        seed = 7140
        region, room = _tree()
        bus = wire_world_handlers(CausalityBus(), seed)
        bus.propagate(room, EventKind.PUZZLE_SOLVED, {"puzzle": "The Lock"})
        bus.emit(region, EventKind.DANGER_ALERT)

        live = persistence.load_ripple_scores(seed)
        rebuilt = persistence.rebuild_ripple_scores(seed)
        assert set(rebuilt) == set(live)
        for name, score in live.items():
            assert rebuilt[name] == pytest.approx(score)
            assert persistence.get_ripple_score(seed, name) == \
                pytest.approx(score)

    def test_producer_attributed_strength_keeps_the_fold_exact(self):
        # A record=False origin: its ripple increment must be derivable
        # from the producer's attributed row — and only counted once,
        # even though the event also left an EVENT_EFFECT delta row.
        seed = 7141
        _, room = _tree()
        persistence.record_mutation(
            seed, room.name, "PUZZLE_SOLVED", "Ada", {"puzzle": "The Lock"},
            actor_identity="ada-key", strength=ORIGIN_STRENGTH)
        bus = wire_world_handlers(CausalityBus(), seed, record=False)
        bus.emit(room, EventKind.PUZZLE_SOLVED, {"puzzle": "The Lock"})

        live = persistence.get_ripple_score(seed, room.name)
        assert live == pytest.approx(0.1)
        rebuilt = persistence.rebuild_ripple_scores(seed)
        assert rebuilt[room.name] == pytest.approx(live)

    def test_cache_drift_is_repaired_by_rebuild(self):
        seed = 7142
        _, room = _tree()
        bus = wire_world_handlers(CausalityBus(), seed)
        bus.emit(room, EventKind.AGENT_VISIT, {"agent": "Scout"})
        assert persistence.get_ripple_score(seed, room.name) == \
            pytest.approx(0.1)

        # Drift the cache (the legacy absolute writer), then repair it.
        persistence.upsert_ripple_score(seed, room.name, 0.93)
        assert persistence.get_ripple_score(seed, room.name) == \
            pytest.approx(0.93)
        persistence.rebuild_ripple_scores(seed)
        assert persistence.get_ripple_score(seed, room.name) == \
            pytest.approx(0.1)

    def test_rebuild_caps_at_one(self):
        seed = 7143
        for _ in range(11):
            persistence.record_mutation(
                seed, "Busy-1", "AGENT_VISIT", None, {}, strength=1.0)
        rebuilt = persistence.rebuild_ripple_scores(seed)
        assert rebuilt["Busy-1"] == pytest.approx(1.0)


class TestFoldSemantics:
    def test_null_deletes_and_nested_merge_match_the_overlay(self):
        # RFC 7396 through the whole stack: the Python fold must reproduce
        # exactly what SQLite's json_patch applied, including nested merge
        # and null-deletes, at every cursor position.
        seed, node = 7150, "Patchwork-1"
        persistence.record_substance_change(
            seed, node, "SCALE_ACT", None, {}, {"a": {"b": 1}, "x": 1})
        persistence.record_substance_change(
            seed, node, "SCALE_ACT", None, {}, {"a": {"c": 2}})
        persistence.record_substance_change(
            seed, node, "SCALE_ACT", None, {}, {"x": None, "a": {"b": None}})

        assert persistence.fold_node_properties(seed, node, upto_version=1) \
            == {"a": {"b": 1}, "x": 1}
        assert persistence.fold_node_properties(seed, node, upto_version=2) \
            == {"a": {"b": 1, "c": 2}, "x": 1}
        final = persistence.fold_node_properties(seed, node)
        assert final == {"a": {"c": 2}}
        assert final == persistence.load_node_property_overrides(seed)[node]

    def test_fold_before_any_delta_is_the_born_state(self):
        assert persistence.fold_node_properties(7151, "Untouched-1") == {}
        assert persistence.fold_node_properties(
            7151, "Untouched-1", upto_version=0) == {}
