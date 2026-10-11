import sqlite3
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def expanded(version=4):
    db=sqlite3.connect(':memory:')
    db.execute('PRAGMA foreign_keys=ON')
    for n in range(1,version+1): db.executescript((ROOT/f'assets/migrations/{n:03}.sql').read_text())
    db.execute("INSERT INTO local_identity VALUES('owner','space','2026-10-11')")
    db.execute("INSERT INTO workspaces VALUES('space','owner','personal','2026-10-11')")
    return db

class OfflineFinanceTests(unittest.TestCase):
    def test_upgrade_from_every_prior_version_preserves_money_and_ids(self):
        for version in [1,2,3]:
            db=expanded(version)
            db.execute("INSERT INTO accounts(id,owner_id,workspace_id,currency,opening_minor) VALUES('a','owner','space','RUB',-100)")
            db.execute("INSERT INTO transactions(id,owner_id,workspace_id,kind,amount_minor,currency,minor_digits,occurred_on,created_at,updated_at) VALUES('money','owner','space','expense',1250,'RUB',2,'2026-10-11','2026-10-11','2026-10-11')")
            db.commit()
            for n in range(version+1,5):
                db.execute('BEGIN')
                for statement in (ROOT/f'assets/migrations/{n:03}.sql').read_text().split(';'):
                    if statement.strip():db.execute(statement)
                db.commit()
            self.assertEqual(db.execute('SELECT id,amount_minor,account_id,category_id FROM transactions').fetchone(),('money',1250,None,None))
            self.assertEqual(db.execute('SELECT id,opening_minor,revision FROM accounts').fetchone(),('a',-100,1))
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall());db.close()
    def test_transfer_is_atomic_and_has_no_income_or_expense_rows(self):
        db=expanded();self.addCleanup(db.close)
        for id,code in [('a','RUB'),('b','USD')]:db.execute('INSERT INTO accounts(id,owner_id,workspace_id,currency) VALUES(?,?,?,?)',(id,'owner','space',code))
        db.execute("INSERT INTO transfers(id,owner_id,workspace_id,from_account_id,to_account_id,sent_minor,received_minor,occurred_on,created_at,updated_at) VALUES('transfer','owner','space','a','b',10000,100,'2026-10-11','2026-10-11','2026-10-11')")
        self.assertEqual(db.execute('SELECT COUNT(*) FROM transactions').fetchone()[0],0)
        with self.assertRaises(sqlite3.IntegrityError):db.execute("UPDATE transfers SET received_minor=0 WHERE id='transfer'")
        self.assertEqual(db.execute('SELECT sent_minor,received_minor FROM transfers').fetchone(),(10000,100))
    def test_invalid_money_and_self_transfer_are_rejected(self):
        db=expanded();self.addCleanup(db.close)
        db.execute("INSERT INTO accounts(id,owner_id,workspace_id,currency) VALUES('a','owner','space','USD')")
        for amount in [0,-1,1.5]:
            with self.assertRaises(sqlite3.IntegrityError):db.execute("INSERT INTO transfers(id,owner_id,workspace_id,from_account_id,to_account_id,sent_minor,received_minor,occurred_on,created_at,updated_at) VALUES('t','owner','space','a','a',?,1,'2026-10-11','2026-10-11','2026-10-11')",(amount,))
