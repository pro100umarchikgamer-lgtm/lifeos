CREATE TABLE habit_pauses (
 id TEXT PRIMARY KEY,
 habit_id TEXT NOT NULL REFERENCES habits(id),
 start_on TEXT NOT NULL,
 end_on TEXT,
 CHECK(end_on IS NULL OR end_on>=start_on)
);
CREATE UNIQUE INDEX habit_open_pause ON habit_pauses(habit_id) WHERE end_on IS NULL;
