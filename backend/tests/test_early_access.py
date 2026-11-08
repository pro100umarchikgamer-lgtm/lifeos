"""Same application scenarios run on SQLite and disposable PostgreSQL schemas."""
import tempfile
import unittest
from pathlib import Path
from backend.early_access import EarlyAccess, CONSENT_VERSION
from backend.service import Backend, Failure
from backend.control import Control, StaffPrincipal
from backend.production import Application


class EarlyAccessScenarios:
    def apply(self, email='tester@example.test'):
        return self.early.apply(email, CONSENT_VERSION, client='198.51.100.1')

    def pending(self):
        self.apply()
        self.code = self.mail['tester@example.test']
        return self.early.confirm('tester@example.test', self.code)

    def request_row(self):
        with self.backend.connect() as db:
            return dict(db.execute('SELECT * FROM early_access WHERE email=?', ('tester@example.test',)).fetchone())

    def test_application_does_not_create_account_or_leak_address_existence(self):
        first = self.apply()
        self.assertEqual(first, self.apply())
        with self.backend.connect() as db:
            self.assertFalse(db.execute('SELECT 1 FROM users WHERE email=?', ('tester@example.test',)).fetchone())
            self.assertEqual(db.execute('SELECT COUNT(*) FROM early_access').fetchone()[0], 1)
        row = self.request_row()
        self.assertNotEqual(row['verification_hash'], self.mail['tester@example.test'])
        self.assertEqual(row['state'], 'unverified')

    def test_one_time_confirmation_management_and_cancellation(self):
        result = self.pending()
        self.assertEqual(result['state'], 'pending')
        with self.assertRaises(Failure): self.early.confirm('tester@example.test', self.code)
        with self.assertRaises(Failure): self.early.manage('x' * 43)
        self.assertEqual(self.early.manage(result['management_token'])['state'], 'pending')
        self.assertEqual(self.early.manage(result['management_token'], True)['state'], 'cancelled')
        self.now += 301
        self.apply()
        again = self.early.confirm('tester@example.test', self.mail['tester@example.test'])
        self.assertEqual(again['state'], 'cancelled')

    def test_expiration_and_wrong_address(self):
        self.apply()
        code = self.mail['tester@example.test']
        with self.assertRaises(Failure): self.early.confirm('other@example.test', code)
        self.now += 900
        with self.assertRaises(Failure): self.early.confirm('tester@example.test', code)
        self.now += 2701
        managed = self.pending()
        self.now += 86400
        with self.assertRaises(Failure): self.early.manage(managed['management_token'])

    def test_consent_honeypot_and_persistent_abuse_limits(self):
        with self.assertRaises(Failure): self.early.apply('tester@example.test', False)
        self.assertTrue(self.early.apply('bot@example.test', CONSENT_VERSION, 'https://spam.invalid', 'bot')['accepted'])
        with self.backend.connect() as db:
            self.assertFalse(db.execute('SELECT 1 FROM early_access').fetchone())
        for i in range(3): self.apply()
        with self.assertRaises(Failure) as error: self.apply()
        self.assertEqual(error.exception.status, 429)
        self.early = EarlyAccess(self.backend)  # Restart does not reset quota.
        with self.assertRaises(Failure): self.apply()

    def test_staff_permissions_invitation_scope_revision_and_revocation(self):
        result = self.pending()
        actor = StaffPrincipal('fixture-owner', 'fixture-user', ('owner',))
        control = Control(self.backend)
        support = StaffPrincipal('fixture-support', 'fixture-user', ('support',))
        with self.assertRaises(Failure): self.early.list(support, control)
        row = self.request_row()
        with self.assertRaises(Failure): self.early.decide(support, control, row['id'], 'approved', row['revision'], 'Test')
        self.assertEqual(len(self.early.list(actor, control)['applications']), 1)
        self.early.decide(actor, control, row['id'], 'approved', row['revision'], 'Closed-test invitation')
        invite = self.mail['tester@example.test']
        self.assertTrue(self.early.invited('TESTER@example.test', invite))
        self.assertFalse(self.early.invited('other@example.test', invite))
        self.assertFalse(self.early.invited('tester@example.test', 'x' * 43))
        with self.assertRaises(Failure): self.early.decide(actor, control, row['id'], 'rejected', row['revision'], 'Stale browser')
        self.early.manage(result['management_token'], True)
        self.assertFalse(self.early.invited('tester@example.test', invite))
        with self.backend.connect() as db:
            audit = db.execute('SELECT after_value FROM control_audit').fetchone()['after_value']
            self.assertNotIn(invite, audit)

    def test_registration_gate_keeps_closed_mode_and_invitation_expiry(self):
        from types import SimpleNamespace
        app = SimpleNamespace(backend=self.backend, settings=SimpleNamespace(registration_mode='closed', registration_allowlist=()))
        self.pending()
        row = self.request_row()
        self.early.decide(StaffPrincipal('owner', 'user', ('owner',)), Control(self.backend), row['id'], 'approved', row['revision'], 'Test invite')
        body = {'email': 'tester@example.test', 'invitation': self.mail['tester@example.test']}
        Application.check_registration(app, body)
        with self.assertRaises(Failure): Application.check_registration(app, {'email': 'other@example.test', 'invitation': body['invitation']})
        self.now += 604800
        with self.assertRaises(Failure): Application.check_registration(app, body)


