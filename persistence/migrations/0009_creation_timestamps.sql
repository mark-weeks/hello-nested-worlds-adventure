-- Creation timestamps for the three tables that couldn't answer "when did
-- this first exist": agent_memory, node_runtime_state, cost_budget.
--
-- SQLite's ADD COLUMN only allows constant defaults, so the columns are
-- added nullable and stamped by the insert paths going forward; rows that
-- already exist are backfilled with the migration time — an honest
-- approximation recorded before any production data exists.
ALTER TABLE agent_memory       ADD COLUMN created_at TEXT;
ALTER TABLE node_runtime_state ADD COLUMN created_at TEXT;
ALTER TABLE cost_budget        ADD COLUMN created_at TEXT;

UPDATE agent_memory       SET created_at = datetime('now') WHERE created_at IS NULL;
UPDATE node_runtime_state SET created_at = datetime('now') WHERE created_at IS NULL;
UPDATE cost_budget        SET created_at = datetime('now') WHERE created_at IS NULL;
