CREATE TABLE IF NOT EXISTS account_state(user_id TEXT PRIMARY KEY REFERENCES users(id),disabled_until BIGINT NOT NULL DEFAULT 0,deleted_at BIGINT NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),family_id TEXT NOT NULL UNIQUE,label TEXT NOT NULL,created_at BIGINT NOT NULL,last_seen_at BIGINT NOT NULL,revoked_at BIGINT NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS session_devices(hash TEXT PRIMARY KEY REFERENCES sessions(hash) ON DELETE CASCADE,device_id TEXT NOT NULL REFERENCES devices(id));
CREATE TABLE IF NOT EXISTS refresh_tokens(hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),device_id TEXT NOT NULL REFERENCES devices(id),family_id TEXT NOT NULL,expires_at BIGINT NOT NULL,used_at BIGINT NOT NULL DEFAULT 0,revoked_at BIGINT NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS device_user_active ON devices(user_id,revoked_at);
CREATE INDEX IF NOT EXISTS refresh_family ON refresh_tokens(family_id);
