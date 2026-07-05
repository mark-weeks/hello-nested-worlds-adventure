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
import threading
from pathlib import Path
from typing import Any, Callable

_DB_PATH = Path.home() / ".nested-worlds" / "worlds.db"
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_TTL_ENV_VAR = "NESTED_WORLDS_MUTATION_TTL_DAYS"
_PRUNE_OVERRIDE_ENV = "NESTED_WORLDS_ALLOW_HISTORY_PRUNE"

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
#   * `INSERT OR REPLACE INTO node_images ...`  — cache_image
#   * `json_patch(...)`   — upsert_node_properties (PG: `properties || ?`)
#   * `json_extract(...)` — get_player_exchanges (PG: `data->>'identity'`)
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
_init_lock = threading.Lock()
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
    # Lazy init happens on the first DB touch, which under a joining rush
    # is N request threads at once — without the lock, two threads race
    # _run_migrations and the loser re-applies a migration onto a schema
    # that already has it ("duplicate column name", caught by the WS soak
    # test). Double-checked so the post-init hot path stays lock-free in
    # _with_db.
    with _init_lock:
        if _DB_PATH in _initialized:
            return
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _connect() as conn:
            _run_migrations(conn)
        # 0o600 — owner read/write only.  Set once on init, not per-connect.
        _DB_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
        _initialized.add(_DB_PATH)
    _maybe_prune_from_env()


def _maybe_prune_from_env() -> None:
    """Honor the NESTED_WORLDS_MUTATION_TTL_DAYS env var on init.

    Default is unset → no pruning. `world_mutations` is the world's
    chronicle — the continuity policy (docs/roadmap/phase-2-scale.md)
    declares it permanent, and the generative art reads its per-node
    activity counts — so the TTL alone no longer prunes: the operator
    must also set NESTED_WORLDS_ALLOW_HISTORY_PRUNE=1 to confirm they
    mean to violate that policy. Invalid values are ignored so a typo
    doesn't break startup.
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
    if os.environ.get(_PRUNE_OVERRIDE_ENV, "").strip() != "1":
        _log.warning(
            "%s is set but ignored: pruning world_mutations erases the "
            "world's chronicle (and the art's activity history), which "
            "the continuity policy forbids. Set %s=1 if you truly mean it.",
            _TTL_ENV_VAR, _PRUNE_OVERRIDE_ENV,
        )
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
    # ON CONFLICT (not INSERT OR REPLACE): REPLACE deletes + reinserts the
    # row, which re-fires the created_at default and erases the world's
    # birth date on every visit. The world's age must be recoverable.
    with _connect() as conn:
        conn.execute(
            """INSERT INTO worlds (seed, node_count, max_depth, min_breadth, max_breadth)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(seed) DO UPDATE SET
                 node_count  = excluded.node_count,
                 max_depth   = excluded.max_depth,
                 min_breadth = excluded.min_breadth,
                 max_breadth = excluded.max_breadth""",
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
def enqueue_causal_hop(world_seed: int, node_name: str, kind: str,
                       strength: float, direction: str, payload: dict,
                       delay_seconds: float) -> None:
    """Schedule one hop of a staged cascade to fire after `delay_seconds`.

    (SQLite-ism: relative datetime modifier — PG: NOW() + make_interval().)
    """
    with _connect() as conn:
        conn.execute(
            """INSERT INTO causal_queue
               (world_seed, node_name, kind, strength, direction, payload, due_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now', ?))""",
            (world_seed, node_name, kind, float(strength), direction,
             json.dumps(payload), f"+{int(delay_seconds)} seconds"),
        )


