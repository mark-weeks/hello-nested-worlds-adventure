import json
import sqlite3
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

import persistence


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    """Redirect the database to a temporary file for every test."""
    db_path = tmp_path / "test_worlds.db"
    monkeypatch.setattr(persistence, "_DB_PATH", db_path)
    yield db_path


class TestInitDb:
    def test_creates_database_file(self, tmp_path):
        persistence.init_db()
        assert persistence._DB_PATH.exists()

    def test_creates_all_tables(self):
        persistence.init_db()
        import sqlite3
        conn = sqlite3.connect(persistence._DB_PATH)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        assert {"worlds", "agent_runs", "puzzle_results", "world_mutations",
                "agent_memory", "node_images"}.issubset(tables)

    def test_db_permissions_owner_only(self):
        persistence.init_db()
        mode = persistence._DB_PATH.stat().st_mode
        assert mode & stat.S_IRWXG == 0, "group bits should be unset"
        assert mode & stat.S_IRWXO == 0, "other bits should be unset"


class TestSaveAndListWorlds:
    def test_save_and_list_world(self):
        persistence.save_world(seed=1, node_count=10, max_depth=4, min_breadth=1, max_breadth=2)
        worlds = persistence.list_worlds()
        assert len(worlds) == 1
        assert worlds[0]["seed"] == 1
        assert worlds[0]["node_count"] == 10

    def test_replace_duplicate_seed(self):
        persistence.save_world(seed=42, node_count=5, max_depth=3, min_breadth=1, max_breadth=2)
        persistence.save_world(seed=42, node_count=99, max_depth=3, min_breadth=1, max_breadth=2)
        worlds = persistence.list_worlds()
        assert len(worlds) == 1
        assert worlds[0]["node_count"] == 99

    def test_list_worlds_empty(self):
        assert persistence.list_worlds() == []


class TestSaveAgentRun:
    def test_save_and_retrieve_run(self):
        persistence.save_world(seed=7, node_count=5, max_depth=3, min_breadth=1, max_breadth=2)
        events = [{"node": "A", "level": "Room", "state": "EXPLORE", "action": "explored"}]
        run_id = persistence.save_agent_run("Scout", 7, 3, events)
        assert isinstance(run_id, int)

        runs = persistence.get_agent_runs(7)
        assert len(runs) == 1
        assert runs[0]["agent_name"] == "Scout"
        assert runs[0]["nodes_visited"] == 3

    def test_multiple_runs_same_seed(self):
        persistence.save_world(seed=9, node_count=5, max_depth=3, min_breadth=1, max_breadth=2)
        persistence.save_agent_run("Alpha", 9, 2, [])
        persistence.save_agent_run("Beta", 9, 4, [])
        runs = persistence.get_agent_runs(9)
        assert len(runs) == 2

    def test_get_runs_unknown_seed(self):
        assert persistence.get_agent_runs(9999) == []


class TestWorldMutations:
    def test_record_and_get_mutation(self):
        persistence.record_mutation(7, "Aethon", "PUZZLE_SOLVED", "Alice", {"puzzle": "The Lock"})
        mutations = persistence.get_mutations(7)
        assert len(mutations) == 1
        m = mutations[0]
        assert m["node"]   == "Aethon"
        assert m["type"]   == "PUZZLE_SOLVED"
        assert m["player"] == "Alice"
        assert m["data"]   == {"puzzle": "The Lock"}

    def test_get_mutations_unknown_seed(self):
        assert persistence.get_mutations(9999) == []

    def test_get_mutations_limit(self):
        for i in range(10):
            persistence.record_mutation(5, f"Node{i}", "PUZZLE_SOLVED", None, {})
        assert len(persistence.get_mutations(5, limit=3)) == 3

    def test_record_mutation_null_player(self):
        persistence.record_mutation(3, "Vorrex", "PUZZLE_SOLVED", None, {"puzzle": "Riddle"})
        mutations = persistence.get_mutations(3)
        assert mutations[0]["player"] is None


