-- Operational community data only. Participant identity/rotation is owned by 0021.
CREATE TABLE community_ideas (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    member_id TEXT NOT NULL REFERENCES participants(id),
    request_id TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    title TEXT NOT NULL CHECK(length(title) <= 120),
    description TEXT NOT NULL CHECK(length(description) <= 2000),
    public_credit INTEGER NOT NULL DEFAULT 0 CHECK(public_credit IN (0,1)),
    status TEXT NOT NULL DEFAULT 'considering' CHECK(status IN
        ('considering','planned','in_progress','implemented','merged','available','deferred','declined','duplicate')),
    visibility TEXT NOT NULL DEFAULT 'visible' CHECK(visibility IN ('visible','hidden','withdrawn')),
    duplicate_id TEXT REFERENCES community_ideas(id),
    response TEXT NOT NULL DEFAULT '',
    availability TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE(member_id, request_id)
);
CREATE INDEX community_ideas_owner ON community_ideas(member_id, created_at);
CREATE INDEX community_ideas_visibility ON community_ideas(visibility, seq);
CREATE TABLE community_votes (
    idea_id TEXT NOT NULL REFERENCES community_ideas(id),
    member_id TEXT NOT NULL REFERENCES participants(id),
    PRIMARY KEY(idea_id, member_id)
);
-- Short-lived operational limits and stable ranking reconstruction; never analytics.
CREATE TABLE community_vote_events (
    id INTEGER PRIMARY KEY,
    idea_id TEXT,
    member_id TEXT NOT NULL,
    delta INTEGER NOT NULL,
    at INTEGER NOT NULL
);
CREATE INDEX community_vote_events_owner ON community_vote_events(member_id, at);
CREATE INDEX community_vote_events_idea ON community_vote_events(idea_id, at);
CREATE TABLE community_ip_writes (ip_hash TEXT NOT NULL, at INTEGER NOT NULL);
CREATE INDEX community_ip_writes_window ON community_ip_writes(ip_hash, at);
CREATE TABLE community_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE community_decisions (
    id INTEGER PRIMARY KEY,
    idea_id TEXT NOT NULL REFERENCES community_ideas(id),
    operator TEXT NOT NULL,
    status TEXT NOT NULL,
    visibility TEXT NOT NULL,
    explanation TEXT NOT NULL,
    at INTEGER NOT NULL
);
CREATE INDEX community_decisions_idea ON community_decisions(idea_id, id);