@_with_db
def claim_due_causal_hops(limit: int = 64) -> list[dict[str, Any]]:
    """Atomically remove and return hops whose due time has arrived.

    DELETE … RETURNING makes the claim atomic, so a hop fires exactly once
    even if multiple pumps ever run.
    """
    with _connect() as conn:
        rows = conn.execute(
            """DELETE FROM causal_queue
               WHERE id IN (SELECT id FROM causal_queue
                            WHERE due_at <= datetime('now')
                            ORDER BY due_at, id LIMIT ?)
               RETURNING world_seed, node_name, kind, strength, direction, payload""",
            (limit,),
        ).fetchall()
        return [{"world_seed": r[0], "node_name": r[1], "kind": r[2],
                 "strength": r[3], "direction": r[4],
                 "payload": json.loads(r[5]) if r[5] else {}} for r in rows]


@_with_db
def pending_causal_hops(world_seed: int | None = None) -> int:
    """How many cascade hops are still in flight (ops / test signal)."""
    with _connect() as conn:
        if world_seed is None:
            row = conn.execute("SELECT COUNT(*) FROM causal_queue").fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) FROM causal_queue WHERE world_seed = ?",
                (world_seed,)).fetchone()
        return int(row[0])


@_with_db
def get_puzzle_solve(world_seed: int, node_name: str,
                     puzzle_name: str) -> dict[str, Any] | None:
    """The most recent HUMAN solve of `puzzle_name` at `node_name`, or None.

    Used to rehydrate a room's in-memory co-op PuzzleSession after a process
    restart, so a solved puzzle stays solved instead of resetting against a
    history that says otherwise. Agent solves (payload carries "agent") are
    excluded — ambient wanderers must not lock puzzles away from players.
    Returns {"solver": name-or-"anonymous", "contributors": [...]}.
    """
    with _connect() as conn:
        rows = conn.execute(
            """SELECT player_name, data FROM world_mutations
               WHERE world_seed = ? AND node_name = ?
                 AND mutation_type = 'PUZZLE_SOLVED'
               ORDER BY recorded_at DESC, id DESC LIMIT 20""",
            (world_seed, node_name),
        ).fetchall()
    for player_name, blob in rows:
        data = json.loads(blob) if blob else {}
        if data.get("agent"):
            continue  # ambient agent solve — not co-op session state
        if data.get("puzzle") != puzzle_name:
            continue
        return {
            "solver": player_name or "anonymous",
            "contributors": data.get("contributors") or [],
        }
    return None


@_with_db
def get_puzzle_results(world_seed: int, limit: int = 20) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT puzzle_name, result, attempts, recorded_at
               FROM puzzle_results WHERE world_seed = ?
               ORDER BY recorded_at DESC, id DESC LIMIT ?""",
            (world_seed, limit),
        ).fetchall()
        return [{"puzzle_name": r[0], "result": r[1], "attempts": r[2],
                 "recorded_at": r[3]} for r in rows]


@_with_db
def list_worlds() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT seed, created_at, node_count, max_depth FROM worlds ORDER BY created_at DESC"
        ).fetchall()
        return [{"seed": r[0], "created_at": r[1], "node_count": r[2], "max_depth": r[3]} for r in rows]


@_with_db
def get_node_history(world_seed: int, node_name: str, limit: int = 10) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT mutation_type, player_name, data, recorded_at
               FROM world_mutations WHERE world_seed = ? AND node_name = ?
               ORDER BY recorded_at DESC, id DESC LIMIT ?""",
            (world_seed, node_name, limit),
        ).fetchall()
        return [
            {"type": r[0], "player": r[1], "data": json.loads(r[2]) if r[2] else {}, "at": r[3]}
            for r in rows
        ]


