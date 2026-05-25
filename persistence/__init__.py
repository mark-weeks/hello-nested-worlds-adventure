"""Durable state for the multiverse.

Single SQLite database, single connection factory (`_connect`), schema
managed by the migration runner over `persistence/migrations/*.sql`.
Caller code outside this module does not touch `sqlite3` directly.

The dialect-specific bits — the few places we depend on SQLite syntax
that won't port to Postgres — are concentrated in the `--- SQL dialect
seam ---` block below. See `docs/decisions/ADR-003-persistence-backend.md`
for the switchover plan and the full translation table.
"""
from __future__ import annotations

import functools
import json
import logging
import os
import sqlite3
import stat
from pathlib import Path
from typing import Any, Callable

_DB_PATH = Path.home() / ".nested-worlds" / "worlds.db"
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_TTL_ENV_VAR = "NESTED_WORLDS_MUTATION_TTL_DAYS"

# --- SQL dialect seam ---
# Concentrate SQLite-isms here so the Postgres port is mechanical.
# See docs/decisions/ADR-003-persistence-backend.md.
#
# Abstracted:
#   _NOW                — current-timestamp expression
#   _delete_older_than  — relative-interval DELETE used by prune_mutations
#
# Not yet abstracted (deliberate — kept as-is to avoid churn before the
# switchover triggers; translation is mechanical at port time):
#   * `INSERT OR REPLACE INTO worlds ...`       — save_world
#   * `INSERT OR REPLACE INTO node_images ...`  — cache_image
#   * `_SCHEMA_VERSION_DDL` `DEFAULT (datetime('now'))` — per-backend DDL
#   * `migrations/*.sql` — schema files are per-backend; a Postgres port
#     ships as `migrations/postgres/*.sql` selected by the runner.

_NOW = "datetime('now')"  # PG: CURRENT_TIMESTAMP


def _delete_older_than(conn: sqlite3.Connection, table: str,
                       column: str, days: int) -> int:
    """Delete rows from `table` where `column` is older than `days` days.

    SQLite-specific because the relative-interval syntax differs. On
    Postgres this becomes:
        DELETE FROM {table} WHERE {column} < NOW() - %s * INTERVAL '1 day'
    """
    cur = conn.execute(
        f"DELETE FROM {table} WHERE {column} < datetime('now', ?)",
        (f"-{int(days)} days",),
    )
    return cur.rowcount


_SCHEMA_VERSION_DDL = """
    CREATE TABLE IF NOT EXISTS schema_version (
        version    INTEGER PRIMARY KEY,
        applied_at TEXT    NOT NULL DEFAULT (datetime('now'))
    );
"""

_initialized: set[Path] = set()
_log = logging.getLogger("nested_worlds.persistence")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _list_migrations() -> list[tuple[int, Path]]:
    """Return [(version, path)] for every well-named migration, sorted.

    Filenames must start with a zero-padded integer followed by an
    underscore (e.g. `0001_initial.sql`); anything else is skipped so a
    stray README in the directory doesn't get executed.
    """
    out: list[tuple[int, Path]] = []
    for path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        head, _, _ = path.name.partition("_")
        try:
            version = int(head)
        except ValueError:
            continue
        out.append((version, path))
    return out


def _run_migrations(conn: sqlite3.Connection) -> list[int]:
    """Apply any migrations not yet recorded in `schema_version`.

    Returns the versions applied in this call (empty if up-to-date).
    Each migration runs in its own transaction so a failure leaves the
    DB at the last successfully-applied version.
    """
    conn.executescript(_SCHEMA_VERSION_DDL)
    applied = {r[0] for r in conn.execute("SELECT version FROM schema_version")}
    just_applied: list[int] = []
    for version, path in _list_migrations():
        if version in applied:
            continue
        sql = path.read_text()
        try:
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (version,)
            )
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise
        just_applied.append(version)
    return just_applied


def init_db() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        _run_migrations(conn)
    # 0o600 — owner read/write only.  Set once on init, not per-connect.
    _DB_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
    _initialized.add(_DB_PATH)
    _maybe_prune_from_env()


def _maybe_prune_from_env() -> None:
    """Honor the NESTED_WORLDS_MUTATION_TTL_DAYS env var on init.

    Default is unset → no pruning. Operators set a positive integer to
    cap mutation-log retention at that many days. Invalid values are
    silently ignored so a typo doesn't break startup.
    """
    raw = os.environ.get(_TTL_ENV_VAR, "").strip()
    if not raw:
        return
    try:
        days = int(raw)
    except ValueError:
        _log.warning("ignoring invalid %s=%r", _TTL_ENV_VAR, raw)
        return
    if days <= 0:
        return
    removed = prune_mutations(days)
    if removed:
        _log.info("pruned %d mutations older than %d days", removed, days)


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


