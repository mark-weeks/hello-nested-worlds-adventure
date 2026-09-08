-- Existing payloads, ids and due times keep their legacy meaning. Completed
-- rows remain inspectable and are the duplicate-delivery fence. Stop all old
-- workers before upgrade: pre-M1 binaries do not filter the new status column.
ALTER TABLE causal_queue ADD COLUMN status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE causal_queue ADD COLUMN semantics_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE causal_queue ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE causal_queue ADD COLUMN last_error TEXT;
ALTER TABLE causal_queue ADD COLUMN retry_at TEXT;
ALTER TABLE causal_queue ADD COLUMN outcome TEXT;
ALTER TABLE causal_queue ADD COLUMN completed_at TEXT;
ALTER TABLE causal_queue ADD COLUMN parent_id INTEGER;
ALTER TABLE causal_queue ADD COLUMN source_event_id INTEGER;

ALTER TABLE verb_maturation ADD COLUMN status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE verb_maturation ADD COLUMN semantics_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE verb_maturation ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE verb_maturation ADD COLUMN last_error TEXT;
ALTER TABLE verb_maturation ADD COLUMN retry_at TEXT;
ALTER TABLE verb_maturation ADD COLUMN outcome TEXT;
ALTER TABLE verb_maturation ADD COLUMN completed_at TEXT;
ALTER TABLE verb_maturation ADD COLUMN source_event_id INTEGER;

CREATE INDEX idx_causal_pending ON causal_queue(due_at, id)
    WHERE status = 'pending';
CREATE INDEX idx_maturation_pending ON verb_maturation(due_at, id)
    WHERE status = 'pending';
