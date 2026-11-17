"""An actual retained server schema remains accepted after optional UI metadata."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.import_sqlite import import_server


class PriorServerImportTests(unittest.TestCase):
    def test_published_server_database_previews_without_new_inbox_admission_or_restore_tables(self):
        schema = Path(__file__).with_name('fixtures').joinpath('server_schema_84b0bdf.sql').read_text()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'server.db'
            with sqlite3.connect(source) as db:
                db.executescript(schema)
                db.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',
                           ('prior-user', 'prior@example.test', 'unused', 'unused', 1, 1794564000))
            counts = import_server(None, source, apply=False)
            self.assertEqual(counts['users'], 1)
            for table in ('inbox_notifications', 'announcements', 'announcement_recipients',
                          'announcement_states', 'inbox_settings', 'budget_inbox_notifications',
                          'budget_inbox_sources', 'control_handoffs', 'control_admissions', 'record_recovery_requests'):
                self.assertEqual(counts[table], 0)


if __name__ == '__main__':
    unittest.main()
