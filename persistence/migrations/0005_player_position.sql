-- Cross-device resume: remember where each tester left off, keyed on their
-- per-user invite key (the stable identity the app already has). Because these
-- columns live on invite_keys, server-side resume is naturally scoped to
-- per-user keys only — a shared-key or no-key session has no row here, so the
-- write no-ops and the client falls back to its own localStorage cache.
--
-- last_node is the node the player last stood on; the four world columns pin the
-- world it belonged to (the node only exists in that specific generated tree),
-- so a returning player on any device reopens the same world at the same node.

ALTER TABLE invite_keys ADD COLUMN last_node        TEXT;
ALTER TABLE invite_keys ADD COLUMN last_seed        INTEGER;
ALTER TABLE invite_keys ADD COLUMN last_depth       INTEGER;
ALTER TABLE invite_keys ADD COLUMN last_min_breadth INTEGER;
ALTER TABLE invite_keys ADD COLUMN last_max_breadth INTEGER;
ALTER TABLE invite_keys ADD COLUMN last_node_at     TEXT;
