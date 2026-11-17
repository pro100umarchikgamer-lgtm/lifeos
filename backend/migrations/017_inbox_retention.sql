-- Dedup metadata outlives capped visible history through the budget period.
CREATE TABLE IF NOT EXISTS budget_inbox_sources (
 user_id TEXT NOT NULL REFERENCES users(id), source_key TEXT NOT NULL,
 expires_at BIGINT NOT NULL, PRIMARY KEY(user_id,source_key)
);
CREATE INDEX IF NOT EXISTS budget_inbox_source_expiry ON budget_inbox_sources(user_id,expires_at);
