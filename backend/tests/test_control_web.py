import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch
from cryptography.fernet import Fernet
from backend.service import Backend, Failure
from backend.control import Control, StaffPrincipal, totp
from backend.support import Support
from backend.config import Settings
from backend.production import Application
from backend.web import Web, ACCOUNT_COOKIE, CONTROL_COOKIE

class WebControlTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.mail={};self.backend=Backend(Path(folder.name)/'web.db',deliver=lambda e,c:self.mail.update({e:c}))
        self.backend.cipher=Fernet(Fernet.generate_key())
        self.owner_user=self.user('owner@example.test');self.user2=self.user('second@example.test')
        self.control=Control(self.backend);self.enrollment=self.control.bootstrap(self.owner_user['email'])
        self.now=int(self.backend.clock());self.backend.clock=lambda:self.now
        self.staff_login=self.control.login(self.owner_user['email'],'a-valid-long-passphrase',totp(self.enrollment['totp_secret'],self.now//30),'fixture')
        self.owner=self.control.authenticate(self.staff_login['token'],'fixture')
        self.settings=Settings.load({'DATABASE_URL':'postgresql://example/db','EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),'RATE_LIMIT_KEY':'x'*48,'SMTP_HOST':'127.0.0.1','SMTP_TLS':'none','EMAIL_FROM':'test@example.test'})
        self.app=Application(self.backend,self.settings)
        self.setup_admission()

    def setup_admission(self):
        _,headers,value=self.request('/account/api/login',{'email':self.owner_user['email'],'password':'a-valid-long-passphrase'},origin='https://getuladim.space')
        _,_,handoff=self.request('/account/api/control/access',{},cookie=headers['Set-Cookie'].split(';')[0],csrf=value['csrf'],origin='https://getuladim.space')
        status,headers,_=self.request('/admit',{'ticket':handoff['ticket']},host='control.getuladim.space',origin='https://getuladim.space',form=True)
        self.assertEqual(status,303); self.admission=headers['Set-Cookie'].split(';')[0]

    def user(self,email):
        result=self.backend.register(email,'a-valid-long-passphrase');actor=self.backend.authenticate(result['token']);self.backend.verify(actor,self.mail[email]);return self.backend.authenticate(result['token'])

    def request(self,path,body=None,host='getuladim.space',cookie='',csrf='',origin=None,form=False):
        data=(urlencode(body).encode() if form else json.dumps(body).encode()) if body is not None else b''
        if host=='control.getuladim.space' and getattr(self,'admission',''):cookie=(cookie+'; '+self.admission).strip('; ')
        env={'HTTP_HOST':host,'REQUEST_METHOD':'POST' if body is not None else 'GET','PATH_INFO':path,'REMOTE_ADDR':'172.30.30.2','HTTP_X_FORWARDED_PROTO':'https','HTTP_USER_AGENT':'fixture','HTTP_COOKIE':cookie,'HTTP_X_CSRF_TOKEN':csrf,'CONTENT_TYPE':'application/x-www-form-urlencoded' if form else 'application/json','CONTENT_LENGTH':str(len(data)),'wsgi.input':io.BytesIO(data)}
        if origin is not None:env['HTTP_ORIGIN']=origin
        result=[]
        with patch.object(self.app,'limit'):
            chunks=self.app(env,lambda s,h:result.append((int(s.split()[0]),dict(h))))
        raw=b''.join(chunks);status,headers=result[0]
        return status,headers,(json.loads(raw) if raw and headers['Content-Type'].startswith('application/json') else raw.decode())

    def login_customer(self):
        status,headers,body=self.request('/account/api/login',{'email':self.user2['email'],'password':'a-valid-long-passphrase'},origin='https://getuladim.space')
        self.assertEqual(status,200)
        return headers['Set-Cookie'].split(';')[0],body['csrf']

    def test_password_first_staff_login_has_no_session_before_second_factor(self):
        origin = 'https://control.getuladim.space'
        credentials = {'email':self.owner_user['email'],'password':'a-valid-long-passphrase'}
        status, headers, value = self.request('/control/api/login',credentials,host='control.getuladim.space',origin=origin)
        self.assertEqual(status,200); self.assertTrue(value['mfa_required']); self.assertNotIn('Set-Cookie',headers)
        self.assertEqual(self.request('/control/api/dashboard',host='control.getuladim.space')[0],401)
        body = {'challenge':value['challenge'],'code':totp(self.enrollment['totp_secret'],(self.now+30)//30),'role':'owner'}
        self.now += 30
        self.assertEqual(self.request('/account/api/login/mfa',body,origin='https://getuladim.space')[0],401)
        self.assertEqual(self.request('/control/api/login/mfa',body,host='control.getuladim.space',origin='https://evil.invalid')[0],403)
        status, headers, value = self.request('/control/api/login/mfa',body,host='control.getuladim.space',origin=origin)
        self.assertEqual(status,200); self.assertIn('__Host-uladim_control=',headers['Set-Cookie'])
        self.assertEqual(self.request('/control/api/login/mfa',body,host='control.getuladim.space',origin=origin)[0],401)

    def test_open_registration_omits_invitation_but_preserves_verification(self):
        from dataclasses import replace
        self.app = Application(self.backend,replace(self.settings,registration_mode='open'))
        self.assertTrue(self.request('/account/api/config')[2]['registration_open'])
        email = 'public-signup@example.test'
        body = {'email':email,'password':'a-valid-long-passphrase','role':'owner','tier':'Premium'}
        status, headers, value = self.request('/account/api/signup',body,origin='https://getuladim.space')
        self.assertEqual(status,200); self.assertNotIn('Set-Cookie',headers); self.assertNotIn('token',value)
        self.assertEqual(self.request('/account/api/signup',body,origin='https://getuladim.space')[2],value)
        with self.backend.connect() as db:
            user = db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
            self.assertEqual(user['verified'],0)
            self.assertIsNone(db.execute('SELECT 1 FROM staff WHERE user_id=?',(user['id'],)).fetchone())
        self.assertEqual(self.request('/account/api/confirm-signup',{'email':email,'code':'x'*43},origin='https://getuladim.space')[0],400)
        code = self.mail[email]
        self.assertEqual(self.request('/account/api/confirm-signup',{'email':email,'code':code},origin='https://getuladim.space')[0],200)
        self.assertEqual(self.request('/account/api/confirm-signup',{'email':email,'code':code},origin='https://getuladim.space')[0],400)
        status, headers, value = self.request('/account/api/login',{'email':email,'password':body['password']},origin='https://getuladim.space')
        self.assertEqual(status,200); self.assertNotIn('mfa_required',value)

    def test_host_boundary_csp_cookies_csrf_and_revocation(self):
        status,headers,html=self.request('/')
        self.assertEqual(status,200);self.assertIn('ULADIM',html);self.assertNotIn('control.getuladim',html)
        self.assertNotIn('unsafe-inline',headers['Content-Security-Policy'])
        self.assertEqual(self.request('/control/api/dashboard')[0],404)
        self.assertEqual(self.request('/account/api/login',{'email':self.user2['email'],'password':'a-valid-long-passphrase'},origin='https://evil.test')[0],403)
        cookie,csrf=self.login_customer()
        self.assertTrue(cookie.startswith(ACCOUNT_COOKIE+'='))
        self.assertEqual(self.request('/account/api/session',cookie=cookie)[0],200)
        self.assertEqual(self.request('/control/api/session',host='control.getuladim.space',cookie=cookie)[0],401)
        self.assertEqual(self.request('/account/api/logout',{},cookie=cookie,origin='https://getuladim.space')[0],403)
        self.assertEqual(self.request('/account/api/logout',{},cookie=cookie,csrf=csrf,origin='https://getuladim.space')[0],200)
        self.assertEqual(self.request('/account/api/session',cookie=cookie)[0],401)
        self.assertEqual(self.request('/account/api/session',cookie=CONTROL_COOKIE+'='+self.staff_login['token'])[0],401)

    def test_staff_cookie_is_not_a_customer_bearer_and_mfa_required(self):
        self.now+=30
        status,headers,body=self.request('/control/api/login',{'email':self.owner_user['email'],'password':'a-valid-long-passphrase','code':totp(self.enrollment['totp_secret'],self.now//30)},host='control.getuladim.space',origin='https://control.getuladim.space')
        self.assertEqual(status,200)
        cookie=headers['Set-Cookie'].split(';')[0]
        self.assertIn('HttpOnly; Secure; SameSite=Strict',headers['Set-Cookie'])
        status,headers,body=self.request('/control/api/session',host='control.getuladim.space',cookie=cookie)
        self.assertEqual(status,200);self.assertEqual(body['roles'],['owner']);self.assertEqual(headers['X-Robots-Tag'],'noindex, nofollow')
        with self.assertRaises(Failure):self.backend.authenticate(cookie.split('=',1)[1])
        self.backend.revoke_all(self.owner_user,'a-valid-long-passphrase')
        self.assertEqual(self.request('/control/api/session',host='control.getuladim.space',cookie=cookie)[0],404)

    def test_support_isolation_redaction_and_no_audit_message_body(self):
        support=Support(self.backend,self.control)
        ticket=support.create(self.user2,'bug','Test','token=super-secret Please help')['ticket_id']
        with self.assertRaises(Failure):support.read(self.owner_user,ticket)
        auditor=StaffPrincipal('auditor',self.owner_user['id'],('auditor',))
        with self.assertRaises(Failure):support.read(auditor,ticket,True)
        self.assertNotIn('super-secret',support.read(self.owner,ticket,True)['messages'][0]['body'])
        support.reply(self.owner,ticket,'Private support response',staff=True)
        events=json.dumps(self.control.audit_log(self.owner))
        self.assertNotIn('Private support response',events)
        self.control.moderate(self.owner,self.user2['id'],'support_write',self.now+100,'Temporary moderation')
        with self.assertRaises(Failure):support.reply(self.user2,ticket,'blocked')
        self.assertEqual(len(support.read(self.user2,ticket)['messages']),2)

    def test_staff_invite_mfa_and_two_phase_flag_updates(self):
        invite=self.control.invite_staff(self.owner,self.user2['email'],['support'],'Need support coverage')
        with self.assertRaises(Failure):self.control.prepare_enrollment(self.owner_user,invite['invitation'],'a-valid-long-passphrase')
        enrollment=self.control.prepare_enrollment(self.user2,invite['invitation'],'a-valid-long-passphrase')
        result=self.control.finish_enrollment(self.user2,enrollment['enrollment'],totp(enrollment['totp_secret'],self.now//30))
        self.assertEqual(len(result['recovery_codes']),8)
        with self.assertRaises(Failure):self.control.finish_enrollment(self.user2,enrollment['enrollment'],totp(enrollment['totp_secret'],self.now//30))
        with self.assertRaises(Failure):self.control.preview_flag(self.owner,'disable_mfa',True,100,0,'Forbidden')
        proposal=self.control.preview_flag(self.owner,'chart_styles',True,100,0,'Closed test rollout')
        self.assertEqual(self.control.flags(),{})
        self.control.commit_flag(self.owner,proposal['proposal_id'],proposal['digest'])
        self.assertTrue(self.control.flags(self.user2['id'])['chart_styles']['active'])
        with self.assertRaises(Failure):self.control.commit_flag(self.owner,proposal['proposal_id'],proposal['digest'])
        stale=self.control.preview_flag(self.owner,'chart_styles',False,0,0,'Stale revision')
        with self.assertRaises(Failure):self.control.commit_flag(self.owner,stale['proposal_id'],stale['digest'])
