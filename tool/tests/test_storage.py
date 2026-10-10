import sqlite3
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = (ROOT / 'assets/migrations/001.sql').read_text()

def database(file=':memory:'):
    db = sqlite3.connect(file)
    db.execute('PRAGMA foreign_keys = ON')
    db.executescript(SCHEMA)
    db.execute("INSERT INTO local_identity VALUES ('owner','space','2026-10-10T00:00:00Z')")
    db.execute("INSERT INTO workspaces VALUES ('space','owner','personal','2026-10-10T00:00:00Z')")
    db.commit()
    return db

def money(db, id='expense', amount=1250, currency='RUB', owner='owner'):
    db.execute("""INSERT INTO transactions
        (id, owner_id, workspace_id, kind, amount_minor, currency, minor_digits, occurred_on, created_at, updated_at)
        VALUES (?, ?, 'space', 'expense', ?, ?, 2, '2026-10-10', 'now', 'now')""", (id, owner, amount, currency))

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.db = database()
        self.addCleanup(self.db.close)

    def test_expense_without_account_does_not_change_any_balance(self):
        self.db.execute("INSERT INTO accounts VALUES ('cash','owner','space','RUB',10000)")
        money(self.db)
        self.assertEqual(self.db.execute('SELECT account_id, amount_minor FROM transactions').fetchone(), (None, 1250))
        self.assertEqual(self.db.execute('SELECT opening_minor FROM accounts').fetchone(), (10000,))

    def test_records_are_private_and_have_owner_version_and_stable_id(self):
        money(self.db)
        self.assertEqual(self.db.execute('SELECT id, owner_id, workspace_id, visibility, revision FROM transactions').fetchone(),
                         ('expense', 'owner', 'space', 'private', 1))
        with self.assertRaises(sqlite3.IntegrityError):
            money(self.db)
        with self.assertRaises(sqlite3.IntegrityError):
            money(self.db, id='foreign', owner='unknown')

    def test_minor_units_stay_exact_and_currencies_remain_separate(self):
        money(self.db, 'a', 10, 'USD')
        money(self.db, 'b', 20, 'USD')
        money(self.db, 'c', 55, 'RUB')
        self.assertEqual(dict(self.db.execute('SELECT currency, sum(amount_minor) FROM transactions GROUP BY currency')),
                         {'RUB': 55, 'USD': 30})

    def test_invalid_financial_states_and_empty_content_rejected(self):
        for amount in (0, -1, 1.5, 1000000000000000):
            with self.assertRaises(sqlite3.IntegrityError):
                money(self.db, str(amount), amount)
        for table, field in [('tasks', 'title'), ('notes', 'body')]:
            with self.assertRaises(sqlite3.IntegrityError):
                self.db.execute(f"INSERT INTO {table} (id,owner_id,workspace_id,{field},created_at,updated_at) VALUES ('id','owner','space','   ','now','now')")

    def test_operation_uniqueness_rolls_back_entire_transaction(self):
        with self.db:
            money(self.db, 'first')
            self.db.execute("INSERT INTO operations VALUES ('op','payload','first','now')")
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db:
                money(self.db, 'second')
                self.db.execute("INSERT INTO operations VALUES ('op','other','second','now')")
        self.assertEqual(self.db.execute('SELECT id FROM transactions').fetchall(), [('first',)])

    def test_actual_sqlite_file_survives_close_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'test.db'
            db = database(file)
            money(db)
            db.execute("INSERT INTO tasks (id,owner_id,workspace_id,title,created_at,updated_at) VALUES ('task','owner','space','Buy milk','now','now')")
            db.execute("INSERT INTO notes (id,owner_id,workspace_id,body,created_at,updated_at) VALUES ('note','owner','space','Text','now','now')")
            db.commit()
            db.close()
            db = sqlite3.connect(file)
            try:
                for table in ['transactions', 'tasks', 'notes']:
                    self.assertEqual(db.execute(f'SELECT count(*) FROM {table}').fetchone(), (1,))
            finally:
                db.close()
