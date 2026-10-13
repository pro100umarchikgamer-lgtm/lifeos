import json
import sqlite3
import tempfile
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]

class SyncMigrationTests(unittest.TestCase):
    def test_upgrade_preserves_money_and_outbox_survives_restart_with_scope_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'local.db';db=sqlite3.connect(file)
            for n in range(1,11):db.executescript((ROOT/f'assets/migrations/{n:03}.sql').read_text())
            db.execute("INSERT INTO local_identity VALUES('person','space','now')")
            db.execute("INSERT INTO workspaces VALUES('space','person','personal','now')")
            db.execute("INSERT INTO transactions(id,owner_id,workspace_id,kind,amount_minor,currency,minor_digits,occurred_on,created_at,updated_at) VALUES('money','person','space','expense',1250,'RUB',2,'2026-10-13','now','now')")
            db.commit();before=db.execute('SELECT * FROM transactions').fetchall()
            db.executescript((ROOT/'assets/migrations/011.sql').read_text())
            self.assertEqual(db.execute('SELECT * FROM transactions').fetchall(),before)
            payload=json.dumps({'id':'op','record_id':'note','data':{'body':'offline'}})
            db.execute('INSERT INTO sync_outbox(scope,workspace_id,operation_id,record_id,payload) VALUES(?,?,?,?,?)',('server|one','family','op','note',payload));db.commit();db.close()
            db=sqlite3.connect(file)
            self.assertEqual(db.execute("SELECT payload FROM sync_outbox WHERE scope='server|one' AND workspace_id='family'").fetchone()[0],payload)
            self.assertEqual(db.execute("SELECT * FROM sync_outbox WHERE scope='server|two'").fetchall(),[])
            with self.assertRaises(sqlite3.IntegrityError):db.execute('INSERT INTO sync_outbox(scope,workspace_id,operation_id,record_id,payload) VALUES(?,?,?,?,?)',('server|one','family','op','note',payload))
            db.close()
