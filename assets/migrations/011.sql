CREATE TABLE sync_outbox(seq INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL, workspace_id TEXT NOT NULL, operation_id TEXT NOT NULL, record_id TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending', result TEXT, UNIQUE(scope,operation_id));
CREATE INDEX sync_pending ON sync_outbox(scope,workspace_id,state,seq);
CREATE TABLE sync_records(scope TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(scope,workspace_id,id));
CREATE TABLE sync_cursors(scope TEXT NOT NULL, workspace_id TEXT NOT NULL, cursor INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(scope,workspace_id));
CREATE TABLE sync_metadata(scope TEXT NOT NULL, key TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(scope,key));
