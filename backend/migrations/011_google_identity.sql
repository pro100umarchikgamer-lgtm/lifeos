CREATE TABLE IF NOT EXISTS google_identities (
 subject TEXT PRIMARY KEY, user_id TEXT NOT NULL UNIQUE REFERENCES users(id),
 created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS account_credentials (
 user_id TEXT PRIMARY KEY REFERENCES users(id), has_password BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS oauth_challenges (
 hash TEXT PRIMARY KEY, client TEXT NOT NULL, agent_hash TEXT NOT NULL,
 binding_hash TEXT NOT NULL, payload BYTEA NOT NULL,
 user_id TEXT REFERENCES users(id), expires_at BIGINT NOT NULL,
 used_at BIGINT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS oauth_challenges_expiry ON oauth_challenges(expires_at);

CREATE TABLE IF NOT EXISTS oauth_web_results (
 hash TEXT PRIMARY KEY, agent_hash TEXT NOT NULL, binding_hash TEXT NOT NULL,
 payload BYTEA NOT NULL, expires_at BIGINT NOT NULL
);
