CREATE TABLE IF NOT EXISTS early_access (
 id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE,
 state TEXT NOT NULL CHECK(state IN ('unverified','pending','approved','rejected','cancelled')),
 created_at BIGINT NOT NULL, updated_at BIGINT NOT NULL,
 consent_version TEXT NOT NULL, verified_at BIGINT NOT NULL DEFAULT 0,
 verification_hash TEXT, verification_until BIGINT NOT NULL DEFAULT 0,
 management_hash TEXT, management_until BIGINT NOT NULL DEFAULT 0,
 invitation_hash TEXT, invitation_until BIGINT NOT NULL DEFAULT 0,
 revision INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS early_access_queue ON early_access(state,created_at,id);

CREATE TABLE IF NOT EXISTS early_access_limits (key TEXT PRIMARY KEY, count INTEGER NOT NULL, until_at BIGINT NOT NULL);
