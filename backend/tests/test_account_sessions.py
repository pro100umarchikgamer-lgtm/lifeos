import tempfile
import unittest
from pathlib import Path

from backend.service import Backend, Failure


class SessionScenarios:
    def login(self):
        return self.backend.login(self.p1['email'], 'a-valid-long-passphrase')

    def test_access_expiry_refresh_rotation_and_replay_revoke_family(self):
        first = self.login()
        other = self.login()
        now = int(self.backend.clock())
        self.backend.clock = lambda: now + 901
        with self.assertRaises(Failure):
            self.backend.authenticate(first['token'])
        second = self.backend.refresh_session(first['refresh_token'])
        self.assertNotEqual(first['refresh_token'], second['refresh_token'])
        self.assertEqual(self.backend.authenticate(second['token'])['id'], self.p1['id'])
        with self.assertRaises(Failure) as caught:
            self.backend.refresh_session(first['refresh_token'])
        self.assertEqual(caught.exception.code, 'refresh_replay')
        for action in [lambda: self.backend.authenticate(second['token']),
                       lambda: self.backend.refresh_session(second['refresh_token'])]:
            with self.assertRaises(Failure): action()
        # A stolen token cannot revoke another legitimate device family.
        self.assertIn('token', self.backend.refresh_session(other['refresh_token']))

    def test_refresh_has_absolute_lifetime_and_revokes_with_logout(self):
        first = self.login()
        self.backend.logout(first['token'])
        with self.assertRaises(Failure): self.backend.refresh_session(first['refresh_token'])
        second = self.login()
        now = int(self.backend.clock())
        self.backend.clock = lambda: now + 30 * 86400
        with self.assertRaises(Failure): self.backend.refresh_session(second['refresh_token'])

    def test_device_scope_and_reauthentication_counters_commit(self):
        first = self.login()
        rows = self.backend.list_devices(self.p1, first['token'])['devices']
        self.assertEqual([r['id'] for r in rows if r['current']], [first['device_id']])
        with self.assertRaises(Failure):
            self.backend.revoke_device(self.p2, first['device_id'], 'a-valid-long-passphrase')
        for _ in range(10):
            with self.assertRaises(Failure) as error:
                self.backend.revoke_device(self.p1, first['device_id'], 'wrong-password')
            self.assertEqual(error.exception.code, 'invalid_credentials')
        with self.assertRaises(Failure) as error:
            self.backend.revoke_device(self.p1, first['device_id'], 'a-valid-long-passphrase')
        self.assertEqual(error.exception.code, 'rate_limited')
        self.assertEqual(self.backend.authenticate(first['token'])['id'], self.p1['id'])

    def test_password_reset_and_revoke_all_invalidate_refresh(self):
        first = self.login()
        self.backend.recover(self.p1['email'])
        self.backend.reset_password(self.p1['email'], self.mail[self.p1['email']], 'Another-valid-phrase')
        with self.assertRaises(Failure): self.backend.refresh_session(first['refresh_token'])
        session = self.backend.login(self.p1['email'], 'Another-valid-phrase')
        self.backend.revoke_all(self.p1, 'Another-valid-phrase')
        with self.assertRaises(Failure): self.backend.refresh_session(session['refresh_token'])

    def test_tokens_are_hashed_and_malformed_tokens_are_rejected(self):
        session = self.login()
        with self.backend.connect() as db:
            hashes = [r['hash'] for r in db.execute('SELECT hash FROM refresh_tokens').fetchall()]
        self.assertNotIn(session['refresh_token'], hashes)
        for bad in [None, [], 'short', 'x' * 43]:
            with self.assertRaises(Failure): self.backend.refresh_session(bad)


class AccountSessionTests(SessionScenarios, unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.mail = {}
        self.backend = Backend(Path(self.folder.name) / 'sessions.db', deliver=lambda e, c: self.mail.update({e: c}))
        self.p1 = self.user('one@example.test')
        self.p2 = self.user('two@example.test')

    def user(self, email):
        result = self.backend.register(email, 'a-valid-long-passphrase')
        return self.backend.authenticate(result['token'])
