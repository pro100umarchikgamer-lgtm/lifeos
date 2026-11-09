import tempfile
import unittest
from pathlib import Path
from cryptography.fernet import Fernet
from backend.service import Backend, Failure
from backend.login_flow import LoginFlow
from backend.customer_mfa import CustomerMFA
from backend.control import Control, totp
from backend.account_lifecycle import AccountLifecycle


class LoginFlowScenarios:
    def setup_flow(self):
        self.now = int(self.backend.clock())
        self.backend.clock = lambda: self.now
        self.flow = LoginFlow(self.backend)

    def enroll_factor(self):
        mfa = CustomerMFA(self.backend)
        value = mfa.begin(self.actor, self.password)
        result = mfa.enable(self.actor, self.password, value['enrollment'], totp(value['totp_secret'], self.now // 30))
        self.now += 30
        return value, result

    def test_no_factor_creates_session_wrong_password_and_unknown_never_disclose_mfa(self):
        self.assertEqual(self.backend.authenticate(self.flow.begin(self.actor['email'], self.password, 'browser')['token'])['id'], self.actor['id'])
        self.enroll_factor()
        for email, password in [(self.actor['email'], 'incorrect-password'), ('missing@example.test', self.password)]:
            with self.assertRaises(Failure) as error:
                self.flow.begin(email, password, 'browser')
            self.assertEqual((error.exception.code, error.exception.status), ('invalid_credentials', 401))

    def test_factor_is_single_use_scope_and_agent_bound_without_early_session(self):
        value, _ = self.enroll_factor()
        challenge = self.flow.begin(self.actor['email'], self.password, 'browser')
        self.assertEqual(set(challenge), {'challenge', 'mfa_required', 'expires_in'})
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM sessions WHERE user_id=?', (self.actor['id'],)).fetchone()['n'], 0)
        code = totp(value['totp_secret'], self.now // 30)
        for agent, staff in [('other-browser', False), ('browser', True)]:
            with self.assertRaises(Failure): self.flow.finish(challenge['challenge'], code, agent, staff)
        session = self.flow.finish(challenge['challenge'], code, 'browser')
        self.assertEqual(self.backend.authenticate(session['token'])['id'], self.actor['id'])
        with self.assertRaises(Failure): self.flow.finish(challenge['challenge'], code, 'browser')

    def test_factor_failures_commit_five_attempt_limit_and_expiry(self):
        _, recovery = self.enroll_factor()
        challenge = self.flow.begin(self.actor['email'], self.password, 'browser')['challenge']
        for _ in range(5):
            with self.assertRaises(Failure): self.flow.finish(challenge, 'invalid', 'browser')
        with self.assertRaises(Failure): self.flow.finish(challenge, recovery['recovery_codes'][0], 'browser')
        challenge = self.flow.begin(self.actor['email'], self.password, 'browser')['challenge']
        self.now += 301
        with self.assertRaises(Failure): self.flow.finish(challenge, recovery['recovery_codes'][0], 'browser')

    def test_password_reset_and_factor_changes_invalidate_pending_challenge(self):
        _, recovery = self.enroll_factor()
        challenge = self.flow.begin(self.actor['email'], self.password, 'browser')['challenge']
        self.backend.recover(self.actor['email'])
        self.backend.reset_password(self.actor['email'], self.mail[self.actor['email']], 'updated-valid-password')
        with self.assertRaises(Failure): self.flow.finish(challenge, recovery['recovery_codes'][0], 'browser')
        self.assertTrue(self.flow.begin(self.actor['email'], 'updated-valid-password', 'browser')['mfa_required'])

    def test_customer_and_staff_recovery_require_password_and_consumption(self):
        _, recovery = self.enroll_factor()
        challenge = self.flow.begin(self.actor['email'], self.password, 'browser')['challenge']
        self.assertIn('token', self.flow.finish(challenge, recovery['recovery_codes'][0], 'browser'))
        challenge = self.flow.begin(self.actor['email'], self.password, 'browser')['challenge']
        with self.assertRaises(Failure): self.flow.finish(challenge, recovery['recovery_codes'][0], 'browser')
        control = Control(self.backend)
        staff = control.bootstrap(self.actor['email'])
        challenge = self.flow.begin(self.actor['email'], self.password, 'browser', True)['challenge']
        session = self.flow.finish(challenge, staff['recovery_codes'][0], 'browser', True)
        self.assertEqual(control.authenticate(session['token'], 'browser').user_id, self.actor['id'])
        challenge = self.flow.begin(self.actor['email'], self.password, 'browser', True)['challenge']
        with self.assertRaises(Failure): self.flow.finish(challenge, staff['recovery_codes'][0], 'browser', True)

    def test_resend_is_generic_rate_limited_and_replaces_old_verification(self):
        lifecycle = AccountLifecycle(self.backend)
        email = 'pending@example.test'
        lifecycle.signup(email, self.password)
        first = self.mail[email]
        accepted = lifecycle.resend_signup(email)
        self.assertEqual(accepted, lifecycle.resend_signup('unknown@example.test'))
        self.assertNotEqual(first, self.mail[email])
        with self.assertRaises(Failure): lifecycle.confirm_signup(email, first)
        lifecycle.confirm_signup(email, self.mail[email])
        with self.assertRaises(Failure): lifecycle.confirm_signup(email, self.mail[email])
        with self.assertRaises(Failure) as error: lifecycle.resend_signup(email)
        self.assertEqual(error.exception.status, 429)

    def test_recovery_cannot_leave_signup_token_that_bypasses_later_mfa(self):
        lifecycle = AccountLifecycle(self.backend)
        email = 'reset-before-confirm@example.test'
        lifecycle.signup(email, self.password)
        initial_code = self.mail[email]
        self.backend.recover(email)
        self.backend.reset_password(email, self.mail[email], self.password)
        with self.assertRaises(Failure): lifecycle.confirm_signup(email, initial_code)
        session = self.backend.login(email, self.password)
        actor = self.backend.authenticate(session['token'])
        mfa = CustomerMFA(self.backend); value = mfa.begin(actor, self.password)
        mfa.enable(actor, self.password, value['enrollment'], totp(value['totp_secret'], self.now//30))
        with self.assertRaises(Failure): lifecycle.confirm_signup(email, initial_code)
        self.assertTrue(self.flow.begin(email, self.password, 'browser')['mfa_required'])

    def test_native_registration_alias_has_generic_response_without_session(self):
        from backend.http_server import dispatch
        body = {'email':'native-signup@example.test','password':self.password}
        first = dispatch(self.backend,'POST','/v1/auth/register',body,'')
        self.assertEqual(first, dispatch(self.backend,'POST','/v1/auth/register',body,''))
        self.assertEqual(first, {'accepted':True,'next':'check_email'})


class LoginFlowTests(LoginFlowScenarios, unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.mail = {}; self.password = 'a-valid-long-passphrase'
        self.backend = Backend(Path(folder.name) / 'login.db', deliver=lambda e, c: self.mail.update({e: c}))
        self.backend.cipher = Fernet(Fernet.generate_key())
        session = self.backend.register('account@example.test', self.password)
        self.actor = self.backend.authenticate(session['token'])
        self.backend.verify(self.actor, self.mail[self.actor['email']])
        self.actor = self.backend.authenticate(session['token'])
        self.setup_flow()
