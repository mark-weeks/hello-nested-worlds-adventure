-- V1 compositional interventions: immutable acceptance plus retained delivery fences.
CREATE TABLE IF NOT EXISTS interventions (
    id TEXT PRIMARY KEY,
    world_seed INTEGER NOT NULL,
    participant_id TEXT NOT NULL,
    node_name TEXT NOT NULL,
    version INTEGER NOT NULL,
    plan TEXT NOT NULL,
    signal TEXT NOT NULL,
    route TEXT NOT NULL,
    performer TEXT NOT NULL,
    source_event_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_interventions_participant ON interventions(participant_id,world_seed,created_at);
CREATE TABLE IF NOT EXISTS intervention_work (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    intervention_id TEXT NOT NULL REFERENCES interventions(id),
    hop INTEGER NOT NULL,
    node_name TEXT NOT NULL,
    due_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    event_id INTEGER,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    retry_at TEXT,
    UNIQUE(intervention_id,hop)
);
CREATE INDEX IF NOT EXISTS idx_intervention_work_due ON intervention_work(status,due_at,id);
