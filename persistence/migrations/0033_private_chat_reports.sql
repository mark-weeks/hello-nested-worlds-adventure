-- Private operational records, deliberately separate from world_mutations.
CREATE TABLE IF NOT EXISTS community_policies (
    digest TEXT PRIMARY KEY NOT NULL CHECK (length(digest) = 64),
    snapshot_json TEXT NOT NULL CHECK (json_valid(snapshot_json) AND json_type(snapshot_json) = 'object'),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS private_chat_messages (
    id INTEGER PRIMARY KEY,
    evidence_ref TEXT UNIQUE NOT NULL CHECK (length(evidence_ref) = 32),
    world_seed INTEGER NOT NULL,
    node_name TEXT NOT NULL,
    participant_id TEXT REFERENCES participants(id),
    session_id TEXT NOT NULL,
    name TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    retention_days INTEGER,
    policy_digest TEXT NOT NULL REFERENCES community_policies(digest),
    CHECK (expires_at IS NULL AND retention_days IS NULL)
);
CREATE INDEX IF NOT EXISTS idx_private_chat_expiry ON private_chat_messages(expires_at);
CREATE INDEX IF NOT EXISTS idx_private_chat_world_time ON private_chat_messages(world_seed,created_at);
CREATE INDEX IF NOT EXISTS idx_private_chat_policy ON private_chat_messages(policy_digest);

CREATE TABLE IF NOT EXISTS private_reports (
    id TEXT PRIMARY KEY NOT NULL CHECK (length(id) = 32),
    reporter_participant_id TEXT NOT NULL REFERENCES participants(id),
    request_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL CHECK (length(fingerprint) = 64),
    world_seed INTEGER NOT NULL,
    target_id TEXT,
    target_session_id TEXT,
    reason TEXT NOT NULL CHECK (reason IN ('harassment','harmful_content','spam','other')),
    detail TEXT NOT NULL CHECK (length(detail) <= 2000),
    -- No FK to chat: explicit deletion and report retention are separate.
    evidence_ref TEXT,
    evidence_expires_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('open','acknowledged','closed')),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    retention_days INTEGER NOT NULL CHECK (typeof(retention_days) = 'integer' AND retention_days >= 1),
    policy_digest TEXT NOT NULL REFERENCES community_policies(digest),
    UNIQUE (reporter_participant_id,request_id),
    CHECK (target_id IS NOT NULL OR evidence_ref IS NOT NULL),
    CHECK (evidence_ref IS NOT NULL OR evidence_expires_at IS NULL),
    CHECK (expires_at > created_at)
);
CREATE INDEX IF NOT EXISTS idx_private_reports_queue ON private_reports(status,expires_at,created_at);
CREATE INDEX IF NOT EXISTS idx_private_reports_expiry ON private_reports(expires_at);
CREATE INDEX IF NOT EXISTS idx_private_reports_policy ON private_reports(policy_digest);
CREATE INDEX IF NOT EXISTS idx_private_reports_evidence_hold ON private_reports(evidence_ref,status);

CREATE TABLE IF NOT EXISTS report_actions (
    id TEXT PRIMARY KEY NOT NULL CHECK (length(id) = 32),
    report_id TEXT NOT NULL REFERENCES private_reports(id),
    action TEXT NOT NULL CHECK (action IN ('acknowledge','close')),
    operator TEXT NOT NULL,
    note TEXT NOT NULL CHECK (length(note) <= 2000),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_report_actions_case ON report_actions(report_id,created_at,id);
CREATE INDEX IF NOT EXISTS idx_report_actions_expiry ON report_actions(expires_at);

-- Opaque proof of completed erasure. No message, name or participant text.
CREATE TABLE IF NOT EXISTS private_chat_deletions (
    evidence_ref TEXT PRIMARY KEY NOT NULL CHECK (length(evidence_ref) = 32),
    deleted_at TEXT NOT NULL
);
