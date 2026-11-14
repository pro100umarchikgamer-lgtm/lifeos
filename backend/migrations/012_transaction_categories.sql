-- Optional metadata only: preserve existing amounts, revisions and permissions.
-- Legacy clients omit this column on update, so a saved category is retained.
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS category TEXT
CHECK(category IS NULL OR category IN ('food','transport','shopping','housing','health','leisure','education','transfers','other'));
