-- Per-user invite keys for the hosted beta. Each row is a key issued to a
-- single tester so the operator can attribute usage and revoke individual
-- access without rotating the shared NESTED_WORLDS_BETA_KEY for everyone.
--
-- The shared env-var key (server/guard.py) still works in parallel; this
-- table is consulted first, and a successful lookup overrides the shared
-- key check. A key is considered valid only when revoked_at IS NULL.

CREATE TABLE IF NOT EXISTS invite_keys (
    key           TEXT    PRIMARY KEY,
    name          TEXT    NOT NULL,
    note          TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    revoked_at    TEXT,
    last_used_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_invite_keys_name ON invite_keys (name);
