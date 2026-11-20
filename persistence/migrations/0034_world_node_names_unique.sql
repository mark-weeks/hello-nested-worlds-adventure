-- ADR-041 D2: a node's name is unique within its world.
--
-- The generator already guarantees it (each level assigns its three-word
-- phrases one-to-one, and each level has its own final words), and the
-- birth path checks it before the insert (persistence.save_world_nodes).
-- This index is the database backstop, and it serves the name-to-address
-- lookup that replaces reading a position out of a name.
--
-- Additive: a new UNIQUE index; the non-unique idx_world_nodes_name from
-- 0013 is left in place. No stored row is rewritten. A world born under
-- generator version 2 cannot violate it: its names end in distinct path
-- digits.
CREATE UNIQUE INDEX IF NOT EXISTS idx_world_nodes_name_unique
    ON world_nodes (world_seed, name);
