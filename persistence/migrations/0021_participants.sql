-- Credentials can change; participant-owned data keeps the same owner.
-- Existing historical actor hashes and invite records are not rewritten.
CREATE TABLE participants (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE participant_credentials (
    credential_digest TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL REFERENCES participants(id),
    actor_identity TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    replaced_at TEXT
);
CREATE INDEX participant_credentials_owner ON participant_credentials(participant_id);
CREATE INDEX participant_credentials_actor ON participant_credentials(actor_identity);
CREATE TABLE participant_profiles (
    participant_id TEXT PRIMARY KEY REFERENCES participants(id),
    bio TEXT NOT NULL DEFAULT '',
    goals TEXT NOT NULL DEFAULT '',
    avatar TEXT NOT NULL DEFAULT 'lantern',
    published INTEGER NOT NULL DEFAULT 0,
    home_seed INTEGER,
    home_node TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE journal_notes (
    id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL REFERENCES participants(id),
    world_seed INTEGER NOT NULL,
    node_name TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX journal_owner_world ON journal_notes(participant_id, world_seed, updated_at);
