-- Deep time: cosmic-scale verbs plant changes that mature later. The act
-- records immediately (SCALE_ACT with matures_in); the property delta
-- waits here and lands when due — a galaxy answers on a galaxy's clock.
-- Durable so an in-flight maturation survives a restart, like causal_queue.

CREATE TABLE IF NOT EXISTS verb_maturation (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    world_seed INTEGER NOT NULL,
    node_name  TEXT    NOT NULL,
    verb       TEXT    NOT NULL,
    changed    TEXT    NOT NULL,          -- the property delta, JSON
    actor      TEXT,                      -- display name of the planter
    due_at     TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_verb_maturation_due ON verb_maturation (due_at);
