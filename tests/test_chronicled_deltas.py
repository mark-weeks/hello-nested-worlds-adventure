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
from causality.wiring import (
    record_origin_event, record_verb_act, wire_world_handlers,
)
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

        def _boom(conn, world_seed, node_name, changed, **_kwargs):
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

    def test_producer_owned_solve_is_all_or_nothing(self):
        # The canonical attributed origin row and its material effect
        # commit together: a crash in the window leaves NO solve row (so
        # restart cannot rehydrate a solve whose delta was lost) and no
        # overlay change.
        seed = 7111
        _, room = _tree()

        def _boom(conn, world_seed, node_name, changed, **_kwargs):
            raise RuntimeError("injected: crash inside the origin write")

        mp = pytest.MonkeyPatch()
        mp.setattr(persistence, "_apply_overlay_patch", _boom)
        try:
            with pytest.raises(RuntimeError):
                record_origin_event(
                    seed, room, EventKind.PUZZLE_SOLVED,
                    {"puzzle": "The Lock"}, player_name="Ada",
                    actor_identity="ada-key")
        finally:
            mp.undo()

        assert persistence.get_node_history(seed, room.name, limit=5) == []
        assert persistence.get_puzzle_solve(seed, room.name, "The Lock") \
            is None
        assert persistence.load_node_property_overrides(seed) == {}
        assert persistence.get_substance_deltas(seed, room.name) == []


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


