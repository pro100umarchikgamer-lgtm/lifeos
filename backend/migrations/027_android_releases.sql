CREATE TABLE IF NOT EXISTS android_releases (
 id TEXT PRIMARY KEY,
 state TEXT NOT NULL CHECK(state IN ('draft','uploaded','validated','rejected','published','cancelled')),
 revision BIGINT NOT NULL CHECK(revision>=1),
 bytes BIGINT, apk_sha256 TEXT, package_name TEXT, certificate_sha256 TEXT,
 version_name TEXT, version_code BIGINT, error TEXT,
 created_at BIGINT NOT NULL, updated_at BIGINT NOT NULL, published_at BIGINT,
 created_by TEXT NOT NULL REFERENCES staff(id)
);
CREATE INDEX IF NOT EXISTS android_release_history ON android_releases(state,updated_at,id);
CREATE UNIQUE INDEX IF NOT EXISTS android_published_version ON android_releases(version_code) WHERE state='published';
CREATE UNIQUE INDEX IF NOT EXISTS android_published_digest ON android_releases(apk_sha256) WHERE state='published';
CREATE TABLE IF NOT EXISTS android_release_current (
 singleton BIGINT PRIMARY KEY CHECK(singleton=1),
 release_id TEXT NOT NULL REFERENCES android_releases(id)
);
-- Committed cancellation survives a worker exit between DB commit and unlink.
CREATE TABLE IF NOT EXISTS android_release_cleanup (
 release_id TEXT PRIMARY KEY REFERENCES android_releases(id)
);
