-- Optional read-only budget alerts evaluated on inbox refresh, without push.
CREATE TABLE IF NOT EXISTS inbox_settings (
 user_id TEXT PRIMARY KEY REFERENCES users(id),
 budget_enabled BIGINT NOT NULL DEFAULT 0 CHECK(budget_enabled IN (0,1)),
 budget_thresholds TEXT NOT NULL DEFAULT '[50,80,100]', timezone TEXT NOT NULL DEFAULT 'UTC'
);
CREATE TABLE IF NOT EXISTS budget_inbox_notifications (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), source_key TEXT NOT NULL,
 title TEXT NOT NULL, body TEXT NOT NULL, link TEXT NOT NULL DEFAULT '',
 created_at BIGINT NOT NULL, starts_at BIGINT NOT NULL, expires_at BIGINT NOT NULL,
 read_at BIGINT NOT NULL DEFAULT 0, dismissed_at BIGINT NOT NULL DEFAULT 0,
 presented_at BIGINT NOT NULL DEFAULT 0, UNIQUE(user_id,source_key)
);
CREATE INDEX IF NOT EXISTS budget_inbox_user_history ON budget_inbox_notifications(user_id,created_at,id);
