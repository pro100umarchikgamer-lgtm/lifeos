-- Public opaque codes, opt-in short aliases, immutable verified attribution.
CREATE TABLE IF NOT EXISTS referral_codes (
 user_id TEXT PRIMARY KEY REFERENCES users(id), code TEXT NOT NULL UNIQUE,
 created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS referral_aliases (
 user_id TEXT PRIMARY KEY REFERENCES users(id), display_name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS referral_attributions (
 invitee_id TEXT PRIMARY KEY REFERENCES users(id),
 referrer_id TEXT REFERENCES users(id), confirmed_at BIGINT NOT NULL,
 CHECK(referrer_id IS NULL OR referrer_id<>invitee_id)
);
CREATE INDEX IF NOT EXISTS referral_referrer ON referral_attributions(referrer_id,confirmed_at,invitee_id);
