CREATE TABLE calendar_entries (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL REFERENCES local_identity(id),
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  title TEXT NOT NULL CHECK (length(trim(title)) > 0),
  task_id TEXT REFERENCES tasks(id),
  note_id TEXT REFERENCES notes(id),
  local_start TEXT NOT NULL,
  timezone TEXT NOT NULL,
  all_day INTEGER NOT NULL DEFAULT 0 CHECK (all_day IN (0, 1)),
  repeat_rule TEXT NOT NULL CHECK (repeat_rule IN ('none', 'daily', 'weekly', 'monthly', 'yearly')),
  repeat_interval INTEGER NOT NULL DEFAULT 1 CHECK (repeat_interval BETWEEN 1 AND 365),
  until_date TEXT,
  reminder INTEGER NOT NULL DEFAULT 0 CHECK (reminder IN (0, 1)),
  reminder_mode TEXT NOT NULL CHECK (reminder_mode IN ('standard', 'important', 'alarm')),
  revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
  native_synced_revision INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  CHECK (task_id IS NULL OR note_id IS NULL)
);
CREATE UNIQUE INDEX calendar_task ON calendar_entries(task_id) WHERE task_id IS NOT NULL AND deleted_at IS NULL;
CREATE UNIQUE INDEX calendar_note ON calendar_entries(note_id) WHERE note_id IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX calendar_scope ON calendar_entries(owner_id, workspace_id, deleted_at);
CREATE TABLE calendar_occurrences (
  entry_id TEXT NOT NULL REFERENCES calendar_entries(id),
  revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
  epoch INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('dismissed', 'completed', 'snoozed')),
  snoozed_until INTEGER,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(entry_id, revision, epoch),
  CHECK ((status = 'snoozed' AND snoozed_until IS NOT NULL) OR (status != 'snoozed' AND snoozed_until IS NULL))
);
