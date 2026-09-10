-- M4 policy metadata only. No rewrite of discovery, context or world history.
ALTER TABLE agent_memory ADD COLUMN scan_cursor TEXT;

CREATE TABLE agent_attention (
    world_seed INTEGER NOT NULL,
    agent_name TEXT NOT NULL,
    node_name TEXT NOT NULL,
    change_id INTEGER NOT NULL DEFAULT -1,
    puzzle_epoch INTEGER NOT NULL DEFAULT -1,
    PRIMARY KEY (world_seed, agent_name, node_name)
);

CREATE INDEX idx_attention_changes ON world_mutations(world_seed, id)
    WHERE delta IS NOT NULL OR mutation_type='PUZZLE_REARM';
