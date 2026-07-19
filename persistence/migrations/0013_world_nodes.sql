-- The world, materialized (ADR-006, Option A — ratified 2026-07-19).
--
-- Rows are BORN once per (world_seed) — the generator runs exactly once
-- per seed as a birthing tool — and are never rewritten by generation
-- again. From this migration on, the stored row is the node's identity
-- and the content banks govern only the birth of not-yet-born worlds:
-- editing a bank can no longer rename or reshape any world that already
-- exists (pinned by tests/test_world_store.py::TestBankEditImmunity).
--
-- Additive only, per the continuity policy. `path` is the node's child
-- ordinals from the root, dot-joined ("1.2.3"); ordinals are single-digit
-- by the generator's MAX_GENERATOR_BREADTH, and every name carries the
-- same path as its digit suffix, so existing chronicle rows (keyed on
-- names) map onto these rows with no data migration.
CREATE TABLE IF NOT EXISTS world_nodes (
    world_seed        INTEGER NOT NULL,
    path              TEXT    NOT NULL,
    name              TEXT    NOT NULL,
    level             TEXT    NOT NULL,
    properties        TEXT    NOT NULL,          -- JSON object, born values
    breadth           INTEGER NOT NULL,          -- child count born with
    generator_version INTEGER NOT NULL,
    born_at           TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (world_seed, path)
);

CREATE INDEX IF NOT EXISTS idx_world_nodes_name
    ON world_nodes (world_seed, name);
