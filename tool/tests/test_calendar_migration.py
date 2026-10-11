import sqlite3
import unittest
from pathlib import Path
from test_storage import database, money
ROOT = Path(__file__).resolve().parents[2]

class CalendarMigrationTests(unittest.TestCase):
    def setUp(self):
        self.db = database()
        self.addCleanup(self.db.close)
        money(self.db)
        self.db.execute("INSERT INTO tasks(id,owner_id,workspace_id,title,created_at,updated_at) VALUES ('task','owner','space','Existing task','now','now')")
        self.db.execute("INSERT INTO notes(id,owner_id,workspace_id,body,created_at,updated_at) VALUES ('note','owner','space','Existing note','now','now')")
        self.db.commit()
        self.before = {table: list(self.db.execute('SELECT * FROM ' + table)) for table in ['local_identity','workspaces','transactions','tasks','notes']}
        with self.db:
            self.db.execute('BEGIN')
            for version in [2,3]:
                for statement in (ROOT / f'assets/migrations/{version:03}.sql').read_text().split(';'):
                    if statement.strip(): self.db.execute(statement)
    def insert(self, id='calendar', task='task', note=None):
        self.db.execute("INSERT INTO calendar_entries(id,owner_id,workspace_id,title,task_id,note_id,local_start,timezone,repeat_rule,reminder_mode,created_at,updated_at) VALUES (?,'owner','space','Title',?,?,'2026-10-11T09:00:00','UTC','daily','alarm','now','now')", (id,task,note))
    def test_upgrade_preserves_all_existing_private_data(self):
        for table, rows in self.before.items(): self.assertEqual(rows, list(self.db.execute('SELECT * FROM ' + table)))
        self.assertEqual([], self.db.execute('PRAGMA foreign_key_check').fetchall())
    def test_links_are_unique_and_soft_deleted_link_can_be_replaced(self):
        self.insert()
        with self.assertRaises(sqlite3.IntegrityError): self.insert('duplicate')
        self.db.execute("UPDATE calendar_entries SET deleted_at='now',revision=revision+1 WHERE id='calendar'")
        self.insert('replacement')
        self.assertEqual(2,self.db.execute('SELECT count(*) FROM calendar_entries').fetchone()[0])
    def test_missing_record_dual_link_and_invalid_recurrence_fail(self):
        for task,note in [('missing',None),('task','note')]:
            with self.assertRaises(sqlite3.IntegrityError): self.insert(task=task,note=note)
        self.insert()
        with self.assertRaises(sqlite3.IntegrityError): self.db.execute("UPDATE calendar_entries SET repeat_interval=0")
        with self.assertRaises(sqlite3.IntegrityError): self.db.execute("UPDATE calendar_entries SET reminder_mode='fake'")
    def test_atomic_restore_rolls_back_existing_data_on_invalid_snapshot(self):
        self.insert(); self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db:
                self.db.execute('DELETE FROM calendar_entries')
                self.db.execute('DELETE FROM tasks')
                self.insert(task='missing')
        self.assertEqual([('task',)],list(self.db.execute('SELECT id FROM tasks')))
        self.assertEqual([('calendar',)],list(self.db.execute('SELECT id FROM calendar_entries')))
    def test_occurrence_state_cannot_reference_missing_schedule_or_lose_snooze(self):
        self.insert()
        with self.assertRaises(sqlite3.IntegrityError): self.db.execute("INSERT INTO calendar_occurrences VALUES ('missing',1,1,'completed',NULL,'now')")
        with self.assertRaises(sqlite3.IntegrityError): self.db.execute("INSERT INTO calendar_occurrences VALUES ('calendar',1,1,'snoozed',NULL,'now')")
        self.db.execute("INSERT INTO calendar_occurrences VALUES ('calendar',1,1,'snoozed',100,'now')")
        self.assertEqual(('snoozed',100),self.db.execute('SELECT status,snoozed_until FROM calendar_occurrences').fetchone())
