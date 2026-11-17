-- Task dates/reminders are additive metadata; existing task records stay compatible.
CREATE TABLE IF NOT EXISTS task_reminders (
 task_id TEXT PRIMARY KEY REFERENCES records(id) ON DELETE CASCADE,
 revision BIGINT NOT NULL CHECK(revision>0), schedule TEXT,
 reminder BIGINT NOT NULL CHECK(reminder IN (0,1)),
 updated_at BIGINT NOT NULL, updated_by TEXT NOT NULL REFERENCES users(id),
 CHECK(reminder=0 OR schedule IS NOT NULL)
);
