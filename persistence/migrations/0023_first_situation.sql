-- One authored situation in existing geography; no topology or birth-row edits.
CREATE TABLE situations (
    id TEXT PRIMARY KEY,
    world_seed INTEGER NOT NULL,
    slug TEXT NOT NULL,
    definition_version INTEGER NOT NULL,
    definition TEXT NOT NULL,
    phase TEXT NOT NULL DEFAULT 'investigate',
    deadline TEXT,
    branch TEXT,
    opened_event_id INTEGER,
    commitment_event_id INTEGER,
    outcome_event_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(world_seed,slug)
);
CREATE TABLE situation_choices (
    situation_id TEXT NOT NULL REFERENCES situations(id),
    participant_id TEXT NOT NULL REFERENCES participants(id),
    branch TEXT NOT NULL,
    PRIMARY KEY(situation_id,participant_id)
);
CREATE TABLE situation_discoveries (
    situation_id TEXT NOT NULL REFERENCES situations(id),
    participant_id TEXT NOT NULL REFERENCES participants(id),
    node_name TEXT NOT NULL,
    PRIMARY KEY(situation_id,participant_id,node_name)
);
CREATE TABLE situation_work (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    situation_id TEXT NOT NULL REFERENCES situations(id),
    step INTEGER NOT NULL,
    due_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    retry_at TEXT,
    last_error TEXT,
    event_id INTEGER,
    UNIQUE(situation_id,step)
);
CREATE INDEX situation_work_due ON situation_work(status,due_at);
CREATE TABLE situation_followups (
    situation_id TEXT NOT NULL REFERENCES situations(id),
    participant_id TEXT NOT NULL REFERENCES participants(id),
    event_id INTEGER NOT NULL,
    PRIMARY KEY(situation_id,participant_id)
);
