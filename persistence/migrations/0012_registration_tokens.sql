-- Self-service registration tokens (ADR-004 §7 follow-up). An operator mints
-- a token and shares /register?invite=<token>; the PLAYER then picks their own
-- unique name, and redemption mints their per-user invite key. Registration
-- stays invite-gated: no token, no account — the beta remains a closed cohort.
--
-- Single-use: a token is valid iff redeemed_at IS NULL AND revoked_at IS NULL.
-- Redemption stamps redeemed_at + redeemed_name (audit: which account this
-- invite became). The play key itself lives only in invite_keys — this table
-- never stores a live credential. Additive only; no existing table changes.

CREATE TABLE IF NOT EXISTS registration_tokens (
    token         TEXT    PRIMARY KEY,
    note          TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    redeemed_at   TEXT,
    redeemed_name TEXT,
    revoked_at    TEXT
);
