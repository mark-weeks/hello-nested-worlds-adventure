-- Owner sanctions on a player (beta checklist G5): a suspension for a set
-- time or a ban, each recorded with a reason, and a lift that ends one early.
--
-- Keyed to participants.id (migration 0021), never to a credential. Rotating
-- a key neither escapes nor erases a sanction, and once a sanction ends the
-- same credential resolves to the same participant again, journal and
-- profile intact. A credential whose participant holds an active sanction is
-- not live (persistence._UNSANCTIONED). The invite gate's latch reads only
-- invite_keys and registration_tokens, so no sanction can reopen it.
--
-- Insert-only from application code, in the style of world_meta (0015):
-- persistence.sanctions exposes no update or delete. A sanction ends at its
-- expiry or by a sanction_lifts row, and neither table is rewritten. Nothing
-- here is written to world_mutations.
--
-- Reasons are private operator data. They are never shown to the sanctioned
-- player and never logged, but they enter every backup of this database.
--
-- Timestamps use datetime('now')'s UTC 'YYYY-MM-DD HH:MM:SS' form, which the
-- CHECKs below enforce, so text comparison against datetime('now') is a time
-- comparison. Foreign keys are off in this process, so persistence.sanctions
-- checks that the participant and the sanction exist before it inserts.
--
-- Additive only, per the continuity policy.
CREATE TABLE IF NOT EXISTS sanctions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    participant_id TEXT    NOT NULL REFERENCES participants(id),
    kind           TEXT    NOT NULL CHECK (kind IN ('suspension', 'ban')),
    reason         TEXT    NOT NULL
                           CHECK (trim(reason, ' ' || char(9, 10, 13)) <> ''),
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
                           CHECK (created_at IS datetime(created_at)),
    expires_at     TEXT    CHECK (expires_at IS datetime(expires_at)),
    -- A suspension ends at a stated time after it began. A ban has no end.
    CHECK ((kind = 'suspension' AND expires_at IS NOT NULL
                                AND expires_at > created_at)
        OR (kind = 'ban' AND expires_at IS NULL))
);

CREATE INDEX IF NOT EXISTS idx_sanctions_participant
    ON sanctions (participant_id);

-- At most one lift per sanction (the primary key). Lifting is the reversal.
-- The sanction row itself is kept as the record of what was decided.
CREATE TABLE IF NOT EXISTS sanction_lifts (
    sanction_id INTEGER PRIMARY KEY REFERENCES sanctions(id),
    reason      TEXT    NOT NULL
                        CHECK (trim(reason, ' ' || char(9, 10, 13)) <> ''),
    lifted_at   TEXT    NOT NULL DEFAULT (datetime('now'))
                        CHECK (lifted_at IS datetime(lifted_at))
);
