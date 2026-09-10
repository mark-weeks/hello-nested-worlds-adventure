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

from contextlib import contextmanager
import functools
import hashlib
import json
import logging
import os
import sqlite3
import stat
import threading
from pathlib import Path
from typing import Any, Callable

from merge_patch import json_merge_patch

_DB_PATH = Path.home() / ".nested-worlds" / "worlds.db"
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_TTL_ENV_VAR = "NESTED_WORLDS_MUTATION_TTL_DAYS"
_PRUNE_OVERRIDE_ENV = "NESTED_WORLDS_ALLOW_HISTORY_PRUNE"

# --- SQL dialect seam ---
# Concentrate SQLite-isms here so the Postgres port is mechanical.
# See docs/decisions/ADR-003-persistence-backend.md.
#
# Abstracted:
#   _NOW                 — current-timestamp expression
#   _older_than_cutoff   — fixed relative-age cutoff for maintenance
#   _delete_older_than   — cutoff-based DELETE used by prune_mutations
#
# Not yet abstracted (deliberate — kept as-is to avoid churn before the
# switchover triggers; translation is mechanical at port time):
#   * `INSERT OR REPLACE INTO node_images ...`  — cache_image
#   * `json_extract(...)` — get_player_exchanges (PG: `data->>'identity'`)
#   * `_SCHEMA_VERSION_DDL` `DEFAULT (datetime('now'))` — per-backend DDL
#   * `migrations/*.sql` — schema files are per-backend; a Postgres port
#     ships as `migrations/postgres/*.sql` selected by the runner.

_NOW = "datetime('now')"  # PG: CURRENT_TIMESTAMP


def _older_than_cutoff(conn: sqlite3.Connection, days: int) -> str:
    """Return the fixed timestamp used by one age-based maintenance pass."""
    return str(conn.execute(
        "SELECT datetime('now', ?)", (f"-{int(days)} days",)
    ).fetchone()[0])


def _delete_older_than(conn: sqlite3.Connection, table: str,
                       column: str, days: int, *,
                       cutoff: str | None = None) -> int:
    """Delete rows from `table` where `column` is older than `days` days.

    The dialect-specific relative interval is resolved once by
    `_older_than_cutoff`; the fixed cutoff keeps checkpoint selection and
    deletion on exactly the same boundary.
    """
    cutoff = cutoff or _older_than_cutoff(conn, days)
    cur = conn.execute(
        f"DELETE FROM {table} WHERE {column} < ?", (cutoff,))
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
    # WAL permits one writer at a time, and this process always has several
    # (request threads, the heartbeat, the causal pump). The default busy
    # timeout is 0 — a second writer fails *immediately* with "database is
    # locked" instead of waiting its turn, and in the WS loop that error
    # tears down the player's connection. Five seconds absorbs essentially
    # all real single-host contention; the Postgres switchover trigger
    # (docs/roadmap/phase-2-scale.md) remains the answer if waits ever show
    # up in latency, but a trigger is not a defense.
    conn.execute("PRAGMA busy_timeout=5000")
    budget = getattr(_transaction_state, "agent_budget", None)
    if budget is not None:
        conn.set_progress_handler(budget["charge"], 1000)
    return conn


# Only explicitly composable persistence helpers use this connection scope.
# A delivery/acceptance transaction belongs to one synchronous request thread.
_transaction_state = threading.local()


@contextmanager
def agent_work_budget(limit: int = 2_000_000):
    """Bound SQL execution across a heartbeat's connections, including writes.

    World birth is a separate one-time initialization. The progress handler
    interrupts SQLite work, not lock waits or Python hydration; those bounds
    are stated separately. An interrupted acceptance transaction rolls back.
    """
    budget = {"steps": 0, "limit": limit}
    def charge():
        budget["steps"] += 1000
        return budget["steps"] >= limit
    budget["charge"] = charge
    _transaction_state.agent_budget = budget
    try:
        yield budget
    finally:
        del _transaction_state.agent_budget


@contextmanager
def _connection():
    current = getattr(_transaction_state, "connection", None)
    if current is not None:
        try:
            yield current
        except BaseException:
            _transaction_state.failed = True
            raise
    else:
        conn = _connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()


@contextmanager
def transaction():
    """Compose local DB work into one BEGIN IMMEDIATE / commit boundary.

    Nested calls join the transaction; no helper can commit it early. An
    exception (even if a caller catches it) dooms the outer transaction.
    Callers must keep external I/O and broadcasts outside this scope and
    discard request-local objects on failure. SQLite releases the claim
    and rolls back every write when a process dies before commit.
    """
    if _DB_PATH not in _initialized:
        init_db()
    if getattr(_transaction_state, "connection", None) is not None:
        with _connection() as conn:
            yield conn
        return
    conn = _connect()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            _transaction_state.connection = conn
            _transaction_state.failed = False
            yield conn
            if _transaction_state.failed:
                raise RuntimeError("nested database operation failed")
    finally:
        _transaction_state.connection = None
        conn.close()


def _begin_write(conn):
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")


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


def _sql_statements(sql: str) -> list[str]:
    """Split a migration file into individual statements.

    `executescript` runs each statement in autocommit, which is exactly
    what the runner must avoid (an interruption mid-file strands committed
    DDL without its schema_version marker). Splitting on complete
    statements lets the runner execute them inside ONE transaction.
    Comment-only fragments are dropped.
    """
    out: list[str] = []
    buf = ""
    for piece in sql.split(";"):
        buf += piece + ";"
        if sqlite3.complete_statement(buf):
            stmt, buf = buf.strip(), ""
            has_sql = any(line.strip() and not line.strip().startswith("--")
                          for line in stmt.rstrip(";").splitlines())
            if has_sql:
                out.append(stmt)
    return out


def _run_migrations(conn: sqlite3.Connection) -> list[int]:
    """Apply any migrations not yet recorded in `schema_version`.

    Returns the versions applied in this call (empty if up-to-date).
    Each migration's statements AND its schema_version marker commit in
    one transaction, so an interruption leaves the DB exactly at the last
    fully-applied version — never a half-applied file whose committed
    ALTERs make the retry fail with "duplicate column name".
    """
    conn.executescript(_SCHEMA_VERSION_DDL)
    applied = {r[0] for r in conn.execute("SELECT version FROM schema_version")}
    just_applied: list[int] = []
    for version, path in _list_migrations():
        if version in applied:
            continue
        sql = path.read_text()
        try:
            conn.execute("BEGIN IMMEDIATE")
            for stmt in _sql_statements(sql):
                conn.execute(stmt)
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
            _hash_legacy_credentials(conn)
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
    with _connection() as conn:
        conn.execute(
            """INSERT INTO puzzle_results (world_seed, puzzle_name, result, attempts)
               VALUES (?, ?, ?, ?)""",
            (world_seed, puzzle_name, result, attempts),
        )


# Queue ids are durable identities scoped by table; distinct requests retain
# distinct work even if their legacy absolute outcomes happen to be equal.
_DELIVERY_QUEUES = {"causal_queue", "verb_maturation"}


def _delivery_queue(queue: str) -> str:
    if queue not in _DELIVERY_QUEUES:
        raise ValueError("unknown delivery queue")
    return queue


@_with_db
def enqueue_causal_hop(world_seed: int, node_name: str, kind: str,
                       strength: float, direction: str, payload: dict,
                       delay_seconds: float, *, parent_id: int | None = None,
                       source_event_id: int | None = None) -> int:
    """Schedule a v1 hop, joining its origin or predecessor transaction."""
    with _connection() as conn:
        cur = conn.execute(
            """INSERT INTO causal_queue
               (world_seed, node_name, kind, strength, direction, payload,
                due_at, parent_id, source_event_id)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now', ?), ?, ?)""",
            (world_seed, node_name, kind, float(strength), direction,
             json.dumps(payload), f"+{int(delay_seconds)} seconds",
             parent_id, source_event_id))
        return cur.lastrowid


@_with_db
def enqueue_verb_maturation(world_seed: int, node_name: str, verb: str,
                            changed: dict, actor: str | None,
                            delay_seconds: float, *,
                            source_event_id: int | None = None,
                            operation: dict | None = None,
                            actor_identity: str | None = None) -> int:
    """Default to a v1 absolute patch; an explicit operation selects v2."""
    with _connection() as conn:
        cur = conn.execute(
            """INSERT INTO verb_maturation
               (world_seed, node_name, verb, changed, actor, due_at, source_event_id,
                semantics_version, operation, actor_identity)
               VALUES (?, ?, ?, ?, ?, datetime('now', ?), ?, ?, ?, ?)""",
            (world_seed, node_name, verb, json.dumps(changed), actor,
             f"+{int(delay_seconds)} seconds", source_event_id,
             1 if operation is None else 2,
             None if operation is None else json.dumps(operation), actor_identity))
        return cur.lastrowid


@_with_db
def pending_verb_work(world_seed: int, node_name: str, verb: str) -> list[dict]:
    """Read this verb's pending v2 work for the locked coalescing decision."""
    with _connection() as conn:
        cur = conn.execute(
            """SELECT * FROM verb_maturation WHERE world_seed = ? AND node_name = ?
                AND verb = ? AND status = 'pending' AND semantics_version = 2
                ORDER BY due_at, id""", (world_seed, node_name, verb))
        return [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]


@_with_db
def pending_verb_summaries(world_seed: int, node_name: str | None = None) -> dict[str, list[dict]]:
    """Public counts combine versions; durable work and its rules stay distinct."""
    where = "world_seed = ? AND status = 'pending'"
    params = [world_seed]
    if node_name is not None:
        where += " AND node_name = ?"
        params.append(node_name)
    with _connection() as conn:
        rows = conn.execute(
            f"""SELECT node_name, verb, COUNT(*), MIN(due_at)
                FROM verb_maturation WHERE {where}
                GROUP BY node_name, verb""", params).fetchall()
    result = {}
    for node, verb, count, due in rows:
        result.setdefault(node, []).append({"verb": verb, "count": count, "due_at": due})
    return result


