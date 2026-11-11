-- Private USD accounting, independent of call-count buckets and world history.
-- A reservation accounts for its full verified upper bound before dispatch.
-- Its participant owner survives credential rotation; no credential is copied.
CREATE TABLE IF NOT EXISTS model_spend_reservations (
    id TEXT PRIMARY KEY NOT NULL,
    day TEXT NOT NULL,
    participant_id TEXT NOT NULL REFERENCES participants(id),
    task TEXT NOT NULL,
    adapter TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    requested_model TEXT NOT NULL,
    policy_json TEXT NOT NULL CHECK (json_valid(policy_json) AND json_type(policy_json) = 'object'),
    reserved_microusd INTEGER NOT NULL CHECK (typeof(reserved_microusd) = 'integer' AND reserved_microusd >= 0),
    accounted_microusd INTEGER NOT NULL CHECK (typeof(accounted_microusd) = 'integer' AND accounted_microusd >= 0),
    status TEXT NOT NULL CHECK (status IN ('reserved', 'settled', 'uncertain', 'anomaly')),
    usage_json TEXT CHECK (usage_json IS NULL OR (json_valid(usage_json) AND json_type(usage_json) = 'object')),
    resolved_model TEXT,
    created_at TEXT NOT NULL,
    settled_at TEXT,
    retention_days INTEGER NOT NULL CHECK (typeof(retention_days) = 'integer' AND retention_days >= 2),
    retain_until TEXT NOT NULL,
    CHECK ((status = 'reserved' AND settled_at IS NULL) OR (status <> 'reserved' AND settled_at IS NOT NULL)),
    CHECK ((status IN ('reserved', 'uncertain') AND accounted_microusd = reserved_microusd)
        OR (status = 'settled' AND accounted_microusd <= reserved_microusd)
        OR (status = 'anomaly' AND accounted_microusd >= reserved_microusd))
);
CREATE INDEX IF NOT EXISTS idx_model_spend_day_participant
    ON model_spend_reservations(day, participant_id, accounted_microusd);
CREATE INDEX IF NOT EXISTS idx_model_spend_retention
    ON model_spend_reservations(retain_until, day);

-- This singleton deliberately has no foreign key to a prunable reservation.
-- A restart, new UTC day, policy replacement or expired-row cleanup never
-- clears the circuit. There is no application reset operation.
CREATE TABLE IF NOT EXISTS model_spend_latch (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    latched_at TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (reason = 'billing_anomaly')
);
