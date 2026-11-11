-- Private, reversible live-chat/presence preferences. These are operational
-- participant data, never world history; credential rotation preserves them.
-- A target is either a participant ID or a namespaced server-owned agent ID.
-- Agents are validated against agents.identities in application code rather
-- than enrolled as credentialed participants or written into world history.
CREATE TABLE IF NOT EXISTS participant_blocks (
    participant_id TEXT NOT NULL REFERENCES participants(id),
    blocked_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (participant_id, blocked_id),
    CHECK (participant_id <> blocked_id)
);
