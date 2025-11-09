CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS repositories (
    repo_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    name TEXT NOT NULL,
    owner_login TEXT NOT NULL,
    stars BIGINT NOT NULL,
    url TEXT,
    metadata JSONB,
    last_scraped TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS repo_star_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repo_id TEXT NOT NULL REFERENCES repositories(repo_id) ON DELETE CASCADE,
    stars BIGINT NOT NULL,
    snapshot_at DATE NOT NULL,
    UNIQUE (repo_id, snapshot_at)
);
