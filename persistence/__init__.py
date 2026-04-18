from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

_DB_PATH = Path.home() / ".nested-worlds" / "worlds.db"


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript("""
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
        """)


def save_world(seed: int, node_count: int, max_depth: int, min_breadth: int, max_breadth: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO worlds (seed, node_count, max_depth, min_breadth, max_breadth)
               VALUES (?, ?, ?, ?, ?)""",
            (seed, node_count, max_depth, min_breadth, max_breadth),
        )


def save_agent_run(agent_name: str, world_seed: int, nodes_visited: int, events: list[dict[str, Any]]) -> int:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO agent_runs (agent_name, world_seed, nodes_visited, events)
               VALUES (?, ?, ?, ?)""",
            (agent_name, world_seed, nodes_visited, json.dumps(events)),
        )
        return cur.lastrowid


def save_puzzle_result(world_seed: int, puzzle_name: str, result: str, attempts: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO puzzle_results (world_seed, puzzle_name, result, attempts)
               VALUES (?, ?, ?, ?)""",
            (world_seed, puzzle_name, result, attempts),
        )


def list_worlds() -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT seed, created_at, node_count, max_depth FROM worlds ORDER BY created_at DESC"
        ).fetchall()
        return [{"seed": r[0], "created_at": r[1], "node_count": r[2], "max_depth": r[3]} for r in rows]


def get_agent_runs(world_seed: int) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT agent_name, started_at, nodes_visited
               FROM agent_runs WHERE world_seed = ?
               ORDER BY started_at DESC""",
            (world_seed,),
        ).fetchall()
        return [{"agent_name": r[0], "started_at": r[1], "nodes_visited": r[2]} for r in rows]
