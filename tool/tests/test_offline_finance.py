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
    if version>=8:
        db.execute("INSERT INTO local_profiles(id,owner_id,workspace_id,name,kind,created_at,updated_at) VALUES('owner','owner','space','LifeOS','adult','2026-10-11','2026-10-11')")
        db.execute("INSERT INTO local_memberships(id,owner_id,workspace_id,profile_id,role,permissions,created_at,updated_at) VALUES('owner','owner','space','owner','owner',7,'2026-10-11','2026-10-11')")
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

class WealthSchemaTests(unittest.TestCase):
    def test_wealth_upgrade_and_no_actual_money_for_virtual_records(self):
        db=expanded(5);self.addCleanup(db.close)
        db.execute("INSERT INTO savings_goals(id,owner_id,workspace_id,name,currency,target_minor,created_at,updated_at) VALUES('g','owner','space','Holiday','USD',10000,'2026-10-11','2026-10-11')")
        db.execute("INSERT INTO savings_entries(id,owner_id,workspace_id,goal_id,amount_minor,occurred_on,created_at,updated_at) VALUES('c','owner','space','g',1000,'2026-10-11','2026-10-11','2026-10-11')")
        self.assertEqual(db.execute('SELECT COUNT(*) FROM transactions').fetchone()[0],0)
        self.assertEqual(db.execute('SELECT SUM(amount_minor) FROM savings_entries').fetchone()[0],1000)
        with self.assertRaises(sqlite3.IntegrityError):db.execute("UPDATE savings_entries SET amount_minor=1.5")
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())

class ImportSchemaTests(unittest.TestCase):
    def test_origin_unique_and_reversal_cannot_include_unrelated_money(self):
        db=expanded(6);self.addCleanup(db.close)
        for id in ['manual','imported']:
            db.execute("INSERT INTO transactions(id,owner_id,workspace_id,kind,amount_minor,currency,minor_digits,occurred_on,created_at,updated_at) VALUES(?,'owner','space','expense',1234,'RUB',2,'2026-10-11','2026-10-11','2026-10-11')",(id,))
        db.execute("INSERT INTO import_batches(id,owner_id,workspace_id,content_key,row_count,created_at,updated_at) VALUES('batch','owner','space','key',1,'2026-10-11','2026-10-11')")
        db.execute("INSERT INTO import_rows(origin_key,batch_id,fingerprint,transaction_id) VALUES('origin','batch','hash','imported')")
        with self.assertRaises(sqlite3.IntegrityError):db.execute("INSERT INTO import_rows(origin_key,batch_id,fingerprint,transaction_id) VALUES('origin','batch','hash','manual')")
        db.execute("UPDATE transactions SET deleted_at='2026-10-11' WHERE id IN (SELECT transaction_id FROM import_rows WHERE batch_id='batch')")
        self.assertEqual(db.execute("SELECT deleted_at FROM transactions WHERE id='manual'").fetchone(),(None,))
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())

class PersonalModulesSchemaTests(unittest.TestCase):
    def test_canonical_tasks_and_note_body_are_not_duplicated(self):
        db=expanded(7);self.addCleanup(db.close)
        db.execute("INSERT INTO projects(id,owner_id,workspace_id,name,status,created_at,updated_at) VALUES('p','owner','space','Study','active','2026-10-11','2026-10-11')")
        db.execute("INSERT INTO tasks(id,owner_id,workspace_id,title,created_at,updated_at) VALUES('t','owner','space','Read','2026-10-11','2026-10-11')")
        db.execute("INSERT INTO task_placements(id,owner_id,workspace_id,task_id,project_id,created_at,updated_at) VALUES('place','owner','space','t','p','2026-10-11','2026-10-11')")
        db.execute("INSERT INTO notes(id,owner_id,workspace_id,body,created_at,updated_at) VALUES('note','owner','space','Original body','2026-10-11','2026-10-11')")
        db.execute("INSERT INTO note_metadata(id,owner_id,workspace_id,note_id,tags,created_at,updated_at) VALUES('tags','owner','space','note','study,reading','2026-10-11','2026-10-11')")
        self.assertEqual(db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0],1)
        self.assertEqual(db.execute('SELECT body FROM notes').fetchone()[0],'Original body')
        with self.assertRaises(sqlite3.IntegrityError):db.execute("UPDATE task_placements SET parent_task_id=task_id")
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
    def test_migration_failure_rolls_back_without_losing_original_records(self):
        db=expanded(6);self.addCleanup(db.close)
        db.commit();db.execute('BEGIN')
        with self.assertRaises(sqlite3.OperationalError):
            for statement in ((ROOT/'assets/migrations/007.sql').read_text()+';INVALID SQL').split(';'):
                if statement.strip():db.execute(statement)
        db.rollback()
        self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='projects'").fetchone())
        self.assertEqual(db.execute('SELECT id FROM local_identity').fetchone(),('owner',))