@_with_db
def due_work(queue: str, limit: int, world_seed: int | None = None) -> list[int]:
    """Read bounded candidates, not claims. Delivery rechecks under the lock."""
    queue = _delivery_queue(queue)
    with _connection() as conn:
        return [r[0] for r in conn.execute(
            f"""SELECT id FROM {queue} WHERE status = 'pending'
                AND due_at <= datetime('now')
                AND (retry_at IS NULL OR retry_at <= datetime('now'))
                AND (? IS NULL OR world_seed = ?)
                ORDER BY due_at, id LIMIT ?""",
            (world_seed, world_seed, max(0, limit))).fetchall()]


@_with_db
def inspect_work(queue: str, work_id: int) -> dict | None:
    """Read the unchanged input, retries, linkage and terminal outcome."""
    queue = _delivery_queue(queue)
    with _connection() as conn:
        cur = conn.execute(f"SELECT * FROM {queue} WHERE id = ?", (work_id,))
        row = cur.fetchone()
        return dict(zip([c[0] for c in cur.description], row)) if row else None


@_with_db
def deliver_work(queue: str, work_id: int, apply: Callable[[dict], str], *,
                 prepare: Callable[[dict], None] | None = None) -> bool:
    """Claim, apply and complete one local effect in the SAME transaction.

    No committed in-progress state or lease is needed: SQLite's writer lock
    is the claim. Duplicate candidates recheck status after acquiring it.
    Exceptions roll back all writes and retain pending input with capped
    exponential retry delay (1..300s); no retry limit silently discards work.
    A process death before error recording also leaves the original pending
    row eligible. The callback must perform only bounded local DB work.
    """
    queue = _delivery_queue(queue)
    try:
        if prepare is not None:
            candidate = inspect_work(queue, work_id)
            if candidate is None or candidate["status"] != "pending":
                return False
            prepare(candidate)
        with transaction() as conn:
            row = inspect_work(queue, work_id)
            if row is None or row["status"] != "pending":
                return False
            eligible = conn.execute(
                f"""SELECT 1 FROM {queue} WHERE id = ?
                    AND due_at <= datetime('now')
                    AND (retry_at IS NULL OR retry_at <= datetime('now'))""",
                (work_id,)).fetchone()
            if not eligible:
                return False
            supported = (1, 2) if queue == "verb_maturation" else (1,)
            if row["semantics_version"] not in supported:
                raise ValueError("unsupported delivery semantics version")
            field = "payload" if queue == "causal_queue" else "changed"
            row[field] = json.loads(row[field]) if row[field] else {}
            if not isinstance(row[field], dict):
                raise ValueError(f"delivery {field} must be a JSON object")
            if row["semantics_version"] == 2:
                row["operation"] = json.loads(row["operation"])
            outcome = apply(row)
            conn.execute(
                f"""UPDATE {queue} SET status = 'completed', outcome = ?,
                    completed_at = datetime('now'), attempts = attempts + 1,
                    retry_at = NULL WHERE id = ?""", (outcome, work_id))
        return True
    except Exception as exc:
        # Outside the failed transaction. If another worker completed in
        # between, do not overwrite its terminal outcome with this failure.
        try:
            with transaction() as conn:
                conn.execute(
                    f"""UPDATE {queue} SET attempts = attempts + 1, last_error = ?,
                        retry_at = datetime('now', '+' ||
                            min(300, (1 << min(attempts, 9))) || ' seconds')
                        WHERE id = ? AND status = 'pending'""",
                    (f"{type(exc).__name__}: {exc}"[:2000], work_id))
        except Exception:
            # Storage trouble can also prevent diagnostics/backoff. The
            # original input is still pending; keep trying the other items.
            _log.exception("could not record delivery failure: %s:%s", queue, work_id)
        _log.exception("delivery failed: %s:%s; retained for retry", queue, work_id)
        return False


@_with_db
def retry_work(queue: str, work_id: int) -> bool:
    """Operator retry after inspection/repair; never resets a completed item."""
    queue = _delivery_queue(queue)
    with _connection() as conn:
        return conn.execute(
            f"UPDATE {queue} SET retry_at = NULL WHERE id = ? AND status = 'pending'",
            (work_id,)).rowcount == 1


@_with_db
def latest_event_id(mutation_type: str | None = None) -> int:
    """Link new work to the origin just written in the caller's transaction."""
    # BEGIN IMMEDIATE excludes other writers, and the origin writers always
    # append a row even when their material delta is empty.
    if getattr(_transaction_state, "connection", None) is None:
        raise RuntimeError("origin linkage requires a transaction")
    with _connection() as conn:
        return conn.execute(
            "SELECT MAX(id) FROM world_mutations WHERE ? IS NULL OR mutation_type = ?",
            (mutation_type, mutation_type)).fetchone()[0]


@_with_db
def _pending_work(queue: str, world_seed: int | None) -> int:
    queue = _delivery_queue(queue)
    with _connection() as conn:
        return conn.execute(
            f"""SELECT COUNT(*) FROM {queue} WHERE status = 'pending'
                AND (? IS NULL OR world_seed = ?)""",
            (world_seed, world_seed)).fetchone()[0]


def pending_verb_maturations(world_seed: int | None = None) -> int:
    return _pending_work("verb_maturation", world_seed)


def pending_causal_hops(world_seed: int | None = None) -> int:
    return _pending_work("causal_queue", world_seed)


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
    with _connection() as conn:
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
def get_node_history(world_seed: int, node_name: str, limit: int = 10, *,
                     include_narration: bool = True) -> list[dict[str, Any]]:
    """Recent rows; count/style consumers can omit provenance and prose."""
    from persistence.history import FIELDS, decode, project
    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT {FIELDS}
               FROM world_mutations WHERE world_seed = ? AND node_name = ?
               ORDER BY recorded_at DESC, id DESC LIMIT ?""",
            (world_seed, node_name, max(1, min(int(limit), 1000))),
        ).fetchall()
        entries = [decode(r) for r in rows]
        return project(conn, world_seed, entries) if include_narration else entries


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
                    actor_identity: str | None = None,
                    strength: float | None = None) -> None:
    """Append one chronicle row.

    `player_name` is the mutable display label; `actor_identity` is the
    durable key for WHO — the credential hash (sha256(key)[:16]) when the
    request carried a per-user invite key, else the display name, else
    None. Callers on human paths should always pass it.

    `strength` is the traced causal event's strength (ADR-009). A row that
    is a fired event's chronicle trace must carry it — including the
    producer-attributed origin rows on record=False buses, which are their
    event's only trace — and every other row must leave it None: ripple is
    rebuilt as a fold over exactly the strength-bearing rows, so a fired
    event must carry strength on exactly one row.
    """
    with _connection() as conn:
        conn.execute(
            """INSERT INTO world_mutations
               (world_seed, node_name, mutation_type, player_name, data,
                actor_identity, strength)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (world_seed, node_name, mutation_type, player_name,
             json.dumps(data), actor_identity,
             None if strength is None else float(strength)),
        )


@_with_db
def get_mutations(world_seed: int, limit: int = 50) -> list[dict[str, Any]]:
    from persistence.history import FIELDS, decode, project
    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT {FIELDS}
               FROM world_mutations WHERE world_seed = ?
               ORDER BY recorded_at DESC, id DESC LIMIT ?""",
            (world_seed, max(1, min(int(limit), 1000))),
        ).fetchall()
        return project(conn, world_seed, [decode(r) for r in rows])


@_with_db
def presented_mutations(world_seed: int, event_ids: list[int]) -> list[dict]:
    """Read committed events for a bounded live notification batch."""
    from persistence.history import FIELDS, decode, positive_id, project
    ids = list(dict.fromkeys(i for i in event_ids if positive_id(i)))[:200]
    if not ids:
        return []
    with _connect() as conn:
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT {FIELDS} FROM world_mutations WHERE world_seed=? "
            f"AND id IN ({placeholders}) ORDER BY id", (world_seed, *ids)).fetchall()
        return project(conn, world_seed, [decode(r) for r in rows])


# ── Redaction: the sanctioned exception to append-only ─────────────────────
# The chronicle is permanent, but permanence needs an escape hatch for
# abuse: a slur cut into a room, doxxing in chat, a poisoned puzzle guess.
# Redaction is CONTENT-level, never row-level — the event, its node, its
# type, its timestamp, and its durable actor_identity all survive (the
# world still remembers that something happened and who did it); only the
# human-authored words are tombstoned. Mechanical fields (puzzle names,
# correct flags, verbs) are preserved so co-op counter rehydration and
# renewal epochs are untouched. See the runbook's "Redaction" section for
# the operator procedure.

_REDACTABLE_FIELDS = ("message", "reply", "text", "guess", "answer_given")
_REDACTED = "[redacted]"


@_with_db
def find_mutations_by_text(needle: str, world_seed: int | None = None,
                           limit: int = 20) -> list[dict[str, Any]]:
    """Locate chronicle rows whose content or display name contains
    `needle` (case-insensitive substring) — the operator's search step
    before redacting. Newest first, ids included for redact_mutation."""
    where = "(data LIKE '%' || ? || '%' OR player_name LIKE '%' || ? || '%')"
    args: list[Any] = [needle, needle]
    if world_seed is not None:
        where += " AND world_seed = ?"
        args.append(world_seed)
    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT id, world_seed, node_name, mutation_type,
                       player_name, data, recorded_at
                FROM world_mutations WHERE {where}
                ORDER BY id DESC LIMIT ?""",
            (*args, limit),
        ).fetchall()
    return [{"id": r[0], "seed": r[1], "node": r[2], "type": r[3],
             "player": r[4], "data": json.loads(r[5]) if r[5] else {},
             "at": r[6]} for r in rows]


