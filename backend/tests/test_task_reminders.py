"""Task scheduling and the real encrypted push queue, using synthetic accounts."""
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest

from cryptography.fernet import Fernet

from backend.service import Backend, Failure, token_hash
from backend.task_reminders import TaskReminders
from backend.tests.test_web_push import PushScenarios, uid


class TaskReminderTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.backend = Backend(Path(folder.name) / 'tasks.db')
        self.backend.cipher = Fernet(Fernet.generate_key())
        # The same additive migration also covers an existing SQLite fixture.
        with self.backend.connect() as db:
            db.executescript(Path('backend/migrations/021_task_reminders.sql').read_text())
        PushScenarios.fixtures(self)
        self.reminders = TaskReminders(self.backend)

    def task(self, title='Private task title'):
        rid = uid()
        data = {'title': title, 'completed': 0, 'assignment': 'any', 'assignees': [], 'review': 0}
        result = self.backend.batch(self.actor, self.workspace, [{
            'id': uid(), 'action': 'record.put', 'record_id': rid, 'revision': 0,
            'kind': 'task', 'visibility': 'private', 'audience': [], 'data': data,
        }])
        self.assertEqual(result['results'][0]['status'], 'accepted')
        return rid

    def schedule(self, offset=0, **values):
        stamp = dt.datetime.fromtimestamp(self.now + offset, dt.timezone.utc).replace(tzinfo=None)
        return {'localStart': stamp.isoformat(timespec='seconds'), 'timezone': 'UTC',
                'allDay': False, 'repeat': 'none', 'interval': 1, 'until': None, **values}

    def save(self, task, *, revision=0, reminder=True, schedule=None, actor=None):
        return self.reminders.save(actor or self.actor, {'workspace_id': self.workspace,
            'task_id': task, 'revision': revision, 'schedule': schedule or self.schedule(), 'reminder': reminder})

    def subscribe(self):
        return PushScenarios.subscribe(self)

    def jobs(self):
        with self.backend.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM web_push_deliveries ORDER BY created_at,id')]

    def test_date_without_reminder_persists_without_changing_task_shape_or_queuing(self):
        task = self.task()
        self.subscribe()
        self.save(task, reminder=False)
        saved = TaskReminders(self.backend).get(self.actor, self.workspace, task)
        self.assertEqual(saved['schedule'], self.schedule())
        self.assertFalse(saved['reminder'])
        self.assertTrue(saved['can_edit'])
        self.assertEqual(self.reminders.list(self.actor, self.workspace)['reminders'][0]['task_id'], task)
        current = self.backend.pull(self.actor, self.workspace, 0)['records'][0]
        self.assertEqual(set(current['data']), {'title', 'completed', 'assignment', 'assignees', 'review'})
        self.assertEqual(current['revision'], 1)
        self.push.scan()
        self.assertEqual(self.jobs(), [])

    def test_opt_in_waits_until_selected_time_then_uses_encrypted_queue_and_task_link(self):
        task = self.task()
        self.subscribe()
        schedule = self.schedule(60)
        self.save(task, schedule=schedule)
        self.push.scan()
        self.assertEqual(self.jobs(), [])  # Calendar's global 15-minute lead does not move task time.
        self.now += 60
        self.push.scan()
        self.push.scan()
        jobs = self.jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['event_id'], task)
        self.assertEqual(jobs[0]['expires_at'], self.now + 3600)
        payload = json.loads(self.backend.cipher.decrypt(bytes(jobs[0]['payload'])))
        self.assertEqual(payload['body'], 'Напоминание о задаче')
        self.assertEqual(payload['url'], '/app?notification=task&workspace=' + self.workspace + '&task=' + task)
        self.assertEqual(payload['priority'], 'high')
        self.assertNotIn('Private task title', json.dumps(payload))
        self.push.tick()
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.jobs()[0]['state'], 'accepted')
        with self.backend.connect() as db:
            inbox = db.execute('SELECT * FROM inbox_notifications').fetchone()
            self.assertEqual(inbox['link'], payload['url'])
            self.assertNotIn('Private task title', inbox['body'])

    def test_date_and_opt_in_do_not_create_a_browser_subscription(self):
        self.save(self.task())
        self.push.scan()
        self.assertEqual(self.jobs(), [])
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM web_push_subscriptions').fetchone()[0], 0)

    def test_task_opt_in_respects_the_browser_notification_priority_preference(self):
        self.push.subscribe(self.actor, {'subscription': self.subscription, 'lead_minutes': 15,
                                       'priority': 'normal', 'timezone': 'UTC'})
        self.save(self.task())
        self.push.tick()
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0][2]['Urgency'], 'normal')

    def test_completed_or_deleted_task_cancels_previously_queued_push(self):
        self.subscribe()
        for action in ['complete', 'delete']:
            with self.subTest(action=action):
                task = self.task()
                self.save(task)
                self.push.scan()
                if action == 'complete':
                    operation = {'id': uid(), 'action': 'record.put', 'record_id': task, 'revision': 1,
                        'kind': 'task', 'visibility': 'private', 'audience': [], 'data': {
                            'title': 'Private task title', 'completed': 1, 'assignment': 'any', 'assignees': [], 'review': 0}}
                else:
                    operation = {'id': uid(), 'action': 'record.delete', 'record_id': task, 'revision': 1}
                self.backend.batch(self.actor, self.workspace, [operation])
                self.push.tick()
                self.assertEqual(next(row for row in self.jobs() if row['event_id'] == task)['state'], 'cancelled')
        self.assertEqual(self.sent, [])

    def test_rescheduling_and_clearing_cancel_pending_delivery_and_detect_stale_revision(self):
        task = self.task()
        self.subscribe()
        saved = self.save(task)
        self.push.scan()
        self.save(task, revision=saved['revision'], schedule=self.schedule(3600))
        self.assertEqual(self.jobs()[0]['state'], 'cancelled')
        with self.assertRaises(Failure) as failure:
            self.save(task, revision=1, schedule=self.schedule(7200))
        self.assertEqual(failure.exception.code, 'revision_conflict')
        cleared = self.reminders.save(self.actor, {'workspace_id': self.workspace, 'task_id': task,
            'revision': 2, 'schedule': None, 'reminder': False})
        self.assertIsNone(cleared['schedule'])
        self.assertEqual(cleared['revision'], 3)
        self.now += 3600
        self.push.scan()
        self.push.tick()
        self.assertEqual(self.sent, [])

    def test_expired_delivery_and_revoked_membership_are_never_sent(self):
        self.subscribe()
        task = self.task()
        self.save(task)
        self.push.scan()
        self.now += 3601
        self.push.tick()
        self.assertEqual(self.jobs()[0]['error_code'], 'expired')
        second = self.task()
        self.save(second)
        self.push.scan()
        with self.backend.transaction() as db:
            db.execute('UPDATE memberships SET active=0 WHERE workspace_id=?', (self.workspace,))
        self.push.tick()
        self.assertEqual(next(row for row in self.jobs() if row['event_id'] == second)['state'], 'cancelled')
        self.assertEqual(self.sent, [])

    def test_cross_account_private_task_is_neither_listed_nor_writable(self):
        task = self.task()
        self.save(task)
        other = self.other_actor()
        self.assertEqual(self.reminders.list(other, self.workspace)['reminders'], [])
        for operation in [lambda: self.reminders.get(other, self.workspace, task),
                          lambda: self.save(task, actor=other, revision=1)]:
            with self.assertRaises(Failure):
                operation()
        workspace = uid()
        with self.backend.transaction() as db:
            db.execute("INSERT INTO workspaces(id,name,creator_id,kind) VALUES(?,?,?,'personal')", (workspace, 'Second personal space', self.user))
            db.execute("INSERT INTO memberships(workspace_id,user_id,role) VALUES(?,?,'owner')", (workspace, self.user))
        with self.assertRaises(Failure):
            self.reminders.get(self.actor, workspace, task)

    def other_actor(self, *, role='adult', permissions='[]'):
        user, device, profile = uid(), uid(), uid()
        actor = {'id': user, 'device_id': device, 'verified': 1, 'email': user + '@example.test'}
        with self.backend.transaction() as db:
            db.execute('INSERT INTO users VALUES(?,?,?,?,1,?)', (user, actor['email'], 'unused', 'unused', self.now))
            db.execute('INSERT INTO devices VALUES(?,?,?,?,?,?,0)', (device, user, uid(), 'Browser', self.now, self.now))
            db.execute('INSERT INTO web_sessions VALUES(?,?,?,?,?,?,?)', (token_hash(device), user, device, self.now, self.now, self.now + 86400, token_hash('fixture')))
            db.execute('INSERT INTO profiles(id,workspace_id,name,permissions) VALUES(?,?,?,?)', (profile, self.workspace, 'Synthetic member', permissions))
            db.execute('INSERT INTO memberships(workspace_id,user_id,role,profile_id) VALUES(?,?,?,?)', (self.workspace, user, role, profile))
        return actor

    def test_read_only_grant_and_completion_only_child_cannot_change_schedule(self):
        task = self.task()
        self.save(task)
        for role, permissions in [('adult', '[]'), ('child', '["complete_tasks"]')]:
            actor = self.other_actor(role=role, permissions=permissions)
            with self.backend.transaction() as db:
                db.execute('INSERT INTO grants VALUES(?,?,0)', (task, actor['id']))
            self.assertFalse(self.reminders.get(actor, self.workspace, task)['can_edit'])
            with self.assertRaises(Failure):
                self.save(task, revision=1, actor=actor)

    def test_revoked_private_grant_suppresses_task_delivery(self):
        task = self.task()
        self.save(task)
        actor = self.other_actor()
        with self.backend.transaction() as db:
            db.execute('INSERT INTO grants VALUES(?,?,0)', (task, actor['id']))
        self.push.subscribe(actor, {'subscription': self.subscription, 'lead_minutes': 15, 'priority': 'high', 'timezone': 'UTC'})
        self.push.scan()
        with self.backend.transaction() as db:
            db.execute('DELETE FROM grants WHERE record_id=? AND user_id=?', (task, actor['id']))
        self.push.tick()
        self.assertEqual(self.jobs()[0]['state'], 'cancelled')
        self.assertEqual(self.sent, [])

    def test_account_erasure_removes_schedule_metadata_and_prevents_pending_push(self):
        from backend.account_erasure import erase_in
        task = self.task()
        self.subscribe()
        self.save(task)
        self.push.scan()
        with self.backend.transaction() as db:
            erase_in(self.backend, db, self.user, self.now)
            erase_in(self.backend, db, self.user, self.now)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM task_reminders').fetchone()[0], 0)
        self.push.tick()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.jobs(), [])

    def test_invalid_schedule_never_writes_and_completed_task_cannot_enable_reminder(self):
        task = self.task()
        for schedule, reminder in [(None, True), (self.schedule(timezone='Invalid/Zone'), True),
                                   (self.schedule(localStart='2026-11-13T10:00:00Z'), False),
                                   (self.schedule(extra=True), False)]:
            with self.subTest(schedule=schedule), self.assertRaises(Failure):
                self.reminders.save(self.actor, {'workspace_id': self.workspace, 'task_id': task,
                    'revision': 0, 'schedule': schedule, 'reminder': reminder})
        with self.backend.transaction() as db:
            db.execute('UPDATE tasks SET completed=1 WHERE id=?', (task,))
        with self.assertRaises(Failure) as failure:
            self.save(task)
        self.assertEqual(failure.exception.code, 'task_completed')
        self.assertEqual(self.reminders.get(self.actor, self.workspace, task)['revision'], 0)
