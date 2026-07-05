-- Actor identity on the chronicle: a stable, credential-derived key for
-- WHO did each thing, independent of the mutable display name.
--
-- player_name remains the human-readable label (user-supplied, ≤32 chars,
-- renameable, non-unique). actor_identity is the durable key: for requests
-- carrying a per-user invite credential it is sha256(key)[:16] — the same
-- scheme the conversation transcripts and the cost ledger already use, so
-- all three are cross-referenceable — otherwise the display name, otherwise
-- NULL. Additive per the continuity policy; historical rows stay NULL.
ALTER TABLE world_mutations ADD COLUMN actor_identity TEXT;