@_with_db
def redact_mutation(mutation_id: int, scrub_name: bool = False,
                    reason: str | None = None) -> dict[str, Any] | None:
    """Tombstone the human-authored content of one chronicle row.

    Replaces the free-text fields in `data` with "[redacted]" and stamps
    redacted/redacted_at (+ an optional short operator reason). With
    `scrub_name`, also nulls the display name (for names that are
    themselves the abuse) — actor_identity is deliberately kept, so
    accountability survives the cleanup. Idempotent. Returns a summary of
    what changed, or None if no row has that id.
    """
    with _connect() as conn:
        row = conn.execute(
            """SELECT world_seed, node_name, mutation_type, player_name,
                      data FROM world_mutations WHERE id = ?""",
            (mutation_id,),
        ).fetchone()
        if row is None:
            return None
        data = json.loads(row[4]) if row[4] else {}
        fields = [f for f in _REDACTABLE_FIELDS
                  if f in data and data[f] != _REDACTED]
        for f in fields:
            data[f] = _REDACTED
        data["redacted"] = True
        data.setdefault(
            "redacted_at",
            conn.execute(f"SELECT {_NOW}").fetchone()[0])
        if reason:
            data["redacted_reason"] = str(reason)[:80]
        name_scrubbed = scrub_name and row[3] is not None
        if name_scrubbed:
            conn.execute(
                """UPDATE world_mutations SET data = ?, player_name = NULL
                   WHERE id = ?""",
                (json.dumps(data), mutation_id))
        else:
            conn.execute(
                "UPDATE world_mutations SET data = ? WHERE id = ?",
                (json.dumps(data), mutation_id))
    return {"id": mutation_id, "seed": row[0], "node": row[1],
            "type": row[2], "fields": fields,
            "name_scrubbed": bool(name_scrubbed)}


