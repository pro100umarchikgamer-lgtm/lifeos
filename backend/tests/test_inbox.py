"""Persistent inbox boundary tests; fixtures never contact a provider or real account."""
import tempfile
import unittest
import uuid
from pathlib import Path
from cryptography.fernet import Fernet

from backend.service import Backend, Failure, token_hash
from backend.control import Control, StaffPrincipal
from backend.http_server import dispatch
from backend.web import Web
from backend.config import Settings


def uid():
    return str(uuid.uuid4())


class InboxScenarios:
    def fixtures(self):
        self.now = 1794564000
        self.backend.clock = lambda: self.now
        self.owner, self.first, self.second = [self.user() for _ in range(3)]
        self.sid = uid()
        with self.backend.transaction() as db:
            db.execute('INSERT INTO staff(id,user_id,roles,mfa_secret,created_at) VALUES(?,?,?,?,?)',
                       (self.sid, self.owner['id'], '["owner"]', b'unused', self.now))
            self.tokens = {actor['id']: self.backend.new_session(db, actor['id'], False)['token']
                           for actor in (self.owner, self.first, self.second)}
        self.staff = StaffPrincipal(self.sid, self.owner['id'], ('owner',))
        settings = Settings.load({'DATABASE_URL': 'postgresql://example/db',
            'EMAIL_QUEUE_KEY': Fernet.generate_key().decode(), 'RATE_LIMIT_KEY': 'x' * 48,
            'SMTP_HOST': '127.0.0.1', 'SMTP_TLS': 'none', 'EMAIL_FROM': 'test@example.test'})
        self.web = Web(self.backend, settings)

    def web_request(self, staff, action, body=None, **extra):
        raw = 's' * 43 if staff else 'w' * 43
        from backend.web import CONTROL_COOKIE, ACCOUNT_COOKIE
        env = {'HTTP_HOST': 'control.getuladim.space' if staff else 'getuladim.space',
            'PATH_INFO': ('/control/api/' if staff else '/account/api/') + action,
            'REQUEST_METHOD': 'POST' if body is not None else 'GET',
            'HTTP_USER_AGENT': 'fixture', 'HTTP_ORIGIN': 'https://control.getuladim.space' if staff else 'https://getuladim.space',
            'HTTP_COOKIE': (CONTROL_COOKIE if staff else ACCOUNT_COOKIE) + '=' + raw,
            'HTTP_X_CSRF_TOKEN': self.web.csrf(raw)}
        env.update(extra)
        try:
            return 200, self.web.request(env, body or {})[0]
        except Failure as error:
            return error.status, {'error': error.code}

    def web_sessions(self):
        with self.backend.transaction() as db:
            device = db.execute('SELECT id FROM devices WHERE user_id=?', (self.first['id'],)).fetchone()['id']
            db.execute('INSERT INTO web_sessions VALUES(?,?,?,?,?,?,?)',
                (token_hash('w' * 43), self.first['id'], device, self.now, self.now, self.now + 86400, token_hash('fixture')))
            db.execute('INSERT INTO control_sessions VALUES(?,?,?,?,?,?)',
                (token_hash('s' * 43), self.sid, self.now, self.now, self.now + 3600, token_hash('fixture')))

    def user(self, verified=1, deleted=False):
        actor = {'id': uid(), 'email': uid() + '@example.test', 'verified': verified}
        with self.backend.transaction() as db:
            db.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',
                       (actor['id'], actor['email'], 'unused', 'unused', verified, self.now))
            if deleted:
                db.execute('INSERT INTO account_state VALUES(?,0,?)', (actor['id'], self.now))
        return actor

    def customer(self, actor=None, suffix='', body=None, query=''):
        actor = actor or self.first
        try:
            result = dispatch(self.backend, 'POST' if body is not None else 'GET',
                '/v1/account/inbox' + suffix + query, body or {}, 'Bearer ' + self.tokens[actor['id']])
            return 200, result
        except Failure as error:
            return error.status, {'error': error.code}

    def staff_request(self, action, body=None, actor=None):
        try:
            return 200, self.web.staff_action(actor or self.staff, 'announcements' + action,
                'POST' if body is not None else 'GET', body or {}, {})
        except Failure as error:
            return error.status, {'error': error.code}

    def draft(self, **overrides):
        body = {'title': 'Product update', 'body': 'A clear plain text update.',
            'presentation': 'fullscreen', 'audience': 'users', 'user_ids': [self.first['id']],
            'starts_at': self.now, 'expires_at': self.now + 86400,
            'link': '/app?tab=calendar', 'reason': 'Fixture announcement'}
        body.update(overrides)
        status, value = self.staff_request('', body)
        self.assertEqual(status, 200, value)
        return value

    def publish(self, draft):
        status, value = self.staff_request('/publish', {'id': draft['id'],
            'revision': draft['revision'], 'reason': 'Fixture publish'})
        self.assertEqual(status, 200, value)
        return value

    def test_draft_preview_and_publish_snapshot_only_eligible_audience(self):
        unverified = self.user(verified=0)
        self.user(deleted=True)
        body = {'title': 'Update', 'body': 'Details', 'presentation': 'banner',
            'audience': 'all', 'reason': 'Preview count'}
        status, preview = self.staff_request('/preview', body)
        self.assertEqual(status, 200, preview)
        self.assertEqual(preview['recipient_count'], 3)
        self.assertEqual(self.staff_request('')[1]['announcements'], [])
        draft = self.draft(audience='all', user_ids=[])
        self.assertEqual(draft['recipient_count'], 3)
        self.assertEqual(self.customer()[1]['notifications'], [])
        published = self.publish(draft)
        self.assertEqual(published['state'], 'published')
        self.assertEqual(published['recipient_count'], 3)
        later = self.user()
        with self.backend.transaction() as db:
            db.execute('UPDATE users SET verified=1 WHERE id=?', (unverified['id'],))
            self.tokens[later['id']] = self.backend.new_session(db, later['id'], False)['token']
            self.tokens[unverified['id']] = self.backend.new_session(db, unverified['id'], False)['token']
        self.assertEqual(len(self.customer()[1]['notifications']), 1)
        self.assertEqual(self.customer(later)[1]['notifications'], [])
        self.assertEqual(self.customer(unverified)[1]['notifications'], [])
        with self.backend.connect() as db:
            audit = db.execute("SELECT after_value FROM control_audit WHERE action='announcement.publish'").fetchone()
            self.assertNotIn('Details', audit['after_value'])
            self.assertNotIn('A clear', audit['after_value'])

    def test_account_state_is_private_idempotent_and_shared_across_clients(self):
        item = self.publish(self.draft())
        self.assertEqual(self.customer()[1]['unread_count'], 1)
        for suffix in ('/read', '/dismiss', '/presented'):
            self.assertEqual(self.customer(self.second, suffix, {'id': item['id']})[0], 404)
        self.assertEqual(self.customer()[1]['notifications'][0]['read_at'], 0)
        self.assertEqual(self.customer(suffix='/presented', body={'id': item['id']})[0], 200)
        self.now += 5
        self.assertEqual(self.customer(suffix='/presented', body={'id': item['id']})[0], 200)
        row = self.customer()[1]['notifications'][0]
        self.assertEqual(row['presented_at'], self.now - 5)
        self.assertEqual(self.customer(suffix='/dismiss', body={'id': item['id']})[0], 200)
        row = self.customer()[1]['notifications'][0]
        self.assertEqual(row['dismissed_at'], self.now)
        self.assertEqual(row['read_at'], self.now)
        self.assertEqual(self.customer()[1]['unread_count'], 0)
        self.publish(self.draft(title='Another update'))
        self.assertEqual(self.customer(suffix='/read', body={'all': True})[0], 200)
        self.assertEqual(self.customer()[1]['unread_count'], 0)
        self.assertEqual(self.customer(self.second)[1]['unread_count'], 0)

    def test_scheduled_expired_and_cancelled_content_never_replays_at_startup(self):
        draft = self.draft(starts_at=self.now + 60, expires_at=self.now + 120)
        item = self.publish(draft)
        self.assertEqual(self.customer()[1]['notifications'], [])
        self.assertEqual(self.customer(suffix='/read', body={'id': item['id']})[0], 404)
        self.now += 60
        self.assertTrue(self.customer()[1]['notifications'][0]['active'])
        self.now += 60
        row = self.customer()[1]['notifications'][0]
        self.assertFalse(row['active'])
        self.assertEqual(self.customer()[1]['unread_count'], 0)
        self.assertEqual(self.customer(suffix='/presented', body={'id': item['id']})[0], 409)
        status, value = self.staff_request('/cancel', {'id': item['id'],
            'revision': item['revision'], 'reason': 'Retire fixture'})
        self.assertEqual(status, 200, value)
        self.assertFalse(self.customer()[1]['notifications'][0]['active'])

    def test_cancelling_an_unpublished_draft_never_exposes_its_content(self):
        draft = self.draft()
        self.assertEqual(self.staff_request('/cancel', {'id': draft['id'],
            'revision': draft['revision'], 'reason': 'Discard draft'})[0], 200)
        self.assertEqual(self.customer()[1]['notifications'], [])

    def test_role_audience_schedule_link_and_cursor_bounds(self):
        support = StaffPrincipal(self.sid, self.owner['id'], ('support',))
        self.assertEqual(self.staff_request('', actor=support)[0], 403)
        base = {'title': 'Update', 'body': 'Details', 'reason': 'Fixture',
            'presentation': 'inbox', 'audience': 'users', 'user_ids': [self.first['id']]}
        for extra in ({'user_ids': []}, {'user_ids': [uid()]}, {'audience': 'everyone'},
                      {'user_ids': [self.first['id']] * 101}, {'presentation': 'html'},
                      {'title': 'x' * 161}, {'body': 'x' * 4001}, {'body': 'bad\x00text'},
                      {'starts_at': self.now + 31 * 86400}, {'expires_at': self.now - 1},
                      {'link': 'https://evil.test/app'}, {'link': '//evil.test/app'},
                      {'link': '/app/../account'}, {'link': '/app\\evil'},
                      {'link': '/app/%2f%2fevil'}, {'link': '/application'}):
            with self.subTest(extra=extra):
                self.assertEqual(self.staff_request('/preview', {**base, **extra})[0], 400)
        for query in ('?limit=101', '?limit=0', '?before=bad', '?before=' + 'x' * 300):
            self.assertEqual(self.customer(query=query)[0], 400)
        draft = self.draft()
        published = self.publish(draft)
        self.assertEqual(self.staff_request('/publish', {'id': draft['id'],
            'revision': draft['revision'], 'reason': 'Replay'})[0], 409)
        self.assertEqual(published['revision'], 2)

    def test_pagination_read_all_and_web_use_same_persistent_records(self):
        ids = {self.publish(self.draft(title='Update ' + str(i)))['id'] for i in range(3)}
        status, page = self.customer(query='?limit=2')
        self.assertEqual(status, 200, page)
        self.assertEqual(len(page['notifications']), 2)
        other = self.customer(query='?limit=2&before=' + page['next_before'])[1]
        self.assertEqual({x['id'] for x in page['notifications'] + other['notifications']}, ids)
        self.assertIsNone(other['next_before'])
        web = self.web.account_action(self.first, 'inbox', 'GET', {}, {})
        self.assertEqual({x['id'] for x in web['notifications']}, ids)
        self.web.account_action(self.first, 'inbox/read', 'POST', {'all': True}, {})
        self.assertEqual(self.customer()[1]['unread_count'], 0)

    def test_cookie_origin_csrf_and_staff_role_boundaries(self):
        self.web_sessions()
        item = self.publish(self.draft())
        self.assertEqual(self.web_request(False, 'inbox', HTTP_COOKIE='')[0], 401)
        self.assertEqual(self.web_request(False, 'inbox/read', {'id': item['id']}, HTTP_X_CSRF_TOKEN='')[0], 403)
        self.assertEqual(self.web_request(False, 'inbox/read', {'id': item['id']}, HTTP_ORIGIN='https://evil.test')[0], 403)
        self.assertEqual(self.web_request(False, 'inbox/read', {'id': item['id']})[0], 200)
        self.assertEqual(self.customer()[1]['unread_count'], 0)
        self.assertEqual(self.web_request(True, 'announcements', HTTP_COOKIE='')[0], 401)
        self.assertEqual(self.web_request(True, 'announcements/preview', {}, HTTP_X_CSRF_TOKEN='')[0], 403)
        self.assertEqual(self.web_request(True, 'announcements/preview', {}, HTTP_ORIGIN='https://evil.test')[0], 403)
        with self.backend.transaction() as db:
            db.execute('UPDATE staff SET roles=? WHERE id=?', ('["support"]', self.sid))
        self.assertEqual(self.web_request(True, 'announcements')[0], 403)

    def test_account_deletion_erases_private_inbox_and_per_user_announcement_state(self):
        from backend.inbox import Inbox
        from backend.account_lifecycle import AccountLifecycle
        item = self.publish(self.draft())
        self.customer(suffix='/dismiss', body={'id': item['id']})
        with self.backend.transaction() as db:
            Inbox(self.backend).append_delivery(db, {'user_id': self.first['id']}, self.now, uid())
            db.execute("INSERT INTO deletion_jobs VALUES(?,?,?,?,'pending',NULL)",
                (uid(), self.first['id'], self.now, self.now))
        self.assertTrue(AccountLifecycle(self.backend).process_one_deletion())
        with self.backend.connect() as db:
            for table in ('inbox_notifications', 'announcement_states', 'announcement_recipients'):
                self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM ' + table + ' WHERE user_id=?', (self.first['id'],)).fetchone()['n'], 0)
            self.assertEqual(db.execute('SELECT state FROM deletion_jobs WHERE user_id=?', (self.first['id'],)).fetchone()['state'], 'completed')


class InboxTests(InboxScenarios, unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.backend = Backend(Path(folder.name) / 'inbox.db')
        self.backend.cipher = Fernet(Fernet.generate_key())
        self.fixtures()


if __name__ == '__main__':
    unittest.main()
