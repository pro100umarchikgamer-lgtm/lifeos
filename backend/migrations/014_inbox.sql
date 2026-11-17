-- Account-scoped history. No push provider, delivery or auth tables are replaced.
CREATE TABLE IF NOT EXISTS inbox_notifications (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
 source_key TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('reminder','test')),
 title TEXT NOT NULL, body TEXT NOT NULL, link TEXT NOT NULL DEFAULT '',
 created_at BIGINT NOT NULL, starts_at BIGINT NOT NULL, expires_at BIGINT NOT NULL,
 read_at BIGINT NOT NULL DEFAULT 0, dismissed_at BIGINT NOT NULL DEFAULT 0,
 presented_at BIGINT NOT NULL DEFAULT 0,
 UNIQUE(user_id,source_key)
);
CREATE INDEX IF NOT EXISTS inbox_user_history ON inbox_notifications(user_id,created_at,id);
CREATE TABLE IF NOT EXISTS announcements (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
 presentation TEXT NOT NULL CHECK(presentation IN ('inbox','banner','fullscreen')),
 audience TEXT NOT NULL CHECK(audience IN ('users','all')),
 link TEXT NOT NULL DEFAULT '', starts_at BIGINT NOT NULL, expires_at BIGINT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('draft','published','cancelled')),
 revision BIGINT NOT NULL DEFAULT 1, created_at BIGINT NOT NULL,
 published_at BIGINT NOT NULL DEFAULT 0, cancelled_at BIGINT NOT NULL DEFAULT 0,
 created_by TEXT NOT NULL REFERENCES staff(id)
);
CREATE INDEX IF NOT EXISTS announcement_history ON announcements(state,published_at,id);
-- Draft users audiences are explicit. All audiences are frozen by INSERT SELECT
-- at publication so later signups/verification never receive an older campaign.
CREATE TABLE IF NOT EXISTS announcement_recipients (
 announcement_id TEXT NOT NULL REFERENCES announcements(id) ON DELETE CASCADE,
 user_id TEXT NOT NULL REFERENCES users(id), PRIMARY KEY(announcement_id,user_id)
);
CREATE INDEX IF NOT EXISTS announcement_recipient_user ON announcement_recipients(user_id,announcement_id);
CREATE TABLE IF NOT EXISTS announcement_states (
 announcement_id TEXT NOT NULL REFERENCES announcements(id) ON DELETE CASCADE,
 user_id TEXT NOT NULL REFERENCES users(id), read_at BIGINT NOT NULL DEFAULT 0,
 dismissed_at BIGINT NOT NULL DEFAULT 0, presented_at BIGINT NOT NULL DEFAULT 0,
 PRIMARY KEY(announcement_id,user_id)
);