@_with_db
def count_node_mutations(world_seed: int, node_name: str,
                         mutation_type: str) -> int:
    """How many events of one type this node has accumulated."""
    with _connection() as conn:
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
    with _connection() as conn:
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
    from persistence.history import FIELDS, decode, project
    limit = max(1, min(int(limit), 200))
    with _connect() as conn:
        if before_id is not None:
            rows = conn.execute(
                f"""SELECT {FIELDS}, actor_identity
                   FROM world_mutations WHERE world_seed = ? AND id < ?
                   ORDER BY id DESC LIMIT ?""",
                (world_seed, before_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""SELECT {FIELDS}, actor_identity
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
        entries = project(conn, world_seed, [dict(decode(r), actor=r[8]) for r in rows])
    exhausted = len(rows) < limit
    return {
        "entries": entries,
        "next_before": None if exhausted else entries[-1]["id"],
        "total": total,
        "began": began,
    }


@_with_db
def count_mutations_by_node(world_seed: int, node_name: str | None = None) -> dict[str, int]:
    """Recorded interactions per node — the world's lived history, in counts.
    Feeds the per-node generative art (trace etchings) via /world."""
    where = "world_seed = ?"
    params = [world_seed]
    if node_name is not None:
        where += " AND node_name = ?"
        params.append(node_name)
    with _connection() as conn:
        rows = conn.execute(
            f"SELECT node_name, COUNT(*) FROM world_mutations WHERE {where} GROUP BY node_name",
            params,
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
    with _connection() as conn:
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
    with _connection() as conn:
        row = conn.execute(
            """SELECT visited_ids, log_entries, updated_at, scan_cursor
               FROM agent_memory WHERE agent_name = ? AND world_seed = ?""",
            (agent_name, world_seed),
        ).fetchone()
        if row is None:
            return None
        return {
            "visited_ids": json.loads(row[0]),
            "log_entries": json.loads(row[1]),
            "updated_at":  row[2],
            "scan_cursor": row[3],
        }


@_with_db
def save_agent_scan_cursor(agent_name: str, world_seed: int, cursor: str) -> None:
    with _connection() as conn:
        conn.execute("""INSERT INTO agent_memory (agent_name, world_seed, scan_cursor)
                        VALUES (?, ?, ?) ON CONFLICT(agent_name, world_seed)
                        DO UPDATE SET scan_cursor=excluded.scan_cursor""",
                     (agent_name, world_seed, cursor))


@_with_db
def load_agent_attention(agent_name: str, world_seed: int,
                         names: list[str]) -> dict[str, dict]:
    if not names:
        return {}
    with _connection() as conn:
        rows = conn.execute(f"""SELECT node_name, change_id, puzzle_epoch
            FROM agent_attention WHERE world_seed=? AND agent_name=?
            AND node_name IN ({','.join('?' for _ in names)})""",
            (world_seed, agent_name, *names)).fetchall()
    return {name: {"change": change, "puzzle": epoch} for name, change, epoch in rows}


@_with_db
def mark_agent_attention(agent_name: str, world_seed: int, node_name: str, *,
                         change: int = -1, puzzle: int = -1) -> None:
    """Consume only the attempted opportunity, in its acceptance transaction."""
    with _connection() as conn:
        conn.execute("""INSERT INTO agent_attention
            (world_seed, agent_name, node_name, change_id, puzzle_epoch)
            VALUES (?, ?, ?, ?, ?) ON CONFLICT(world_seed, agent_name, node_name)
            DO UPDATE SET change_id=MAX(change_id, excluded.change_id),
                          puzzle_epoch=MAX(puzzle_epoch, excluded.puzzle_epoch)""",
            (world_seed, agent_name, node_name, change, puzzle))


class AttentionReadLimit(RuntimeError):
    """History has exceeded one bounded attention projection's SQL budget."""


@_with_db
def recent_attention_nodes(world_seed: int, agent_name: str) -> list[str]:
    """Bounded candidates for the recent-change priority lane.

    Renewal rows are only candidates: heartbeat checks the current epoch,
    consumed marker, persona and live accessibility before assigning slots.
    Read only the latest 64 material/rearm rows using the partial index. This
    is a latency aid, not a complete change queue; fair scanning covers events
    displaced by a busy world. Unknown maturation provenance is not external.
    """
    with _connection() as conn:
        rows = conn.execute("""WITH recent AS (
            SELECT * FROM world_mutations WHERE world_seed=?
              AND (delta IS NOT NULL OR mutation_type='PUZZLE_REARM')
            ORDER BY id DESC LIMIT 64)
            SELECT m.node_name FROM recent m
            LEFT JOIN agent_attention a ON a.world_seed=m.world_seed
              AND a.agent_name=? AND a.node_name=m.node_name
            LEFT JOIN verb_maturation q ON m.mutation_type='SCALE_ACT_MATURED'
              AND json_extract(m.data,'$.delivery.queue')='verb_maturation'
              AND q.id=json_extract(m.data,'$.delivery.id')
              AND q.world_seed=m.world_seed AND q.node_name=m.node_name
              AND q.verb=json_extract(m.data,'$.verb')
            LEFT JOIN world_mutations s ON s.id=q.source_event_id
              AND s.world_seed=m.world_seed AND s.node_name=m.node_name
              AND s.mutation_type='SCALE_ACT' AND s.id<m.id
              AND json_extract(s.data,'$.verb')=q.verb
            WHERE m.mutation_type='PUZZLE_REARM' OR
              (m.id>COALESCE(a.change_id,-1) AND
               CASE WHEN m.mutation_type='SCALE_ACT_MATURED'
                    THEN s.id IS NOT NULL AND json_extract(s.data,'$.agent') IS NULL
                    ELSE json_extract(m.data,'$.agent') IS NULL END)
            ORDER BY m.id DESC""", (world_seed, agent_name)).fetchall()
    return list(dict.fromkeys(row[0] for row in rows))


ATTENTION_SQL_STEPS = 200_000


@_with_db
def agent_attention_signals(world_seed: int, names: list[str], *,
                            seals: bool = False) -> dict[str, dict]:
    """Bounded batch projection of current epochs and external material change.

    Agent payloads identify autonomy, never public labels. Maturation requires
    a matching retained delivery and source, including legacy v1 work. Unknown
    provenance does not manufacture a new external opportunity. Range reads
    use the existing (world_seed, node_name) index; a VM budget also bounds
    historical scanning, not merely the number of returned rows/statements.
    """
    names = list(dict.fromkeys(names))
    if len(names) > 550:
        raise ValueError("attention projection exceeds candidate/ancestor bound")
    if not names:
        return {}
    signals = {name: {"epoch": 0, "change": 0, "solved": set()} for name in names}
    marks = ','.join('?' for _ in names)
    with _connection() as conn:
        steps = 0
        def budget():
            nonlocal steps
            steps += 1000
            total = getattr(_transaction_state, 'agent_budget', None)
            exhausted = total['charge']() if total is not None else False
            return exhausted or steps >= ATTENTION_SQL_STEPS
        conn.set_progress_handler(budget, 1000)
        try:
            rows = conn.execute(f"""
                SELECT m.node_name,
                  SUM(m.mutation_type='PUZZLE_REARM'),
                  MAX(CASE WHEN m.delta IS NOT NULL AND
                    CASE WHEN m.mutation_type='SCALE_ACT_MATURED'
                         THEN s.id IS NOT NULL AND json_extract(s.data, '$.agent') IS NULL
                         ELSE json_extract(m.data, '$.agent') IS NULL END
                    THEN m.id ELSE 0 END)
                FROM world_mutations m
                LEFT JOIN verb_maturation q ON m.mutation_type='SCALE_ACT_MATURED'
                  AND json_extract(m.data, '$.delivery.queue')='verb_maturation'
                  AND q.id=json_extract(m.data, '$.delivery.id')
                  AND q.world_seed=m.world_seed AND q.node_name=m.node_name
                  AND q.verb=json_extract(m.data, '$.verb')
                LEFT JOIN world_mutations s ON s.id=q.source_event_id
                  AND s.world_seed=m.world_seed AND s.node_name=m.node_name
                  AND s.mutation_type='SCALE_ACT' AND s.id<m.id
                  AND json_extract(s.data, '$.verb')=q.verb
                WHERE m.world_seed=? AND m.node_name IN ({marks})
                  AND (m.delta IS NOT NULL OR m.mutation_type='PUZZLE_REARM')
                GROUP BY m.node_name""", (world_seed, *names)).fetchall()
            for name, epoch, change in rows:
                signals[name].update(epoch=epoch, change=change)
            if seals:
                # Match get_puzzle_solve's latest-20 evidence window, in one
                # batch. A cast solve can never open entry into a locked room.
                rows = conn.execute(f"""SELECT node_name, data FROM (
                    SELECT node_name, data, ROW_NUMBER() OVER (
                        PARTITION BY node_name ORDER BY recorded_at DESC, id DESC) AS rn
                    FROM world_mutations WHERE world_seed=? AND node_name IN ({marks})
                      AND mutation_type='PUZZLE_SOLVED') WHERE rn<=20""",
                    (world_seed, *names)).fetchall()
                for name, blob in rows:
                    data = json.loads(blob or '{}')
                    if isinstance(data, dict) and not data.get('agent'):
                        puzzle = data.get('puzzle')
                        if isinstance(puzzle, str):
                            signals[name]['solved'].add(puzzle)
        except sqlite3.OperationalError as exc:
            if str(exc) == 'interrupted':
                raise AttentionReadLimit('attention history budget exhausted') from exc
            raise
        finally:
            total = getattr(_transaction_state, 'agent_budget', None)
            conn.set_progress_handler(total['charge'] if total else None, 1000)
    return signals


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
    with _connection() as conn:
        conn.execute(
            f"""INSERT INTO node_runtime_state (world_seed, node_name, ripple_score, updated_at, created_at)
               VALUES (?, ?, ?, {_NOW}, {_NOW})
               ON CONFLICT(world_seed, node_name) DO UPDATE SET
                 ripple_score = MIN(1.0, ripple_score + excluded.ripple_score),
                 updated_at   = excluded.updated_at""",
            (world_seed, node_name, min(1.0, float(delta))),
        )


# ── Chronicled deltas (ADR-009): the one atomic substance-write API ────────
# Every write that materially changes a node's substance chronicles its
# delta at write time, in the same transaction that applies it. The overlay
# writer below is module-internal: record_substance_change is the only door
# to node properties, so future compliance is structural, not a checklist.

# The live ripple increment adds strength × this per fired event (matching
# the in-memory accumulation in CausalityBus._fire); rebuild_ripple_scores
# folds chronicled strengths through the same constant.
# causality.wiring re-exports it for the bus handlers.
RIPPLE_INCREMENT_PER_STRENGTH = 0.1

# Cache rows written before Wayback were bare merge-patch documents. They stay
# that way so a rollback binary can continue to hydrate them. The additive
# node_property_cache_meta table carries the format marker, an exact copy of
# the marked blob (so writes by a rollback binary invalidate the marker), and
# the marked chronicle head (for tombstones that leave the blob unchanged),
# plus pre-chronicle state that cannot be recovered from world_mutations.
_PROPERTY_CACHE_FORMAT = 1


def _apply_overlay_patch(conn: sqlite3.Connection, world_seed: int,
                         node_name: str, changed: dict, *,
                         cached_overlay: dict | None = None) -> None:
    """Apply `changed` to the node's persisted property cache, on an
    already-open connection — always inside record_substance_change's
    transaction, never on its own.

    The overlay is applied on top of deterministic generation at every world
    rebuild (`load_node_property_overrides` + `apply_property_overrides`), so
    a causal event's material consequence outlives the request that fired it.
    RFC 7396 patch documents are not closed under target-independent
    composition: deleting an object and then adding one nested key must not
    resurrect siblings from the immutable born row. The chronicle is the
    record. Current-format caches materialize the previous effective state in
    O(1), apply this delta once, then derive one exact born-relative patch.
    Only a legacy or missing cache pays for a full chronicle replay; that path
    also repairs tombstones an older cache writer may have discarded.
    """
    if cached_overlay is None:
        cached, current_format, _baseline = _property_cache_snapshot(
            conn, world_seed, node_name)
    else:
        # The atomic writer prepared this exact cache under the same lock
        # immediately before appending the delta.
        cached, current_format = cached_overlay, True
    if current_format:
        born = _load_born_properties(conn, world_seed, node_name)
        current_state = json_merge_patch(born, cached)
        next_state = json_merge_patch(current_state, changed)
        rebuilt = json_merge_diff(born, next_state)
        if not isinstance(rebuilt, dict):  # property roots stay objects
            rebuilt = {}
    else:
        # Defensive fallback for callers outside the atomic writer: the
        # canonical stream already contains `changed`, so repair includes it.
        rebuilt = _prepare_property_cache(conn, world_seed, node_name)
    _store_property_overlay(conn, world_seed, node_name, rebuilt)


def _insert_substance_row(conn: sqlite3.Connection, world_seed: int,
                          node_name: str, mutation_type: str,
                          player_name: str | None, data: dict, delta: dict,
                          strength: float | None,
                          actor_identity: str | None) -> int:
    """The atomic core, on an already-locked connection: allocate the
    per-node version, append the delta-bearing chronicle row, apply the
    overlay patch. Returns the allocated version."""
    # Upgrade a legacy cache before appending. Otherwise a replay after the
    # insert has no source for cache-only, pre-chronicle fields.
    cached_overlay = _prepare_property_cache(conn, world_seed, node_name)
    version = _property_delta_head(conn, world_seed, node_name) + 1
    conn.execute(
        """INSERT INTO world_mutations
           (world_seed, node_name, mutation_type, player_name, data,
            actor_identity, strength, delta, node_version)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (world_seed, node_name, mutation_type, player_name,
         json.dumps(data), actor_identity,
         None if strength is None else float(strength),
         json.dumps(delta), version),
    )
    _apply_overlay_patch(
        conn, world_seed, node_name, delta,
        cached_overlay=cached_overlay)
    return version


@_with_db
def record_substance_change(world_seed: int, node_name: str,
                            mutation_type: str, player_name: str | None,
                            data: dict, delta: dict, *,
                            strength: float | None = None,
                            actor_identity: str | None = None) -> int:
    """Chronicle a substance change and apply it — one transaction (ADR-009).

    For deltas that are ABSOLUTE facts (a planted maturation landing, a
    constellation lighting): appends the chronicle row (the merge patch in
    `delta`, the triggering event's kind as `mutation_type`, and its
    `strength` when this row is the event's strength-bearing trace),
    applies the same patch to the node_runtime_state overlay, and allocates
    the per-node monotonic `node_version` that defines the fold order.
    A crash mid-write leaves neither half; concurrent writers on one node
    serialize into distinct versions. Returns the allocated version.

    Deltas that are TRANSITIONS of current state (danger rises by one,
    the inscription count increments) must use
    `record_substance_transition` instead, which recomputes the delta
    under the serialization lock — a transition computed from a
    request-local snapshot chronicles a stale change when writers race.
    """
    if not delta:
        raise ValueError("record_substance_change requires a non-empty delta")
    with _connection() as conn:
        # Take the write lock before reading MAX(node_version): a deferred
        # transaction would let two writers allocate the same version from
        # the same read snapshot and fail non-retryably on upgrade.
        _begin_write(conn)
        return _insert_substance_row(
            conn, world_seed, node_name, mutation_type, player_name, data,
            delta, strength, actor_identity)


@_with_db
def record_substance_transition(world_seed: int, node_name: str,
                                mutation_type: str, player_name: str | None,
                                data: dict,
                                compute: Callable[[dict], dict | None], *,
                                strength: float | None = None,
                                actor_identity: str | None = None
                                ) -> dict | None:
    """Chronicle an event whose material delta depends on current state.

    Holds the write lock, reads the node's LIVE overlay, and calls
    `compute(live_overlay) -> delta | None` — so the transition is derived
    from the state it will actually apply to, never from a request-local
    snapshot that a concurrent writer may have outrun (two danger alerts
    from danger 5 land 6 then 7, not 6 twice). The event row is appended
    either way (a fired event always chronicles); when `compute` yields a
    delta the same row carries it (+ node_version) and the overlay change
    commits in the same transaction. `compute` must be pure and fast — it
    runs inside the transaction and must not touch the database. Returns
    the applied delta, or None when the event had no material consequence
    against live state.
    """
    with _connection() as conn:
        _begin_write(conn)
        live_overlay = _current_property_overlay(
            conn, world_seed, node_name, repair=True)
        delta = compute(live_overlay)
        if delta:
            _insert_substance_row(
                conn, world_seed, node_name, mutation_type, player_name,
                data, delta, strength, actor_identity)
            return delta
        conn.execute(
            """INSERT INTO world_mutations
               (world_seed, node_name, mutation_type, player_name, data,
                actor_identity, strength)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (world_seed, node_name, mutation_type, player_name,
             json.dumps(data), actor_identity,
             None if strength is None else float(strength)),
        )
        return None


def json_merge_diff(source: Any, target: Any) -> Any:
    """Return an RFC 7396 patch that transforms ``source`` into ``target``.

    The persisted overlay cache is always relative to a node's immutable born
    properties. Deriving it from the fully folded state avoids the impossible
    task of composing arbitrary merge-patch documents without their target.
    """
    if _json_equal(source, target):
        return {}
    if not isinstance(source, dict) or not isinstance(target, dict):
        return target

    patch: dict[str, Any] = {
        key: None for key in source.keys() - target.keys()
    }
    for key, value in target.items():
        if key not in source:
            patch[key] = value
        elif not _json_equal(source[key], value):
            patch[key] = json_merge_diff(source[key], value)
    return patch


def _json_equal(left: Any, right: Any) -> bool:
    """Compare JSON values without Python's bool/number coercion."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return (left.keys() == right.keys()
                and all(_json_equal(value, right[key])
                        for key, value in left.items()))
    if isinstance(left, list):
        return (len(left) == len(right)
                and all(_json_equal(a, b) for a, b in zip(left, right)))
    return left == right


def _rebuild_property_overlay(conn: sqlite3.Connection, world_seed: int,
                              node_name: str,
                              legacy_baseline: dict | None = None) -> dict:
    """Fold canonical history and return the exact born-relative cache patch."""

    born = _load_born_properties(conn, world_seed, node_name)
    state: Any = json_merge_patch(born, legacy_baseline or {})
    rows = conn.execute(
        """SELECT delta FROM world_mutations
           WHERE world_seed = ? AND node_name = ? AND delta IS NOT NULL
           ORDER BY node_version""",
        (world_seed, node_name),
    ).fetchall()
    for (blob,) in rows:
        state = json_merge_patch(state, json.loads(blob))
    if not isinstance(state, dict):
        state = {}
    rebuilt = json_merge_diff(born, state)
    return rebuilt if isinstance(rebuilt, dict) else {}


def _load_born_properties(conn: sqlite3.Connection, world_seed: int,
                          node_name: str) -> dict:
    """Load one immutable born property object; synthetic test nodes use {}."""
    born_row = conn.execute(
        """SELECT properties FROM world_nodes
           WHERE world_seed = ? AND name = ?""",
        (world_seed, node_name),
    ).fetchone()
    value = json.loads(born_row[0]) if born_row and born_row[0] else {}
    return value if isinstance(value, dict) else {}


def _store_property_overlay(conn: sqlite3.Connection, world_seed: int,
                            node_name: str, overlay: dict, *,
                            legacy_baseline: dict | None = None) -> None:
    """Write one rollback-readable cache and its validation metadata."""
    blob = json.dumps(overlay)
    delta_version = _property_delta_head(conn, world_seed, node_name)
    conn.execute(
        f"""INSERT INTO node_runtime_state
            (world_seed, node_name, ripple_score, properties, updated_at, created_at)
           VALUES (?, ?, 0.0, ?, {_NOW}, {_NOW})
           ON CONFLICT(world_seed, node_name) DO UPDATE SET
             properties = excluded.properties,
             updated_at = excluded.updated_at""",
        (world_seed, node_name, blob),
    )
    baseline_blob = json.dumps(legacy_baseline or {})
    if legacy_baseline is None:
        conn.execute(
            f"""INSERT INTO node_property_cache_meta
                (world_seed, node_name, cache_format, properties_blob,
                 delta_version, legacy_baseline, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, {_NOW})
               ON CONFLICT(world_seed, node_name) DO UPDATE SET
                 cache_format = excluded.cache_format,
                 properties_blob = excluded.properties_blob,
                 delta_version = excluded.delta_version,
                 updated_at = excluded.updated_at""",
            (world_seed, node_name, _PROPERTY_CACHE_FORMAT, blob,
             delta_version,
             baseline_blob),
        )
    else:
        conn.execute(
            f"""INSERT INTO node_property_cache_meta
                (world_seed, node_name, cache_format, properties_blob,
                 delta_version, legacy_baseline, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, {_NOW})
               ON CONFLICT(world_seed, node_name) DO UPDATE SET
                 cache_format = excluded.cache_format,
                 properties_blob = excluded.properties_blob,
                 delta_version = excluded.delta_version,
                 legacy_baseline = excluded.legacy_baseline,
                 updated_at = excluded.updated_at""",
            (world_seed, node_name, _PROPERTY_CACHE_FORMAT, blob,
             delta_version,
             baseline_blob),
        )


def _property_delta_head(conn: sqlite3.Connection, world_seed: int,
                         node_name: str) -> int:
    """Latest allocated material version, including a pruned checkpoint."""
    return int(conn.execute(
        """SELECT MAX(
               COALESCE((
                   SELECT MAX(node_version) FROM world_mutations
                   WHERE world_seed = ? AND node_name = ?
                     AND delta IS NOT NULL
               ), 0),
               COALESCE((
                   SELECT delta_version FROM node_property_cache_meta
                   WHERE world_seed = ? AND node_name = ?
               ), 0)
           )""",
        (world_seed, node_name, world_seed, node_name),
    ).fetchone()[0])


def _decode_property_blob(blob: str | None) -> tuple[dict, bool]:
    """Return a patch and whether its persisted representation is a dict."""
    if not blob:
        return {}, True
    value = json.loads(blob)
    if isinstance(value, dict):
        return value, True
    # Development builds before the rollback-safe metadata table briefly
    # wrote [format, patch]. Read and repair those rows, but never write one.
    if (isinstance(value, list) and len(value) == 2
            and value[0] == _PROPERTY_CACHE_FORMAT
            and isinstance(value[1], dict)):
        return value[1], False
    return {}, False


def _property_cache_values(
        blob: str | None, cache_format: int | None,
        marked_blob: str | None, marked_version: int | None,
        delta_version: int,
        baseline_blob: str | None) -> tuple[dict, bool, dict]:
    """Decode one joined cache row and validate its side-table marker."""
    cached, plain_object = _decode_property_blob(blob)
    current_format = (
        plain_object
        and cache_format == _PROPERTY_CACHE_FORMAT
        and marked_blob == blob
        and marked_version == delta_version
    )
    if baseline_blob:
        baseline, baseline_is_object = _decode_property_blob(baseline_blob)
        if not baseline_is_object:
            baseline = {}
    else:
        # With no marker this is the last observable pre-chronicle state.
        baseline = cached
    return cached, current_format, baseline


def _property_cache_snapshot(conn: sqlite3.Connection, world_seed: int,
                             node_name: str) -> tuple[dict, bool, dict]:
    row = conn.execute(
        """SELECT state.properties, meta.cache_format,
                  meta.properties_blob, meta.delta_version,
                  MAX(COALESCE((
                      SELECT MAX(mutation.node_version)
                      FROM world_mutations AS mutation
                      WHERE mutation.world_seed = state.world_seed
                        AND mutation.node_name = state.node_name
                        AND mutation.delta IS NOT NULL
                  ), 0), COALESCE(meta.delta_version, 0)),
                  meta.legacy_baseline
           FROM node_runtime_state AS state
           LEFT JOIN node_property_cache_meta AS meta
             ON meta.world_seed = state.world_seed
            AND meta.node_name = state.node_name
           WHERE state.world_seed = ? AND state.node_name = ?""",
        (world_seed, node_name),
    ).fetchone()
    return _property_cache_values(
        *(row or (None, None, None, None, 0, None)))


def _prepare_property_cache(conn: sqlite3.Connection, world_seed: int,
                            node_name: str) -> dict:
    """Upgrade or repair one cache while the caller holds a write lock."""
    cached, current_format, baseline = _property_cache_snapshot(
        conn, world_seed, node_name)
    if current_format:
        return cached
    rebuilt = _rebuild_property_overlay(
        conn, world_seed, node_name, baseline)
    _store_property_overlay(
        conn, world_seed, node_name, rebuilt,
        legacy_baseline=baseline)
    return rebuilt


def _current_property_overlay(conn: sqlite3.Connection, world_seed: int,
                              node_name: str, *, repair: bool) -> dict:
    """Read a cache, rebuilding it when canonical deltas exist.

    Read-only callers leave cache-only legacy rows untouched. A writer asking
    for repair first captures that row as the pre-chronicle baseline. Once a
    node has canonical deltas, baseline + born + chronicle repairs historical
    tombstone loss and future cache drift.
    """
    cached, current_format, baseline = _property_cache_snapshot(
        conn, world_seed, node_name)
    if current_format:
        return cached
    has_deltas = conn.execute(
        """SELECT 1 FROM world_mutations
           WHERE world_seed = ? AND node_name = ? AND delta IS NOT NULL
           LIMIT 1""",
        (world_seed, node_name),
    ).fetchone()
    if repair:
        return _prepare_property_cache(conn, world_seed, node_name)
    if not has_deltas:
        return cached
    return _rebuild_property_overlay(conn, world_seed, node_name, baseline)


@_with_db
def fold_node_properties(world_seed: int, node_name: str,
                         upto_version: int | None = None) -> dict:
    """The node's overlay at a point in its history, folded from the record.

    State-at-T is the born row (world_nodes, immutable) plus this fold:
    every chronicled delta for the node, merged in per-node version order,
    up to and including `upto_version` (None folds everything — which must
    equal the live overlay). recorded_at is second-precision and cannot
    order non-commutative patches sharing a timestamp, so the version is
    the cursor; the wayback surface (batch 4) resolves a wall-clock T to
    the greatest version recorded at or before it, then calls this.
    """
    with _connect() as conn:
        born = _load_born_properties(conn, world_seed, node_name)
        _cached, _current, baseline = _property_cache_snapshot(
            conn, world_seed, node_name)
        if upto_version is None:
            rows = conn.execute(
                """SELECT delta FROM world_mutations
                   WHERE world_seed = ? AND node_name = ?
                     AND delta IS NOT NULL
                   ORDER BY node_version""",
                (world_seed, node_name),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT delta FROM world_mutations
                   WHERE world_seed = ? AND node_name = ?
                     AND delta IS NOT NULL AND node_version <= ?
                   ORDER BY node_version""",
                (world_seed, node_name, upto_version),
            ).fetchall()
    # Step/version zero remains born. A captured legacy baseline is
    # pre-chronicle state and participates once the fold advances.
    state: Any = dict(born)
    if upto_version is None or upto_version > 0:
        state = json_merge_patch(state, baseline)
    for (blob,) in rows:
        state = json_merge_patch(state, json.loads(blob))
    if not isinstance(state, dict):
        state = {}
    overlay = json_merge_diff(born, state)
    return overlay if isinstance(overlay, dict) else {}


@_with_db
def get_substance_deltas(world_seed: int,
                         node_name: str) -> list[dict[str, Any]]:
    """The node's chronicled delta rows in fold order — the change stream
    the fold and the invariant tests read."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT node_version, mutation_type, delta, strength,
                      recorded_at
               FROM world_mutations
               WHERE world_seed = ? AND node_name = ? AND delta IS NOT NULL
               ORDER BY node_version""",
            (world_seed, node_name),
        ).fetchall()
    return [{"version": r[0], "type": r[1], "delta": json.loads(r[2]),
             "strength": r[3], "at": r[4]} for r in rows]


@_with_db
def get_wayback_state(world_seed: int, node_name: str,
                      born_properties: dict[str, Any],
                      at_step: int | None = None) -> dict[str, Any]:
    """Reconstruct one node immediately after its Nth chronicled interaction.

    ``at_step`` is a node-local event ordinal: 0 is the immutable born state,
    N is immediately after the node's Nth ``world_mutations`` row, and None is
    the latest step. The selected row id is the exact cross-table cursor;
    timestamps are labels only because they have second precision. Material
    deltas still fold in their per-node ``node_version`` order (ADR-009).

    The fold begins with ``born_properties`` rather than an empty overlay so a
    stored RFC 7396 null can remove a property that existed at birth. Ripple
    and activity are derived through the same cursor. The returned moment is
    deliberately actor-blind: the wayback surface shows a birth, trace,
    ripple, or mechanical change — never a human/agent classification.

    This function is read-only. An explicit transaction gives all queries one
    SQLite snapshot if a heartbeat appends a new event during reconstruction.
    """
    with _connect() as conn:
        conn.execute("BEGIN")
        total = conn.execute(
            """SELECT COUNT(*) FROM world_mutations
               WHERE world_seed = ? AND node_name = ?""",
            (world_seed, node_name),
        ).fetchone()[0]
        step = total if at_step is None else int(at_step)
        if step < 0 or step > total:
            raise ValueError(
                f"wayback step must be between 0 and {total}, got {step}")

        first = conn.execute(
            """SELECT recorded_at FROM world_mutations
               WHERE world_seed = ? AND node_name = ?
               ORDER BY id LIMIT 1""",
            (world_seed, node_name),
        ).fetchone()

        if step == 0:
            cursor = 0
            selected = None
        else:
            selected = conn.execute(
                """SELECT id, recorded_at, delta, strength
                   FROM world_mutations
                   WHERE world_seed = ? AND node_name = ?
                   ORDER BY id LIMIT 1 OFFSET ?""",
                (world_seed, node_name, step - 1),
            ).fetchone()
            # COUNT and SELECT share one transaction snapshot, so the ordinal
            # must resolve unless the database is corrupt.
            if selected is None:  # pragma: no cover - defensive invariant
                raise RuntimeError("wayback cursor disappeared during read")
            cursor = selected[0]

        properties: Any = dict(born_properties)
        if cursor:
            baseline_row = conn.execute(
                """SELECT legacy_baseline
                   FROM node_property_cache_meta
                   WHERE world_seed = ? AND node_name = ?""",
                (world_seed, node_name),
            ).fetchone()
            if baseline_row and baseline_row[0]:
                baseline, is_object = _decode_property_blob(baseline_row[0])
                if is_object:
                    properties = json_merge_patch(properties, baseline)
            deltas = conn.execute(
                """SELECT delta FROM world_mutations
                   WHERE world_seed = ? AND node_name = ?
                     AND delta IS NOT NULL AND id <= ?
                   ORDER BY node_version""",
                (world_seed, node_name, cursor),
            ).fetchall()
            for (blob,) in deltas:
                properties = json_merge_patch(properties, json.loads(blob))
            strength_sum = conn.execute(
                """SELECT COALESCE(SUM(strength), 0.0)
                   FROM world_mutations
                   WHERE world_seed = ? AND node_name = ?
                     AND strength IS NOT NULL AND id <= ?""",
                (world_seed, node_name, cursor),
            ).fetchone()[0]
        else:
            strength_sum = 0.0

    if not isinstance(properties, dict):  # merge-patch root replacement guard
        properties = {}
    if selected is None:
        moment = {"at": None, "kind": "birth", "delta": {},
                  "strength": None}
    else:
        delta = json.loads(selected[2]) if selected[2] else {}
        strength = selected[3]
        kind = "change" if delta else (
            "ripple" if strength is not None else "trace")
        moment = {"at": selected[1], "kind": kind, "delta": delta,
                  "strength": strength}

    return {
        "properties": properties,
        "ripple_score": round(min(
            1.0, float(strength_sum) * RIPPLE_INCREMENT_PER_STRENGTH), 3),
        "activity": step,
        "timeline": {
            "step": step,
            "total": total,
            "cursor": cursor,
            "present": step == total,
            "first_witness": ({"at": first[0]} if first else None),
            "moment": moment,
        },
    }


@_with_db
def rebuild_ripple_scores(world_seed: int) -> dict[str, float]:
    """Recompute every node's ripple_score from the chronicle (ADR-009).

    The persisted score is a derived cache, never authoritative: each fired
    causal event carries its strength on exactly one chronicle row, and the
    live increment is monotonic, non-negative, and capped at 1.0 — a pure
    fold of chronicled strengths × RIPPLE_INCREMENT_PER_STRENGTH. Cache
    drift is repaired by calling this; only the chronicle is the record.
    Returns the rebuilt {node_name: score} map.
    """
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        sums = conn.execute(
            """SELECT node_name, SUM(strength) FROM world_mutations
               WHERE world_seed = ? AND strength IS NOT NULL
               GROUP BY node_name""",
            (world_seed,),
        ).fetchall()
        rebuilt = {name: min(1.0, total * RIPPLE_INCREMENT_PER_STRENGTH)
                   for name, total in sums}
        conn.execute(
            f"""UPDATE node_runtime_state
                SET ripple_score = 0.0, updated_at = {_NOW}
                WHERE world_seed = ?""",
            (world_seed,),
        )
        for name, score in rebuilt.items():
            conn.execute(
                f"""INSERT INTO node_runtime_state
                    (world_seed, node_name, ripple_score, updated_at, created_at)
                   VALUES (?, ?, ?, {_NOW}, {_NOW})
                   ON CONFLICT(world_seed, node_name) DO UPDATE SET
                     ripple_score = excluded.ripple_score,
                     updated_at   = excluded.updated_at""",
                (world_seed, name, score),
            )
    return rebuilt


@_with_db
def load_node_property_override(world_seed: int, node_name: str) -> dict:
    """Read one current overlay without hydrating the rest of the world."""
    with _connection() as conn:
        return _current_property_overlay(conn, world_seed, node_name, repair=False)


@_with_db
def load_node_property_overrides(world_seed: int, names: list[str] | None = None) -> dict[str, dict]:
    """All property overlays, lazily repaired from born rows + chronicle.

    The cache is derived. Nodes with canonical deltas are rebuilt before
    hydration so upgrades cannot revive born values whose old cached
    tombstones were discarded; legacy cache-only rows remain intact.
    """
    if names is not None:
        names = list(dict.fromkeys(names))
        if not names:
            return {}
        if len(names) > 550:
            raise ValueError("property projection exceeds candidate/ancestor bound")
    selected = '' if names is None else f" AND node_name IN ({','.join('?' for _ in names)})"
    args = (world_seed, *(names or []))

    def read_rows(conn: sqlite3.Connection) -> tuple[
            list[tuple], dict[str, int]]:
        rows = conn.execute(
            f"""SELECT state.node_name, state.properties, meta.cache_format,
                      meta.properties_blob, meta.delta_version,
                      meta.legacy_baseline
               FROM node_runtime_state AS state
               LEFT JOIN node_property_cache_meta AS meta
                 ON meta.world_seed = state.world_seed
                AND meta.node_name = state.node_name
               WHERE state.world_seed = ? AND state.properties IS NOT NULL
               {selected.replace('node_name', 'state.node_name')}""",
            args,
        ).fetchall()
        delta_versions = {name: int(version) for name, version in conn.execute(
            f"""SELECT node_name, MAX(node_version) FROM world_mutations
               WHERE world_seed = ? AND delta IS NOT NULL {selected}
               GROUP BY node_name""",
            args,
        ).fetchall()}
        return rows, delta_versions

    def hydrate(conn: sqlite3.Connection, rows: list[tuple],
                delta_versions: dict[str, int], *,
                repair: bool) -> tuple[dict, bool]:
        overrides: dict[str, dict] = {}
        cached_names: set[str] = set()
        needs_repair = False
        for (name, blob, cache_format, marked_blob, marked_version,
             baseline_blob) in rows:
            cached_names.add(name)
            expected_version = max(
                delta_versions.get(name, 0), int(marked_version or 0))
            cached, current_format, baseline = _property_cache_values(
                blob, cache_format, marked_blob, marked_version,
                expected_version, baseline_blob)
            if current_format or (
                    name not in delta_versions and marked_version is None):
                overrides[name] = cached
                continue
            needs_repair = True
            if repair:
                rebuilt = _rebuild_property_overlay(
                    conn, world_seed, name, baseline)
                _store_property_overlay(
                    conn, world_seed, name, rebuilt,
                    legacy_baseline=baseline)
                overrides[name] = rebuilt
        for name in delta_versions.keys() - cached_names:
            needs_repair = True
            if repair:
                rebuilt = _rebuild_property_overlay(
                    conn, world_seed, name, {})
                _store_property_overlay(
                    conn, world_seed, name, rebuilt,
                    legacy_baseline={})
                overrides[name] = rebuilt
        return overrides, needs_repair

    with _connection() as conn:
        rows, delta_versions = read_rows(conn)
        overrides, needs_repair = hydrate(
            conn, rows, delta_versions, repair=False)
        if not needs_repair:
            return overrides

        # Re-read and repair under one write lock. A concurrent canonical
        # writer cannot land between replay and the cache marker write.
        _begin_write(conn)
        rows, delta_versions = read_rows(conn)
        repaired, _ = hydrate(
            conn, rows, delta_versions, repair=True)
        return repaired


# ── The materialized world (ADR-006 Option A) ──
# Rows in world_nodes are born once per seed and never rewritten by
# generation again; the stored row IS the node's identity. Only
# multiverse/store.py writes here, and only through save_world_nodes.


@_with_db
def world_is_born(world_seed: int) -> bool:
    with _connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM world_nodes WHERE world_seed = ? LIMIT 1",
            (world_seed,),
        ).fetchone()
        return row is not None


@_with_db
def save_world_nodes(world_seed: int,
                     rows: list[tuple[str, str, str, str, int]],
                     generator_version: int) -> int:
    """Birth a world: write its node rows in one transaction.

    `rows` is [(path, name, level, properties_json, breadth), ...].
    Refuses to overwrite: if the seed already has any row (including a
    concurrent birth racing this one — the PK raises IntegrityError),
    nothing is written and 0 is returned. A born world is never re-born.
    """
    with _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM world_nodes WHERE world_seed = ? LIMIT 1",
            (world_seed,),
        ).fetchone()
        if exists:
            return 0
        try:
            conn.executemany(
                f"""INSERT INTO world_nodes
                    (world_seed, path, name, level, properties, breadth,
                     generator_version, born_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, {_NOW})""",
                [(world_seed, path, name, level, props_json, breadth,
                  generator_version)
                 for path, name, level, props_json, breadth in rows],
            )
        except sqlite3.IntegrityError:
            conn.rollback()  # lost a birth race — the other writer's world stands
            return 0
        return len(rows)


