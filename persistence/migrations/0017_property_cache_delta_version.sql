-- Complete the rollback marker with the material chronicle head. The prior
-- binary can apply a born-key tombstone while leaving a bare '{}' patch blob
-- unchanged; delta_version makes that write visible after re-upgrade.
ALTER TABLE node_property_cache_meta
    ADD COLUMN delta_version INTEGER NOT NULL DEFAULT 0;