@_with_db
def get_player_exchanges(world_seed: int, node_name: str, identity: str,
                         limit: int = 3) -> list[dict[str, Any]]:
    """The most recent PLAYER_SPEAK exchanges between one speaker and this
    node, oldest first — the per-(node, speaker) conversation transcript that
    lets the second conversation know the first one happened.

    `identity` is the speaker's durable conversation key: a hash of their
    per-user invite credential when one was presented, else their display
    name. Keying on the credential means two players who both call
    themselves "Ada" do not share a memory, and renaming yourself does not
    orphan yours. (SQLite-ism: json_extract — see the dialect seam note.)

    Each entry is {"user": <what they said>, "assistant": <what the node
    answered, if recorded>}.
    """
    if not identity:
        return []
    with _connect() as conn:
        rows = conn.execute(
            """SELECT data FROM world_mutations
               WHERE world_seed = ? AND node_name = ?
                 AND mutation_type = 'PLAYER_SPEAK'
                 AND json_extract(data, '$.identity') = ?
               ORDER BY recorded_at DESC, id DESC LIMIT ?""",
            (world_seed, node_name, identity, limit),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for (blob,) in reversed(rows):
        data = json.loads(blob) if blob else {}
        if data.get("message"):
            out.append({"user": data["message"], "assistant": data.get("reply")})
    return out


@_with_db
def record_mutation(world_seed: int, node_name: str, mutation_type: str,
                    player_name: str | None, data: dict,
                    actor_identity: str | None = None) -> None:
    """Append one chronicle row.

    `player_name` is the mutable display label; `actor_identity` is the
    durable key for WHO — the credential hash (sha256(key)[:16]) when the
    request carried a per-user invite key, else the display name, else
    None. Callers on human paths should always pass it.
    """
    with _connect() as conn:
        conn.execute(
            """INSERT INTO world_mutations
               (world_seed, node_name, mutation_type, player_name, data,
                actor_identity)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (world_seed, node_name, mutation_type, player_name,
             json.dumps(data), actor_identity),
        )


@_with_db
def get_mutations(world_seed: int, limit: int = 50) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT node_name, mutation_type, player_name, data, recorded_at
               FROM world_mutations WHERE world_seed = ?
               ORDER BY recorded_at DESC, id DESC LIMIT ?""",
            (world_seed, limit),
        ).fetchall()
        return [{"node": r[0], "type": r[1], "player": r[2],
                 "data": json.loads(r[3]) if r[3] else {}, "at": r[4]}
                for r in rows]


@_with_db
def count_node_mutations(world_seed: int, node_name: str,
                         mutation_type: str) -> int:
    """How many events of one type this node has accumulated."""
    with _connect() as conn:
        return conn.execute(
            """SELECT COUNT(*) FROM world_mutations
               WHERE world_seed = ? AND node_name = ? AND mutation_type = ?""",
            (world_seed, node_name, mutation_type),
        ).fetchone()[0]


@_with_db
def count_rearms_by_node(world_seed: int) -> dict[str, int]:
    """Per-node puzzle renewal counts — each node's current puzzle epoch.

    A PUZZLE_REARM lands when the world's entropy (a strong decay event)
    hits a node whose current puzzle is already solved; the epoch folds
    into puzzle generation so the node grows a fresh, unsolved puzzle.
    """
    with _connect() as conn:
        rows = conn.execute(
            """SELECT node_name, COUNT(*) FROM world_mutations
               WHERE world_seed = ? AND mutation_type = 'PUZZLE_REARM'
               GROUP BY node_name""",
            (world_seed,),
        ).fetchall()
    return {name: count for name, count in rows}


@_with_db
def get_puzzle_attempt_state(world_seed: int, node_name: str,
                             puzzle_name: str) -> dict[str, Any]:
    """Rehydrate the pooled co-op attempt state from the attempt log.

    Attempt counts previously lived only in in-memory PuzzleSession, so a
    deploy silently refunded a room's spent attempts. Every guess is now a
    PUZZLE_ATTEMPT chronicle row; this counts them back.
    """
    with _connect() as conn:
        rows = conn.execute(
            """SELECT player_name FROM world_mutations
               WHERE world_seed = ? AND node_name = ?
                 AND mutation_type = 'PUZZLE_ATTEMPT'
                 AND json_extract(data, '$.puzzle') = ?""",
            (world_seed, node_name, puzzle_name),
        ).fetchall()
    return {"attempts": len(rows),
            "contributors": {r[0] for r in rows if r[0]}}


@_with_db
def get_chronicle(world_seed: int, limit: int = 50,
                  before_id: int | None = None) -> dict[str, Any]:
    """A page of the world's full history, newest first, cursor-paginated.

    `before_id` walks backward in time (fetch entries with id < before_id).
    Returns {entries, next_before, total, began}: `next_before` is the
    cursor for the next-older page (None when exhausted), `total` the
    world's full event count, `began` the timestamp of its first recorded
    event — the world's birth in lived history.
    """
    limit = max(1, min(int(limit), 200))
    with _connect() as conn:
        if before_id is not None:
            rows = conn.execute(
                """SELECT id, node_name, mutation_type, player_name, data,
                          recorded_at, actor_identity
                   FROM world_mutations WHERE world_seed = ? AND id < ?
                   ORDER BY id DESC LIMIT ?""",
                (world_seed, before_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, node_name, mutation_type, player_name, data,
                          recorded_at, actor_identity
                   FROM world_mutations WHERE world_seed = ?
                   ORDER BY id DESC LIMIT ?""",
                (world_seed, limit),
            ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM world_mutations WHERE world_seed = ?",
            (world_seed,),
        ).fetchone()[0]
        began = conn.execute(
            "SELECT MIN(recorded_at) FROM world_mutations WHERE world_seed = ?",
            (world_seed,),
        ).fetchone()[0]
    entries = [{"id": r[0], "node": r[1], "type": r[2], "player": r[3],
                "data": json.loads(r[4]) if r[4] else {}, "at": r[5],
                "actor": r[6]}
               for r in rows]
    exhausted = len(rows) < limit
    return {
        "entries": entries,
        "next_before": None if exhausted else entries[-1]["id"],
        "total": total,
        "began": began,
    }


@_with_db
def count_mutations_by_node(world_seed: int) -> dict[str, int]:
    """Recorded interactions per node — the world's lived history, in counts.
    Feeds the per-node generative art (trace etchings) via /world."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT node_name, COUNT(*) FROM world_mutations
               WHERE world_seed = ? GROUP BY node_name""",
            (world_seed,),
        ).fetchall()
        return {name: count for name, count in rows}


@_with_db
def get_agent_runs(world_seed: int) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT agent_name, started_at, nodes_visited
               FROM agent_runs WHERE world_seed = ?
               ORDER BY started_at DESC, id DESC""",
            (world_seed,),
        ).fetchall()
        return [{"agent_name": r[0], "started_at": r[1], "nodes_visited": r[2]} for r in rows]


@_with_db
def save_agent_memory(agent_name: str, world_seed: int,
                      visited_ids: list[str], log_entries: list[dict[str, Any]]) -> None:
    with _connect() as conn:
        conn.execute(
            f"""INSERT INTO agent_memory (agent_name, world_seed, visited_ids, log_entries, updated_at, created_at)
               VALUES (?, ?, ?, ?, {_NOW}, {_NOW})
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
            f"""INSERT INTO node_runtime_state (world_seed, node_name, ripple_score, updated_at, created_at)
               VALUES (?, ?, ?, {_NOW}, {_NOW})
               ON CONFLICT(world_seed, node_name) DO UPDATE SET
                 ripple_score = excluded.ripple_score,
                 updated_at   = excluded.updated_at""",
            (world_seed, node_name, float(ripple_score)),
        )


@_with_db
def increment_ripple_score(world_seed: int, node_name: str, delta: float) -> None:
    """Atomically add `delta` to a node's persisted causal pressure (clamped
    to 1.0). Additive at the DB level so two simultaneous players' cascades
    compound instead of overwriting each other (the lost-update race that an
    absolute upsert from each request's private tree would create)."""
    with _connect() as conn:
        conn.execute(
            f"""INSERT INTO node_runtime_state (world_seed, node_name, ripple_score, updated_at, created_at)
               VALUES (?, ?, ?, {_NOW}, {_NOW})
               ON CONFLICT(world_seed, node_name) DO UPDATE SET
                 ripple_score = MIN(1.0, ripple_score + excluded.ripple_score),
                 updated_at   = excluded.updated_at""",
            (world_seed, node_name, min(1.0, float(delta))),
        )


@_with_db
def upsert_node_properties(world_seed: int, node_name: str, changed: dict) -> None:
    """Merge `changed` into the node's persisted property overlay.

    The overlay is applied on top of deterministic generation at every world
    rebuild (`load_node_property_overrides` + `apply_property_overrides`), so
    a causal event's material consequence outlives the request that fired it.
    `json_patch` merges atomically at the DB level.
    """
    with _connect() as conn:
        conn.execute(
            f"""INSERT INTO node_runtime_state (world_seed, node_name, ripple_score, properties, updated_at, created_at)
               VALUES (?, ?, 0.0, ?, {_NOW}, {_NOW})
               ON CONFLICT(world_seed, node_name) DO UPDATE SET
                 properties = json_patch(COALESCE(node_runtime_state.properties, '{{}}'), excluded.properties),
                 updated_at = excluded.updated_at""",
            (world_seed, node_name, json.dumps(changed)),
        )


@_with_db
def load_node_property_overrides(world_seed: int) -> dict[str, dict]:
    """All persisted property overlays for a world, keyed by node name."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT node_name, properties FROM node_runtime_state
               WHERE world_seed = ? AND properties IS NOT NULL""",
            (world_seed,),
        ).fetchall()
        return {name: json.loads(blob) for name, blob in rows if blob}


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
            f"""INSERT INTO cost_budget (bucket, day, calls, created_at)
               VALUES (?, ?, 1, {_NOW})
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
def mint_invite_key(key: str, name: str, note: str | None = None) -> None:
    """Insert a new invite key. Caller generates the random key string.

    Raises sqlite3.IntegrityError on collision so the caller can retry
    with a new random key — at 32 hex chars (128 bits) collisions are
    astronomically unlikely in practice.
    """
    with _connect() as conn:
        conn.execute(
            "INSERT INTO invite_keys (key, name, note) VALUES (?, ?, ?)",
            (key, name, note),
        )


@_with_db
def lookup_invite_key(key: str) -> dict[str, Any] | None:
    """Return the row for `key` iff it exists AND is not revoked.

    Returns None for unknown keys and revoked keys alike — the caller
    treats both as "not authorized" without leaking which condition
    matched.
    """
    with _connect() as conn:
        row = conn.execute(
            """SELECT key, name, note, created_at, revoked_at, last_used_at
               FROM invite_keys WHERE key = ? AND revoked_at IS NULL""",
            (key,),
        ).fetchone()
        if row is None:
            return None
        return {
            "key": row[0], "name": row[1], "note": row[2],
            "created_at": row[3], "revoked_at": row[4],
            "last_used_at": row[5],
        }


@_with_db
def touch_invite_key(key: str) -> None:
    """Update last_used_at for `key` to now. No-op for unknown keys."""
    with _connect() as conn:
        conn.execute(
            f"UPDATE invite_keys SET last_used_at = {_NOW} WHERE key = ?",
            (key,),
        )


@_with_db
def revoke_invite_key(key: str) -> bool:
    """Mark `key` revoked. Returns True iff a row was actually updated."""
    with _connect() as conn:
        cur = conn.execute(
            f"""UPDATE invite_keys SET revoked_at = {_NOW}
                WHERE key = ? AND revoked_at IS NULL""",
            (key,),
        )
        return cur.rowcount > 0


@_with_db
def list_invite_keys(include_revoked: bool = False) -> list[dict[str, Any]]:
    """Return all invite keys, newest first. Active-only unless include_revoked."""
    where = "" if include_revoked else "WHERE revoked_at IS NULL"
    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT key, name, note, created_at, revoked_at, last_used_at
                FROM invite_keys {where}
                ORDER BY created_at DESC"""
        ).fetchall()
        return [
            {"key": r[0], "name": r[1], "note": r[2],
             "created_at": r[3], "revoked_at": r[4], "last_used_at": r[5]}
            for r in rows
        ]


@_with_db
def save_player_position(key: str, node_name: str, seed: int, depth: int,
                         min_breadth: int, max_breadth: int) -> bool:
    """Record where an invite-key holder left off, for cross-device resume.

    Keyed on the per-user invite key, so this only persists for a real per-user
    credential — the UPDATE affects zero rows (returns False) for the shared env
    key, an unknown key, or a revoked one, and the client keeps using its local
    cache. Best-effort: callers fire-and-forget on navigation.
    """
    if not key:
        return False
    with _connect() as conn:
        cur = conn.execute(
            f"""UPDATE invite_keys
                SET last_node = ?, last_seed = ?, last_depth = ?,
                    last_min_breadth = ?, last_max_breadth = ?, last_node_at = {_NOW}
                WHERE key = ? AND revoked_at IS NULL""",
            (node_name, seed, depth, min_breadth, max_breadth, key),
        )
        return cur.rowcount > 0


@_with_db
def get_player_position(key: str) -> dict[str, Any] | None:
    """Return the invite-key holder's saved position, or None if none is stored
    (or the key isn't an active per-user key)."""
    if not key:
        return None
    with _connect() as conn:
        row = conn.execute(
            """SELECT last_node, last_seed, last_depth, last_min_breadth, last_max_breadth
               FROM invite_keys WHERE key = ? AND revoked_at IS NULL""",
            (key,),
        ).fetchone()
    if row is None or row[0] is None:
        return None
    return {
        "node":        row[0],
        "seed":        row[1],
        "depth":       row[2],
        "min_breadth": row[3],
        "max_breadth": row[4],
    }


@_with_db
def checkpoint() -> None:
    """Flush the WAL back into the main DB file.

    Called on graceful shutdown so a redeploy doesn't leave a large `-wal`
    sidecar to be replayed on next open. Best-effort; a busy checkpoint that
    can't fully truncate is harmless (WAL is still durable).
    """
    with _connect() as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")


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


@_with_db
def restore_from(source: Path) -> dict[str, Any]:
    """Restore the live DB from a backup file — `backup_to` in reverse.

    The continuity policy's promise is "a bad migration is a restore, not
    a lost epoch"; this is the restore. Uses the same sqlite backup API,
    which takes the proper locks, so it is safe against a live server's
    per-operation connections (rehearsed against a running instance in the
    pre-deployment review). In-memory state (rooms, puzzle sessions, rate
    buckets) still reflects the pre-restore world — restart the process
    after restoring (`fly machine restart` in production).

    Refuses anything that is not a readable SQLite database containing a
    `world_mutations` table, so a typo'd path can't blank the chronicle.
    Returns {events_before, events_after} for the operator's sanity check.
    """
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(f"backup not found: {source}")
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        try:
            tables = {r[0] for r in src.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        except sqlite3.DatabaseError as exc:
            raise ValueError(f"{source} is not a SQLite database") from exc
        if "world_mutations" not in tables:
            raise ValueError(
                f"{source} is a SQLite database but not a worlds backup "
                "(no world_mutations table) — refusing to restore it")
        with _connect() as live:
            before = live.execute(
                "SELECT COUNT(*) FROM world_mutations").fetchone()[0]
            src.backup(live)
            after = live.execute(
                "SELECT COUNT(*) FROM world_mutations").fetchone()[0]
    finally:
        src.close()
    return {"events_before": before, "events_after": after}
