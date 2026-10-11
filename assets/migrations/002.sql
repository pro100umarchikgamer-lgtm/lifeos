CREATE TABLE record_changes (
  id TEXT PRIMARY KEY,
  operation_id TEXT NOT NULL UNIQUE REFERENCES operations(id) DEFERRABLE INITIALLY DEFERRED,
  record_id TEXT NOT NULL,
  table_name TEXT NOT NULL CHECK (table_name IN ('transactions', 'tasks', 'notes')),
  revision INTEGER NOT NULL CHECK (revision > 1),
  before_json TEXT NOT NULL,
  after_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(table_name, record_id, revision)
);
CREATE INDEX transactions_scope_date ON transactions(owner_id, workspace_id, deleted_at, occurred_on);
CREATE INDEX tasks_scope ON tasks(owner_id, workspace_id, deleted_at, completed);
CREATE INDEX notes_scope ON notes(owner_id, workspace_id, deleted_at, updated_at);