class EarlyAccessTests(EarlyAccessScenarios, unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        self.now = 1800000000
        self.mail = {}
        self.backend = Backend(Path(directory.name) / 'early.db', deliver=lambda e,c: self.mail.update({e:c}), clock=lambda: self.now)
        self.early = EarlyAccess(self.backend)

class EarlyAccessHTTPTests(unittest.TestCase):
    def setUp(self):
        import io
        from cryptography.fernet import Fernet
        from backend.config import Settings
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        self.mail = {}
        self.backend = Backend(Path(directory.name)/'web.db', deliver=lambda e,c:self.mail.update({e:c}))
        self.app = Application(self.backend, Settings.load({'DATABASE_URL':'postgresql://example/db','EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),'RATE_LIMIT_KEY':'x'*48,'SMTP_HOST':'127.0.0.1','SMTP_TLS':'none','EMAIL_FROM':'test@example.test'}))

    def request(self, path, body=None, origin='https://getuladim.space', host='getuladim.space'):
        import io, json
        from unittest.mock import patch
        data=json.dumps(body).encode() if body is not None else b''
        env={'HTTP_HOST':host,'REQUEST_METHOD':'POST' if body is not None else 'GET','PATH_INFO':path,'REMOTE_ADDR':'172.30.30.2','HTTP_X_FORWARDED_PROTO':'https','HTTP_ORIGIN':origin,'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(data)),'wsgi.input':io.BytesIO(data)}
        response=[]
        with patch.object(self.app, 'limit'):
            result=b''.join(self.app(env, lambda status,headers:response.append((int(status.split()[0]),dict(headers)))))
        return response[0][0],response[0][1],result

    def test_public_intake_origin_method_host_and_registration_boundaries(self):
        import json
        data={'email':'tester@example.test','consent_version':CONSENT_VERSION}
        self.assertEqual(self.request('/early-access')[0],200)
        self.assertEqual(self.request('/early-access/api/apply', data, origin='https://evil.invalid')[0],403)
        self.assertEqual(self.request('/early-access/api/apply')[0],405)
        self.assertEqual(self.request('/early-access/api/apply',data,host='control.getuladim.space')[0],404)
        status,headers,body=self.request('/early-access/api/apply',data)
        self.assertEqual(status,200);self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertNotIn('unsafe-inline',headers['Content-Security-Policy'])
        code=self.mail['tester@example.test']
        status,headers,body=self.request('/early-access/api/confirm',{'email':data['email'],'code':code})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)['state'],'pending')
        self.assertEqual(self.request('/account/api/signup',{'email':data['email'],'password':'valid-test-passphrase'})[0],403)
        self.assertEqual(self.request('/control/api/applications',host='control.getuladim.space')[0],401)
