import json
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
