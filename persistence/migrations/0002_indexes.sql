-- Hot-path indexes. Without these, get_node_history and get_mutations both
-- table-scan world_mutations as the table grows; get_agent_runs scans
-- agent_runs. node_runtime_state and agent_memory both have composite
-- primary keys whose leading prefixes already cover their lookups, so
-- they don't need separate indexes here.

CREATE INDEX IF NOT EXISTS idx_world_mutations_seed_node
    ON world_mutations (world_seed, node_name);

CREATE INDEX IF NOT EXISTS idx_world_mutations_seed_time
    ON world_mutations (world_seed, recorded_at);

CREATE INDEX IF NOT EXISTS idx_agent_runs_seed
    ON agent_runs (world_seed, started_at);
