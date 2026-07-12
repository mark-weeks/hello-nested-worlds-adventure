-- ADR-004 §7: every player has a unique name; nobody plays anonymously.
-- The registered name on a per-user invite key becomes the player's
-- authoritative display name (server-derived at runtime), so it must be
-- unique. Enforce uniqueness case-insensitively and whitespace-insensitively
-- at the database, as the atomic backstop to the application-level check in
-- persistence.mint_invite_key.
--
-- Additive: a new UNIQUE index (the existing non-unique idx_invite_keys_name
-- is left in place). Pre-launch, so no real duplicate names exist and a fresh
-- or already-unique invite_keys table indexes cleanly; the app-level check
-- keeps this from ever being hit in normal operation.
CREATE UNIQUE INDEX IF NOT EXISTS idx_invite_keys_name_unique
    ON invite_keys (lower(trim(name)));
