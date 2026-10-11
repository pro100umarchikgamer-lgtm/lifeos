-- Financial identities and money movements remain distinct from plans.
ALTER TABLE accounts ADD COLUMN name TEXT NOT NULL DEFAULT '';
ALTER TABLE accounts ADD COLUMN kind TEXT NOT NULL DEFAULT 'cash' CHECK(kind IN ('cash','card','wallet','deposit','custom'));
ALTER TABLE accounts ADD COLUMN archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1));
ALTER TABLE accounts ADD COLUMN revision INTEGER NOT NULL DEFAULT 1 CHECK(revision > 0);
ALTER TABLE accounts ADD COLUMN created_at TEXT NOT NULL DEFAULT '';
ALTER TABLE accounts ADD COLUMN updated_at TEXT NOT NULL DEFAULT '';
ALTER TABLE accounts ADD COLUMN deleted_at TEXT;
UPDATE accounts SET created_at=(SELECT created_at FROM local_identity WHERE id=accounts.owner_id), updated_at=(SELECT created_at FROM local_identity WHERE id=accounts.owner_id), name=currency WHERE name='';
CREATE TABLE categories (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 name TEXT NOT NULL CHECK(length(trim(name))>0), parent_id TEXT REFERENCES categories(id), archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN(0,1)),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), deleted_at TEXT,
 CHECK(parent_id IS NULL OR parent_id != id)
);
ALTER TABLE transactions ADD COLUMN category_id TEXT REFERENCES categories(id);
CREATE TABLE transfers (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 from_account_id TEXT NOT NULL REFERENCES accounts(id), to_account_id TEXT NOT NULL REFERENCES accounts(id),
 sent_minor INTEGER NOT NULL CHECK(typeof(sent_minor)='integer' AND sent_minor>0 AND sent_minor<=999999999999999),
 received_minor INTEGER NOT NULL CHECK(typeof(received_minor)='integer' AND received_minor>0 AND received_minor<=999999999999999),
 occurred_on TEXT NOT NULL, label TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), deleted_at TEXT, CHECK(from_account_id != to_account_id)
);
CREATE TABLE transaction_splits (
 id TEXT PRIMARY KEY, transaction_id TEXT NOT NULL REFERENCES transactions(id), category_id TEXT REFERENCES categories(id),
 project_id TEXT, profile_id TEXT, amount_minor INTEGER NOT NULL CHECK(typeof(amount_minor)='integer' AND amount_minor>0)
);
CREATE TABLE budgets (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 name TEXT NOT NULL CHECK(length(trim(name))>0), currency TEXT NOT NULL CHECK(length(currency)=3), category_id TEXT REFERENCES categories(id),
 limit_minor INTEGER NOT NULL CHECK(typeof(limit_minor)='integer' AND limit_minor>=0 AND limit_minor<=999999999999999),
 period TEXT NOT NULL CHECK(period IN('week','month','year','custom')), start_on TEXT NOT NULL, end_on TEXT,
 rollover TEXT NOT NULL DEFAULT 'none' CHECK(rollover IN('none','positive','negative','both')),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), deleted_at TEXT
);
CREATE TABLE planned_payments (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 name TEXT NOT NULL CHECK(length(trim(name))>0), kind TEXT NOT NULL CHECK(kind IN('expense','income')), currency TEXT NOT NULL CHECK(length(currency)=3),
 amount_minor INTEGER NOT NULL CHECK(typeof(amount_minor)='integer' AND amount_minor>0 AND amount_minor<=999999999999999),
 account_id TEXT REFERENCES accounts(id), category_id TEXT REFERENCES categories(id), calendar_id TEXT NOT NULL REFERENCES calendar_entries(id),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), deleted_at TEXT
);
CREATE TABLE planned_confirmations (
 plan_id TEXT NOT NULL REFERENCES planned_payments(id), occurrence TEXT NOT NULL, transaction_id TEXT NOT NULL UNIQUE REFERENCES transactions(id),
 PRIMARY KEY(plan_id,occurrence)
);
CREATE TABLE entity_changes (
 operation_id TEXT PRIMARY KEY REFERENCES operations(id) DEFERRABLE INITIALLY DEFERRED,
 table_name TEXT NOT NULL, record_id TEXT NOT NULL, revision INTEGER NOT NULL,
 before_json TEXT, after_json TEXT NOT NULL, UNIQUE(table_name,record_id,revision)
);
CREATE INDEX transactions_account ON transactions(account_id,occurred_on);
CREATE INDEX transactions_category ON transactions(category_id,occurred_on);
