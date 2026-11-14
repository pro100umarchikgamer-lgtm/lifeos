"""Staff may request recipient-owned recovery, never obtain/set credentials."""
import json
import unittest
from backend.control import StaffPrincipal, totp
from backend.service import Failure

class ControlRecoveryTests(unittest.TestCase):
    def setUp(self):
        from backend.tests.test_control_web import WebControlTests
        self.fixture=WebControlTests(methodName='test_staff_cookie_is_not_a_customer_bearer_and_mfa_required')
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)

    def test_owner_recovery_route_returns_no_secret_and_preserves_password_and_mfa(self):
        f=self.fixture
        with f.backend.connect() as db:
            before=dict(db.execute('SELECT password_hash,salt FROM users WHERE id=?',(f.user2['id'],)).fetchone())
        from backend.customer_mfa import CustomerMFA
        mfa=CustomerMFA(f.backend); setup=mfa.begin(f.user2,'a-valid-long-passphrase')
        mfa.enable(f.user2,'a-valid-long-passphrase',setup['enrollment'],totp(setup['totp_secret'],f.now//30))
        with f.backend.connect() as db: factor_before=bytes(db.execute('SELECT secret FROM account_mfa WHERE user_id=?',(f.user2['id'],)).fetchone()['secret'])
        token=f.staff_login['token']
        status,_,result=f.request('/control/api/user/recovery',{'user_id':f.user2['id'],'reason':'Verified user requested help'},host='control.getuladim.space',cookie='__Host-uladim_control='+token,csrf=f.app.web.csrf(token),origin='https://control.getuladim.space')
        self.assertEqual(status,200,result); self.assertEqual(result,{'recovery_requested':True})
        code=f.mail[f.user2['email']]; self.assertEqual(len(code),43)
        with f.backend.connect() as db:
            after=dict(db.execute('SELECT password_hash,salt FROM users WHERE id=?',(f.user2['id'],)).fetchone())
        self.assertEqual(after,before)
        events=f.control.audit_log(f.owner)['events']; event=events[0]
        self.assertEqual(event['action'],'user.recovery.request'); self.assertEqual(event['subject_id'],f.user2['id'])
        self.assertNotIn(code,json.dumps(events)); self.assertNotIn(code,json.dumps(result))
        with self.assertRaises(Failure) as limited:f.control.request_recovery(f.owner,f.user2['id'],'Repeated request')
        self.assertEqual(limited.exception.status,429)
        with f.backend.connect() as db:self.assertEqual(bytes(db.execute('SELECT secret FROM account_mfa WHERE user_id=?',(f.user2['id'],)).fetchone()['secret']),factor_before)

    def test_recovery_permission_target_hierarchy_and_verified_recipient(self):
        f=self.fixture
        for role in ('moderator','auditor','billing_manager'):
            with self.assertRaises(Failure) as denied:f.control.request_recovery(StaffPrincipal('synthetic',f.user2['id'],(role,)),f.user2['id'],'No permission')
            self.assertEqual(denied.exception.status,403)
        support=StaffPrincipal('support-synthetic',f.user2['id'],('support',))
        with self.assertRaises(Failure) as denied:f.control.request_recovery(support,f.owner_user['id'],'Cannot reset owner')
        self.assertEqual(denied.exception.status,403)
        with f.backend.transaction() as db:db.execute('UPDATE users SET verified=0 WHERE id=?',(f.user2['id'],))
        with self.assertRaises(Failure) as denied:f.control.request_recovery(f.owner,f.user2['id'],'Unverified recipient')
        self.assertEqual(denied.exception.status,409)
