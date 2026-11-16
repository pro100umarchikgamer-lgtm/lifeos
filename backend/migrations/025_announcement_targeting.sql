-- Future cohorts are separate from the unchanged all/users audience snapshots.
CREATE INDEX IF NOT EXISTS users_created_history ON users(created_at,id);
CREATE TABLE IF NOT EXISTS announcement_targeting (
 announcement_id TEXT PRIMARY KEY REFERENCES announcements(id) ON DELETE CASCADE,
 mode TEXT NOT NULL CHECK(mode='newcomers'),
 no_expiry BIGINT NOT NULL DEFAULT 0 CHECK(no_expiry IN (0,1)),
 cohort_at BIGINT NOT NULL DEFAULT 0
);
-- Only existing accounts tied in the publication second need exact exclusions.
CREATE TABLE IF NOT EXISTS announcement_cohort_exclusions (
 announcement_id TEXT NOT NULL REFERENCES announcements(id) ON DELETE CASCADE,
 user_id TEXT NOT NULL REFERENCES users(id),
 PRIMARY KEY(announcement_id,user_id)
);
CREATE INDEX IF NOT EXISTS announcement_cohort_user ON announcement_cohort_exclusions(user_id,announcement_id);
-- Retain the consumed welcome after its campaign expires or is reclaimed.
CREATE TABLE IF NOT EXISTS newcomer_welcome_claims (
 user_id TEXT PRIMARY KEY REFERENCES users(id),
 announcement_id TEXT REFERENCES announcements(id) ON DELETE SET NULL,
 claimed_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS newcomer_welcome_announcement ON newcomer_welcome_claims(announcement_id,user_id);
