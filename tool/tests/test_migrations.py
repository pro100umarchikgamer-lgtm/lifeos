import json
import sqlite3
import unittest
from pathlib import Path
from test_storage import database, money

ROOT = Path(__file__).resolve().parents[2]

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.db = database()
        self.addCleanup(self.db.close)
        money(self.db)
        self.db.execute("INSERT INTO operations VALUES ('old-op','old-payload','expense','now')")
        self.db.commit()
        self.before = list(self.db.execute('SELECT * FROM transactions'))
        with self.db:
            self.db.execute('BEGIN')
            for statement in (ROOT / 'assets/migrations/002.sql').read_text().split(';'):
                if statement.strip():
                    self.db.execute(statement)

    def test_upgrade_preserves_identity_money_operations_and_key_independent_schema(self):
        self.assertEqual(self.before, list(self.db.execute('SELECT * FROM transactions')))
        self.assertEqual(self.db.execute('SELECT * FROM operations').fetchone(),
                         ('old-op', 'old-payload', 'expense', 'now'))
        self.assertEqual(self.db.execute('SELECT id FROM local_identity').fetchone(), ('owner',))
        self.assertEqual(self.db.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_revision_delete_undo_and_recalculation(self):
        before = dict(zip([x[0] for x in self.db.execute('SELECT * FROM transactions').description], self.before[0]))
        with self.db:
            count = self.db.execute("UPDATE transactions SET amount_minor=1750, revision=2 WHERE id='expense' AND owner_id='owner' AND workspace_id='space' AND revision=1 AND deleted_at IS NULL").rowcount
            self.assertEqual(count, 1)
            self.db.execute("INSERT INTO record_changes VALUES ('change','edit-op','expense','transactions',2,?,?,'now')", (json.dumps(before), '{}'))
            self.db.execute("INSERT INTO operations VALUES ('edit-op','edit','expense','now')")
        self.assertEqual(self.db.execute("UPDATE transactions SET amount_minor=900,revision=3 WHERE id='expense' AND revision=1").rowcount, 0)
        self.assertEqual(self.db.execute('SELECT sum(amount_minor) FROM transactions WHERE deleted_at IS NULL').fetchone(), (1750,))
        with self.db:
            self.db.execute("UPDATE transactions SET deleted_at='now',revision=3 WHERE id='expense' AND revision=2")
        self.assertEqual(self.db.execute('SELECT count(*) FROM transactions WHERE deleted_at IS NULL').fetchone(), (0,))
        with self.db:
            self.db.execute("UPDATE transactions SET deleted_at=NULL,revision=4 WHERE id='expense' AND revision=3")
        self.assertEqual(self.db.execute('SELECT id,amount_minor,revision FROM transactions').fetchone(), ('expense',1750,4))

    def test_history_and_record_write_rollback_together(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db:
                self.db.execute("UPDATE transactions SET amount_minor=888,revision=2 WHERE id='expense'")
                self.db.execute("INSERT INTO record_changes VALUES ('bad','missing-op','expense','transactions',2,'{}','{}','now')")
        self.assertEqual(self.before, list(self.db.execute('SELECT * FROM transactions')))

    def test_failed_migration_rolls_back_all_changes(self):
        with self.assertRaises(sqlite3.OperationalError):
            with self.db:
                self.db.execute('BEGIN')
                self.db.execute('CREATE TABLE should_rollback(id TEXT)')
                self.db.execute('INVALID SQL')
        self.assertIsNone(self.db.execute("SELECT name FROM sqlite_master WHERE name='should_rollback'").fetchone())
