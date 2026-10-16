import tempfile
import unittest
from pathlib import Path
from cryptography.fernet import Fernet
from backend.service import Backend,Failure
from backend.customer_mfa import CustomerMFA
from backend.control import totp

class MFAScenarios:
    def setup_mfa(self):
        self.mfa=CustomerMFA(self.backend);self.now=int(self.backend.clock());self.backend.clock=lambda:self.now

    def enroll(self):
        value=self.mfa.begin(self.p1,'a-valid-long-passphrase')
        code=totp(value['totp_secret'],self.now//30)
        result=self.mfa.enable(self.p1,'a-valid-long-passphrase',value['enrollment'],code)
        return value,result

    def test_totp_enrollment_login_replay_recovery_and_reset_no_bypass(self):
        value,result=self.enroll()
        self.assertTrue(self.mfa.status(self.p1)['enabled'])
        self.assertEqual(self.backend.login(self.p1['email'],'a-valid-long-passphrase'),{'mfa_required':True})
        with self.assertRaises(Failure):self.backend.login(self.p1['email'],'a-valid-long-passphrase',totp(value['totp_secret'],self.now//30))
        self.now+=30
        code=totp(value['totp_secret'],self.now//30)
        login=self.backend.login(self.p1['email'],'a-valid-long-passphrase',code)
        with self.assertRaises(Failure):self.backend.login(self.p1['email'],'a-valid-long-passphrase',code)
        self.backend.recover(self.p1['email'])
        self.backend.reset_password(self.p1['email'],self.mail[self.p1['email']],'another-valid-password')
        self.assertEqual(self.backend.login(self.p1['email'],'another-valid-password'),{'mfa_required':True})
        recovered=self.backend.login(self.p1['email'],'another-valid-password',result['recovery_codes'][0])
        with self.assertRaises(Failure):self.backend.login(self.p1['email'],'another-valid-password',result['recovery_codes'][0])
        self.assertEqual(self.backend.authenticate(recovered['token'])['id'],self.p1['id'])
        with self.assertRaises(Failure):self.backend.authenticate(login['token'])
        self.assertEqual(self.mfa.status(self.p1)['recovery_codes_remaining'],7)

    def test_customer_mfa_scope_disable_requires_second_factor_and_revokes(self):
        value=self.mfa.begin(self.p1,'a-valid-long-passphrase')
        with self.assertRaises(Failure):self.mfa.enable(self.p2,'a-valid-long-passphrase',value['enrollment'],totp(value['totp_secret'],self.now//30))
        result=self.mfa.enable(self.p1,'a-valid-long-passphrase',value['enrollment'],totp(value['totp_secret'],self.now//30))
        with self.assertRaises(Failure):self.mfa.disable(self.p1,'a-valid-long-passphrase','000000')
        self.mfa.disable(self.p1,'a-valid-long-passphrase',result['recovery_codes'][0])
        self.assertFalse(self.mfa.status(self.p1)['enabled'])
        self.assertIn('token',self.backend.login(self.p1['email'],'a-valid-long-passphrase'))
        with self.backend.connect() as db:self.assertIsNone(db.execute('SELECT 1 FROM account_recovery WHERE user_id=?',(self.p1['id'],)).fetchone())

    def test_failed_mfa_attempts_commit_rate_limit_without_sessions(self):
        _,result=self.enroll()
        for i in range(10):
            try:self.backend.login(self.p1['email'],'a-valid-long-passphrase','invalid-factor')
            except Failure:pass
        with self.assertRaises(Failure) as raised:self.backend.login(self.p1['email'],'a-valid-long-passphrase',result['recovery_codes'][0])
        self.assertEqual(raised.exception.code,'rate_limited')
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM sessions WHERE user_id=?',(self.p1['id'],)).fetchone()['n'],0)

class CustomerMFATests(MFAScenarios,unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup);self.mail={}
        self.backend=Backend(Path(folder.name)/'mfa.db',deliver=lambda e,c:self.mail.update({e:c}));self.backend.cipher=Fernet(Fernet.generate_key())
        self.p1=self.user('owner@example.test');self.p2=self.user('second@example.test');self.setup_mfa()
    def user(self,email):
        result=self.backend.register(email,'a-valid-long-passphrase');actor=self.backend.authenticate(result['token']);self.backend.verify(actor,self.mail[email]);return self.backend.authenticate(result['token'])
