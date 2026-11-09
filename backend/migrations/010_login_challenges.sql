CREATE TABLE IF NOT EXISTS login_challenges (
 hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
 scope TEXT NOT NULL, agent_hash TEXT NOT NULL, credential_version TEXT NOT NULL,
 expires_at BIGINT NOT NULL, attempts BIGINT NOT NULL DEFAULT 0,
 used_at BIGINT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS login_challenges_user ON login_challenges(user_id,scope);
