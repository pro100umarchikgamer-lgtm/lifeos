"""Per-address abuse limits and generic recovery replies on disposable accounts."""
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
from backend.login_flow import LoginFlow
from backend.service import Backend, Failure, token_hash

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

    def concurrent(self, action):
        barrier=Barrier(12)
        def invoke(index):
            barrier.wait(timeout=15)
            try:
                action(index)
                return 'accepted'
            except Failure as error:
                return error.code
        with ThreadPoolExecutor(max_workers=12) as pool:
            return list(pool.map(invoke,range(12)))

    def test_parallel_web_and_native_login_cannot_lose_address_attempts(self):
        flow=LoginFlow(self.backend)
        for address in (self.p1['email'],'unknown-parallel@example.test'):
            outcomes=self.concurrent(lambda i:flow.begin(address.upper(),'incorrect-password','synthetic-browser') if i%2 else self.backend.login(address,'incorrect-password'))
            self.assertEqual(outcomes.count('invalid_credentials'),10,outcomes)
            self.assertEqual(outcomes.count('rate_limited'),2,outcomes)
            with self.backend.connect() as db:
                self.assertEqual(db.execute('SELECT count FROM auth_limits WHERE key=?',(token_hash(address),)).fetchone()['count'],10)

    def test_parallel_recovery_only_reserves_one_request_and_one_known_address_mail(self):
        sent=[];original=self.backend._deliver
        def capture(db,email,code,purpose):
            original(db,email,code,purpose);sent.append((email,purpose))
        self.backend._deliver=capture
        for address in (self.p1['email'],'unknown-parallel@example.test'):
            outcomes=self.concurrent(lambda i:self.backend.recover(address.upper() if i%2 else address))
            self.assertEqual(outcomes.count('accepted'),1,outcomes)
            self.assertEqual(outcomes.count('rate_limited'),11,outcomes)
        self.assertEqual(sent,[(self.p1['email'],'recovery')])

    def test_erasure_removes_reset_address_counter_without_erasing_other_address_limits(self):
        from backend.account_erasure import erase_in
        unknown='unknown-parallel@example.test'
        for address in (self.p1['email'],unknown):
            with self.assertRaises(Failure):self.backend.reset_password(address,'x'*43,PASSWORD)
        with self.backend.transaction() as db:erase_in(self.backend,db,self.p1['id'],self.now)
        with self.backend.connect() as db:
            self.assertIsNone(db.execute('SELECT count FROM auth_limits WHERE key=?',(token_hash('password-reset:'+self.p1['email']),)).fetchone())
            self.assertIsNotNone(db.execute('SELECT count FROM auth_limits WHERE key=?',(token_hash('password-reset:'+unknown),)).fetchone())

class AddressLimitTests(AddressLimitScenarios, unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.mail = {}
        self.backend = Backend(Path(folder.name) / 'limits.db', deliver=lambda email, code: self.mail.update({email: code}))
        session = self.backend.register('known@example.test', PASSWORD)
        self.p1 = self.backend.authenticate(session['token'])
        self.backend.verify(self.p1, self.mail[self.p1['email']])
        self.setup_limits()
