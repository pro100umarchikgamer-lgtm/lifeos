CREATE TABLE projects (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
name TEXT NOT NULL, goal TEXT NOT NULL DEFAULT '', status TEXT NOT NULL CHECK(status IN ('active','paused','done')), due_on TEXT, budget_id TEXT REFERENCES budgets(id)
);
CREATE TABLE project_milestones (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
project_id TEXT NOT NULL REFERENCES projects(id), name TEXT NOT NULL, due_on TEXT, completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0,1))
);
CREATE TABLE task_placements (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
task_id TEXT NOT NULL UNIQUE REFERENCES tasks(id), project_id TEXT REFERENCES projects(id), parent_task_id TEXT REFERENCES tasks(id), priority INTEGER NOT NULL DEFAULT 0 CHECK(priority BETWEEN 0 AND 3), CHECK(parent_task_id IS NULL OR parent_task_id<>task_id)
);
CREATE TABLE habits (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
name TEXT NOT NULL, paused INTEGER NOT NULL DEFAULT 0 CHECK(paused IN (0,1)), calendar_id TEXT NOT NULL UNIQUE REFERENCES calendar_entries(id)
);
CREATE TABLE habit_checks (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
habit_id TEXT NOT NULL REFERENCES habits(id), local_date TEXT NOT NULL, timezone TEXT NOT NULL, completed INTEGER NOT NULL CHECK(completed IN (0,1)), UNIQUE(habit_id,local_date)
);
CREATE TABLE learning_subjects (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
name TEXT NOT NULL, project_id TEXT REFERENCES projects(id)
);
CREATE TABLE study_items (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
subject_id TEXT NOT NULL REFERENCES learning_subjects(id), name TEXT NOT NULL, task_id TEXT REFERENCES tasks(id), calendar_id TEXT UNIQUE REFERENCES calendar_entries(id), completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0,1))
);
CREATE TABLE checklists (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
name TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('note','shopping','chores')), note_id TEXT REFERENCES notes(id), project_id TEXT REFERENCES projects(id)
);
CREATE TABLE checklist_items (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
checklist_id TEXT NOT NULL REFERENCES checklists(id), name TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0,1)), quantity TEXT NOT NULL DEFAULT '', task_id TEXT REFERENCES tasks(id)
);
CREATE TABLE note_metadata (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
note_id TEXT NOT NULL UNIQUE REFERENCES notes(id), tags TEXT NOT NULL DEFAULT ''
);
CREATE TABLE record_links (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
note_id TEXT NOT NULL REFERENCES notes(id), target_type TEXT NOT NULL CHECK(target_type IN ('task','note','project','goal')), target_id TEXT NOT NULL, UNIQUE(note_id,target_type,target_id)
);
CREATE TABLE wellness_entries (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
kind TEXT NOT NULL CHECK(kind IN ('sleep','activity')), local_date TEXT NOT NULL, minutes INTEGER NOT NULL CHECK(typeof(minutes)='integer' AND minutes BETWEEN 0 AND 1440), label TEXT NOT NULL DEFAULT ''
);
CREATE TABLE dashboard_configs (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
widget TEXT NOT NULL CHECK(widget IN ('financial','tasks','notes','projects','habits','shopping')), visible INTEGER NOT NULL CHECK(visible IN (0,1)), position INTEGER NOT NULL CHECK(position BETWEEN 0 AND 100), expanded INTEGER NOT NULL CHECK(expanded IN (0,1)), UNIQUE(owner_id,workspace_id,widget)
);
CREATE INDEX task_project ON task_placements(project_id,parent_task_id);
CREATE INDEX habit_date ON habit_checks(habit_id,local_date);
CREATE INDEX checklist_parent ON checklist_items(checklist_id,completed);
