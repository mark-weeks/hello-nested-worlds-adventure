# ADR-003: Persistence Backend (SQLite → Postgres switchover path)

**Status:** Accepted 2026-05-25 — documents the migration plan and the in-code seam. Implementation deliberately deferred; see "When to migrate."

---

## Context

All durable state lives in a single SQLite database at `~/.nested-worlds/worlds.db`, opened in WAL mode for concurrent readers plus one writer. The schema is managed by a homegrown migration runner over `persistence/migrations/*.sql`, with versions tracked in a `schema_version` table. Every caller goes through module-level functions in `persistence/__init__.py`; there is exactly one `_connect()` factory and no direct `sqlite3` calls outside the module (verified by grep across `agents/`, `causality/`, `consciousness/`, `interface/`, `multiverse/`, `puzzles/`, `server/`, `main.py`).

Hot paths — the writes that will bottleneck first:

- **`record_mutation`** — fires on every `AGENT_VISIT`, `DANGER_ALERT`, `PUZZLE_FAILED`, `PLAYER_SPEAK`, `PLAYER_CHAT`, and every agent-driven causal event. One `INSERT` per fire.
- **`upsert_ripple_score`** — fires from the causality bus on every event propagation, per node, per hop. One UPSERT per fire (typically 5–10 per player action with bidirectional propagation).
- **`get_node_history`** — called on every `/speak` and every image-prompt assembly. Indexed by `(world_seed, node_name)` via `idx_world_mutations_seed_node`.

The three account for the bulk of synchronous traffic and all run inside the request path.

---

## When to migrate

Pull the trigger on any one of these:

- **Sustained concurrent writers > 1 within a 200 ms window.** SQLite WAL serializes writers; under burst load, `SQLITE_BUSY` retries will start to surface in the access log. The first observable symptom will be elevated p99 latency on `/puzzle/attempt` or `/speak`.
- **Beta scales past ~30 concurrent active sessions.** Empirical estimate — based on the per-event UPSERT load from `upsert_ripple_score` alone (one fire per hop × ~5 hops per propagation × multiple players interacting simultaneously). Revisit once we have real per-endpoint latency data.
- **Multi-host deploy.** SQLite's single-file model rules this out. The moment we want two app servers behind a load balancer, the storage layer needs to move.
- **Read-replica need.** Reporting, analytics, or a dashboard effort would benefit from a hot standby — SQLite can't.
- **`world_mutations` exceeds ~50 M rows** without `NESTED_WORLDS_MUTATION_TTL_DAYS` being a tolerable mitigation. The hot-path indexes help reads, but SQLite's single-writer model bottlenecks the prune itself.

None of these conditions are currently met. Beta is invite-gated, rate-limited (20 req/min/IP on the hot endpoints), cost-capped (500 Anthropic calls/day default), and single-host. **The migration is premature today.** This ADR exists so it's a half-day refactor when the trigger fires, not a multi-week investigation.

---

## What's already in place (the seam)

The persistence module is shaped so the swap is a localized refactor, not a rewrite:

- **Single connection factory.** `_connect()` is the only place that opens a database handle. Every public function in `persistence/__init__.py` goes through it. No other source file calls `sqlite3` directly.
- **Migration runner is forward-compatible.** Versions are recorded in `schema_version`; the runner skips already-applied versions. A Postgres-targeted set of migration files can slot in as `migrations/postgres/*.sql` selected by the same runner via a dialect prefix.
- **Caller code is dialect-light.** Apart from this module, no source file uses anything beyond plain `INSERT` / `SELECT` / `UPDATE`. The existing `ON CONFLICT … DO UPDATE` clauses (`agent_memory`, `node_runtime_state`, `cost_budget`) port to Postgres unchanged.
- **Tests redirect via `_DB_PATH`.** `tests/conftest.py` monkeypatches a single attribute. For a Postgres test path, a sibling fixture can rebind `_connect()` to a per-test schema or wrap each test in a transaction with rollback.
- **Dialect-specific SQL is consolidated.** The Python module concentrates its SQLite-isms in one labelled section near the top of `persistence/__init__.py` — search for `--- SQL dialect seam ---`. At time of writing, that section holds:
  - `_NOW` — the current-timestamp expression (`datetime('now')` → `CURRENT_TIMESTAMP`).
  - `_delete_older_than(...)` — the relative-interval `DELETE`, used by `prune_mutations`.
  - A line-referenced inventory of the remaining SQLite-isms that are *not* yet abstracted (two `INSERT OR REPLACE` statements). Translation is mechanical (see table below).

---

## SQL dialect translation table