class TestSameKeyConcurrency:
    def test_concurrent_danger_transitions_compound_not_clobber(self):
        # Two DANGER_ALERTs from danger 5 must land 6 then 7 — never 6
        # twice. Each writer works from its own request-local snapshot
        # (as real requests do); the transition is recomputed against the
        # live overlay under the write lock.
        seed, writers = 7160, 4
        persistence.init_db()
        barrier = threading.Barrier(writers)
        errors: list[Exception] = []

        def alert(i: int) -> None:
            try:
                node = SpatialNode("Contested-R", "Region",
                                   properties={"danger_level": 5})
                bus = wire_world_handlers(CausalityBus(), seed)
                barrier.wait()
                bus.emit(node, EventKind.DANGER_ALERT)
            except Exception as exc:  # noqa: BLE001 — collected to assert
                errors.append(exc)

        threads = [threading.Thread(target=alert, args=(i,))
                   for i in range(writers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        overlay = persistence.load_node_property_overrides(seed)
        assert overlay["Contested-R"]["danger_level"] == 5 + writers
        rows = persistence.get_substance_deltas(seed, "Contested-R")
        assert [r["version"] for r in rows] == list(range(1, writers + 1))
        assert [r["delta"]["danger_level"] for r in rows] == \
            [6, 7, 8, 9][:writers]
        assert persistence.fold_node_properties(seed, "Contested-R") == \
            overlay["Contested-R"]
        rebuilt = persistence.rebuild_ripple_scores(seed)
        assert rebuilt["Contested-R"] == pytest.approx(
            persistence.get_ripple_score(seed, "Contested-R"))

    def test_concurrent_verb_acts_serialize_their_counter(self):
        # The Room verb increments the inscription count — a transition.
        # Two concurrent actors must chronicle 1 then 2, not 1 twice.
        seed, writers = 7161, 3
        persistence.init_db()
        verb = verb_for_level("Room")
        barrier = threading.Barrier(writers)
        errors: list[Exception] = []

        def act(i: int) -> None:
            try:
                node = SpatialNode("Scriptorium", "Room", properties={})
                barrier.wait()
                record_verb_act(
                    seed, node, verb, f"actor{i}:Scriptorium",
                    dict(node.properties), {"verb": verb.name},
                    player_name=f"actor{i}")
            except Exception as exc:  # noqa: BLE001 — collected to assert
                errors.append(exc)

        threads = [threading.Thread(target=act, args=(i,))
                   for i in range(writers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        overlay = persistence.load_node_property_overrides(seed)
        assert overlay["Scriptorium"]["inscriptions"] == writers
        rows = persistence.get_substance_deltas(seed, "Scriptorium")
        assert [r["delta"]["inscriptions"] for r in rows] == \
            list(range(1, writers + 1))
        assert persistence.fold_node_properties(seed, "Scriptorium") == \
            overlay["Scriptorium"]


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

    def test_producer_owned_origin_carries_its_effect_on_one_row(self):
        # record=False: the producer's ONE attributed row carries the
        # strength AND the material delta, atomic with the overlay — and
        # the in-memory node folds the applied delta.
        seed = 7131
        _, room = _tree()
        applied = record_origin_event(
            seed, room, EventKind.PUZZLE_SOLVED, {"puzzle": "The Lock"},
            player_name="Ada", actor_identity="ada-key")
        bus = wire_world_handlers(CausalityBus(), seed, record=False)
        bus.emit(room, EventKind.PUZZLE_SOLVED, {"puzzle": "The Lock"})

        assert applied == {"stabilized": True}
        assert room.properties["stabilized"] is True
        rows = persistence.get_substance_deltas(seed, room.name)
        assert len(rows) == 1
        assert rows[0]["type"] == "PUZZLE_SOLVED"
        assert rows[0]["delta"] == {"stabilized": True}
        assert rows[0]["strength"] == pytest.approx(ORIGIN_STRENGTH)
        assert rows[0]["version"] == 1
        overlay = persistence.load_node_property_overrides(seed)
        assert persistence.fold_node_properties(seed, room.name) == \
            overlay[room.name]
        # Exactly one chronicle row total: attributed, solver preserved —
        # no second anonymous copy to shadow co-op rehydration.
        history = persistence.get_node_history(seed, room.name, limit=10)
        assert len(history) == 1
        assert history[0]["player"] == "Ada"
        assert persistence.get_puzzle_solve(
            seed, room.name, "The Lock")["solver"] == "Ada"

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
        # from the producer's one attributed row — counted exactly once.
        seed = 7141
        _, room = _tree()
        record_origin_event(
            seed, room, EventKind.PUZZLE_SOLVED, {"puzzle": "The Lock"},
            player_name="Ada", actor_identity="ada-key")
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
    def test_legacy_cache_survives_first_absolute_and_transition_writes(self):
        seed = 7147
        persistence.init_db()
        with persistence._connect() as conn:
            for name, properties in (
                    ("Legacy-absolute", {"legacy": True}),
                    ("Legacy-transition", {"legacy": True, "count": 4})):
                conn.execute(
                    """INSERT INTO node_runtime_state
                       (world_seed, node_name, ripple_score, properties,
                        updated_at, created_at)
                       VALUES (?, ?, 0.0, ?, datetime('now'), datetime('now'))""",
                    (seed, name, json.dumps(properties)),
                )

        persistence.record_substance_change(
            seed, "Legacy-absolute", "SCALE_ACT", None, {}, {"fresh": True})
        applied = persistence.record_substance_transition(
            seed, "Legacy-transition", "DANGER_ALERT", None, {},
            lambda live: {"count": live["count"] + 1})

        assert applied == {"count": 5}
        assert persistence.load_node_property_overrides(seed) == {
            "Legacy-absolute": {"legacy": True, "fresh": True},
            "Legacy-transition": {"legacy": True, "count": 5},
        }
        assert persistence.get_wayback_state(
            seed, "Legacy-absolute", {}, at_step=0)["properties"] == {}
        assert persistence.get_wayback_state(
            seed, "Legacy-absolute", {})["properties"] == {
                "legacy": True, "fresh": True}

    def test_plain_object_cache_survives_rollback_and_repairs_old_writes(self):
        seed, node = 7148, "Rollback-1"
        born = {"theme": "warm"}
        persistence.save_world_nodes(
            seed, [("1", node, "World", json.dumps(born), 0)], 2)
        # Capture a marked empty cache without adding a material version.
        assert persistence.record_substance_transition(
            seed, node, "AGENT_VISIT", None, {}, lambda _live: None) is None

        with persistence._connect() as conn:
            blob = conn.execute(
                """SELECT properties FROM node_runtime_state
                   WHERE world_seed = ? AND node_name = ?""",
                (seed, node),
            ).fetchone()[0]
            assert json.loads(blob) == {}  # old loader accepts it

            # Simulate the prior binary: it chronicles and json_patch-es the
            # plain object but knows nothing about the side-table marker. A
            # born-key tombstone leaves the bare patch blob unchanged.
            conn.execute(
                """INSERT INTO world_mutations
                   (world_seed, node_name, mutation_type, data, delta,
                    node_version)
                   VALUES (?, ?, 'SCALE_ACT', '{}', ?, 1)""",
                (seed, node, json.dumps({"theme": None})),
            )
            conn.execute(
                """UPDATE node_runtime_state
                   SET properties = json_patch(properties, ?)
                   WHERE world_seed = ? AND node_name = ?""",
                (json.dumps({"theme": None}), seed, node),
            )
            assert conn.execute(
                """SELECT properties FROM node_runtime_state
                   WHERE world_seed = ? AND node_name = ?""",
                (seed, node),
            ).fetchone()[0] == blob

        assert persistence.load_node_property_overrides(seed)[node] == {
            "theme": None}
        with persistence._connect() as conn:
            properties, marked, marked_version = conn.execute(
                """SELECT state.properties, meta.properties_blob,
                          meta.delta_version
                   FROM node_runtime_state AS state
                   JOIN node_property_cache_meta AS meta
                     ON meta.world_seed = state.world_seed
                    AND meta.node_name = state.node_name
                   WHERE state.world_seed = ? AND state.node_name = ?""",
                (seed, node),
            ).fetchone()
        assert properties == marked
        assert marked_version == 1

    def test_current_caches_avoid_replay_and_point_reads(
            self, monkeypatch):
        seed = 7149
        persistence.record_substance_change(
            seed, "Hot-1", "SCALE_ACT", None, {}, {"count": 1})
        persistence.record_substance_change(
            seed, "Warm-2", "SCALE_ACT", None, {}, {"ready": True})

        def no_replay(*_args, **_kwargs):
            raise AssertionError("current-format cache replayed its chronicle")

        monkeypatch.setattr(
            persistence, "_rebuild_property_overlay", no_replay)
        persistence.record_substance_change(
            seed, "Hot-1", "SCALE_ACT", None, {}, {"count": 2})

        def no_point_read(*_args, **_kwargs):
            raise AssertionError("bulk hydration used a point cache read")

        monkeypatch.setattr(
            persistence, "_current_property_overlay", no_point_read)
        assert persistence.load_node_property_overrides(seed) == {
            "Hot-1": {"count": 2},
            "Warm-2": {"ready": True},
        }

    def test_lazy_repair_serializes_with_a_concurrent_writer(self, monkeypatch):
        seed, node = 7152, "Repair-race"
        persistence.record_substance_change(
            seed, node, "SCALE_ACT", None, {}, {"first": 1})
        with persistence._connect() as conn:
            conn.execute(
                """DELETE FROM node_property_cache_meta
                   WHERE world_seed = ? AND node_name = ?""",
                (seed, node),
            )

        entered = threading.Event()
        release = threading.Event()
        original = persistence._rebuild_property_overlay

        def paused_rebuild(*args, **kwargs):
            entered.set()
            assert release.wait(5)
            return original(*args, **kwargs)

        monkeypatch.setattr(
            persistence, "_rebuild_property_overlay", paused_rebuild)
        errors: list[Exception] = []

        def repair() -> None:
            try:
                persistence.load_node_property_overrides(seed)
            except Exception as exc:  # noqa: BLE001 - asserted below
                errors.append(exc)

        def write() -> None:
            try:
                persistence.record_substance_change(
                    seed, node, "SCALE_ACT", None, {}, {"second": 2})
            except Exception as exc:  # noqa: BLE001 - asserted below
                errors.append(exc)

        repair_thread = threading.Thread(target=repair)
        repair_thread.start()
        assert entered.wait(5)
        writer_thread = threading.Thread(target=write)
        writer_thread.start()
        release.set()
        repair_thread.join(5)
        writer_thread.join(5)

        assert not repair_thread.is_alive()
        assert not writer_thread.is_alive()
        assert not errors
        assert persistence.load_node_property_overrides(seed)[node] == {
            "first": 1, "second": 2}

    def test_null_deletes_and_nested_merge_match_the_overlay(self):
        # RFC 7396 through the whole stack: the Python fold must reproduce
        # the hydrated cache result, including nested merge and null-deletes,
        # at every cursor position. The cache itself is a minimal patch
        # relative to the born state (empty here), not a composed patch log.
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
        overlay = persistence.load_node_property_overrides(seed)[node]
        assert overlay == {"a": {"c": 2}}
        assert final == persistence.json_merge_patch({}, overlay)

    def test_fold_before_any_delta_is_the_born_state(self):
        assert persistence.fold_node_properties(7151, "Untouched-1") == {}
        assert persistence.fold_node_properties(
            7151, "Untouched-1", upto_version=0) == {}

    def test_fold_is_born_aware_and_json_type_exact(self):
        seed, name = 7153, "Typed-1"
        born = {
            "theme": "warm",
            "flag": True,
            "nested": {"value": True},
        }
        persistence.save_world_nodes(
            seed, [("1", name, "World", json.dumps(born), 0)], 2)
        persistence.record_substance_change(
            seed, name, "SCALE_ACT", None, {},
            {"theme": None, "flag": 1, "nested": {"value": 1}})

        overlay = persistence.load_node_property_overrides(seed)[name]
        assert persistence.fold_node_properties(seed, name) == overlay == {
            "theme": None,
            "flag": 1,
            "nested": {"value": 1},
        }
        assert persistence.json_merge_patch(born, overlay) == {
            "flag": 1,
            "nested": {"value": 1},
        }


class TestInterruptedMigrationRecovery:
    def test_failed_migration_commits_nothing_and_retries_cleanly(
            self, tmp_path, monkeypatch):
        # A migration's statements and its schema_version marker must
        # commit as one transaction: an interruption mid-file must not
        # strand committed ALTERs that make the retry die with
        # "duplicate column name".
        import sqlite3
        db = tmp_path / "recovery.db"
        migs = tmp_path / "migs"
        migs.mkdir()
        (migs / "0001_base.sql").write_text(
            "CREATE TABLE t (a INTEGER);\n")
        (migs / "0002_widen.sql").write_text(
            "-- widens t, then hits a bad statement\n"
            "ALTER TABLE t ADD COLUMN b INTEGER;\n"
            "ALTER TABLE missing ADD COLUMN c INTEGER;\n")
        monkeypatch.setattr(persistence, "_DB_PATH", db)
        monkeypatch.setattr(persistence, "_MIGRATIONS_DIR", migs)
        persistence._initialized.discard(db)

        with pytest.raises(sqlite3.OperationalError):
            persistence.init_db()

        conn = sqlite3.connect(db)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(t)")]
        versions = [r[0] for r in conn.execute(
            "SELECT version FROM schema_version ORDER BY version")]
        conn.close()
        assert cols == ["a"]        # the first ALTER did not survive alone
        assert versions == [1]      # 0002 is not marked applied

        # The corrected file applies on retry — no duplicate-column death.
        (migs / "0002_widen.sql").write_text(
            "ALTER TABLE t ADD COLUMN b INTEGER;\n"
            "ALTER TABLE t ADD COLUMN c INTEGER;\n")
        persistence.init_db()
        conn = sqlite3.connect(db)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(t)")]
        versions = [r[0] for r in conn.execute(
            "SELECT version FROM schema_version ORDER BY version")]
        conn.close()
        assert cols == ["a", "b", "c"]
        assert versions == [1, 2]
