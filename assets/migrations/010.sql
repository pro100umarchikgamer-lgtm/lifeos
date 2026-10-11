ALTER TABLE projects ADD COLUMN calendar_id TEXT REFERENCES calendar_entries(id);
ALTER TABLE project_milestones ADD COLUMN calendar_id TEXT REFERENCES calendar_entries(id);
