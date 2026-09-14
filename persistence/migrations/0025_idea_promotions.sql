-- A retained local intent is the fence between SQLite and remote publication.
CREATE TABLE community_promotions (
    idea_id TEXT PRIMARY KEY REFERENCES community_ideas(id),
    token TEXT NOT NULL UNIQUE,
    repository TEXT NOT NULL,
    public_title TEXT NOT NULL,
    brief TEXT NOT NULL,
    review_hash TEXT NOT NULL,
    reviewed_by TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('prepared','publishing','uncertain','published','cancelled')),
    issue_number INTEGER,
    issue_url TEXT,
    last_error TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE(repository, issue_number)
);
CREATE TABLE community_promotion_events (
    id INTEGER PRIMARY KEY,
    idea_id TEXT NOT NULL REFERENCES community_ideas(id),
    operator TEXT NOT NULL,
    action TEXT NOT NULL,
    at INTEGER NOT NULL
);
CREATE INDEX community_promotion_events_idea ON community_promotion_events(idea_id,id);
