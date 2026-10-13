CREATE INDEX IF NOT EXISTS workspace_change_cursor ON changes(workspace_id,seq DESC);
CREATE INDEX IF NOT EXISTS workspace_access_cursor ON changes(workspace_id,seq DESC) WHERE record_id IS NULL OR kind IN ('record.grant','access.changed');