| Concern | SQLite (today) | Postgres (target) |
|---|---|---|
| Param style | `?` | `%s` (psycopg) / `$1` (asyncpg) |
| Current timestamp | `datetime('now')` | `CURRENT_TIMESTAMP` |
| Relative interval | `datetime('now', '-N days')` | `NOW() - N * INTERVAL '1 day'` |
| Upsert (replace) | `INSERT OR REPLACE` | `INSERT … ON CONFLICT(...) DO UPDATE SET … ` |
| Upsert (merge) | `INSERT … ON CONFLICT(...) DO UPDATE SET …` | same syntax — portable ✓ |
| JSON storage | `TEXT` + `json.dumps()` | `JSONB` + native typed bind |
| `json_array_length(text)` | works on text | requires `JSONB` input — convert column or wrap the bind |
| Auto-PK | `INTEGER PRIMARY KEY AUTOINCREMENT` | `BIGSERIAL PRIMARY KEY` (or `GENERATED BY DEFAULT AS IDENTITY`) |
| Last insert id | `cur.lastrowid` | `INSERT … RETURNING id` |
| Online backup | `Connection.backup()` | `pg_dump` / logical replication |
| WAL pragma | `PRAGMA journal_mode=WAL` | n/a (MVCC native) |
| Permissions | `chmod 0600` on the DB file | role-based `GRANT` / `REVOKE` |

The `cur.lastrowid` site is `save_agent_run` — that's the only one in the module.

---

## Schema notes for the Postgres port

- All `TEXT` timestamp columns become `TIMESTAMPTZ`. Straightforward because we always wrote ISO-8601 UTC strings (`datetime('now')` produces `YYYY-MM-DD HH:MM:SS` UTC).
- All `TEXT` JSON columns (`agent_runs.events`, `world_mutations.data`, `agent_memory.visited_ids`, `agent_memory.log_entries`) become `JSONB`. We never JSON-query in SQLite *except* `list_agent_memories` (`json_array_length(visited_ids)`), and that one ports cleanly once the column is `JSONB`.
- Indexes carry over by name; the hot-path indexes (`idx_world_mutations_seed_node`, `idx_world_mutations_seed_time`, `idx_agent_runs_seed`) are dialect-neutral.
- `node_runtime_state` and `agent_memory` UPSERTs are on composite primary keys; Postgres handles those identically.
- `cost_budget` `(bucket, day)` upsert ports unchanged.
- File-level `0o600` on `worlds.db` becomes role-level grants: a dedicated app role with `INSERT, SELECT, UPDATE, DELETE` on the application tables; no superuser.

---

## Data-copy approach (when the time comes)

Preferred sequence — biased toward simplicity over uptime, because the audience is invited beta testers:

1. **Stand up Postgres.** Apply `migrations/postgres/0001_initial.sql` (hand-translated mirror of the current SQLite schema, with the type changes from the section above).
2. **Quiesce writers.** Flip `NESTED_WORLDS_DISABLE_AI=1` and `NESTED_WORLDS_DISABLE_IMAGES=1` to drop external-API call load to zero, then take the WebSocket server offline for the cut-over window. Expected window for current data volumes: 10–60 seconds.
3. **Run a one-shot copier.** A Python script streams rows out of SQLite in primary-key order, JSON-decodes + re-encodes for `JSONB`, and batch-inserts into Postgres with `COPY` for the high-volume tables (`world_mutations`, `agent_runs`). Per-table parity check: row counts match and a sampled-hash of `(seed, name, recorded_at)` agrees.
4. **Cut over.** Point a new `NESTED_WORLDS_DB_URL` env var at Postgres, restart the server, verify `/health`, `schema_versions()`, and a smoke-test `/speak`. The `_connect()` factory dispatches on the URL scheme.
5. **Keep the SQLite file** as a rollback artifact for at least one week before deletion.

No dual-write phase. The downtime cost is lower than the complexity cost of running both backends in lockstep, given the audience and write rates.

---

## Rollback

Until the SQLite file is deleted: stop the server, unset `NESTED_WORLDS_DB_URL`, restart. The cut-over window is short enough that any writes lost on rollback are acceptable — players will be informed via the beta channel.

After the SQLite file is deleted, rollback requires restoring the pre-cut-over backup (we already snapshot daily via `main.py backup --to ...`).

---

## Out of scope for this ADR

- **Connection pooling, async drivers (`asyncpg`), per-request transaction scoping, sharding-by-seed.** All post-migration concerns — track separately when the trigger fires.
- **Migrating `node_images` URL cache to Redis or first-party object store (R2).** That decision lives in ADR-002 with its own trigger conditions.
- **Schema-level changes that aren't required for the port** (e.g. denormalizing `world_mutations.data`, partitioning by `world_seed`). Consider after the migration is settled.

---

## Acceptance criteria for "the seam is preserved"

These are the invariants that make this ADR's plan executable. If a future change breaks any of them, update this ADR.

1. No source file outside `persistence/` imports `sqlite3` or otherwise opens the database directly.
2. Every connection in `persistence/__init__.py` goes through `_connect()`.
3. Every `datetime('now')` in Python (not in the `.sql` migration files) is sourced from `_NOW`.
4. Every relative-interval `DELETE` goes through `_delete_older_than(...)`.
5. New SQL added to the module that is *not* portable to Postgres must be listed in the dialect-seam comment block — so the translation work is visible.
