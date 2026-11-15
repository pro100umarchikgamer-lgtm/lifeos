-- Personal display order only: opaque live record IDs, never finance payloads.
CREATE TABLE IF NOT EXISTS user_layout_preferences (
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 kind TEXT NOT NULL CHECK(kind IN ('account','budget')),
 order_ids TEXT NOT NULL DEFAULT '[]',
 revision BIGINT NOT NULL CHECK(revision>0),
 PRIMARY KEY(user_id,workspace_id,kind)
);
