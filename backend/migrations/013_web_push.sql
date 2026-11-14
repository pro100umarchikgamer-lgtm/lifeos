-- Additive, opt-in Web Push. Provider endpoints/keys and queued content are encrypted.
CREATE TABLE IF NOT EXISTS web_push_keys (
 id TEXT PRIMARY KEY CHECK(id='v1'), secret BYTEA NOT NULL,
 public_key TEXT NOT NULL, created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS web_push_subscriptions (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
 device_id TEXT NOT NULL REFERENCES devices(id), endpoint_hash TEXT NOT NULL,
 secret BYTEA NOT NULL, created_at BIGINT NOT NULL, updated_at BIGINT NOT NULL,
 enabled BIGINT NOT NULL CHECK(enabled IN (0,1)), lead_minutes BIGINT NOT NULL CHECK(lead_minutes IN (5,15,30,60)),
 priority TEXT NOT NULL CHECK(priority IN ('high','normal')), timezone TEXT NOT NULL, error_code TEXT,
 scanned_until BIGINT NOT NULL DEFAULT 0,
 enabled_at BIGINT NOT NULL DEFAULT 0,
 UNIQUE(user_id,device_id,endpoint_hash)
);
CREATE INDEX IF NOT EXISTS web_push_active ON web_push_subscriptions(enabled,id);
CREATE TABLE IF NOT EXISTS web_push_deliveries (
 id TEXT PRIMARY KEY, subscription_id TEXT NOT NULL REFERENCES web_push_subscriptions(id) ON DELETE CASCADE,
 event_id TEXT REFERENCES records(id), event_revision BIGINT, occurrence_at BIGINT,
 created_at BIGINT NOT NULL, state TEXT NOT NULL CHECK(state IN ('queued','sending','accepted','displayed','suppressed','failed','cancelled')),
 attempts BIGINT NOT NULL DEFAULT 0, next_attempt BIGINT NOT NULL, leased_until BIGINT NOT NULL DEFAULT 0,
 expires_at BIGINT NOT NULL, payload BYTEA NOT NULL, receipt_hash TEXT NOT NULL,
 accepted_at BIGINT, displayed_at BIGINT, error_code TEXT,
 UNIQUE(subscription_id,event_id,occurrence_at)
);
CREATE INDEX IF NOT EXISTS web_push_queue ON web_push_deliveries(state,next_attempt,leased_until);
CREATE INDEX IF NOT EXISTS web_push_subscription_history ON web_push_deliveries(subscription_id,created_at);