class TestGetNodeHistory:
    def test_returns_events_for_node(self):
        persistence.record_mutation(42, "Vault-3", "PUZZLE_SOLVED", "Alice", {"puzzle": "The Lock"})
        persistence.record_mutation(42, "Vault-3", "AGENT_VISIT", None, {"agent": "Scout"})
        persistence.record_mutation(42, "OtherNode", "PUZZLE_SOLVED", "Bob", {})
        history = persistence.get_node_history(42, "Vault-3")
        assert len(history) == 2
        assert all(h["type"] in ("PUZZLE_SOLVED", "AGENT_VISIT") for h in history)

    def test_excludes_other_nodes(self):
        persistence.record_mutation(42, "Vault-3", "PUZZLE_SOLVED", "Alice", {})
        persistence.record_mutation(42, "OtherNode", "PUZZLE_SOLVED", "Bob", {})
        history = persistence.get_node_history(42, "OtherNode")
        assert len(history) == 1
        assert history[0]["type"] == "PUZZLE_SOLVED"

    def test_excludes_other_seeds(self):
        persistence.record_mutation(1, "Vault-3", "PUZZLE_SOLVED", "Alice", {})
        assert persistence.get_node_history(2, "Vault-3") == []

    def test_respects_limit(self):
        for i in range(10):
            persistence.record_mutation(5, "Node-X", "AGENT_VISIT", None, {"i": i})
        assert len(persistence.get_node_history(5, "Node-X", limit=4)) == 4

    def test_empty_when_no_history(self):
        assert persistence.get_node_history(99, "Ghost") == []

    def test_agent_in_data_field(self):
        persistence.record_mutation(7, "Nexus", "AGENT_VISIT", None, {"agent": "Wanderer"})
        h = persistence.get_node_history(7, "Nexus")
        assert h[0]["data"]["agent"] == "Wanderer"
        assert h[0]["player"] is None


class TestAgentMemoryPersistence:
    def test_save_and_load_memory(self):
        persistence.save_agent_memory("Scout", 42, ["id-1", "id-2"], [{"node": "A", "action": "explored"}])
        m = persistence.load_agent_memory("Scout", 42)
        assert m is not None
        assert m["visited_ids"] == ["id-1", "id-2"]
        assert m["log_entries"][0]["node"] == "A"

    def test_load_missing_returns_none(self):
        assert persistence.load_agent_memory("Ghost", 99) is None

    def test_save_overwrites_existing(self):
        persistence.save_agent_memory("Scout", 1, ["a"], [])
        persistence.save_agent_memory("Scout", 1, ["a", "b", "c"], [])
        m = persistence.load_agent_memory("Scout", 1)
        assert m["visited_ids"] == ["a", "b", "c"]

    def test_different_seeds_are_independent(self):
        persistence.save_agent_memory("Scout", 1, ["x"], [])
        persistence.save_agent_memory("Scout", 2, ["y", "z"], [])
        assert persistence.load_agent_memory("Scout", 1)["visited_ids"] == ["x"]
        assert persistence.load_agent_memory("Scout", 2)["visited_ids"] == ["y", "z"]

    def test_list_agent_memories(self):
        persistence.save_agent_memory("Alpha", 10, ["a", "b"], [])
        persistence.save_agent_memory("Beta",  20, ["c"], [])
        memories = persistence.list_agent_memories()
        names = {m["agent_name"] for m in memories}
        assert "Alpha" in names and "Beta" in names

    def test_list_agent_memories_node_count(self):
        persistence.save_agent_memory("Counter", 5, ["p", "q", "r", "s"], [])
        memories = persistence.list_agent_memories()
        entry = next(m for m in memories if m["agent_name"] == "Counter")
        assert entry["node_count"] == 4


class TestNodeRuntimeState:
    def test_unknown_node_returns_zero(self):
        assert persistence.get_ripple_score(42, "Ghost") == 0.0

    def test_upsert_then_get(self):
        persistence.upsert_ripple_score(42, "Vault-3", 0.37)
        assert persistence.get_ripple_score(42, "Vault-3") == pytest.approx(0.37)

    def test_upsert_overwrites(self):
        persistence.upsert_ripple_score(42, "Vault-3", 0.2)
        persistence.upsert_ripple_score(42, "Vault-3", 0.8)
        assert persistence.get_ripple_score(42, "Vault-3") == pytest.approx(0.8)

    def test_seeds_isolated(self):
        persistence.upsert_ripple_score(1, "Vault-3", 0.5)
        persistence.upsert_ripple_score(2, "Vault-3", 0.9)
        assert persistence.get_ripple_score(1, "Vault-3") == pytest.approx(0.5)
        assert persistence.get_ripple_score(2, "Vault-3") == pytest.approx(0.9)

    def test_load_ripple_scores_returns_dict(self):
        persistence.upsert_ripple_score(7, "Aethon-1", 0.4)
        persistence.upsert_ripple_score(7, "Vault-3",  0.7)
        scores = persistence.load_ripple_scores(7)
        assert scores == {"Aethon-1": pytest.approx(0.4),
                          "Vault-3":  pytest.approx(0.7)}

    def test_load_ripple_scores_unknown_seed_empty(self):
        assert persistence.load_ripple_scores(9999) == {}


