-- Keep node_runtime_state.properties as a plain JSON object so the previous
-- binary can hydrate it after rollback. Metadata lives beside the cache:
-- properties_blob is the initial exact marker. Migration 0017 adds the
-- chronicle-head half without rewriting this already-applied migration.
CREATE TABLE IF NOT EXISTS node_property_cache_meta (
    world_seed       INTEGER NOT NULL,
    node_name        TEXT    NOT NULL,
    cache_format     INTEGER NOT NULL,
    properties_blob  TEXT    NOT NULL,
    legacy_baseline  TEXT    NOT NULL DEFAULT '{}',
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (world_seed, node_name)
);
