"""Explicit user-authored support messages; no automatic personal-data upload."""
import uuid
from .service import require, text, identifier
from .control import scrub

CATEGORIES = {'account', 'sync', 'billing', 'bug', 'other'}
STATES = {'open', 'waiting', 'resolved'}

class Support:
    def __init__(self, backend, control):
        self.backend, self.control = backend, control

    def _writable(self, db, uid):
        hold = db.execute("SELECT until_at FROM service_holds WHERE user_id=? AND service='support_write'", (uid,)).fetchone()
        require(not hold or hold['until_at'] <= int(self.backend.clock()), 'support_restricted', 403)

    def list(self, actor, staff=False):
        if staff: self.control.require(actor, 'support.read')
        with self.backend.connect() as db:
            sql = 'SELECT id,user_id,category,subject,state,priority,created_at,updated_at FROM support_tickets'
            rows = db.execute(sql + (' ORDER BY updated_at DESC LIMIT 100' if staff else ' WHERE user_id=? ORDER BY updated_at DESC LIMIT 100'), () if staff else (actor['id'],)).fetchall()
        return {'tickets': [dict(r) for r in rows]}

    def _ticket(self, db, actor, tid, staff):
        identifier(tid)
        if staff: self.control.require(actor, 'support.read')
        row = db.execute('SELECT * FROM support_tickets WHERE id=?', (tid,)).fetchone()
        require(row is not None and (staff or row['user_id'] == actor['id']), 'not_found', 404)
        return row

    def read(self, actor, tid, staff=False):
        with self.backend.connect() as db:
            row = self._ticket(db, actor, tid, staff)
            messages = db.execute('SELECT id,is_staff,body,created_at FROM support_messages WHERE ticket_id=? ORDER BY created_at,id LIMIT 200', (tid,)).fetchall()
        return {'ticket': dict(row), 'messages': [dict(m) for m in messages]}

    def create(self, actor, category, subject, body):
        require(actor['verified'] == 1, 'verify_email', 403)
        require(category in CATEGORIES)
        subject, body = scrub(text(subject, 160)), scrub(text(body, 8000))
        now, tid = int(self.backend.clock()), str(uuid.uuid4())
        with self.backend.transaction() as db:
            self._writable(db, actor['id'])
            count = db.execute('SELECT COUNT(*) AS n FROM support_tickets WHERE user_id=? AND created_at>?', (actor['id'], now - 86400)).fetchone()['n']
            require(count < 10, 'rate_limited', 429)
            db.execute('INSERT INTO support_tickets VALUES(?,?,?,?,?,?,?,?,0)', (tid, actor['id'], category, subject, 'open', 'normal', now, now))
            self._message(db, tid, actor['id'], False, body, now)
        return {'ticket_id': tid}

    def _message(self, db, tid, aid, staff, body, now):
        count = db.execute('SELECT COUNT(*) AS n FROM support_messages WHERE ticket_id=?', (tid,)).fetchone()['n']
        require(count < 200, 'thread_limit', 409)
        db.execute('INSERT INTO support_messages VALUES(?,?,?,?,?,?)', (str(uuid.uuid4()), tid, aid, int(staff), body, now))

    def reply(self, actor, tid, body, state='open', staff=False):
        if staff: self.control.require(actor, 'support.reply')
        require(state in STATES)
        body, now = scrub(text(body, 8000)), int(self.backend.clock())
        with self.backend.transaction() as db:
            prior = self._ticket(db, actor, tid, staff)
            if not staff: self._writable(db, actor['id'])
            self._message(db, tid, actor.id if staff else actor['id'], staff, body, now)
            db.execute('UPDATE support_tickets SET state=?,updated_at=? WHERE id=?', (state, now, tid))
            if staff: self.control.audit(db, actor, prior['user_id'], 'support.reply', {'ticket_id': tid, 'state': prior['state']}, {'ticket_id': tid, 'state': state}, 'Staff support response')
        return {'updated': True}
