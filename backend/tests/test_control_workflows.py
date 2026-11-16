"""Real authorization and state boundaries for the Control workbench."""
import json
import unittest
import uuid

from backend.control import Control, StaffPrincipal, totp
from backend.http_server import dispatch
from backend.service import Failure


class ControlWorkflowTests(unittest.TestCase):
    def setUp(self):
        from backend.tests.test_control_web import WebControlTests
        self.f = WebControlTests(methodName='test_staff_cookie_is_not_a_customer_bearer_and_mfa_required')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def staff(self, action, body=None, actor=None, query=None):
        return self.f.app.web.staff_action(actor or self.f.owner, action,
            'POST' if body is not None else 'GET', body or {}, query or {})

    def post(self, action, body):
        f = self.f
        token = f.staff_login['token']
        return f.request('/control/api/' + action, body, host='control.getuladim.space',
            cookie='__Host-uladim_control=' + token, csrf=f.app.web.csrf(token),
            origin='https://control.getuladim.space')

    def test_identity_is_self_managed_and_directory_pages_and_escapes_search(self):
        f = self.f
        cookie, csrf = f.login_customer()
        status, _, value = f.request('/account/api/identity', {'display_name': 'Умар U.'},
            cookie=cookie, csrf=csrf, origin='https://getuladim.space')
        self.assertEqual(status, 200, value)
        self.assertEqual(value['display_name'], 'Умар U.')
        result = self.staff('users', query={'search': ['умар']})
        self.assertEqual([row['id'] for row in result['users']], [f.user2['id']])
        self.assertEqual(result['users'][0]['name_source'], 'account_identity')
        self.assertNotIn('password_hash', json.dumps(result))
        first = self.staff('users', query={'limit': ['1']})
        self.assertTrue(first['next_before'])
        second = self.staff('users', query={'limit': ['1'], 'before': [first['next_before']]})
        self.assertNotEqual(first['users'][0]['id'], second['users'][0]['id'])
        self.assertEqual(self.staff('users', query={'search': ['%']})['users'], [])
        with self.assertRaises(Failure):
            self.staff('users', query={'limit': ['101']})
        token = f.backend.login(f.user2['email'], 'a-valid-long-passphrase')['token']
        self.assertEqual(dispatch(f.backend, 'GET', '/v1/account/identity', {}, 'Bearer ' + token), value)
        with f.backend.transaction() as db:
            db.execute("INSERT INTO deletion_jobs VALUES(?,?,?,?, 'erasing',NULL)",
                (str(uuid.uuid4()), f.user2['id'], f.now, f.now))
        self.assertEqual(self.staff('users', query={'search': ['умар']})['users'], [])

    def test_invitation_denials_are_effective_and_update_revokes_old_session(self):
        f = self.f
        status, _, invite = self.post('staff/invite', {'email': f.user2['email'],
            'roles': ['support', 'moderator'], 'denied_permissions': ['users.moderate', 'support.reply'],
            'reason': 'Read and recovery coverage'})
        self.assertEqual(status, 200, invite)
        capsule = f.control.prepare_enrollment(f.user2, invite['invitation'], 'a-valid-long-passphrase')
        result = f.control.finish_enrollment(f.user2, capsule['enrollment'], totp(capsule['totp_secret'], f.now // 30))
        f.now += 30
        login = f.control.login(f.user2['email'], 'a-valid-long-passphrase',
            totp(capsule['totp_secret'], f.now // 30), 'fixture')
        member = f.control.authenticate(login['token'], 'fixture')
        self.assertNotIn('users.moderate', member.permissions)
        self.assertIn('records.recover', member.permissions)
        third = f.user('moderation-target@example.test')
        from backend.service import token_hash
        with f.backend.transaction() as db:
            device = db.execute('SELECT id FROM devices WHERE user_id=?', (f.user2['id'],)).fetchone()['id']
            db.execute('INSERT INTO web_sessions VALUES(?,?,?,?,?,?,?)',
                (token_hash('m' * 43), f.user2['id'], device, f.now, f.now, f.now + 3600, token_hash('fixture')))
        admission, _ = f.app.web.admission.redeem(f.app.web.admission.issue('m' * 43, 'fixture'), 'fixture')
        old_admission, f.admission = f.admission, '__Host-uladim_control_admission=' + admission
        status, _, value = f.request('/control/api/moderate', {'user_id': third['id'], 'service': 'account',
            'until_at': f.now + 60, 'reason': 'Crafted request cannot bypass deny'}, host='control.getuladim.space',
            cookie='__Host-uladim_control=' + login['token'], csrf=f.app.web.csrf(login['token']),
            origin='https://control.getuladim.space')
        f.admission = old_admission
        self.assertEqual(status, 403, value)
        with f.backend.connect() as db:
            self.assertFalse(db.execute('SELECT 1 FROM account_state WHERE user_id=?', (third['id'],)).fetchone())
        with self.assertRaises(Failure):
            f.control.moderate(member, f.owner_user['id'], 'account', f.now + 60, 'Denied')
        team = self.staff('staff')['staff']
        row = next(row for row in team if row['id'] == result['staff_id'])
        self.assertIn('users.moderate', row['base_permissions'])
        self.assertNotIn('users.moderate', row['permissions'])
        self.assertEqual(sorted(row['denied_permissions']), ['support.reply', 'users.moderate'])
        from backend.login_flow import LoginFlow
        challenge = LoginFlow(f.backend).begin(f.user2['email'], 'a-valid-long-passphrase', 'fixture', True)
        self.staff('staff/update', {'staff_id': row['id'], 'roles': row['roles'], 'active': True,
            'revision': row['revision'], 'denied_permissions': ['records.recover'], 'reason': 'Changed duties'})
        with self.assertRaises(Failure):
            f.control.authenticate(login['token'], 'fixture')
        f.now += 30
        with self.assertRaises(Failure):
            LoginFlow(f.backend).finish(challenge['challenge'], totp(capsule['totp_secret'], f.now // 30), 'fixture', True)
        with self.assertRaises(Failure):
            self.staff('staff/update', {'staff_id': f.owner.id, 'roles': ['support'], 'active': True,
                'revision': 1, 'denied_permissions': [], 'reason': 'Cannot edit owner'})

    def test_restricted_issuer_cannot_delegate_or_redeem_old_invitation(self):
        f = self.f
        issuer_id = str(uuid.uuid4())
        with f.backend.transaction() as db:
            db.execute('INSERT INTO staff(id,user_id,roles,mfa_secret,created_at) VALUES(?,?,?,?,?)',
                (issuer_id, f.user2['id'], '["admin"]', b'unused', f.now))
        issuer = StaffPrincipal(issuer_id, f.user2['id'], ('admin',))
        target = f.user('third@example.test')
        invite = f.control.invite_staff(issuer, target['email'], ['support'], 'Initial coverage')
        capsule = f.control.prepare_enrollment(target, invite['invitation'], 'a-valid-long-passphrase')
        status, _, value = self.post('staff/update', {'staff_id': issuer_id, 'roles': ['admin'],
            'active': True, 'revision': 1, 'denied_permissions': ['staff.manage'], 'reason': 'Revoke delegation'})
        self.assertEqual(status, 200, value)
        with self.assertRaises(Failure) as denied:
            f.control.finish_enrollment(target, capsule['enrollment'], totp(capsule['totp_secret'], f.now // 30))
        self.assertEqual(denied.exception.status, 403)
        # An issuer retaining staff.manage cannot delegate another denied capability.
        self.staff('staff/update', {'staff_id': issuer_id, 'roles': ['admin'], 'active': True,
            'revision': 2, 'denied_permissions': ['records.recover'], 'reason': 'Narrow delegation'})
        with f.backend.transaction() as db:
            db.execute('INSERT INTO control_sessions VALUES(?,?,?,?,?,?)',
                ('synthetic', issuer_id, f.now, f.now, f.now + 600, 'unused'))
        from backend.staff_permissions import principal
        with f.backend.connect() as db:
            issuer = principal(db, db.execute('SELECT * FROM staff WHERE id=?', (issuer_id,)).fetchone())
        with self.assertRaises(Failure):
            f.control.invite_staff(issuer, target['email'], ['support'], 'Would broaden authority')

    def test_other_account_ticket_never_confirms_target_case_or_creates_record_consent(self):
        f = self.f
        author = f.user('contact@example.test')
        ticket = f.app.web.support.create(author, 'account', 'Help original account', 'Private contact text')['ticket_id']
        status, _, detail = self.post('recovery-cases', {'target_user_id': f.user2['id'],
            'ticket_id': ticket, 'kind': 'records', 'reason': 'External contact about original account'})
        self.assertEqual(status, 200, detail)
        self.assertEqual(detail['target']['id'], f.user2['id'])
        self.assertFalse(detail['source']['same_account'])
        self.assertEqual(detail['case']['state'], 'waiting_owner')
        self.assertEqual(detail['requests'], [])
        self.assertNotIn('Private contact text', json.dumps(detail))
        case_id = detail['case']['id']
        with self.assertRaises(Failure) as denied:
            f.app.web.account_action(author, 'recovery-case', 'GET', {}, {'id': [case_id]})
        self.assertEqual(denied.exception.status, 404)
        with self.assertRaises(Failure):
            f.app.web.account_action(author, 'recovery-cases/confirm', 'POST', {'id': case_id, 'revision': 1}, {})
        confirmed = f.app.web.account_action(f.user2, 'recovery-cases/confirm', 'POST',
            {'id': case_id, 'revision': 1}, {})
        self.assertEqual(confirmed['case']['state'], 'confirmed')
        self.assertEqual(confirmed['requests'], [])
        with f.backend.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM record_recovery_requests').fetchone()['n'], 0)

    def test_manual_case_reset_uses_original_address_and_revision_and_keeps_mfa(self):
        f = self.f
        from backend.customer_mfa import CustomerMFA
        mfa = CustomerMFA(f.backend)
        enrollment = mfa.begin(f.user2, 'a-valid-long-passphrase')
        mfa.enable(f.user2, 'a-valid-long-passphrase', enrollment['enrollment'], totp(enrollment['totp_secret'], f.now // 30))
        status, _, detail = self.post('recovery-cases', {'target_user_id': f.user2['id'],
            'kind': 'access', 'reason': 'Person contacted support by email'})
        self.assertEqual(status, 200, detail)
        self.assertEqual(detail['source']['kind'], 'manual')
        case = detail['case']
        status, _, result = self.post('recovery-cases/update', {'id': case['id'], 'revision': case['revision'],
            'action': 'send_reset', 'reason': 'Send to original verified address'})
        self.assertEqual(status, 200, result)
        self.assertTrue(result['recovery_requested'])
        self.assertEqual(result['case']['revision'], 2)
        self.assertNotIn(f.mail[f.user2['email']], json.dumps(result))
        with f.backend.connect() as db:
            self.assertTrue(db.execute('SELECT 1 FROM account_mfa WHERE user_id=?', (f.user2['id'],)).fetchone())
        status, _, _ = self.post('recovery-cases/update', {'id': case['id'], 'revision': 1,
            'action': 'close', 'reason': 'Stale state'})
        self.assertEqual(status, 409)
        with f.backend.transaction() as db:
            db.execute("INSERT INTO deletion_jobs VALUES(?,?,?,?, 'erasing',NULL)",
                (str(uuid.uuid4()), f.user2['id'], f.now, f.now))
        status, _, _ = self.post('recovery-cases/update', {'id': case['id'], 'revision': 2,
            'action': 'send_reset', 'reason': 'Erased target cannot recover'})
        self.assertEqual(status, 403)

    def test_original_owner_case_links_consent_and_only_owner_restores_via_bearer(self):
        f = self.f
        wid, rid = str(uuid.uuid4()), str(uuid.uuid4())
        f.backend.family(f.user2, {'id': str(uuid.uuid4()), 'workspace_id': wid,
            'action': 'workspace.create', 'kind': 'personal', 'name': 'Private workspace'})
        f.backend.batch(f.user2, wid, [{'id': str(uuid.uuid4()), 'action': 'record.put', 'record_id': rid,
            'revision': 0, 'kind': 'note', 'visibility': 'private', 'audience': [], 'data': {'body': 'Never in staff projection'}}])
        f.backend.batch(f.user2, wid, [{'id': str(uuid.uuid4()), 'action': 'record.delete', 'record_id': rid, 'revision': 1}])
        detail = self.staff('recovery-cases', {'target_user_id': f.user2['id'], 'kind': 'records', 'reason': 'Help original owner'})
        token = f.backend.login(f.user2['email'], 'a-valid-long-passphrase')['token']
        auth = 'Bearer ' + token
        cid = detail['case']['id']
        self.assertEqual(dispatch(f.backend, 'GET', '/v1/account/recovery-case?id=' + cid, {}, auth)['case']['id'], cid)
        confirmed = dispatch(f.backend, 'POST', '/v1/account/recovery-cases/confirm', {'id': cid, 'revision': 1}, auth)
        self.assertEqual(confirmed['case']['state'], 'confirmed')
        preview = dispatch(f.backend, 'GET', '/v1/account/trash?workspace=' + wid + '&record=' + rid, {}, auth)['records'][0]
        consent = dispatch(f.backend, 'POST', '/v1/account/recovery/request', {'record_id': rid,
            'revision': preview['revision'], 'consent_hash': preview['consent_hash']}, auth)['request']
        detail = self.staff('recovery-case', query={'id': [cid]})
        self.assertEqual([request['id'] for request in detail['requests']], [consent['id']])
        self.assertNotIn('Never in staff projection', json.dumps(detail))
        access_only = StaffPrincipal(f.owner.id, f.owner.user_id, f.owner.roles, ('records.recover',))
        access_case = self.staff('recovery-cases', {'target_user_id': f.user2['id'], 'kind': 'access',
            'reason': 'Access assistance with no record authority'}, actor=access_only)
        self.assertEqual(access_case['requests'], [])
        filtered = self.staff('record-recovery', query={'user_id': [f.user2['id']], 'state': ['pending']})
        self.assertEqual([request['id'] for request in filtered['requests']], [consent['id']])
        approved = self.staff('record-recovery/approve', {'request_id': consent['id'], 'revision': consent['revision'],
            'consent_hash': consent['consent_hash'], 'reason': 'Approve exact owner consent'})['request']
        grant = dispatch(f.backend, 'POST', '/v1/account/recovery/prepare', {'request_id': approved['id']}, auth)
        operation = {'request_id': approved['id'], 'grant': grant['grant'], 'operation_id': str(uuid.uuid4())}
        first = dispatch(f.backend, 'POST', '/v1/account/recovery/commit', operation, auth)
        second = dispatch(f.backend, 'POST', '/v1/account/recovery/commit', operation, auth)
        self.assertEqual(first, second)
        self.assertEqual(first['results'][0]['status'], 'accepted')

    def test_new_metadata_is_erased_with_subject_and_source_contact(self):
        f = self.f
        from backend.account_identity import AccountIdentity
        from backend.account_erasure import erase_in
        AccountIdentity(f.backend).identity(f.user2, {'display_name': 'Temporary account name'})
        author = f.user('erased-contact@example.test')
        ticket = f.app.web.support.create(author, 'account', 'Original account', 'Voluntary contact')['ticket_id']
        case = self.staff('recovery-cases', {'target_user_id': f.user2['id'], 'ticket_id': ticket,
            'kind': 'records', 'reason': 'Contact assistance'})['case']
        with f.backend.transaction() as db:
            erase_in(f.backend, db, author['id'], f.now)
            self.assertFalse(db.execute('SELECT 1 FROM support_recovery_cases WHERE id=?', (case['id'],)).fetchone())
            self.assertFalse(db.execute('SELECT 1 FROM control_audit_notes WHERE subject_id=?', (author['id'],)).fetchone())
            self.assertFalse(db.execute('SELECT 1 FROM control_audit_notes WHERE subject_id=?', (case['id'],)).fetchone())
        self.staff('recovery-cases', {'target_user_id': f.user2['id'], 'kind': 'records', 'reason': 'Manual assistance'})
        with f.backend.transaction() as db:
            erase_in(f.backend, db, f.user2['id'], f.now)
            self.assertFalse(db.execute('SELECT 1 FROM account_identity WHERE user_id=?', (f.user2['id'],)).fetchone())
            self.assertFalse(db.execute('SELECT 1 FROM support_recovery_cases WHERE user_id=?', (f.user2['id'],)).fetchone())
        self.assertEqual(self.staff('users', query={'search': ['Temporary account name']})['users'], [])


if __name__ == '__main__':
    unittest.main()
