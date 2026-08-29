-- Immutable world metadata (ADR-008): first-selection records that, once
-- written, ARE the fact they record — beginning with the wrap passage's
-- hinge particle. A row here mirrors the world_nodes discipline: the
-- stored value is the identity, and nothing in application code may
-- rewrite it (persistence exposes no update or delete for this table;
-- pin_world_meta refuses to overwrite).
--
-- Additive only, per the continuity policy.
CREATE TABLE IF NOT EXISTS world_meta (
    world_seed  INTEGER NOT NULL,
    key         TEXT    NOT NULL,
    value       TEXT    NOT NULL,
    recorded_at TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (world_seed, key)
);
