-- Staged causality: strong events no longer cascade to every scale in the
-- same instant. Each ring of a cascade is enqueued here with a due time and
-- fired by the causal pump (server/heartbeat.py), so consequences travel
-- outward over observable seconds — a solve settles its room now, its
-- region shortly, its galaxy later. Durable, so in-flight cascades survive
-- a restart and finish arriving afterwards.
CREATE TABLE IF NOT EXISTS causal_queue (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    world_seed INTEGER NOT NULL,
    node_name  TEXT    NOT NULL,
    kind       TEXT    NOT NULL,
    strength   REAL    NOT NULL,
    direction  TEXT    NOT NULL,          -- 'up' | 'down'
    payload    TEXT,
    due_at     TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_causal_queue_due
    ON causal_queue (due_at);
