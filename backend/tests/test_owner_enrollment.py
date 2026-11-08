import tempfile
import unittest
from pathlib import Path
from cryptography.fernet import Fernet
from backend.control import Control, totp
from backend.owner_enrollment import OwnerEnrollment
from backend.service import Backend, Failure, token_hash


class OwnerSetupScenarios:
    def test_capability_does_not_grant_staff_before_mfa_and_is_email_bound(self):
        invitation = self.setup.issue(self.actor['email'])
        self.assertTrue(self.setup.invited(self.actor['email'], invitation['invitation']))
        self.assertFalse(self.setup.invited('other@example.test', invitation['invitation']))
        with self.backend.connect() as db:
            self.assertFalse(db.execute('SELECT 1 FROM staff').fetchone())
            self.assertEqual(db.execute('SELECT hash FROM owner_setup').fetchone()['hash'], token_hash(invitation['invitation']))
        with self.assertRaises(Failure): self.setup.begin(self.actor, invitation['invitation'], 'incorrect-password')
        enrollment = self.setup.begin(self.actor, invitation['invitation'], self.password)
        with self.assertRaises(Failure): self.setup.finish(self.actor, enrollment['enrollment'], 'not-otp')
        with self.backend.connect() as db: self.assertFalse(db.execute('SELECT 1 FROM staff').fetchone())
        result = self.setup.finish(self.actor, enrollment['enrollment'], totp(enrollment['totp_secret'], self.now // 30))
        self.assertEqual(len(result['recovery_codes']), 8)
        self.assertFalse(self.setup.invited(self.actor['email'], invitation['invitation']))
        with self.assertRaises(Failure): self.setup.finish(self.actor, enrollment['enrollment'], totp(enrollment['totp_secret'], self.now // 30))
        with self.assertRaises(Failure): self.setup.issue(self.actor['email'])
        # Enrollment OTP cannot be replayed as a staff login.
        with self.assertRaises(Failure): Control(self.backend).login(self.actor['email'], self.password, totp(enrollment['totp_secret'], self.now // 30), 'browser')
        self.now += 30
        login = Control(self.backend).login(self.actor['email'], self.password, totp(enrollment['totp_secret'], self.now // 30), 'browser')
        self.assertIn('applications.manage', Control(self.backend).authenticate(login['token'], 'browser').permissions)

    def test_unverified_wrong_account_expiry_and_reissue(self):
        first = self.setup.issue(self.actor['email'])
        with self.assertRaises(Failure): self.setup.begin(dict(self.actor, verified=0), first['invitation'], self.password)
        with self.assertRaises(Failure): self.setup.begin(dict(self.actor, email='other@example.test'), first['invitation'], self.password)
        second = self.setup.issue(self.actor['email'])
        self.assertFalse(self.setup.invited(self.actor['email'], first['invitation']))
        self.now += 86400
        self.assertFalse(self.setup.invited(self.actor['email'], second['invitation']))
        with self.assertRaises(Failure): self.setup.begin(self.actor, second['invitation'], self.password)


class OwnerSetupTests(OwnerSetupScenarios, unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.now, self.password = 1800000000, 'synthetic-owner-passphrase'
        mail = {}
        self.backend = Backend(Path(folder.name)/'owner.db', deliver=lambda e,c: mail.update({e:c}), clock=lambda:self.now)
        self.backend.cipher = Fernet(Fernet.generate_key())
        registered = self.backend.register('owner@example.test', self.password)
        self.actor = self.backend.authenticate(registered['token'])
        self.backend.verify(self.actor, mail[self.actor['email']])
        self.actor = self.backend.authenticate(registered['token'])
        self.setup = OwnerEnrollment(self.backend)
