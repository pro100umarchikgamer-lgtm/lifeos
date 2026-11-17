"""Persisted task dates and opt-in reminders using existing record authority.

Task data and synchronization payloads remain unchanged. Web Push owns delivery;
this module does not create subscriptions or claim an Android alarm was scheduled.
"""
import json
import uuid

from .service import canonical, identifier, require


class TaskReminders:
    def __init__(self, backend):
        self.backend = backend

    def _task(self, db, actor, workspace, task_id):
        identifier(workspace)
        identifier(task_id)
        space = self.backend._workspace(db, actor, workspace)
        task = db.execute("SELECT r.*,t.title,t.completed FROM records r JOIN tasks t ON t.id=r.id WHERE r.id=? AND r.workspace_id=? AND r.kind='task' AND r.deleted=0", (task_id, workspace)).fetchone()
        require(task is not None, 'record_missing', 404)
        require(self.backend._readable(db, actor, space, task), 'record_forbidden', 403)
        return space, task

    def _editable(self, db, actor, space, task):
        if not self.backend._editable(db, actor, space, task):
            return False
        # Completing an assigned task is not permission to change its schedule.
        return space['role'] != 'child' or (
            task['owner_id'] == actor['id'] and 'edit_own' in self.backend._permissions(db, space))

    def _public(self, db, actor, space, task, row):
        return {'task_id': task['id'], 'revision': row['revision'] if row else 0,
                'schedule': json.loads(row['schedule']) if row and row['schedule'] else None,
                'reminder': bool(row and row['reminder']),
                'updated_at': row['updated_at'] if row else 0,
                'can_edit': self._editable(db, actor, space, task)}

    def get(self, actor, workspace, task_id):
        with self.backend.connect() as db:
            space, task = self._task(db, actor, workspace, task_id)
            row = db.execute('SELECT * FROM task_reminders WHERE task_id=?', (task_id,)).fetchone()
            return self._public(db, actor, space, task, row)

    def list(self, actor, workspace):
        identifier(workspace)
        with self.backend.connect() as db:
            space = self.backend._workspace(db, actor, workspace)
            rows = db.execute("SELECT r.* FROM records r JOIN task_reminders tr ON tr.task_id=r.id WHERE r.workspace_id=? AND r.kind='task' AND r.deleted=0 AND tr.schedule IS NOT NULL ORDER BY r.id", (workspace,)).fetchall()
            values = []
            for task in rows:
                if self.backend._readable(db, actor, space, task):
                    row = db.execute('SELECT * FROM task_reminders WHERE task_id=?', (task['id'],)).fetchone()
                    values.append(self._public(db, actor, space, task, row))
            return {'reminders': values}

    def save(self, actor, body):
        require(isinstance(body, dict) and set(body) == {
            'workspace_id', 'task_id', 'revision', 'schedule', 'reminder'}, 'task_reminder_invalid')
        workspace, task_id, expected = body['workspace_id'], body['task_id'], body['revision']
        schedule, enabled = body['schedule'], body['reminder']
        require(type(expected) is int and expected >= 0 and type(enabled) is bool, 'task_reminder_invalid')
        require(schedule is not None or not enabled, 'task_reminder_invalid')
        with self.backend.transaction() as db:
            space, task = self._task(db, actor, workspace, task_id)
            require(self._editable(db, actor, space, task), 'record_forbidden', 403)
            if space['kind'] == 'family':
                self.backend.check_service(db, actor['id'], 'family_write')
            if schedule is not None:
                # Reuse the cloud calendar's exact schedule validator and timezone rules.
                self.backend._validate_data(db, workspace, 'event', {'title': task['title'], 'schedule': schedule},
                                            json.loads(task['audience']), actor, space)
            require(not enabled or not task['completed'], 'task_completed', 409)
            old = db.execute('SELECT * FROM task_reminders WHERE task_id=?', (task_id,)).fetchone()
            require((old['revision'] if old else 0) == expected, 'revision_conflict', 409)
            value, now = canonical(schedule) if schedule is not None else None, int(self.backend.clock())
            if old and old['schedule'] == value and bool(old['reminder']) == enabled:
                return self._public(db, actor, space, task, old)
            db.execute('INSERT INTO task_reminders(task_id,revision,schedule,reminder,updated_at,updated_by) VALUES(?,?,?,?,?,?) ON CONFLICT(task_id) DO UPDATE SET revision=excluded.revision,schedule=excluded.schedule,reminder=excluded.reminder,updated_at=excluded.updated_at,updated_by=excluded.updated_by',
                       (task_id, expected + 1, value, int(enabled), now, actor['id']))
            db.execute("UPDATE web_push_deliveries SET state='cancelled',payload=?,error_code='event_changed' WHERE event_id=? AND state IN ('queued','sending')", (b'', task_id))
            row = db.execute('SELECT * FROM task_reminders WHERE task_id=?', (task_id,)).fetchone()
            return self._public(db, actor, space, task, row)

    @staticmethod
    def link(task):
        return '/app?notification=task&workspace=' + task['workspace_id'] + '&task=' + task['id']

    def authorize_delivery(self, db, actor, task, job):
        metadata = db.execute('SELECT * FROM task_reminders WHERE task_id=?', (task['id'],)).fetchone()
        status = db.execute('SELECT completed FROM tasks WHERE id=?', (task['id'],)).fetchone()
        require(metadata and metadata['reminder'] and metadata['schedule'] and
                metadata['revision'] == job['event_revision'] and status and not status['completed'],
                'event_changed', 403)
        space = self.backend._workspace(db, actor, task['workspace_id'])
        require(self.backend._readable(db, actor, space, task), 'event_forbidden', 403)

    def append_delivery(self, db, sub, now, task, occurrence):
        from . import inbox_retention as retention
        db.execute("""INSERT INTO inbox_notifications(id,user_id,source_key,kind,title,body,link,created_at,starts_at,expires_at)
            VALUES(?,?,?,'reminder','ULADIM',?,?,?,?,?) ON CONFLICT(user_id,source_key) DO NOTHING""",
            (str(uuid.uuid4()), sub['user_id'], 'task:' + task['id'] + ':' + str(occurrence),
             'Напоминание о задаче', self.link(task), now, now, now + 90 * 86400))
        retention.sweep_user(db, sub['user_id'], now)
