-- V1 rows keep their absolute patches and all delivery metadata unchanged.
ALTER TABLE verb_maturation ADD COLUMN operation TEXT;
ALTER TABLE verb_maturation ADD COLUMN actor_identity TEXT;
CREATE INDEX idx_maturation_node_pending
    ON verb_maturation(world_seed, node_name, verb, id) WHERE status = 'pending';
