"""Per-address abuse limits and generic recovery replies on disposable accounts."""
import tempfile
import unittest
from pathlib import Path
from backend.login_flow import LoginFlow
from backend.service import Backend, Failure

PASSWORD = 'synthetic-address-limit-password'

class AddressLimitScenarios:
    def setup_limits(self):
        self.now = int(self.backend.clock())
        self.backend.clock = lambda: self.now

    def test_recovery_unknown_address_has_same_reply_without_mail_and_same_cooldown(self):
        known, unknown = self.p1['email'], 'unregistered@example.test'
        before = dict(self.mail)
        self.assertEqual(self.backend.recover(known), self.backend.recover(unknown))
        self.assertNotIn(unknown, self.mail)
        self.assertNotEqual(before[known], self.mail[known])
        for address in (known.upper(), unknown.upper()):
            with self.assertRaises(Failure) as error:
                self.backend.recover(address)
            self.assertEqual((error.exception.code, error.exception.status), ('rate_limited', 429))
        self.now += 61
        self.assertEqual(self.backend.recover(known), self.backend.recover(unknown))
        self.assertNotIn(unknown, self.mail)

    def test_web_and_native_login_share_normalized_address_limit_without_new_sessions(self):
        flow = LoginFlow(self.backend)
        for address in (self.p1['email'], 'unregistered@example.test'):
            with self.backend.connect() as db:
                before = db.execute('SELECT COUNT(*) AS n FROM sessions').fetchone()['n']
            for index in range(10):
                with self.assertRaises(Failure) as error:
                    if index % 2:
                        flow.begin(address.upper(), 'incorrect-password', 'synthetic-browser')
                    else:
                        self.backend.login(address, 'incorrect-password')
                self.assertEqual(error.exception.code, 'invalid_credentials')
            with self.assertRaises(Failure) as error:
                flow.begin(address, PASSWORD, 'synthetic-browser')
            self.assertEqual((error.exception.code, error.exception.status), ('rate_limited', 429))
            with self.backend.connect() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM sessions').fetchone()['n'], before)

    def test_reset_failures_persist_per_address_limit_and_expire_without_consuming_real_code(self):
        known, unknown = self.p1['email'], 'unregistered@example.test'
        self.backend.recover(known)
        real_code = self.mail[known]
        for address in (known, unknown):
            for index in range(10):
                with self.assertRaises(Failure) as error:
                    self.backend.reset_password(address.upper() if index % 2 else address, 'x' * 43, PASSWORD)
                self.assertEqual(error.exception.code, 'verification_invalid')
            with self.assertRaises(Failure) as error:
                self.backend.reset_password(address, real_code, PASSWORD)
            self.assertEqual((error.exception.code, error.exception.status), ('rate_limited', 429))
        self.now += 901
        # Request a fresh code after the limit window; the old code has expired.
        self.backend.recover(known)
        self.assertEqual(self.backend.reset_password(known.upper(), self.mail[known], PASSWORD), {'password_reset': True})
        self.assertNotIn(unknown, self.mail)

class AddressLimitTests(AddressLimitScenarios, unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.mail = {}
        self.backend = Backend(Path(folder.name) / 'limits.db', deliver=lambda email, code: self.mail.update({email: code}))
        session = self.backend.register('known@example.test', PASSWORD)
        self.p1 = self.backend.authenticate(session['token'])
        self.backend.verify(self.p1, self.mail[self.p1['email']])
        self.setup_limits()
