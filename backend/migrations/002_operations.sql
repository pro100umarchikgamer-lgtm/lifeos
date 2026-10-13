CREATE TABLE email_jobs(id TEXT PRIMARY KEY,payload BYTEA NOT NULL,expires_at BIGINT NOT NULL,next_attempt BIGINT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,leased_until BIGINT NOT NULL DEFAULT 0,delivered_at BIGINT,last_error TEXT);
CREATE INDEX email_due ON email_jobs(next_attempt) WHERE delivered_at IS NULL;
CREATE INDEX session_expiry ON sessions(expires_at);
CREATE INDEX verification_expiry ON verification(expires_at);
CREATE INDEX recovery_expiry ON password_recovery(expires_at);
CREATE TABLE http_limits(key TEXT PRIMARY KEY,count BIGINT NOT NULL,until_at BIGINT NOT NULL);
CREATE TABLE worker_health(name TEXT PRIMARY KEY,last_seen BIGINT NOT NULL);
