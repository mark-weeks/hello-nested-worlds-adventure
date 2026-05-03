from __future__ import annotations

import functools
import json
import sqlite3
import stat
from pathlib import Path
from typing import Any, Callable

_DB_PATH = Path.home() / ".nested-worlds" / "worlds.db"

_SCHEMA = """
    CREATE TABLE IF NOT EXISTS worlds (
        seed        INTEGER PRIMARY KEY,
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        node_count  INTEGER,
        max_depth   INTEGER,
        min_breadth INTEGER,
        max_breadth INTEGER
    );

    CREATE TABLE IF NOT EXISTS agent_runs (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_name    TEXT NOT NULL,
        world_seed    INTEGER NOT NULL,
        started_at    TEXT NOT NULL DEFAULT (datetime('now')),
        nodes_visited INTEGER,
        events        TEXT
    );

    CREATE TABLE IF NOT EXISTS puzzle_results (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        world_seed  INTEGER NOT NULL,
        puzzle_name TEXT NOT NULL,
        result      TEXT NOT NULL,
        attempts    INTEGER NOT NULL,
        recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS world_mutations (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        world_seed    INTEGER NOT NULL,
        node_name     TEXT NOT NULL,
        mutation_type TEXT NOT NULL,
        player_name   TEXT,
        data          TEXT,
        recorded_at   TEXT NOT NULL DEFAULT (datetime('now'))
    );
"""

_initialized: set[Path] = set()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    # 0o600 — owner read/write only.  Set once on init, not per-connect.
    _DB_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
    _initialized.add(_DB_PATH)


def _with_db(fn: Callable) -> Callable:
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if _DB_PATH not in _initialized:
            init_db()
        return fn(*args, **kwargs)
    return wrapper


@_with_db
def save_world(seed: int, node_count: int, max_depth: int, min_breadth: int, max_breadth: int) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO worlds (seed, node_count, max_depth, min_breadth, max_breadth)
               VALUES (?, ?, ?, ?, ?)""",
            (seed, node_count, max_depth, min_breadth, max_breadth),
        )


@_with_db
def save_agent_run(agent_name: str, world_seed: int, nodes_visited: int, events: list[dict[str, Any]]) -> int:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO agent_runs (agent_name, world_seed, nodes_visited, events)
               VALUES (?, ?, ?, ?)""",
            (agent_name, world_seed, nodes_visited, json.dumps(events)),
        )
        return cur.lastrowid


@_with_db
def save_puzzle_result(world_seed: int, puzzle_name: str, result: str, attempts: int) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO puzzle_results (world_seed, puzzle_name, result, attempts)
               VALUES (?, ?, ?, ?)""",
            (world_seed, puzzle_name, result, attempts),
        )


@_with_db
def list_worlds() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT seed, created_at, node_count, max_depth FROM worlds ORDER BY created_at DESC"
        ).fetchall()
        return [{"seed": r[0], "created_at": r[1], "node_count": r[2], "max_depth": r[3]} for r in rows]


@_with_db
def get_node_history(world_seed: int, node_name: str, limit: int = 8) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT mutation_type, player_name, data, recorded_at
               FROM world_mutations WHERE world_seed = ? AND node_name = ?
               ORDER BY recorded_at DESC LIMIT ?""",
            (world_seed, node_name, limit),
        ).fetchall()
        return [
            {"type": r[0], "player": r[1], "data": json.loads(r[2]) if r[2] else {}, "at": r[3]}
            for r in rows
        ]


@_with_db
def record_mutation(world_seed: int, node_name: str, mutation_type: str,
                    player_name: str | None, data: dict) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO world_mutations (world_seed, node_name, mutation_type, player_name, data)
               VALUES (?, ?, ?, ?, ?)""",
            (world_seed, node_name, mutation_type, player_name, json.dumps(data)),
        )


@_with_db
def get_mutations(world_seed: int, limit: int = 50) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT node_name, mutation_type, player_name, data, recorded_at
               FROM world_mutations WHERE world_seed = ?
               ORDER BY recorded_at DESC LIMIT ?""",
            (world_seed, limit),
        ).fetchall()
        return [{"node": r[0], "type": r[1], "player": r[2],
                 "data": json.loads(r[3]) if r[3] else {}, "at": r[4]}
                for r in rows]


@_with_db
def get_agent_runs(world_seed: int) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT agent_name, started_at, nodes_visited
               FROM agent_runs WHERE world_seed = ?
               ORDER BY started_at DESC""",
            (world_seed,),
        ).fetchall()
        return [{"agent_name": r[0], "started_at": r[1], "nodes_visited": r[2]} for r in rows]
