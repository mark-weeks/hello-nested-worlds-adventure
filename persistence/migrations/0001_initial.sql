-- Initial schema. All statements use IF NOT EXISTS so this migration is
-- idempotent: it can be applied to a fresh database, or to a pre-runner
-- database that already carries these tables (in which case it's a no-op).

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

CREATE TABLE IF NOT EXISTS agent_memory (
    agent_name  TEXT    NOT NULL,
    world_seed  INTEGER NOT NULL,
    visited_ids TEXT    NOT NULL DEFAULT '[]',
    log_entries TEXT    NOT NULL DEFAULT '[]',
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (agent_name, world_seed)
);

CREATE TABLE IF NOT EXISTS node_images (
    node_key   TEXT PRIMARY KEY,
    image_url  TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS node_runtime_state (
    world_seed   INTEGER NOT NULL,
    node_name    TEXT    NOT NULL,
    ripple_score REAL    NOT NULL DEFAULT 0.0,
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (world_seed, node_name)
);
