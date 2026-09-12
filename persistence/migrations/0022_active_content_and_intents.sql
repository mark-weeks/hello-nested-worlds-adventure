-- First-use definitions remain available through later code/content releases.
CREATE TABLE puzzle_instances (
    world_seed INTEGER NOT NULL,
    node_name TEXT NOT NULL,
    epoch INTEGER NOT NULL,
    definition_version INTEGER NOT NULL,
    definition TEXT NOT NULL,
    evidence TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY(world_seed,node_name,epoch)
);
-- Optional HTTP intent identity is distinct from a queue's delivery identity.
CREATE TABLE request_receipts (
    participant_id TEXT NOT NULL,
    world_seed INTEGER NOT NULL,
    operation TEXT NOT NULL,
    request_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    response TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY(participant_id,world_seed,operation,request_id)
);
