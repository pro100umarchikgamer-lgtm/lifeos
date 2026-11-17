-- Session-bound, single-use Google reauthentication; no provider tokens stored.
ALTER TABLE email_jobs ADD COLUMN IF NOT EXISTS user_id TEXT REFERENCES users(id);
-- Classify old freeform events without inspecting or rewriting their chain.
ALTER TABLE control_audit ADD COLUMN IF NOT EXISTS format_version BIGINT NOT NULL DEFAULT 1;
CREATE TABLE IF NOT EXISTS account_reauth_grants (
 hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
 auth_hash TEXT NOT NULL, credential_version TEXT NOT NULL,
 expires_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS account_reauth_expiry ON account_reauth_grants(expires_at);
-- UUIDs only. Export outside database archives and reapply before restored APIs
-- or workers start; deliberately has no FK to a potentially older restored DB.
CREATE TABLE IF NOT EXISTS account_erasure_ledger (
 user_id TEXT PRIMARY KEY, erased_at BIGINT NOT NULL
);
-- A generic, immutable account shell can anchor another participant's transfer.
CREATE TABLE IF NOT EXISTS erased_financial_stubs (
 record_id TEXT PRIMARY KEY REFERENCES records(id), erased_at BIGINT NOT NULL
);
-- Detailed staff rationale is erasable and bounded; never hash it into the
-- immutable security event chain. Existing chain entries remain untouched.
CREATE TABLE IF NOT EXISTS control_audit_notes (
 entry_id TEXT PRIMARY KEY REFERENCES control_audit(id), subject_id TEXT,
 actor_id TEXT NOT NULL, note BYTEA NOT NULL, expires_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS control_audit_notes_expiry ON control_audit_notes(expires_at);
