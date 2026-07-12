-- Per-user invite keys for the hosted beta. Each row is a key issued to a
-- single tester so the operator can attribute usage and revoke individual
-- access. This table is the whole invite gate (server/guard.py): there is no
-- shared key. A key is considered valid only when revoked_at IS NULL.

CREATE TABLE IF NOT EXISTS invite_keys (
    key           TEXT    PRIMARY KEY,
    name          TEXT    NOT NULL,
    note          TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    revoked_at    TEXT,
    last_used_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_invite_keys_name ON invite_keys (name);
