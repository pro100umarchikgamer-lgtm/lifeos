CREATE TABLE import_batches (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 content_key TEXT NOT NULL, row_count INTEGER NOT NULL CHECK(row_count>0 AND row_count<=10000),
 revision INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
 UNIQUE(owner_id,workspace_id,content_key)
);
CREATE TABLE import_rows (
 origin_key TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES import_batches(id),
 fingerprint TEXT NOT NULL, transaction_id TEXT NOT NULL UNIQUE REFERENCES transactions(id),
 imported_revision INTEGER NOT NULL DEFAULT 1 CHECK(imported_revision=1)
);
CREATE INDEX import_fingerprint ON import_rows(fingerprint);