class LocalIdentitySchemaTests(unittest.TestCase):
    def test_upgrade_seeds_original_immutable_owner_and_allows_equal_names(self):
        db=expanded(7);self.addCleanup(db.close)
        db.executescript((ROOT/'assets/migrations/008.sql').read_text())
        self.assertEqual(db.execute('SELECT id,owner_id,kind FROM local_profiles').fetchone(),('owner','owner','adult'))
        self.assertEqual(db.execute('SELECT profile_id,role,permissions FROM local_memberships').fetchone(),('owner','owner',7))
        for id in ['adult1','adult2']:
            db.execute("INSERT INTO local_profiles(id,owner_id,workspace_id,name,kind,created_at,updated_at) VALUES(?,'owner','space','Alex','adult','2026-10-11','2026-10-11')",(id,))
        db.execute("UPDATE local_profiles SET name='Renamed' WHERE id='adult1'")
        self.assertEqual(db.execute("SELECT id FROM local_profiles WHERE name='Alex'").fetchone(),('adult2',))
        with self.assertRaises(sqlite3.IntegrityError):db.execute("INSERT INTO local_profiles(id,owner_id,workspace_id,name,kind,guardian_id,created_at,updated_at) VALUES('child','owner','space','Child','child','missing','2026-10-11','2026-10-11')")
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
    def test_all_prior_versions_upgrade_preserving_records(self):
        for version in range(1,10):
            db=expanded(version)
            db.execute("INSERT INTO notes(id,owner_id,workspace_id,body,created_at,updated_at) VALUES('note','owner','space','Keep me','2026-10-11','2026-10-11')");db.commit()
            for n in range(version+1,11):db.executescript((ROOT/f'assets/migrations/{n:03}.sql').read_text())
            self.assertEqual(db.execute('SELECT id,body FROM notes').fetchone(),('note','Keep me'))
            self.assertEqual(db.execute('SELECT id FROM local_profiles').fetchone(),('owner',))
            self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall());db.close()


class HabitPauseSchemaTests(unittest.TestCase):
    def test_one_open_pause_and_valid_boundaries(self):
        db=expanded(9);self.addCleanup(db.close)
        db.execute("INSERT INTO calendar_entries(id,owner_id,workspace_id,title,local_start,timezone,repeat_rule,reminder_mode,created_at,updated_at) VALUES('calendar','owner','space','Habit','2026-10-11T09:00:00','UTC','daily','standard','2026-10-11','2026-10-11')")
        db.execute("INSERT INTO habits(id,owner_id,workspace_id,name,calendar_id,created_at,updated_at) VALUES('h','owner','space','Walk','calendar','2026-10-11','2026-10-11')")
        db.execute("INSERT INTO habit_pauses VALUES('pause','h','2026-10-11',NULL)")
        with self.assertRaises(sqlite3.IntegrityError):db.execute("INSERT INTO habit_pauses VALUES('other','h','2026-10-12',NULL)")
        with self.assertRaises(sqlite3.IntegrityError):db.execute("UPDATE habit_pauses SET end_on='2026-10-10'")
        db.execute("UPDATE habit_pauses SET end_on='2026-10-13'")
        self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
