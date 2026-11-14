"""Same-browser staff admission against real temporary persistence and WSGI."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode
from cryptography.fernet import Fernet
from backend.config import Settings
from backend.control import Control, totp
from backend.production import Application
from backend.service import Backend

class ControlAdmissionTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.now=1800000000; self.mail={}; self.password='synthetic-owner-passphrase'
        self.backend=self.make_backend(Path(folder.name)/'admission.db')
        self.backend.cipher=Fernet(Fernet.generate_key())
        self.users=[]
        for email in ('owner@example.test','other@example.test'):
            value=self.backend.register(email,self.password); actor=self.backend.authenticate(value['token'])
            self.backend.verify(actor,self.mail[email]); self.users.append(self.backend.authenticate(value['token']))
        self.control=Control(self.backend); self.setup=self.control.bootstrap(self.users[0]['email'])
        settings=Settings.load({'DATABASE_URL':'postgresql://unused/test','EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),'RATE_LIMIT_KEY':'a'*48,'SMTP_HOST':'localhost','SMTP_TLS':'none','EMAIL_FROM':'fixture@example.test'})
        self.app=Application(self.backend,settings)
        with self.backend.connect() as db: db.execute('CREATE TABLE IF NOT EXISTS http_limits(key TEXT PRIMARY KEY,count BIGINT NOT NULL,until_at BIGINT NOT NULL)')
        self.parent=[]
        for user in self.users:
            status,headers,body=self.request('/account/api/login',{'email':user['email'],'password':self.password})
            self.assertEqual(status,200); self.parent.append((dict(headers)['Set-Cookie'].split(';')[0],body['csrf']))

    def make_backend(self, path):
        return Backend(path,deliver=lambda e,c:self.mail.update({e:c}),clock=lambda:self.now)

    def request(self,path,body=None,*,staff=False,cookie='',csrf='',origin=None,agent='browser-A',form=False,method=None):
        host='control.getuladim.space' if staff else 'getuladim.space'
        data=(urlencode(body).encode() if form else json.dumps(body).encode()) if body is not None else b''
        env={'HTTP_HOST':host,'REQUEST_METHOD':method or ('POST' if body is not None else 'GET'),'PATH_INFO':path,'REMOTE_ADDR':'172.30.30.2','HTTP_X_FORWARDED_PROTO':'https','HTTP_USER_AGENT':agent,'HTTP_ORIGIN':origin or 'https://'+host,'HTTP_COOKIE':cookie,'HTTP_X_CSRF_TOKEN':csrf,'CONTENT_TYPE':'application/x-www-form-urlencoded' if form else 'application/json','CONTENT_LENGTH':str(len(data)),'wsgi.input':io.BytesIO(data)}
        response=[]; raw=b''.join(self.app(env,lambda s,h:response.append((int(s.split()[0]),h))))
        status,headers=response[0]; kind=dict(headers).get('Content-Type','')
        return status,headers,json.loads(raw) if raw and kind.startswith('application/json') else raw

    def issue(self,index=0):
        cookie,csrf=self.parent[index]
        status,headers,body=self.request('/account/api/control/access',{},cookie=cookie,csrf=csrf)
        self.assertEqual(status,200,body); return body

    def admit(self):
        ticket=self.issue(); status,headers,body=self.request('/admit',{'ticket':ticket['ticket']},staff=True,form=True,origin='https://getuladim.space')
        self.assertEqual(status,303,body); self.assertEqual(dict(headers)['Location'],'/')
        cookies=[v for k,v in headers if k=='Set-Cookie']; self.assertEqual(len(cookies),1)
        self.assertIn('HttpOnly; Secure; SameSite=Strict',cookies[0]); self.assertNotIn('Domain=',cookies[0])
        return cookies[0].split(';')[0]

    def test_control_is_hidden_before_admission_including_assets_api_health_and_methods(self):
        for path in ('/','/assets/web.js','/assets/locales.json','/control/api/session','/health/ready','/metrics'):
            for method in ('GET','HEAD','OPTIONS'):
                with self.subTest(path=path,method=method):
                    status,_,_=self.request(path,staff=True,method=method)
                    self.assertEqual(status,404)
        self.assertEqual(self.request('/control/api/login',{'email':self.users[0]['email'],'password':self.password},staff=True)[0],404)
        self.assertEqual(self.request('/',staff=True,cookie=self.parent[0][0])[0],404)

    def test_own_staff_metadata_and_csrf_protected_ticket_only(self):
        for index,want in ((0,True),(1,False)):
            status,headers,body=self.request('/account/api/session',cookie=self.parent[index][0])
            self.assertEqual(status,200); self.assertIs(body.get('control_available'),want)
        self.assertEqual(self.request('/account/api/control/access',{},cookie=self.parent[1][0],csrf=self.parent[1][1])[0],404)
        self.assertEqual(self.request('/account/api/control/access',{},cookie=self.parent[0][0])[0],403)
        self.assertEqual(self.request('/account/api/control/access',{},cookie=self.parent[0][0],csrf=self.parent[0][1],origin='https://evil.example')[0],403)
        ticket=self.issue(); self.assertEqual(ticket['control_url'],'https://control.getuladim.space/admit'); self.assertEqual(ticket['expires_in'],60)
        self.assertNotIn('token',ticket)
        _,headers,_=self.request('/app')
        self.assertIn("form-action 'self' https://control.getuladim.space",dict(headers)['Content-Security-Policy'])

    def test_post_handoff_is_origin_bound_single_use_and_does_not_grant_staff_mfa(self):
        ticket=self.issue()
        self.assertEqual(self.request('/admit',{'ticket':ticket['ticket']},staff=True,form=True,origin='https://evil.example')[0],404)
        status,headers,_=self.request('/admit',{'ticket':ticket['ticket']},staff=True,form=True,origin='https://getuladim.space')
        self.assertEqual(status,303)
        admission=dict(headers)['Set-Cookie'].split(';')[0]
        self.assertEqual(self.request('/admit',{'ticket':ticket['ticket']},staff=True,form=True,origin='https://getuladim.space')[0],404)
        self.assertEqual(self.request('/',staff=True,cookie=admission)[0],200)
        self.assertEqual(self.request('/control/api/session',staff=True,cookie=admission)[0],401)
        self.assertEqual(self.request('/control/api/login',{'email':self.users[1]['email'],'password':self.password},staff=True,cookie=admission)[0],404)
        status,headers,body=self.request('/control/api/login',{'email':self.users[0]['email'],'password':self.password},staff=True,cookie=admission)
        self.assertEqual(status,200); self.assertTrue(body['mfa_required']); self.assertNotIn('Set-Cookie',dict(headers))
        self.now+=30
        status,headers,body=self.request('/control/api/login/mfa',{'challenge':body['challenge'],'code':totp(self.setup['totp_secret'],self.now//30)},staff=True,cookie=admission)
        self.assertEqual(status,200); staff_cookie=dict(headers)['Set-Cookie'].split(';')[0]
        self.assertEqual(self.request('/control/api/session',staff=True,cookie=admission+'; '+staff_cookie)[0],200)
        self.assertEqual(self.request('/control/api/session',staff=True,cookie=staff_cookie)[0],404)

    def test_parent_logout_and_device_revocation_remove_admission_immediately(self):
        admission=self.admit()
        self.assertEqual(self.request('/',staff=True,cookie=admission,agent='browser-B')[0],404)
        cookie,csrf=self.parent[0]
        self.assertEqual(self.request('/account/api/logout',{},cookie=cookie,csrf=csrf)[0],200)
        self.assertEqual(self.request('/',staff=True,cookie=admission)[0],404)

    def test_expired_ticket_or_parent_session_and_inactive_staff_are_hidden(self):
        ticket=self.issue(); self.now+=61
        self.assertEqual(self.request('/admit',{'ticket':ticket['ticket']},staff=True,form=True,origin='https://getuladim.space')[0],404)
        admission=self.admit()
        with self.backend.transaction() as db: db.execute('UPDATE staff SET active=0 WHERE user_id=?',(self.users[0]['id'],))
        self.assertEqual(self.request('/',staff=True,cookie=admission)[0],404)
        self.assertIs(self.request('/account/api/session',cookie=self.parent[0][0])[2]['control_available'],False)

    def test_ticket_cannot_be_redeemed_by_different_browser_or_after_parent_revocation(self):
        ticket=self.issue()
        self.assertEqual(self.request('/admit',{'ticket':ticket['ticket']},staff=True,form=True,origin='https://getuladim.space',agent='browser-B')[0],404)
        self.backend.revoke_all(self.users[0],self.password)
        self.assertEqual(self.request('/admit',{'ticket':ticket['ticket']},staff=True,form=True,origin='https://getuladim.space')[0],404)

    def test_admission_expires_with_parent_and_rejects_foreign_mfa_challenge(self):
        admission=self.admit()
        self.assertEqual(self.request('/control/api/login/mfa',{'challenge':[], 'code':'123456'},staff=True,cookie=admission)[0],404)
        with self.backend.transaction() as db: db.execute('UPDATE web_sessions SET expires_at=? WHERE user_id=?',(self.now,self.users[0]['id']))
        self.assertEqual(self.request('/',staff=True,cookie=admission)[0],404)

    def test_admission_cookie_cannot_authenticate_a_different_staff_identity(self):
        admission=self.admit()
        invite=self.control.invite_staff(self.control.authenticate(self.control.login(self.users[0]['email'],self.password,totp(self.setup['totp_secret'],self.now//30),'browser-A')['token'],'browser-A'),self.users[1]['email'],['support'],'Synthetic invitation')
        setup=self.control.prepare_enrollment(self.users[1],invite['invitation'],self.password)
        self.control.finish_enrollment(self.users[1],setup['enrollment'],totp(setup['totp_secret'],self.now//30))
        self.now+=30
        wrong=self.control.login(self.users[1]['email'],self.password,totp(setup['totp_secret'],self.now//30),'browser-A')
        self.assertEqual(self.request('/control/api/session',staff=True,cookie=admission+'; __Host-uladim_control='+wrong['token'])[0],404)

    def test_signing_another_customer_into_same_browser_removes_old_admission(self):
        admission=self.admit()
        status,_,_=self.request('/account/api/login',{'email':self.users[1]['email'],'password':self.password},cookie=self.parent[0][0])
        self.assertEqual(status,200)
        self.assertEqual(self.request('/',staff=True,cookie=admission)[0],404)
        # Admission invalidation does not rewrite existing customer auth semantics.
        self.assertEqual(self.request('/account/api/session',cookie=self.parent[0][0])[0],200)

    def test_customer_mfa_completion_invalidates_admission_only_when_login_finishes(self):
        from backend.customer_mfa import CustomerMFA
        admission=self.admit(); mfa=CustomerMFA(self.backend)
        factor=mfa.begin(self.users[1],self.password)
        mfa.enable(self.users[1],self.password,factor['enrollment'],totp(factor['totp_secret'],self.now//30))
        status,headers,pending=self.request('/account/api/login',{'email':self.users[1]['email'],'password':self.password},cookie=self.parent[0][0])
        self.assertEqual(status,200); self.assertTrue(pending['mfa_required']); self.assertNotIn('Set-Cookie',dict(headers))
        self.assertEqual(self.request('/',staff=True,cookie=admission)[0],200)
        self.now+=30
        status,headers,_=self.request('/account/api/login/mfa',{'challenge':pending['challenge'],'code':totp(factor['totp_secret'],self.now//30)},cookie=self.parent[0][0])
        self.assertEqual(status,200); self.assertIn('__Host-uladim_account=',dict(headers)['Set-Cookie'])
        self.assertEqual(self.request('/',staff=True,cookie=admission)[0],404)

    def test_signup_and_confirmation_do_not_replace_signed_in_customer_cookie(self):
        from dataclasses import replace
        self.app=Application(self.backend,replace(self.app.settings,registration_mode='open'))
        admission=self.admit(); email='signup@example.test'
        status,headers,_=self.request('/account/api/signup',{'email':email,'password':self.password},cookie=self.parent[0][0])
        self.assertEqual(status,200); self.assertNotIn('Set-Cookie',dict(headers))
        status,headers,_=self.request('/account/api/confirm-signup',{'email':email,'code':self.mail[email]},cookie=self.parent[0][0])
        self.assertEqual(status,200); self.assertNotIn('Set-Cookie',dict(headers))
        self.assertEqual(self.request('/',staff=True,cookie=admission)[0],200)

    def test_app_handoff_preserves_origin_without_referrer_path_and_null_is_rejected(self):
        _,headers,_=self.request('/app')
        self.assertEqual(dict(headers)['Referrer-Policy'],'strict-origin')
        ticket=self.issue()
        self.assertEqual(self.request('/admit',{'ticket':ticket['ticket']},staff=True,form=True,origin='null')[0],404)
        self.assertEqual(self.request('/admit',{'ticket':ticket['ticket']},staff=True,form=True,origin='https://getuladim.space')[0],303)
