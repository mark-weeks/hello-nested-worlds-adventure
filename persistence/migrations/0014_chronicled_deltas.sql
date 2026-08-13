-- Chronicled deltas (ADR-009): the chronicle learns to remember state,
-- not just events. Three additive columns on world_mutations:
--
--   strength     — the triggering causal event's (dampened) strength.
--                  Exactly one chronicle row per fired event carries it,
--                  so ripple-at-T is a pure fold of the record.
--   delta        — the RFC 7396 merge patch this event applied to the
--                  node's property overlay, stored at write time (never
--                  recomputed at read time — the era-names lesson).
--   node_version — per-node monotonic fold order, allocated inside the
--                  atomic write. recorded_at is second-precision and
--                  cannot order non-commutative patches sharing a
--                  timestamp; this can.
--
-- Additive only, per the continuity policy: historical rows stay NULL.

ALTER TABLE world_mutations ADD COLUMN strength REAL;
ALTER TABLE world_mutations ADD COLUMN delta TEXT;
ALTER TABLE world_mutations ADD COLUMN node_version INTEGER;

-- The fold reads (world_seed, node_name) in node_version order, and the
-- atomic write allocates MAX(node_version) + 1 under the same key.
CREATE INDEX IF NOT EXISTS idx_world_mutations_node_version
    ON world_mutations (world_seed, node_name, node_version);
