"""Target-bound assistance; only the original owner can consent to restoration."""
import uuid

from .account_identity import cursor, user_in
from .control import Control
from .service import identifier, require, text

STATES = {'waiting_owner', 'confirmed', 'closed', 'cancelled'}
FIELDS = ('id', 'ticket_id', 'kind', 'state', 'revision', 'created_at', 'expires_at', 'confirmed_at', 'updated_at')


class RecoveryCases:
    def __init__(self, backend):
        self.backend = backend
        self.control = Control(backend)

    def _staff(self, actor, kind=None):
        self.control.require(actor, 'users.read')
        if kind:
            self.control.require(actor, 'users.recover' if kind == 'access' else 'records.recover')
        else:
            require(bool({'users.recover', 'records.recover'} & actor.permissions), 'staff_forbidden', 403)

    def _owner(self, db, actor):
        self.backend._account_available(db, actor['id'])
        require(actor.get('verified') == 1, 'verify_email', 403)

    def _value(self, row):
        return dict({field: row[field] for field in FIELDS}, target_user_id=row['user_id'],
            expired=row['expires_at'] <= int(self.backend.clock()))

    def _case(self, db, cid, actor=None):
        row = db.execute('SELECT * FROM support_recovery_cases WHERE id=?', (identifier(cid),)).fetchone()
        require(row is not None and (actor is None or row['user_id'] == actor['id']), 'not_found', 404)
        self.backend._account_available(db, row['user_id'])
        return row

    def _detail(self, db, row, staff=False, include_requests=True):
        source = {'kind': 'ticket' if row['ticket_id'] else 'manual', 'ticket_id': row['ticket_id']}
        if staff and row['ticket_id']:
            ticket = db.execute('SELECT user_id FROM support_tickets WHERE id=?', (row['ticket_id'],)).fetchone()
            if ticket:
                source.update(author_user_id=ticket['user_id'], same_account=ticket['user_id'] == row['user_id'])
        from .record_recovery import REQUEST_FIELDS
        requests = db.execute('SELECT ' + ','.join(REQUEST_FIELDS) +
            ' FROM record_recovery_requests WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 100', (row['user_id'],)).fetchall() if include_requests else []
        return {'case': self._value(row), 'target': user_in(db, row['user_id']), 'source': source,
            'requests': [dict(item) for item in requests], 'owner_url': '/app?settings=recovery&case=' + row['id']}

    def listing(self, actor, query=None, staff=False):
        query = query or {}
        require(set(query) <= {'target_user_id', 'state', 'before'} and all(len(v) == 1 for v in query.values()), 'invalid_fields')
        state = query.get('state', [None])[0]
        require(state is None or state in STATES, 'invalid_input')
        stamp, last = cursor(query.get('before', [None])[0])
        target = query.get('target_user_id', [None])[0]
        if staff:
            self._staff(actor)
            if target is not None:
                identifier(target)
        else:
            require(target is None, 'invalid_fields')
            target = actor['id']
        sql = 'SELECT c.* FROM support_recovery_cases c LEFT JOIN account_state a ON a.user_id=c.user_id WHERE COALESCE(a.deleted_at,0)=0 AND NOT EXISTS(SELECT 1 FROM deletion_jobs j WHERE j.user_id=c.user_id AND j.state=\'erasing\') AND (c.created_at<? OR (c.created_at=? AND c.id<?))'
        params = (stamp, stamp, last)
        if staff:
            kinds = [kind for kind, permission in (('access', 'users.recover'), ('records', 'records.recover')) if permission in actor.permissions]
            sql += ' AND c.kind IN (' + ','.join('?' for _ in kinds) + ')'
            params += tuple(kinds)
        if target is not None:
            sql += ' AND c.user_id=?'
            params += (target,)
        if state is not None:
            sql += ' AND c.state=?'
            params += (state,)
        with self.backend.connect() as db:
            if not staff:
                self._owner(db, actor)
            rows = db.execute(sql + ' ORDER BY c.created_at DESC,c.id DESC LIMIT 51', params).fetchall()
            page = rows[:50]
            values = []
            for row in page:
                value = self._value(row)
                if staff:
                    target = user_in(db, row['user_id'])
                    value['target'] = {key: target[key] for key in ('id', 'email', 'display_name')}
                values.append(value)
        return {'cases': values,
            'next_before': str(page[-1]['created_at']) + ':' + page[-1]['id'] if len(rows) > 50 else None}

    def read(self, actor, cid, staff=False):
        if staff:
            self._staff(actor)
        with self.backend.connect() as db:
            if not staff:
                self._owner(db, actor)
            row = self._case(db, cid, None if staff else actor)
            if staff:
                self._staff(actor, row['kind'])
            return self._detail(db, row, staff, not staff or 'records.recover' in actor.permissions)

    def create(self, actor, body):
        require(isinstance(body, dict) and set(body) <= {'target_user_id', 'ticket_id', 'kind', 'reason'}, 'invalid_fields')
        target, kind = identifier(body.get('target_user_id')), body.get('kind')
        require(kind in ('access', 'records'))
        self._staff(actor, kind)
        reason, ticket = text(body.get('reason'), 500), body.get('ticket_id')
        if ticket is not None:
            identifier(ticket)
            self.control.require(actor, 'support.read')
        now, cid = int(self.backend.clock()), str(uuid.uuid4())
        with self.backend.transaction() as db:
            user_in(db, target)
            self.backend._account_available(db, target)
            if kind == 'access':
                self.control._target_rank(db, actor, target)
            if ticket:
                require(db.execute('SELECT 1 FROM support_tickets WHERE id=?', (ticket,)).fetchone() is not None, 'not_found', 404)
            count = db.execute('SELECT COUNT(*) AS n FROM support_recovery_cases WHERE created_by=? AND created_at>?', (actor.id, now - 900)).fetchone()['n']
            require(count < 20, 'rate_limited', 429)
            db.execute("INSERT INTO support_recovery_cases VALUES(?,?,?,?,'waiting_owner',1,?,?,0,?,?)",
                (cid, target, ticket, kind, now, now + 7 * 86400, now, actor.id))
            self.control.audit(db, actor, cid, 'recovery.case.create', {},
                {'case_id': cid, 'kind': kind, 'ticket_id': ticket, 'state': 'waiting_owner'}, reason)
            return self._detail(db, self._case(db, cid), True, 'records.recover' in actor.permissions)

    def confirm(self, actor, body):
        require(isinstance(body, dict) and set(body) == {'id', 'revision'}, 'invalid_fields')
        revision = body.get('revision')
        require(type(revision) is int and revision > 0)
        now = int(self.backend.clock())
        with self.backend.transaction() as db:
            self._owner(db, actor)
            row = self._case(db, body.get('id'), actor)
            require(row['revision'] == revision and row['state'] == 'waiting_owner' and row['expires_at'] > now, 'revision_conflict', 409)
            db.execute("UPDATE support_recovery_cases SET state='confirmed',revision=revision+1,confirmed_at=?,updated_at=? WHERE id=?", (now, now, row['id']))
            self.control.audit(db, 'user:' + actor['id'], row['id'], 'recovery.case.confirm',
                {'case_id': row['id']}, {'state': 'confirmed'}, 'Original target authenticated and confirmed assistance; no record consent granted')
            return self._detail(db, self._case(db, row['id'], actor))

    def update(self, actor, body):
        require(isinstance(body, dict) and set(body) == {'id', 'revision', 'action', 'reason'}, 'invalid_fields')
        self._staff(actor)
        revision, action = body.get('revision'), body.get('action')
        require(type(revision) is int and revision > 0 and action in ('send_reset', 'close', 'cancel'))
        reason, now = text(body.get('reason'), 500), int(self.backend.clock())
        with self.backend.transaction() as db:
            row = self._case(db, body.get('id'))
            self._staff(actor, row['kind'])
            require(row['revision'] == revision and row['state'] in ('waiting_owner', 'confirmed'), 'revision_conflict', 409)
            extra = {}
            state = row['state']
            if action == 'send_reset':
                require(row['expires_at'] > now, 'recovery_unavailable', 409)
                extra = self.control._request_recovery_in(db, actor, row['user_id'], 'Original target reset requested through assistance case ' + row['id'])
            else:
                state = 'closed' if action == 'close' else 'cancelled'
            db.execute('UPDATE support_recovery_cases SET state=?,revision=revision+1,updated_at=? WHERE id=?', (state, now, row['id']))
            self.control.audit(db, actor, row['id'], 'recovery.case.' + action,
                {'case_id': row['id'], 'revision': revision}, {'state': state, 'revision': revision + 1}, reason)
            return dict(self._detail(db, self._case(db, row['id']), True, 'records.recover' in actor.permissions), **extra)
