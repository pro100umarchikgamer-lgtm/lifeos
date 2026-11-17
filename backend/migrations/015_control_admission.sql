CREATE TABLE IF NOT EXISTS control_handoffs (
 hash TEXT PRIMARY KEY,
 parent_hash TEXT NOT NULL REFERENCES web_sessions(hash) ON DELETE CASCADE,
 agent_hash TEXT NOT NULL,
 expires_at BIGINT NOT NULL,
 used_at BIGINT NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS control_admissions (
 hash TEXT PRIMARY KEY,
 parent_hash TEXT NOT NULL REFERENCES web_sessions(hash) ON DELETE CASCADE,
 agent_hash TEXT NOT NULL,
 expires_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS control_handoffs_expiry ON control_handoffs(expires_at);
CREATE INDEX IF NOT EXISTS control_admissions_expiry ON control_admissions(expires_at);
