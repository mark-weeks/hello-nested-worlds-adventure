-- Sparse material reads skip conversational history at even the busiest node.
-- Indexes only: born rows, historical deltas, and all retained work stay intact.
CREATE INDEX idx_world_mutations_material_node
    ON world_mutations(world_seed, node_name, id DESC, node_version)
    WHERE delta IS NOT NULL;

-- Both world-wide epoch maps and one-node evidence reads skip non-renewal rows.
CREATE INDEX idx_world_mutations_rearms
    ON world_mutations(world_seed, node_name)
    WHERE mutation_type = 'PUZZLE_REARM';