@_with_db
def save_agent_memory(agent_name: str, world_seed: int,
                      visited_ids: list[str], log_entries: list[dict[str, Any]]) -> None:
    with _connect() as conn:
        conn.execute(
            f"""INSERT INTO agent_memory (agent_name, world_seed, visited_ids, log_entries, updated_at)
               VALUES (?, ?, ?, ?, {_NOW})
               ON CONFLICT(agent_name, world_seed) DO UPDATE SET
                 visited_ids = excluded.visited_ids,
                 log_entries = excluded.log_entries,
                 updated_at  = excluded.updated_at""",
            (agent_name, world_seed, json.dumps(visited_ids), json.dumps(log_entries)),
        )


@_with_db
def load_agent_memory(agent_name: str, world_seed: int) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            """SELECT visited_ids, log_entries, updated_at
               FROM agent_memory WHERE agent_name = ? AND world_seed = ?""",
            (agent_name, world_seed),
        ).fetchone()
        if row is None:
            return None
        return {
            "visited_ids": json.loads(row[0]),
            "log_entries": json.loads(row[1]),
            "updated_at":  row[2],
        }


@_with_db
def get_cached_image(node_key: str) -> str | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT image_url FROM node_images WHERE node_key = ?", (node_key,)
        ).fetchone()
        return row[0] if row else None


@_with_db
def cache_image(node_key: str, image_url: str) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO node_images (node_key, image_url)
               VALUES (?, ?)""",
            (node_key, image_url),
        )


@_with_db
def upsert_ripple_score(world_seed: int, node_name: str, ripple_score: float) -> None:
    """Write through the in-memory ripple_score for one node.

    Called from the causality bus on every fired event so the cumulative
    causal pressure survives the per-request world rebuild — without this,
    `generate_node_hierarchy` returns fresh nodes each call and the score
    resets to 0 between endpoint hits.
    """
    with _connect() as conn:
        conn.execute(
            f"""INSERT INTO node_runtime_state (world_seed, node_name, ripple_score, updated_at)
               VALUES (?, ?, ?, {_NOW})
               ON CONFLICT(world_seed, node_name) DO UPDATE SET
                 ripple_score = excluded.ripple_score,
                 updated_at   = excluded.updated_at""",
            (world_seed, node_name, float(ripple_score)),
        )


@_with_db
def get_ripple_score(world_seed: int, node_name: str) -> float:
    with _connect() as conn:
        row = conn.execute(
            "SELECT ripple_score FROM node_runtime_state WHERE world_seed = ? AND node_name = ?",
            (world_seed, node_name),
        ).fetchone()
        return float(row[0]) if row else 0.0


@_with_db
def load_ripple_scores(world_seed: int) -> dict[str, float]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT node_name, ripple_score FROM node_runtime_state WHERE world_seed = ?",
            (world_seed,),
        ).fetchall()
        return {name: float(score) for name, score in rows}


@_with_db
def list_agent_memories() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT agent_name, world_seed, updated_at,
                      json_array_length(visited_ids) AS node_count
               FROM agent_memory ORDER BY updated_at DESC"""
        ).fetchall()
        return [
            {"agent_name": r[0], "world_seed": r[1], "updated_at": r[2], "node_count": r[3]}
            for r in rows
        ]


@_with_db
def prune_mutations(days: int) -> int:
    """Delete `world_mutations` rows older than *days*. Returns rows removed.

    Off by default — `init_db` only invokes this when
    `NESTED_WORLDS_MUTATION_TTL_DAYS` is set to a positive integer. Operators
    can also call directly from a maintenance script. `days <= 0` is a no-op
    so callers don't need to guard the threshold themselves.
    """
    if days <= 0:
        return 0
    with _connect() as conn:
        return _delete_older_than(conn, "world_mutations", "recorded_at", days)


@_with_db
def get_cost_calls(bucket: str, day: str) -> int:
    """Read today's call count for `bucket` (returns 0 if no row yet)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT calls FROM cost_budget WHERE bucket = ? AND day = ?",
            (bucket, day),
        ).fetchone()
        return int(row[0]) if row else 0


@_with_db
def increment_cost_calls(bucket: str, day: str) -> int:
    """Atomically bump the (bucket, day) counter and return the new value."""
    with _connect() as conn:
        conn.execute(
            """INSERT INTO cost_budget (bucket, day, calls) VALUES (?, ?, 1)
               ON CONFLICT(bucket, day) DO UPDATE SET calls = calls + 1""",
            (bucket, day),
        )
        row = conn.execute(
            "SELECT calls FROM cost_budget WHERE bucket = ? AND day = ?",
            (bucket, day),
        ).fetchone()
        return int(row[0]) if row else 0


@_with_db
def schema_versions() -> list[int]:
    """Return all migration versions recorded as applied, sorted ascending."""
    with _connect() as conn:
        return [r[0] for r in conn.execute(
            "SELECT version FROM schema_version ORDER BY version"
        )]


@_with_db
def backup_to(target: Path) -> None:
    """Write a consistent online snapshot of the live DB to `target`.

    Uses sqlite's `Connection.backup()` so concurrent readers/writers are
    safe — this is the supported way to copy a WAL-mode database while it's
    in use. Operators wire this to a host cron / Fly cron / Render cron job
    so the volume that holds `worlds.db` isn't a single point of failure.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as src:
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            dst.close()
    target.chmod(stat.S_IRUSR | stat.S_IWUSR)
