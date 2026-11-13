"""Persistent account inbox and explicit staff announcements; no push sending."""
import re
import uuid
from urllib.parse import unquote, urlsplit

from .control import Control
from .service import Failure, identifier, require, text

DAY = 86400
PUBLIC_FIELDS = ('id', 'kind', 'title', 'body', 'presentation', 'created_at',
                 'starts_at', 'expires_at', 'link', 'read_at', 'dismissed_at', 'presented_at')


def plain(value, limit):
    value = text(value, limit)
    require(not any(ord(char) < 32 and char not in '\n\t' or ord(char) == 127 for char in value),
            'announcement_text_invalid')
    # Text is returned as JSON and rendered as text by clients, never as markup.
    return value.strip()


def app_link(value):
    require(isinstance(value, str) and len(value) <= 1000, 'announcement_link_invalid')
    if not value:
        return ''
    decoded = unquote(value)
    parsed = urlsplit(decoded)
    require(not parsed.scheme and not parsed.netloc and '\\' not in decoded
        and not any(ord(char) <= 32 or ord(char) == 127 for char in decoded)
        and (parsed.path == '/app' or parsed.path.startswith('/app/'))
        and not any(part in ('.', '..', '') for part in parsed.path.split('/')[2:])
        and not re.search(r'%2f|%5c|%2e', value, re.I), 'announcement_link_invalid')
    return value


