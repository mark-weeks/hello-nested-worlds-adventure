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
        assert {"worlds", "agent_runs", "puzzle_results"}.issubset(tables)

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
