"""The Wayback Surface (ADR-011): state-at-T without rewriting history.

The contract is behavioral:

- step 0 is the immutable born node; step N is immediately after the node's
  Nth recorded interaction, exact even when timestamps collide;
- properties fold stored deltas (never effects code), pressure folds stored
  strengths, and activity counts the same prefix;
- reads create no row and expose no human/agent classification;
- the HTTP boundary rejects forged nodes, invalid cursors, and parallel worlds.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request

import pytest

import persistence
from multiverse import store
from multiverse.utils import apply_property_overrides


def _born_node(seed: int):
    return store.world_tree(seed=seed, max_depth=1)


def _seed_history(seed: int):
    node = _born_node(seed)
    born = dict(node.properties)
    removed_key = next(iter(born))

    persistence.record_mutation(
        seed, node.name, "PLAYER_MOVE", "Ada", {"movement": "ordinary"},
        actor_identity="human-shaped-but-never-returned")
    persistence.record_substance_change(
        seed, node.name, "DANGER_ALERT", None, {},
        {"wayback_mark": "first"}, strength=0.5)
    persistence.record_substance_change(
        seed, node.name, "SCALE_ACT", "Tessera", {"verb": "attune"},
        {removed_key: None, "wayback_mark": "second"},
        strength=0.25, actor_identity="agent-shaped-but-never-returned")
    return node, born, removed_key


class TestStateAtStep:
    def test_birth_trace_and_changes_share_one_exact_cursor(self):
        seed = 8110
        node, born, removed_key = _seed_history(seed)

        birth = persistence.get_wayback_state(seed, node.name, born, at_step=0)
        assert birth["properties"] == born
        assert birth["ripple_score"] == 0.0
        assert birth["activity"] == 0
        assert birth["timeline"]["moment"]["kind"] == "birth"

        trace = persistence.get_wayback_state(seed, node.name, born, at_step=1)
        assert trace["properties"] == born
        assert trace["ripple_score"] == 0.0
        assert trace["activity"] == 1
        assert trace["timeline"]["moment"]["kind"] == "trace"
        assert trace["timeline"]["first_witness"]["at"] is not None

        first = persistence.get_wayback_state(seed, node.name, born, at_step=2)
        assert first["properties"] == {**born, "wayback_mark": "first"}
        assert first["ripple_score"] == 0.05
        assert first["activity"] == 2
        assert first["timeline"]["moment"] == {
            "at": first["timeline"]["moment"]["at"],
            "kind": "change",
            "delta": {"wayback_mark": "first"},
            "strength": 0.5,
        }

        present = persistence.get_wayback_state(seed, node.name, born)
        assert present["timeline"]["step"] == 3
        assert present["timeline"]["total"] == 3
        assert present["timeline"]["present"] is True
        assert present["properties"]["wayback_mark"] == "second"
        assert removed_key not in present["properties"]
        assert present["ripple_score"] == 0.075
        assert present["activity"] == 3
        live_overlay = persistence.load_node_property_overrides(seed)[node.name]
        assert present["properties"] == persistence.json_merge_patch(
            born, live_overlay)
        live = store.world_tree(seed=seed, max_depth=1)
        apply_property_overrides(live, {node.name: live_overlay})
        assert live.properties == present["properties"]

    def test_cursor_range_is_strict_and_empty_nodes_stay_at_birth(self):
        seed = 8111
        node = _born_node(seed)
        empty = persistence.get_wayback_state(
            seed, node.name, node.properties)
        assert empty["timeline"] == {
            "step": 0,
            "total": 0,
            "cursor": 0,
            "present": True,
            "first_witness": None,
            "moment": {"at": None, "kind": "birth", "delta": {},
                       "strength": None},
        }
        with pytest.raises(ValueError):
            persistence.get_wayback_state(
                seed, node.name, node.properties, at_step=-1)
        with pytest.raises(ValueError):
            persistence.get_wayback_state(
                seed, node.name, node.properties, at_step=1)

    def test_delete_then_nested_add_does_not_resurrect_born_siblings(self):
        seed, name = 8116, "Archive-1"
        born = {"a": {"old": 1}, "theme": "warm"}
        persistence.save_world_nodes(
            seed, [("1", name, "World", json.dumps(born), 0)], 2)

        persistence.record_substance_change(
            seed, name, "SCALE_ACT", None, {}, {"a": None})
        persistence.record_substance_change(
            seed, name, "SCALE_ACT", None, {}, {"a": {"new": 2}})

        present = persistence.get_wayback_state(seed, name, born)
        overlay = persistence.load_node_property_overrides(seed)[name]
        assert present["properties"] == {"a": {"new": 2}, "theme": "warm"}
        assert persistence.json_merge_patch(born, overlay) == \
            present["properties"]
        assert "old" not in present["properties"]["a"]

    def test_hydration_repairs_a_tombstone_dropped_by_an_old_cache(self):
        seed, name = 8117, "Archive-1"
        born = {"theme": "warm", "nested": {"kept": True}}
        persistence.save_world_nodes(
            seed, [("1", name, "World", json.dumps(born), 0)], 2)
        persistence.record_substance_change(
            seed, name, "SCALE_ACT", None, {}, {"theme": None})

        # Reproduce the pre-fix cache: SQLite json_patch({}, tombstone)
        # discarded the deletion even though the chronicle retained it.
        with persistence._connect() as conn:
            conn.execute(
                """UPDATE node_runtime_state SET properties = '{}'
                   WHERE world_seed = ? AND node_name = ?""",
                (seed, name),
            )

        overlay = persistence.load_node_property_overrides(seed)[name]
        assert overlay == {"theme": None}
        assert persistence.json_merge_patch(born, overlay) == {
            "nested": {"kept": True}}
        with persistence._connect() as conn:
            cached = conn.execute(
                """SELECT properties FROM node_runtime_state
                   WHERE world_seed = ? AND node_name = ?""",
                (seed, name),
            ).fetchone()[0]
        assert json.loads(cached) == [
            persistence._PROPERTY_CACHE_FORMAT, {"theme": None}]


@pytest.fixture()
def srv():
    from server import _Handler, _ThreadedServer
    server = _ThreadedServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def _wayback_url(base: str, seed: int, node_name: str, at: int | None = None):
    query = {"seed": seed, "node_name": node_name}
    if at is not None:
        query["at"] = at
    return f"{base}/wayback?{urllib.parse.urlencode(query)}"


class TestWaybackEndpoint:
    def test_returns_actor_blind_state_and_the_honesty_line(self, srv):
        seed = 8112
        node, born, _ = _seed_history(seed)
        before = len(persistence.get_mutations(seed, limit=20))

        with urllib.request.urlopen(_wayback_url(srv, seed, node.name, 2)) as response:
            data = json.loads(response.read())

        assert data["seed"] == seed
        assert data["node"]["name"] == node.name
        assert data["node"]["level"] == node.level
        assert data["node"]["properties"] == {
            **born, "wayback_mark": "first"}
        assert data["node"]["ripple_score"] == 0.05
        assert data["node"]["activity"] == 2
        assert data["timeline"]["moment"]["kind"] == "change"
        assert data["lens"] == "the node as it was, seen with today's eyes"

        encoded = json.dumps(data).lower()
        assert "player" not in encoded
        assert "actor" not in encoded
        assert "human-shaped" not in encoded
        assert "agent-shaped" not in encoded
        assert len(persistence.get_mutations(seed, limit=20)) == before

    def test_rejects_forged_nodes_and_out_of_range_steps(self, srv):
        seed = 8113
        node = _born_node(seed)
        with pytest.raises(urllib.error.HTTPError) as forged:
            urllib.request.urlopen(_wayback_url(srv, seed, "Forged-111"))
        assert forged.value.code == 404

        with pytest.raises(urllib.error.HTTPError) as bad_step:
            urllib.request.urlopen(_wayback_url(srv, seed, node.name, 1))
        assert bad_step.value.code == 400

    def test_canonical_world_guard_precedes_birth(self, srv, monkeypatch):
        canonical = 8114
        other = 8115
        node = _born_node(canonical)
        monkeypatch.setenv("NESTED_WORLDS_CANONICAL_SEED", str(canonical))

        with pytest.raises(urllib.error.HTTPError) as mismatch:
            urllib.request.urlopen(_wayback_url(srv, other, node.name))
        assert mismatch.value.code == 400
        assert persistence.world_is_born(other) is False