class Inbox:
    def __init__(self, backend):
        self.backend = backend
        self.control = Control(backend)

    def _account(self, db, actor):
        require(actor.get('verified') == 1, 'verify_email', 403)
        self.backend._account_available(db, actor['id'])

    def _union(self):
        return """SELECT n.id,n.kind,n.title,n.body,'inbox' AS presentation,
            n.created_at,n.starts_at,n.expires_at,n.link,n.read_at,n.dismissed_at,n.presented_at,
            CASE WHEN n.expires_at>? THEN 1 ELSE 0 END AS active
            FROM inbox_notifications n WHERE n.user_id=? AND n.starts_at<=?
            UNION ALL
            SELECT a.id,'announcement' AS kind,a.title,a.body,a.presentation,
            a.published_at AS created_at,a.starts_at,a.expires_at,a.link,
            COALESCE(s.read_at,0) AS read_at,COALESCE(s.dismissed_at,0) AS dismissed_at,
            COALESCE(s.presented_at,0) AS presented_at,
            CASE WHEN a.state='published' AND a.expires_at>? THEN 1 ELSE 0 END AS active
            FROM announcements a JOIN announcement_recipients r ON r.announcement_id=a.id
            LEFT JOIN announcement_states s ON s.announcement_id=a.id AND s.user_id=r.user_id
            WHERE r.user_id=? AND a.published_at>0 AND a.state IN ('published','cancelled') AND a.starts_at<=?
            UNION ALL
            SELECT n.id,'budget' AS kind,n.title,n.body,'inbox' AS presentation,
            n.created_at,n.starts_at,n.expires_at,n.link,n.read_at,n.dismissed_at,n.presented_at,
            CASE WHEN n.expires_at>? THEN 1 ELSE 0 END AS active
            FROM budget_inbox_notifications n WHERE n.user_id=? AND n.starts_at<=?"""

    def _params(self, actor, now):
        return (now, actor['id'], now, now, actor['id'], now, now, actor['id'], now)

    def list(self, actor, before=None, limit=50):
        require(type(limit) is int and 1 <= limit <= 100, 'inbox_cursor_invalid')
        stamp, last_id = 9223372036854775807, 'ffffffff-ffff-ffff-ffff-ffffffffffff'
        if before is not None:
            require(isinstance(before, str) and len(before) <= 64, 'inbox_cursor_invalid')
            parts = before.split(':')
            require(len(parts) == 2 and parts[0].isdigit() and len(parts[0]) <= 19, 'inbox_cursor_invalid')
            stamp, last_id = int(parts[0]), identifier(parts[1])
            require(0 <= stamp <= 9223372036854775807, 'inbox_cursor_invalid')
        now = int(self.backend.clock())
        with self.backend.transaction() as db:
            self._account(db, actor)
            from .budget_inbox import BudgetInbox
            evaluation = BudgetInbox(self.backend).evaluate(db, actor, now)
            union, params = self._union(), self._params(actor, now)
            rows = db.execute('SELECT * FROM (' + union + ') n WHERE created_at<? OR (created_at=? AND id<?) ORDER BY created_at DESC,id DESC LIMIT ?',
                params + (stamp, stamp, last_id, limit + 1)).fetchall()
            unread = db.execute('SELECT COUNT(*) AS n FROM (' + union + ') n WHERE active=1 AND read_at=0 AND dismissed_at=0', params).fetchone()['n']
        page = rows[:limit]
        return {'notifications': [dict({field: row[field] for field in PUBLIC_FIELDS}, active=bool(row['active'])) for row in page],
            'unread_count': unread,
            'next_before': str(page[-1]['created_at']) + ':' + page[-1]['id'] if len(rows) > limit else None,
            'budget_evaluation': evaluation}

    def settings(self, actor, body=None):
        from .budget_inbox import BudgetInbox
        with self.backend.transaction() as db:
            self._account(db, actor)
            return BudgetInbox(self.backend).settings(db, actor['id'], body)

    def mutate(self, actor, action, body):
        require(action in ('read', 'dismiss', 'presented'), 'not_found', 404)
        all_read = body.get('all') is True
        require(not all_read or action == 'read' and not body.get('id'))
        nid = None if all_read else identifier(body.get('id'))
        now = max(1, int(self.backend.clock()))
        with self.backend.transaction() as db:
            self._account(db, actor)
            if all_read:
                db.execute('UPDATE inbox_notifications SET read_at=? WHERE user_id=? AND starts_at<=? AND read_at=0', (now, actor['id'], now))
                db.execute('UPDATE budget_inbox_notifications SET read_at=? WHERE user_id=? AND starts_at<=? AND read_at=0', (now, actor['id'], now))
                db.execute("""INSERT INTO announcement_states(announcement_id,user_id,read_at)
                    SELECT a.id,r.user_id,? FROM announcements a JOIN announcement_recipients r ON r.announcement_id=a.id
                    WHERE r.user_id=? AND a.published_at>0 AND a.state IN ('published','cancelled') AND a.starts_at<=?
                    ON CONFLICT(announcement_id,user_id) DO UPDATE SET read_at=CASE WHEN announcement_states.read_at=0 THEN excluded.read_at ELSE announcement_states.read_at END""", (now, actor['id'], now))
                return {'updated': True}
            row = db.execute('SELECT * FROM (' + self._union() + ') n WHERE id=?', self._params(actor, now) + (nid,)).fetchone()
            require(row is not None, 'not_found', 404)
            if action == 'presented':
                require(row['active'] and not row['dismissed_at'], 'notification_inactive', 409)
            fields = ('read_at',) if action == 'read' else ('presented_at',) if action == 'presented' else ('dismissed_at', 'read_at', 'presented_at')
            if row['kind'] == 'announcement':
                db.execute('INSERT INTO announcement_states(announcement_id,user_id) VALUES(?,?) ON CONFLICT(announcement_id,user_id) DO NOTHING', (nid, actor['id']))
                table, clause = 'announcement_states', 'announcement_id=? AND user_id=?'
            else:
                table, clause = ('budget_inbox_notifications' if row['kind'] == 'budget' else 'inbox_notifications'), 'id=? AND user_id=?'
            updates = ','.join(field + '=CASE WHEN ' + field + '=0 THEN ? ELSE ' + field + ' END' for field in fields)
            db.execute('UPDATE ' + table + ' SET ' + updates + ' WHERE ' + clause, tuple(now for _ in fields) + (nid, actor['id']))
        return {'updated': True}

    def append_delivery(self, db, sub, now, delivery_id, event=None, occurrence=None, day=None):
        """Called inside the existing enqueue transaction, once per account/source.

        A queued reminder is history, not a claim of push receipt or delivery.
        Event titles and private record contents are deliberately not copied.
        """
        source = 'event:' + event['id'] + ':' + str(occurrence) if event else 'test:' + delivery_id
        kind = 'reminder' if event else 'test'
        link = '/app?notification=calendar&workspace=' + event['workspace_id'] + '&day=' + day if event else '/app'
        db.execute("""INSERT INTO inbox_notifications(id,user_id,source_key,kind,title,body,link,created_at,starts_at,expires_at)
            VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,source_key) DO NOTHING""",
            (str(uuid.uuid4()), sub['user_id'], source, kind, 'ULADIM',
             'Напоминание о событии календаря' if event else 'Проверка уведомлений поставлена в очередь',
             link, now, now, now + 90 * DAY))

    def _eligible(self, db, now, user_ids=None):
        sql = "SELECT u.id FROM users u LEFT JOIN account_state s ON s.user_id=u.id WHERE u.verified=1 AND COALESCE(s.deleted_at,0)=0"
        params = ()
        if user_ids is not None:
            sql += ' AND u.id IN (' + ','.join('?' for _ in user_ids) + ')'
            params = tuple(user_ids)
        return sql, params

    def _validate(self, db, body, now):
        title, message = plain(body.get('title'), 160), plain(body.get('body'), 4000)
        presentation, audience = body.get('presentation', 'inbox'), body.get('audience', 'users')
        require(presentation in ('inbox', 'banner', 'fullscreen') and audience in ('all', 'users'), 'announcement_invalid')
        recipients = body.get('user_ids', [])
        require(isinstance(recipients, list) and len(recipients) <= 100, 'announcement_audience_invalid')
        for recipient in recipients:
            identifier(recipient)
        require(len(set(recipients)) == len(recipients) and (audience == 'all' and not recipients or audience == 'users' and recipients), 'announcement_audience_invalid')
        start = body.get('starts_at', now)
        expiry = body.get('expires_at', start + 30 * DAY) if type(start) is int else None
        require(type(start) is int and 0 <= start <= now + 30 * DAY and type(expiry) is int
            and max(start, now) < expiry <= start + 90 * DAY, 'announcement_schedule_invalid')
        sql, params = self._eligible(db, now, recipients if audience == 'users' else None)
        count = db.execute('SELECT COUNT(*) AS n FROM (' + sql + ') eligible', params).fetchone()['n']
        require(audience == 'all' or count == len(recipients), 'announcement_audience_invalid')
        return {'title': title, 'body': message, 'presentation': presentation, 'audience': audience,
            'user_ids': recipients, 'starts_at': start, 'expires_at': expiry,
            'link': app_link(body.get('link', '')), 'recipient_count': count}

    def _staff_value(self, db, row):
        value = dict(row)
        value['user_ids'] = [recipient['user_id'] for recipient in db.execute(
            'SELECT user_id FROM announcement_recipients WHERE announcement_id=? ORDER BY user_id',
            (row['id'],)).fetchall()] if row['audience'] == 'users' else []
        if row['state'] == 'draft' and row['audience'] == 'all':
            sql, params = self._eligible(db, int(self.backend.clock()))
            value['recipient_count'] = db.execute('SELECT COUNT(*) AS n FROM (' + sql + ') eligible', params).fetchone()['n']
        else:
            value['recipient_count'] = db.execute('SELECT COUNT(*) AS n FROM announcement_recipients WHERE announcement_id=?', (row['id'],)).fetchone()['n']
        return value

    def announcements(self, actor):
        self.control.require(actor, 'announcements.manage')
        with self.backend.connect() as db:
            rows = db.execute('SELECT * FROM announcements ORDER BY created_at DESC,id DESC LIMIT 100').fetchall()
            return {'announcements': [self._staff_value(db, row) for row in rows]}

    def compose(self, actor, body, preview=False):
        self.control.require(actor, 'announcements.manage')
        now = int(self.backend.clock())
        with self.backend.transaction() as db:
            value = self._validate(db, body, now)
            if preview:
                return value
            reason = plain(body.get('reason'), 500)
            nid = str(uuid.uuid4())
            db.execute("""INSERT INTO announcements(id,title,body,presentation,audience,link,starts_at,expires_at,state,created_at,created_by)
                VALUES(?,?,?,?,?,?,?,?,'draft',?,?)""", (nid, value['title'], value['body'], value['presentation'],
                value['audience'], value['link'], value['starts_at'], value['expires_at'], now, actor.id))
            for recipient in value['user_ids']:
                db.execute('INSERT INTO announcement_recipients VALUES(?,?)', (nid, recipient))
            self.control.audit(db, actor, nid, 'announcement.draft', {},
                {'presentation': value['presentation'], 'audience': value['audience'], 'recipient_count': value['recipient_count']}, reason)
            return self._staff_value(db, db.execute('SELECT * FROM announcements WHERE id=?', (nid,)).fetchone())

    def transition(self, actor, body, cancel=False):
        self.control.require(actor, 'announcements.manage')
        nid, revision, reason = identifier(body.get('id')), body.get('revision'), plain(body.get('reason'), 500)
        require(type(revision) is int and revision > 0)
        now = int(self.backend.clock())
        with self.backend.transaction() as db:
            row = db.execute('SELECT * FROM announcements WHERE id=?', (nid,)).fetchone()
            require(row is not None, 'not_found', 404)
            require(row['revision'] == revision and row['state'] != 'cancelled'
                and (cancel or row['state'] == 'draft'), 'revision_conflict', 409)
            if not cancel:
                require(row['expires_at'] > now, 'announcement_expired', 409)
                if row['audience'] == 'all':
                    sql, params = self._eligible(db, now)
                    db.execute('INSERT INTO announcement_recipients(announcement_id,user_id) SELECT ?,eligible.id FROM (' + sql + ') eligible', (nid,) + params)
                else:
                    targets = [r['user_id'] for r in db.execute('SELECT user_id FROM announcement_recipients WHERE announcement_id=?', (nid,)).fetchall()]
                    require(bool(targets), 'announcement_audience_invalid')
                    sql, params = self._eligible(db, now, targets)
                    require(db.execute('SELECT COUNT(*) AS n FROM (' + sql + ') eligible', params).fetchone()['n'] == len(targets), 'announcement_audience_invalid')
            state, field = ('cancelled', 'cancelled_at') if cancel else ('published', 'published_at')
            db.execute('UPDATE announcements SET state=?,revision=revision+1,' + field + '=? WHERE id=?', (state, max(1, now), nid))
            updated = self._staff_value(db, db.execute('SELECT * FROM announcements WHERE id=?', (nid,)).fetchone())
            self.control.audit(db, actor, nid, 'announcement.' + ('cancel' if cancel else 'publish'),
                {'state': row['state'], 'revision': row['revision']},
                {'state': state, 'revision': updated['revision'], 'recipient_count': updated['recipient_count'],
                 'presentation': row['presentation'], 'starts_at': row['starts_at'], 'expires_at': row['expires_at']}, reason)
            return updated
