"""Adversarial, two-account HTTP checks on disposable data only."""
import io
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from urllib.parse import urlencode
from cryptography.fernet import Fernet
from backend.config import Settings
from backend.control import Control, ROLE_PERMISSIONS, totp
from backend.production import Application
from backend.service import Backend
from backend.support import Support

EVIDENCE = []


class SecurityAuditTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.now = 1800000000
        self.mail = {}
        self.backend = Backend(Path(folder.name)/'audit.db', deliver=lambda e,c:self.mail.update({e:c}), clock=lambda:self.now)
        self.backend.cipher = Fernet(Fernet.generate_key())
        self.prepare_audit()

    def prepare_audit(self):
        self.password = 'audit-only-passphrase'
        self.people, self.cookies = [], []
        settings = Settings.load({'DATABASE_URL':'postgresql://unused/test', 'EMAIL_QUEUE_KEY':Fernet.generate_key().decode(), 'RATE_LIMIT_KEY':'a'*48, 'SMTP_HOST':'localhost', 'SMTP_TLS':'none', 'EMAIL_FROM':'fixture@example.test'})
        self.app = Application(self.backend, settings)
        with self.backend.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS http_limits(key TEXT PRIMARY KEY,count BIGINT NOT NULL,until_at BIGINT NOT NULL)')
        for email in ('alice@example.test', 'bob@example.test'):
            session = self.backend.register(email, self.password)
            actor = self.backend.authenticate(session['token'])
            self.backend.verify(actor, self.mail[email])
            self.people.append(self.backend.authenticate(session['token']))
            status, headers, value = self.request('/account/api/login', {'email':email,'password':self.password})
            self.assertEqual(status, 200)
            self.cookies.append((headers['Set-Cookie'].split(';')[0], value['csrf']))
        self.alice, self.bob = self.people
        self.spaces = []
        for actor in self.people:
            wid = str(uuid.uuid4()); self.spaces.append(wid)
            self.backend.family(actor, {'id':str(uuid.uuid4()), 'workspace_id':wid,'action':'workspace.create','kind':'personal','name':'Audit fixture'})

    def request(self, path, body=None, *, identity=None, staff=False, method=None, origin=None, extra=None, form=False):
        path, _, query = path.partition('?')
        host = 'control.getuladim.space' if staff else 'getuladim.space'
        data = (urlencode(body).encode() if form else json.dumps(body).encode()) if body is not None else b''
        cookie, csrf = identity or ('','')
        if staff and getattr(self,'admission',''):cookie=(cookie+'; '+self.admission).strip('; ')
        env = {'HTTP_HOST':host,'REQUEST_METHOD':method or ('POST' if body is not None else 'GET'), 'PATH_INFO':path,'QUERY_STRING':query,'REMOTE_ADDR':'172.30.30.2','HTTP_X_FORWARDED_PROTO':'https','HTTP_USER_AGENT':'audit-fixture','HTTP_ORIGIN':origin or 'https://'+host,'HTTP_COOKIE':cookie,'HTTP_X_CSRF_TOKEN':csrf,'CONTENT_TYPE':'application/x-www-form-urlencoded' if form else 'application/json','CONTENT_LENGTH':str(len(data)),'wsgi.input':io.BytesIO(data)}
        env.update(extra or {})
        response=[]
        raw=b''.join(self.app(env, lambda s,h:response.append((int(s.split()[0]),dict(h)))))
        status, headers=response[0]
        value=json.loads(raw) if raw and headers['Content-Type'].startswith('application/json') else raw
        return status, headers, value

    def admit_staff(self, identity):
        status,_,handoff=self.request('/account/api/control/access',{},identity=identity)
        self.assertEqual(status,200,handoff)
        status,headers,_=self.request('/admit',{'ticket':handoff['ticket']},staff=True,form=True,origin='https://getuladim.space')
        self.assertEqual(status,303); self.admission=headers['Set-Cookie'].split(';')[0]

    def check(self, name, actual, expected):
        engine='PostgreSQL' if hasattr(self.backend,'pool') else 'SQLite'
        EVIDENCE.append({'case':name,'expected':expected,'actual':actual,'passed':actual==expected,'fixture':'isolated two-account '+engine+' WSGI'})
        self.assertEqual(actual, expected, name)

    def test_cross_account_records_spaces_and_mass_assignment(self):
        payloads={'task':{'title':'Private task','completed':0,'assignment':'any','assignees':[],'review':0}, 'note':{'body':'Private note'}, 'account':{'name':'Private account','currency':'RUB','opening_minor':10000},'transaction':{'kind':'expense','amount_minor':100,'currency':'RUB','date':'2026-11-09','label':'Private expense','account_id':None}}
        for kind, data in payloads.items():
            op={'id':str(uuid.uuid4()),'action':'record.put','record_id':str(uuid.uuid4()),'revision':0,'kind':kind,'visibility':'private','audience':[],'data':data}
            self.backend.batch(self.alice,self.spaces[0],[op])
            status,_,body=self.request('/account/api/sync?workspace='+self.spaces[0],identity=self.cookies[1])
            self.check(kind+' foreign workspace read',status,403)
            forged=dict(op,id=str(uuid.uuid4()),revision=1)
            _,_,body=self.request('/account/api/sync',{'workspace_id':self.spaces[1],'operations':[forged]},identity=self.cookies[1])
            self.check(kind+' foreign record edit',body['results'][0]['error'],'record_forbidden')
            forged.update(action='record.delete',id=str(uuid.uuid4()))
            _,_,body=self.request('/account/api/sync',{'workspace_id':self.spaces[1],'operations':[forged]},identity=self.cookies[1])
            self.check(kind+' foreign record delete',body['results'][0]['error'],'record_forbidden')
        status,_,_=self.request('/account/api/session?user_id='+self.alice['id'],identity=self.cookies[1])
        self.check('user ID parameter does not select identity',status,200)
        _,_,body=self.request('/account/api/session?user_id='+self.alice['id'],identity=self.cookies[1])
        self.check('actual session owner remains Bob',body['user_id'],self.bob['id'])
        self.check('Alice records unchanged',len(self.backend.pull(self.alice,self.spaces[0],0)['records']),4)

    def test_support_idor_csrf_cors_cookie_and_methods(self):
        tid=Support(self.backend,Control(self.backend)).create(self.alice,'bug','Fixture','Private support')['ticket_id']
        for path,body in [('/account/api/thread?id='+tid,None),('/account/api/support/reply',{'ticket_id':tid,'message':'foreign write'})]:
            self.check('foreign support '+path,self.request(path,body,identity=self.cookies[1])[0],404)
        self.check('missing CSRF',self.request('/account/api/logout',{},identity=(self.cookies[1][0],''))[0],403)
        status,headers,_=self.request('/account/api/logout',{},identity=self.cookies[1],origin='https://evil.example')
        self.check('cross-origin write rejected',status,403)
        self.check('no permissive CORS header',headers.get('Access-Control-Allow-Origin'),None)
        for method in ('PUT','PATCH','DELETE','OPTIONS'):
            self.check('method '+method,self.request('/account/api/session',identity=self.cookies[1],method=method)[0],405)
        for cookie in ('__Host-uladim_account='+'x'*43, '__Host-uladim_control='+'x'*43):
            self.check('forged '+cookie.split('=')[0],self.request('/account/api/session',identity=(cookie,''))[0],401)
        self.check('client role ignored',self.request('/control/api/users',identity=self.cookies[1],staff=True,extra={'HTTP_X_ROLE':'owner'})[0],404)
        self.check('public origin cannot reach Control',self.request('/control/api/users',identity=self.cookies[1])[0],404)

    def test_staff_http_permission_matrix_and_mfa(self):
        control=Control(self.backend)
        enrollment=control.bootstrap(self.alice['email'])
        self.admit_staff(self.cookies[0])
        status, headers, pending = self.request('/control/api/login',{'email':self.alice['email'],'password':self.password},staff=True)
        self.check('password step returns only pending MFA',status,200)
        self.check('password without staff MFA has no cookie','Set-Cookie' in headers,False)
        self.check('password without staff MFA has no authority',pending.get('authenticated',False),False)
        self.check('pending MFA cannot authorize Control',self.request('/control/api/dashboard',staff=True,identity=('__Host-uladim_control='+pending['challenge'],''))[0],401)
        secret='GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'
        sid=str(uuid.uuid4())
        with self.backend.connect() as db:
            db.execute('INSERT INTO staff(id,user_id,roles,mfa_secret,created_at) VALUES(?,?,?,?,?)',(sid,self.bob['id'],'["support"]',self.backend.cipher.encrypt(secret.encode()),self.now))
        self.admit_staff(self.cookies[1])
        reads={'record-recovery':'records.recover','dashboard':'dashboard.read','users':'users.read','staff':'staff.manage','audit':'audit.read','support':'support.read','flags':'flags.manage','applications':'applications.manage','catalog':'plans.grant'}
        writes={'record-recovery/approve':'records.recover','user/recovery':'users.recover','applications/decide':'applications.manage','moderate':'users.moderate','grant':'plans.grant','revoke-grant':'plans.grant','override':'plans.grant','catalog':'plans.catalog','staff/invite':'staff.manage','staff/update':'staff.manage','support/reply':'support.reply','support/triage':'support.reply','flags/preview':'flags.manage','flags/commit':'flags.manage'}
        for role, permissions in ROLE_PERMISSIONS.items():
            with self.backend.connect() as db:
                db.execute('UPDATE staff SET roles=?,last_counter=-1 WHERE id=?',(json.dumps([role]),sid))
            status,headers,result=self.request('/control/api/login',{'email':self.bob['email'],'password':self.password,'code':totp(secret,self.now//30)},staff=True)
            self.assertEqual(status,200,(role,result))
            identity=(headers['Set-Cookie'].split(';')[0],result['csrf'])
            self.assertTrue(all(v in headers['Set-Cookie'] for v in ('HttpOnly','Secure','SameSite=Strict','Path=/')))
            for path,permission in reads.items():
                status,_,_=self.request('/control/api/'+path,identity=identity,staff=True)
                self.check(role+' GET '+path,status,200 if permission in permissions else 403)
            for path,permission in writes.items():
                if permission in permissions: continue  # Allowed mutations have separate domain tests.
                status,_,body=self.request('/control/api/'+path,{},identity=identity,staff=True)
                self.check(role+' forbidden POST '+path,(status,body.get('error')),(403,'staff_forbidden'))
            self.check(role+' MFA replay rejected',self.request('/control/api/login',{'email':self.bob['email'],'password':self.password,'code':totp(secret,self.now//30)},staff=True)[0],401)
            # Each role gets a new real limiter window; the limiter is never mocked.
            self.now+=901

    def test_sessions_fixation_logout_and_password_revoke(self):
        prior=self.cookies[1]
        _,headers,result=self.request('/account/api/login',{'email':self.bob['email'],'password':self.password},identity=prior)
        new=(headers['Set-Cookie'].split(';')[0],result['csrf'])
        self.assertNotEqual(new[0],prior[0])
        self.check('logout succeeds',self.request('/account/api/logout',{},identity=new)[0],200)
        self.check('logged out cookie replay',self.request('/account/api/session',identity=new)[0],401)
        self.backend.password(self.bob,self.password,'new-audit-passphrase')
        self.check('old web cookie after password change',self.request('/account/api/session',identity=prior)[0],401)

    def test_head_is_read_only_get_with_empty_body(self):
        get_status,get_headers,_=self.request('/app')
        status,headers,body=self.request('/app',method='HEAD')
        self.check('HEAD static route status',status,get_status)
        self.check('HEAD preserves representation length',headers['Content-Length'],get_headers['Content-Length'])
        self.check('HEAD body omitted',len(body),0)
        # No JSON body exists in HEAD responses, so invoke WSGI directly here.
        cookie,csrf=self.cookies[1]
        env={'HTTP_HOST':'getuladim.space','REQUEST_METHOD':'HEAD','PATH_INFO':'/account/api/logout','REMOTE_ADDR':'172.30.30.2','HTTP_X_FORWARDED_PROTO':'https','HTTP_USER_AGENT':'audit-fixture','HTTP_COOKIE':cookie,'HTTP_X_CSRF_TOKEN':csrf}
        response=[]
        raw=b''.join(self.app(env,lambda s,h:response.append(s)))
        self.check('HEAD cannot log out',int(response[0].split()[0]),404)
        self.check('HEAD logout body omitted',len(raw),0)
        self.check('session survives HEAD logout',self.request('/account/api/session',identity=self.cookies[1])[0],200)

    def test_staff_lockout_attempts_and_idle_expiry(self):
        control=Control(self.backend)
        enrollment=control.bootstrap(self.alice['email'])
        self.admit_staff(self.cookies[0])
        for _ in range(10):
            self.assertEqual(self.request('/control/api/login',{'email':self.alice['email'],'password':'wrong','code':'000000'},staff=True)[0],401)
        self.check('staff brute force persists',self.request('/control/api/login',{'email':self.alice['email'],'password':self.password,'code':totp(enrollment['totp_secret'],self.now//30)},staff=True)[0],429)

    def test_admission_lifecycle_capability_scope_and_no_automatic_account(self):
        from backend.early_access import CONSENT_VERSION, EarlyAccess
        email='applicant@example.test'
        status,_,_=self.request('/early-access/api/apply',{'email':email,'consent_version':CONSENT_VERSION})
        self.check('guest application accepted',status,200)
        with self.backend.connect() as db:
            self.check('application creates no user',db.execute('SELECT COUNT(*) AS n FROM users').fetchone()['n'],2)
        status,_,result=self.request('/early-access/api/confirm',{'email':email,'code':self.mail[email]})
        self.check('confirmed applicant enters queue',(status,result['state']),(200,'pending'))
        capability=result['management_token']
        self.check('confirmation is one-use',self.request('/early-access/api/confirm',{'email':email,'code':self.mail[email]})[0],400)
        self.check('uninvited registration stays closed',self.request('/account/api/signup',{'email':email,'password':self.password})[0],403)
        control=Control(self.backend);enrollment=control.bootstrap(self.alice['email'])
        token=control.login(self.alice['email'],self.password,totp(enrollment['totp_secret'],self.now//30),'audit-fixture')['token']
        owner=control.authenticate(token,'audit-fixture')
        early=EarlyAccess(self.backend)
        row=early.list(owner,control)['applications'][0]
        early.decide(owner,control,row['id'],'approved',row['revision'],'Audit fixture approval')
        invitation=self.mail[email]
        self.check('invitation bound to recipient',self.request('/account/api/signup',{'email':'other@example.test','password':self.password,'invitation':invitation})[0],403)
        self.check('invited signup',self.request('/account/api/signup',{'email':email,'password':self.password,'invitation':invitation})[0],200)
        self.check('email confirmation completes registration',self.request('/account/api/confirm-signup',{'email':email,'code':self.mail[email]})[0],200)
        self.check('application status capability',self.request('/early-access/api/status',{'management_token':capability})[2]['state'],'approved')
        self.check('cancel applicant',self.request('/early-access/api/cancel',{'management_token':capability})[2]['state'],'cancelled')
        self.check('cancellation invalidates invitation',early.invited(email,invitation),False)

    def test_tiers_and_family_invitation_replay_and_revocation(self):
        from backend.entitlements import grant
        status,_,result=self.request('/account/api/entitlements?tier=Premium',identity=self.cookies[1])
        self.check('client cannot select Premium',(status,result['tier']),(200,'Free'))
        for tier in ('Plus','Premium'):
            with self.backend.connect() as db:
                grant(db,self.bob['id'],tier,'manual',self.now+86400,'Fixture grant','audit-operator',self.now)
            self.check('server-issued '+tier,self.request('/account/api/entitlements',identity=self.cookies[1])[2]['tier'],tier)
        self.check('customer cannot grant own plan',self.request('/account/api/grant',{'tier':'Premium'},identity=self.cookies[1])[0],404)
        wid=str(uuid.uuid4())
        def family(action,**values):
            return self.backend.family(self.alice,dict(id=str(uuid.uuid4()),workspace_id=wid,action=action,**values))
        family('workspace.create',kind='family',name='Audit family')
        invite=family('invite.create',email=self.bob['email'],role='adult',profile_id=None)['invitation']
        self.check('family invitation cannot be forwarded',self.request('/account/api/invitations/accept',{'id':str(uuid.uuid4()),'invitation':invite},identity=self.cookies[0])[0],403)
        self.check('recipient joins family',self.request('/account/api/invitations/accept',{'id':str(uuid.uuid4()),'invitation':invite},identity=self.cookies[1])[0],200)
        self.check('family invite one-use',self.request('/account/api/invitations/accept',{'id':str(uuid.uuid4()),'invitation':invite},identity=self.cookies[1])[0],403)
        self.check('family member cannot dissolve',self.request('/account/api/family',{'id':str(uuid.uuid4()),'workspace_id':wid,'action':'workspace.dissolve','revision':1},identity=self.cookies[1])[0],403)
        family('member.remove',user_id=self.bob['id'],revision=1)
        self.check('removed family member loses read access',self.request('/account/api/sync?workspace='+wid,identity=self.cookies[1])[0],403)
