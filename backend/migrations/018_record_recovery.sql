CREATE TABLE IF NOT EXISTS record_recovery_requests (
 id TEXT PRIMARY KEY,
 user_id TEXT NOT NULL REFERENCES users(id),
 workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 record_id TEXT NOT NULL REFERENCES records(id),
 kind TEXT NOT NULL,
 record_revision BIGINT NOT NULL,
 consent_hash TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('pending','approved','rejected','cancelled','completed')),
 revision BIGINT NOT NULL DEFAULT 1,
 created_at BIGINT NOT NULL,
 expires_at BIGINT NOT NULL,
 approved_at BIGINT NOT NULL DEFAULT 0,
 approved_by TEXT,
 completed_at BIGINT NOT NULL DEFAULT 0,
 decision_reason TEXT NOT NULL DEFAULT '',
 grant_hash TEXT NOT NULL DEFAULT '',
 grant_expires_at BIGINT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS record_recovery_user ON record_recovery_requests(user_id,created_at,id);
CREATE INDEX IF NOT EXISTS record_recovery_queue ON record_recovery_requests(created_at,id);
