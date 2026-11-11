-- Private acknowledgements for an explicitly declared temporary test world.
-- Ownership follows the participant across credential rotation. A revised
-- notice requires a separate acknowledgement; no fictional history is changed.
CREATE TABLE IF NOT EXISTS participation_consents (
    participant_id TEXT NOT NULL REFERENCES participants(id),
    revision TEXT NOT NULL,
    notice_json TEXT NOT NULL,
    accepted_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (participant_id, revision)
);
