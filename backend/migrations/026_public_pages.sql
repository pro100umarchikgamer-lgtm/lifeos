CREATE TABLE IF NOT EXISTS public_page_revisions (
 page TEXT NOT NULL, locale TEXT NOT NULL, revision BIGINT NOT NULL CHECK(revision>0),
 source_generation TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('draft','published','restored')),
 from_revision BIGINT CHECK(from_revision>=0 AND from_revision<revision),
 content TEXT NOT NULL, created_at BIGINT NOT NULL,
 author_id TEXT NOT NULL REFERENCES staff(id),
 PRIMARY KEY(page,locale,revision)
);

CREATE TABLE IF NOT EXISTS public_page_states (
 page TEXT NOT NULL, locale TEXT NOT NULL, version BIGINT NOT NULL CHECK(version>0),
 draft_revision BIGINT CHECK(draft_revision>0 AND draft_revision<=version),
 published_revision BIGINT CHECK(published_revision>0 AND published_revision<=version),
 PRIMARY KEY(page,locale),
 FOREIGN KEY(page,locale,draft_revision) REFERENCES public_page_revisions(page,locale,revision),
 FOREIGN KEY(page,locale,published_revision) REFERENCES public_page_revisions(page,locale,revision)
);

CREATE TABLE IF NOT EXISTS public_page_media (
 id TEXT PRIMARY KEY, data BYTEA NOT NULL, mime TEXT NOT NULL CHECK(mime='image/webp'),
 width BIGINT NOT NULL CHECK(width>0), height BIGINT NOT NULL CHECK(height>0),
 created_at BIGINT NOT NULL, author_id TEXT NOT NULL REFERENCES staff(id)
);

CREATE TABLE IF NOT EXISTS public_page_revision_media (
 page TEXT NOT NULL, locale TEXT NOT NULL, revision BIGINT NOT NULL,
 media_id TEXT NOT NULL REFERENCES public_page_media(id),
 PRIMARY KEY(page,locale,revision,media_id),
 FOREIGN KEY(page,locale,revision) REFERENCES public_page_revisions(page,locale,revision)
);

CREATE INDEX IF NOT EXISTS public_page_media_visibility
 ON public_page_revision_media(media_id,page,locale,revision);
