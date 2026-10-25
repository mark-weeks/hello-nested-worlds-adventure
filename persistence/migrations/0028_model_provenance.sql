-- Which text provider and resolved model produced a model-written chronicle
-- row. A side table, not new columns on world_mutations: the chronicle's
-- row image stays append-only and readable by an older column list, and
-- redaction of human-authored words cannot touch this record.
--
-- No row means nothing is recorded. Historical rows are not backfilled
-- (unknown, not a claim that no model spoke). Rows written without a model
-- call record none. Both columns are nullable and have no default, so a
-- present row never invents a provider or a model the call result omitted.

CREATE TABLE IF NOT EXISTS mutation_model_provenance (
    mutation_id    INTEGER PRIMARY KEY,
    provider       TEXT,
    resolved_model TEXT
);
