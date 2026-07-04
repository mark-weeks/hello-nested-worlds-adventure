-- Causal events now change node substance (see multiverse/effects.py).
-- The changed properties persist as a JSON overlay per (world_seed,
-- node_name), applied on top of the deterministic generation at every
-- world rebuild — the mechanism by which the world durably evolves.
ALTER TABLE node_runtime_state ADD COLUMN properties TEXT;
