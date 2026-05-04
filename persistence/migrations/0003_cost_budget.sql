-- Daily call counters for paid external APIs. One row per (bucket, UTC day);
-- the server peeks the row before each Anthropic / fal.ai call and bumps it
-- after a successful response. Bucket values are 'anthropic' and 'fal_ai'.

CREATE TABLE IF NOT EXISTS cost_budget (
    bucket TEXT    NOT NULL,
    day    TEXT    NOT NULL,
    calls  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (bucket, day)
);
