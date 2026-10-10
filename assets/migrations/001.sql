CREATE TABLE local_identity (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);
CREATE TABLE workspaces (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL REFERENCES local_identity(id),
  kind TEXT NOT NULL CHECK (kind = 'personal'),
  created_at TEXT NOT NULL
);
CREATE TABLE accounts (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL REFERENCES local_identity(id),
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  currency TEXT NOT NULL CHECK (length(currency) = 3),
  opening_minor INTEGER NOT NULL DEFAULT 0 CHECK (typeof(opening_minor) = 'integer')
);
CREATE TABLE transactions (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL REFERENCES local_identity(id),
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  visibility TEXT NOT NULL DEFAULT 'private' CHECK (visibility = 'private'),
  kind TEXT NOT NULL CHECK (kind IN ('expense', 'income')),
  amount_minor INTEGER NOT NULL CHECK (typeof(amount_minor) = 'integer' AND amount_minor > 0 AND amount_minor <= 999999999999999),
  currency TEXT NOT NULL CHECK (length(currency) = 3),
  minor_digits INTEGER NOT NULL CHECK (minor_digits BETWEEN 0 AND 3),
  label TEXT NOT NULL DEFAULT '',
  occurred_on TEXT NOT NULL,
  account_id TEXT REFERENCES accounts(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
  deleted_at TEXT
);
CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL REFERENCES local_identity(id),
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  visibility TEXT NOT NULL DEFAULT 'private' CHECK (visibility = 'private'),
  title TEXT NOT NULL CHECK (length(trim(title)) > 0),
  completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
  deleted_at TEXT
);
CREATE TABLE notes (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL REFERENCES local_identity(id),
  workspace_id TEXT NOT NULL REFERENCES workspaces(id),
  visibility TEXT NOT NULL DEFAULT 'private' CHECK (visibility = 'private'),
  body TEXT NOT NULL CHECK (length(trim(body)) > 0),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
  deleted_at TEXT
);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE operations (
  id TEXT PRIMARY KEY,
  payload TEXT NOT NULL,
  result_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX transactions_date ON transactions(occurred_on, created_at);
CREATE INDEX tasks_created ON tasks(created_at);
CREATE INDEX notes_created ON notes(created_at);