class TestMigrations:
    def test_init_records_all_known_migrations(self):
        persistence.init_db()
        applied = persistence.schema_versions()
        # At minimum, 0001_initial and 0002_indexes both present after init.
        assert 1 in applied
        assert 2 in applied
        assert applied == sorted(applied)

    def test_schema_version_table_exists(self):
        persistence.init_db()
        conn = sqlite3.connect(persistence._DB_PATH)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchall()
        conn.close()
        assert rows == [("schema_version",)]

    def test_indexes_present_after_init(self):
        persistence.init_db()
        conn = sqlite3.connect(persistence._DB_PATH)
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )}
        conn.close()
        # The three hot-path indexes from 0002_indexes.sql.
        assert "idx_world_mutations_seed_node" in names
        assert "idx_world_mutations_seed_time" in names
        assert "idx_agent_runs_seed"           in names

    def test_idempotent_on_existing_database(self):
        # Running init twice must not duplicate version rows or fail.
        persistence.init_db()
        first = persistence.schema_versions()
        persistence._initialized.discard(persistence._DB_PATH)
        persistence.init_db()
        second = persistence.schema_versions()
        assert first == second

    def test_runner_skips_unknown_filenames(self, tmp_path, monkeypatch):
        # A stray file that doesn't match the NNNN_name.sql pattern must be
        # ignored — otherwise the runner could try to executescript a README
        # or notes file dropped into the migrations directory.
        bogus_dir = tmp_path / "migrations"
        bogus_dir.mkdir()
        (bogus_dir / "README.md").write_text("# notes")
        (bogus_dir / "0001_real.sql").write_text(
            "CREATE TABLE IF NOT EXISTS m_test (id INTEGER PRIMARY KEY);"
        )
        monkeypatch.setattr(persistence, "_MIGRATIONS_DIR", bogus_dir)
        # Re-initialize so the new migrations dir is consulted.
        persistence._initialized.discard(persistence._DB_PATH)
        persistence.init_db()
        assert persistence.schema_versions() == [1]


class TestPruneMutations:
    def test_prune_zero_is_noop(self):
        persistence.record_mutation(1, "N", "AGENT_VISIT", None, {})
        assert persistence.prune_mutations(0) == 0
        assert len(persistence.get_mutations(1)) == 1

    def test_prune_negative_is_noop(self):
        persistence.record_mutation(1, "N", "AGENT_VISIT", None, {})
        assert persistence.prune_mutations(-5) == 0
        assert len(persistence.get_mutations(1)) == 1

    def test_prune_removes_old_rows_only(self):
        # Insert one fresh + one ancient row by manually backdating it.
        persistence.record_mutation(1, "Fresh", "AGENT_VISIT", None, {})
        persistence.record_mutation(1, "Stale", "AGENT_VISIT", None, {})
        conn = sqlite3.connect(persistence._DB_PATH)
        conn.execute(
            "UPDATE world_mutations SET recorded_at = datetime('now', '-90 days') "
            "WHERE node_name = 'Stale'"
        )
        conn.commit()
        conn.close()
        removed = persistence.prune_mutations(30)
        assert removed == 1
        nodes = {m["node"] for m in persistence.get_mutations(1)}
        assert nodes == {"Fresh"}

    def test_env_flag_triggers_prune_on_init(self, monkeypatch):
        # Seed an ancient mutation, then re-init with the TTL env var set.
        persistence.record_mutation(1, "Stale", "AGENT_VISIT", None, {})
        conn = sqlite3.connect(persistence._DB_PATH)
        conn.execute(
            "UPDATE world_mutations SET recorded_at = datetime('now', '-90 days')"
        )
        conn.commit()
        conn.close()
        monkeypatch.setenv("NESTED_WORLDS_MUTATION_TTL_DAYS", "30")
        persistence._initialized.discard(persistence._DB_PATH)
        persistence.init_db()
        assert persistence.get_mutations(1) == []

    def test_invalid_env_var_is_ignored(self, monkeypatch):
        persistence.record_mutation(1, "Fresh", "AGENT_VISIT", None, {})
        monkeypatch.setenv("NESTED_WORLDS_MUTATION_TTL_DAYS", "not-a-number")
        persistence._initialized.discard(persistence._DB_PATH)
        persistence.init_db()
        # No prune attempted, fresh row still present.
        assert len(persistence.get_mutations(1)) == 1


class TestSavePuzzleResult:
    def test_save_puzzle_result(self):
        persistence.save_puzzle_result(world_seed=5, puzzle_name="The Lock", result="SOLVED", attempts=2)
        # No exception means success; verify via direct query
        import sqlite3
        conn = sqlite3.connect(persistence._DB_PATH)
        rows = conn.execute("SELECT puzzle_name, result, attempts FROM puzzle_results").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0] == ("The Lock", "SOLVED", 2)