@_with_db
def get_world_nodes(world_seed: int,
                    max_depth: int | None = None) -> list[tuple[str, str, str, str, int]]:
    """All born rows for a seed as (path, name, level, properties_json,
    breadth), ordered by path so parents precede children. `max_depth`
    limits path length in ordinals (a depth view of the stored world)."""
    with _connection() as conn:
        if max_depth is None:
            rows = conn.execute(
                """SELECT path, name, level, properties, breadth
                   FROM world_nodes WHERE world_seed = ? ORDER BY path""",
                (world_seed,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT path, name, level, properties, breadth
                   FROM world_nodes WHERE world_seed = ?
                   AND (LENGTH(path) - LENGTH(REPLACE(path, '.', '')) + 1) <= ?
                   ORDER BY path""",
                (world_seed, max_depth),
            ).fetchall()
        return rows


@_with_db
def get_world_node_chain(world_seed: int,
                         paths: list[str]) -> list[tuple[str, str, str, str, int]]:
    """The rows for an ancestor chain (a list of path prefixes), ordered
    root-first. Missing paths are simply absent from the result."""
    if not paths:
        return []
    with _connection() as conn:
        marks = ",".join("?" for _ in paths)
        rows = conn.execute(
            f"""SELECT path, name, level, properties, breadth
                FROM world_nodes WHERE world_seed = ? AND path IN ({marks})
                ORDER BY LENGTH(path), path""",
            (world_seed, *paths),
        ).fetchall()
        return rows


# ── Immutable world metadata (ADR-008) ──
# First-selection records: written once, then the stored value IS the fact.
# There is deliberately no update or delete here — pinning is the only door,
# and it refuses to overwrite (the same one-way discipline as world_nodes).


@_with_db
def get_world_meta(world_seed: int, key: str) -> str | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT value FROM world_meta WHERE world_seed = ? AND key = ?",
            (world_seed, key),
        ).fetchone()
        return row[0] if row else None


@_with_db
def pin_world_meta(world_seed: int, key: str, value: str) -> str:
    """Pin `value` under (world_seed, key) — write-once.

    Returns the durable value: the one just written, or the one already
    pinned (including by a concurrent pinner racing this call — the PK
    raises IntegrityError and the winner's value stands). A pinned value
    is never overwritten.
    """
    with _connect() as conn:
        try:
            conn.execute(
                f"""INSERT INTO world_meta (world_seed, key, value, recorded_at)
                    VALUES (?, ?, ?, {_NOW})""",
                (world_seed, key, value),
            )
            return value
        except sqlite3.IntegrityError:
            conn.rollback()  # already pinned — the standing value is the fact
            row = conn.execute(
                "SELECT value FROM world_meta WHERE world_seed = ? AND key = ?",
                (world_seed, key),
            ).fetchone()
            return row[0]


@_with_db
def get_ripple_score(world_seed: int, node_name: str) -> float:
    with _connection() as conn:
        row = conn.execute(
            "SELECT ripple_score FROM node_runtime_state WHERE world_seed = ? AND node_name = ?",
            (world_seed, node_name),
        ).fetchone()
        return float(row[0]) if row else 0.0


@_with_db
def load_ripple_scores(world_seed: int) -> dict[str, float]:
    with _connection() as conn:
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
    """Checkpoint then delete `world_mutations` rows older than *days*.

    Off by default — `init_db` only invokes this when
    `NESTED_WORLDS_MUTATION_TTL_DAYS` is set to a positive integer. Operators
    can also call directly from a maintenance script. `days <= 0` is a no-op
    so callers don't need to guard the threshold themselves. Any material
    delta prefix being removed is folded into the rollback-readable baseline
    in the same transaction, so later cache repair cannot revert live state.
    A timestamp-disordered, non-prefix deletion is refused because one
    baseline cannot preserve deltas interleaved with surviving history.
    """
    if days <= 0:
        return 0
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cutoff = _older_than_cutoff(conn, days)
        affected = conn.execute(
            """SELECT world_seed, node_name, MAX(node_version)
               FROM world_mutations
               WHERE recorded_at < ? AND delta IS NOT NULL
               GROUP BY world_seed, node_name""",
            (cutoff,),
        ).fetchall()

        for world_seed, node_name, deleted_head in affected:
            interleaved = conn.execute(
                """SELECT 1 FROM world_mutations
                   WHERE world_seed = ? AND node_name = ?
                     AND delta IS NOT NULL AND recorded_at >= ?
                     AND node_version <= ? LIMIT 1""",
                (world_seed, node_name, cutoff, deleted_head),
            ).fetchone()
            if interleaved:
                raise RuntimeError(
                    "refusing non-prefix mutation prune for "
                    f"world {world_seed}, node {node_name!r}")

            # Repair first if a rollback binary changed the cache. The durable
            # baseline remains the pre-chronicle starting point.
            _prepare_property_cache(conn, world_seed, node_name)
            _cached, _current, baseline = _property_cache_snapshot(
                conn, world_seed, node_name)
            born = _load_born_properties(conn, world_seed, node_name)
            checkpoint: Any = json_merge_patch(born, baseline)
            pruned_deltas = conn.execute(
                """SELECT delta FROM world_mutations
                   WHERE world_seed = ? AND node_name = ?
                     AND recorded_at < ? AND delta IS NOT NULL
                   ORDER BY node_version""",
                (world_seed, node_name, cutoff),
            ).fetchall()
            for (blob,) in pruned_deltas:
                checkpoint = json_merge_patch(checkpoint, json.loads(blob))
            if not isinstance(checkpoint, dict):
                checkpoint = {}
            new_baseline = json_merge_diff(born, checkpoint)
            if not isinstance(new_baseline, dict):
                new_baseline = {}
            conn.execute(
                """UPDATE node_property_cache_meta SET legacy_baseline = ?
                   WHERE world_seed = ? AND node_name = ?""",
                (json.dumps(new_baseline), world_seed, node_name),
            )

        removed = _delete_older_than(
            conn, "world_mutations", "recorded_at", days, cutoff=cutoff)

        for world_seed, node_name, _deleted_head in affected:
            _cached, _current, baseline = _property_cache_snapshot(
                conn, world_seed, node_name)
            rebuilt = _rebuild_property_overlay(
                conn, world_seed, node_name, baseline)
            _store_property_overlay(
                conn, world_seed, node_name, rebuilt,
                legacy_baseline=baseline)
        return removed


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


class NameUnavailable(ValueError):
    """A registration was attempted with a name already in use.

    Distinct from the key-collision IntegrityError: the *name* clashed, not
    the random key. Callers (the invite CLI) turn this into a friendly
    'choose another name' message. (ADR-004 §7 — every player's name is
    unique.)
    """


def _normalize_invite_name(name: str) -> str:
    """The comparison form used for name-uniqueness: trimmed and lowercased.

    Kept in lockstep with the DB's `lower(trim(name))` UNIQUE index
    (migration 0011) so the application check and the database backstop
    agree on what counts as 'the same name'.
    """
    return name.strip().lower()


def _credential_digest(secret: str) -> str:
    """The at-rest form of an invite key or registration token: sha256 hex.

    Credentials are the one thing every backup of this DB used to hand over
    in plaintext — everything *derived* from them (actor_identity, the cost
    ledger buckets) was already hashed, but the credential row itself was
    not. Stored form is the full digest; the plaintext appears exactly once,
    at mint/registration, and cannot be recovered afterwards (lost key →
    revoke and re-mint). Plaintext credentials carry a `nw_`/`nwr_` prefix
    and digests are pure hex, so the two forms can never collide — which is
    what makes the one-time legacy backfill in `init_db` safe.
    """
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _hash_legacy_credentials(conn: sqlite3.Connection) -> None:
    """One-time, idempotent: convert any plaintext credential rows to digests.

    Runs on every init; matches only rows still carrying the plaintext
    prefix (`nw_` / `nwr_`), so an already-converted DB is a no-op. UPDATEs
    a credential *store*, not the chronicle — invite_keys and
    registration_tokens are operational tables, outside the append-only
    covenant's protected set.
    """
    for table, column, prefix in (
        ("invite_keys", "key", "nw@_%"),
        ("registration_tokens", "token", "nwr@_%"),
    ):
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if not exists:
            # A partially-migrated DB (e.g. a test applying a filtered
            # migration set) may not have the table yet; nothing to backfill.
            continue
        rows = conn.execute(
            f"SELECT {column} FROM {table} WHERE {column} LIKE ? ESCAPE '@'",
            (prefix,),
        ).fetchall()
        for (plaintext,) in rows:
            conn.execute(
                f"UPDATE {table} SET {column} = ? WHERE {column} = ?",
                (_credential_digest(plaintext), plaintext),
            )
        if rows:
            _log.info("hashed %d legacy plaintext %s row(s) at rest",
                      len(rows), table)


def _mint_invite_key_on(conn, key: str, name: str,
                        note: str | None = None) -> None:
    """Name-uniqueness check + INSERT on an already-open connection.

    Shared by `mint_invite_key` and `redeem_registration_token`: redemption
    must mint inside its OWN transaction (consume the token and mint the key
    as one unit — and roll back together if the name is taken), and a second
    writer connection opened mid-transaction would risk SQLITE_BUSY.
    """
    norm = _normalize_invite_name(name)
    taken = conn.execute(
        "SELECT 1 FROM invite_keys WHERE lower(trim(name)) = ?", (norm,)
    ).fetchone()
    if taken is not None:
        raise NameUnavailable(f"the name {name!r} is already registered")
    conn.execute(
        "INSERT INTO invite_keys (key, name, note) VALUES (?, ?, ?)",
        (_credential_digest(key), name, note),
    )


@_with_db
def mint_invite_key(key: str, name: str, note: str | None = None) -> None:
    """Insert a new invite key. Caller generates the random key string.

    The name must be unique (case- and whitespace-insensitively) across all
    invite keys — it becomes the player's authoritative display name at
    runtime (ADR-004 §7). Raises NameUnavailable if the name is already
    registered, and sqlite3.IntegrityError on a key collision so the caller
    can retry with a new random key (at 32 hex chars, key collisions are
    astronomically unlikely).
    """
    with _connect() as conn:
        _mint_invite_key_on(conn, key, name, note)


@_with_db
def lookup_invite_key(key: str) -> dict[str, Any] | None:
    """Return the row for `key` iff it exists AND is not revoked.

    Returns None for unknown keys and revoked keys alike — the caller
    treats both as "not authorized" without leaking which condition
    matched. `key` is the plaintext credential the request presented; the
    row's stored (and returned) "key" field is its at-rest sha256 digest.
    """
    with _connect() as conn:
        row = conn.execute(
            """SELECT key, name, note, created_at, revoked_at, last_used_at
               FROM invite_keys WHERE key = ? AND revoked_at IS NULL""",
            (_credential_digest(key),),
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
            (_credential_digest(key),),
        )


@_with_db
def revoke_invite_key(key: str) -> bool:
    """Mark `key` revoked. Returns True iff a row was actually updated.

    Accepts the plaintext key (`nw_…`, what an operator pastes from a share
    URL) or a unique digest prefix of ≥12 hex chars (what `invite list`
    shows) — revocation must stay possible after the plaintext is gone. The
    digest form is only honoured here, never on the auth path: knowing a
    digest revokes a key, it does not authorize one.
    """
    with _connect() as conn:
        cur = conn.execute(
            f"""UPDATE invite_keys SET revoked_at = {_NOW}
                WHERE key = ? AND revoked_at IS NULL""",
            (_credential_digest(key),),
        )
        if cur.rowcount > 0:
            return True
        return _revoke_by_digest_prefix(conn, "invite_keys", "key", key)


def _revoke_by_digest_prefix(conn, table: str, column: str,
                             supplied: str) -> bool:
    """Revoke by a digest prefix from the CLI listing. Ops convenience only.

    Requires ≥12 hex chars and exactly ONE live row matching — an ambiguous
    prefix revokes nothing rather than guessing. Table/column are internal
    constants supplied by the two callers, never user input.
    """
    prefix = supplied.strip().rstrip("…")
    if len(prefix) < 12 or not all(c in "0123456789abcdef" for c in prefix):
        return False
    rows = conn.execute(
        f"""SELECT {column} FROM {table}
            WHERE {column} LIKE ? AND revoked_at IS NULL""",
        (prefix + "%",),
    ).fetchall()
    if len(rows) != 1:
        return False
    conn.execute(
        f"UPDATE {table} SET revoked_at = {_NOW} WHERE {column} = ?",
        (rows[0][0],),
    )
    return True


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


class TokenInvalid(ValueError):
    """A registration was attempted with an unknown, spent, or cancelled token.

    Distinct from NameUnavailable: the INVITE failed, not the chosen name.
    Callers reply "this invite isn't valid" without leaking which condition
    matched (unknown / already used / cancelled all read the same).
    """


def _registration_token_row(row) -> dict[str, Any]:
    return {
        "token": row[0], "note": row[1], "created_at": row[2],
        "redeemed_at": row[3], "redeemed_name": row[4], "revoked_at": row[5],
    }


_REG_TOKEN_COLS = ("token, note, created_at, redeemed_at, redeemed_name, "
                   "revoked_at")


@_with_db
def create_registration_token(token: str, note: str | None = None) -> None:
    """Insert a new single-use registration token (ADR-004 §7 self-service).

    Caller generates the random token string. Raises sqlite3.IntegrityError
    on a token collision so the caller can retry with a fresh random value.
    Stored hashed at rest, like invite keys — the plaintext token exists
    only in the share link.
    """
    with _connect() as conn:
        conn.execute(
            "INSERT INTO registration_tokens (token, note) VALUES (?, ?)",
            (_credential_digest(token), note),
        )


@_with_db
def lookup_registration_token(token: str) -> dict[str, Any] | None:
    """Return the row for `token` iff it is still redeemable.

    None for unknown, already-redeemed, and cancelled tokens alike — the
    caller treats all three as "not a valid invite" without learning which.
    """
    with _connect() as conn:
        row = conn.execute(
            f"""SELECT {_REG_TOKEN_COLS} FROM registration_tokens
                WHERE token = ? AND redeemed_at IS NULL
                      AND revoked_at IS NULL""",
            (_credential_digest(token),),
        ).fetchone()
        return _registration_token_row(row) if row else None


@_with_db
def redeem_registration_token(token: str, key: str, name: str) -> None:
    """Consume `token` and mint the per-user invite key, atomically.

    One transaction covers the token check, the name-uniqueness check, the
    invite-key INSERT, and the token consumption — so a taken name
    (NameUnavailable) rolls the whole thing back and the token stays
    redeemable for another try, while a successful redeem can never leave the
    token live. Raises TokenInvalid for an unknown/spent/cancelled token.
    """
    with _connect() as conn:
        token_digest = _credential_digest(token)
        live = conn.execute(
            """SELECT 1 FROM registration_tokens
               WHERE token = ? AND redeemed_at IS NULL
                     AND revoked_at IS NULL""",
            (token_digest,),
        ).fetchone()
        if live is None:
            raise TokenInvalid("this invite is not valid")
        _mint_invite_key_on(conn, key, name)
        conn.execute(
            f"""UPDATE registration_tokens
                SET redeemed_at = {_NOW}, redeemed_name = ?
                WHERE token = ?""",
            (name, token_digest),
        )


@_with_db
def cancel_registration_token(token: str) -> bool:
    """Cancel an outstanding token (e.g. a leaked link). True iff it was live.

    Only unredeemed tokens can be cancelled — a redeemed one has already
    become an invite key, and revoking THAT is `revoke_invite_key`.
    Accepts the plaintext token or a unique ≥12-hex-char digest prefix
    (same rationale as `revoke_invite_key`: cancellation must outlive the
    plaintext).
    """
    with _connect() as conn:
        cur = conn.execute(
            f"""UPDATE registration_tokens SET revoked_at = {_NOW}
                WHERE token = ? AND redeemed_at IS NULL
                      AND revoked_at IS NULL""",
            (_credential_digest(token),),
        )
        if cur.rowcount > 0:
            return True
        return _cancel_token_by_digest_prefix(conn, token)


def _cancel_token_by_digest_prefix(conn, supplied: str) -> bool:
    """Cancel a still-redeemable token by a unique ≥12-hex-char digest prefix."""
    prefix = supplied.strip().rstrip("…")
    if len(prefix) < 12 or not all(c in "0123456789abcdef" for c in prefix):
        return False
    rows = conn.execute(
        """SELECT token FROM registration_tokens
           WHERE token LIKE ? AND redeemed_at IS NULL AND revoked_at IS NULL""",
        (prefix + "%",),
    ).fetchall()
    if len(rows) != 1:
        return False
    conn.execute(
        f"UPDATE registration_tokens SET revoked_at = {_NOW} WHERE token = ?",
        (rows[0][0],),
    )
    return True


@_with_db
def list_registration_tokens(include_spent: bool = False) -> list[dict[str, Any]]:
    """All registration tokens, newest first. Redeemable-only unless
    include_spent (then redeemed and cancelled rows appear too)."""
    where = ("" if include_spent
             else "WHERE redeemed_at IS NULL AND revoked_at IS NULL")
    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT {_REG_TOKEN_COLS} FROM registration_tokens {where}
                ORDER BY created_at DESC"""
        ).fetchall()
        return [_registration_token_row(r) for r in rows]


@_with_db
def save_player_position(key: str, node_name: str, seed: int, depth: int,
                         min_breadth: int, max_breadth: int) -> bool:
    """Record where an invite-key holder left off, for cross-device resume.

    Keyed on the per-user invite key, so this only persists for a real per-user
    credential — the UPDATE affects zero rows (returns False) for an unknown key
    or a revoked one, and the client keeps using its local cache. Best-effort:
    callers fire-and-forget on navigation.
    """
    if not key:
        return False
    with _connect() as conn:
        cur = conn.execute(
            f"""UPDATE invite_keys
                SET last_node = ?, last_seed = ?, last_depth = ?,
                    last_min_breadth = ?, last_max_breadth = ?, last_node_at = {_NOW}
                WHERE key = ? AND revoked_at IS NULL""",
            (node_name, seed, depth, min_breadth, max_breadth,
             _credential_digest(key)),
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
            (_credential_digest(key),),
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
