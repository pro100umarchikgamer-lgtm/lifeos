"""Privacy regression fixtures: synthetic subjects, isolated DBs, no provider/SMTP calls."""
import contextlib
import io
import json
import os
import socket
import threading
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from backend.account_erasure import append_ledger, apply_ledger, initialize, read_ledger
from backend.account_lifecycle import AccountLifecycle
from backend.config import Settings
from backend.control import totp
from backend.google_identity import GoogleIdentity
from backend.http_server import dispatch
from backend.service import Backend, Failure, token_hash
from backend.tests.test_google_identity import SyntheticGoogle, CLIENT

PASSWORD = 'privacy-synthetic-passphrase'


def uid(): return str(uuid.uuid4())


class SyntheticLedgerSocket:
    def __init__(self,path,handler):
        self.path=str(path);self.handler=handler;self.errors=[];self.requests=[]
        self.server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.server.bind(self.path);self.server.listen(4);self.server.settimeout(0.2)
        self.stopped=False;self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def run(self):
        while not self.stopped:
            try:client,_=self.server.accept()
            except socket.timeout:continue
            except OSError:return
            with client:
                try:
                    request=json.loads(client.makefile('rb').readline(1024));self.requests.append(request)
                    response=self.handler(request)
                except Exception as error:
                    self.errors.append(error);response={'acknowledged':False}
                try:client.sendall((json.dumps(response)+'\n').encode())
                except OSError:pass
    def close(self):
        self.stopped=True;self.server.close();self.thread.join(timeout=2)


class PrivacyScenarios:
    def fixtures(self):
        self.now = int(time.time())
        self.backend.clock = lambda: self.now
        self.mail = {}
        original = self.backend._deliver
        def capture(db, email, code, purpose):
            if hasattr(self.backend, 'pool'): original(db, email, code, purpose)
            self.mail[email] = code
        self.backend._deliver = capture
        self.lifecycle = AccountLifecycle(self.backend)
        self.settings = Settings.load({'DATABASE_URL':'postgresql://unused/test', 'EMAIL_QUEUE_KEY':Fernet.generate_key().decode(), 'RATE_LIMIT_KEY':'x'*48, 'SMTP_HOST':'localhost', 'SMTP_TLS':'none', 'EMAIL_FROM':'fixture@example.test', 'GOOGLE_OAUTH_CLIENT_ID':CLIENT, 'GOOGLE_OAUTH_CLIENT_SECRET':'fixture-secret', 'REGISTRATION_MODE':'open'})
        self.provider = SyntheticGoogle()
        self.google = GoogleIdentity(self.backend, self.settings, self.provider)
        self.owner, self.owner_session = self.user('owner@example.test')
        self.peer, self.peer_session = self.user('peer@example.test')

    def user(self, email):
        session = self.backend.register(email, PASSWORD)
        actor = self.backend.authenticate(session['token'])
        self.backend.verify(actor, self.mail[email])
        actor = self.backend.authenticate(session['token'])
        actor['_auth_hash'] = token_hash(session['token'])
        return actor, session

    def google_user(self):
        start = self.google.start('android', 'fixture')
        session = self.google.finish(start['challenge'], 'android', 'fixture', id_token=self.provider.sign(start['nonce']))
        actor = self.backend.authenticate(session['token'])
        actor['_auth_hash'] = token_hash(session['token'])
        return actor, session

    def proof(self, actor, **changes):
        start = self.google.start('android', 'fixture', actor=actor, auth_hash=actor['_auth_hash'], purpose='reauth')
        return self.google.finish(start['challenge'], 'android', 'fixture', id_token=self.provider.sign(start['nonce'], **changes))['reauth_token']

    def family(self):
        wid = uid()
        self.backend.family(self.owner, {'id':uid(), 'workspace_id':wid, 'action':'workspace.create', 'kind':'family', 'name':'Private family name'})
        invitation = self.backend.family(self.owner, {'id':uid(),'workspace_id':wid,'action':'invite.create','email':self.peer['email'],'role':'parent','profile_id':None})
        self.backend.accept(self.peer, {'id':uid(),'invitation':invitation['invitation']})
        transfer = self.lifecycle.transfer(self.owner, wid, self.peer['id'], PASSWORD)
        self.lifecycle.accept_transfer(self.peer, transfer['transfer_id'], PASSWORD)
        return wid

    def put(self, actor, wid, kind, data, visibility='shared', audience=None):
        rid = uid()
        result = self.backend.batch(actor, wid, [{'id':uid(),'action':'record.put','record_id':rid,'revision':0,'kind':kind,'visibility':visibility,'audience':audience or [],'data':data}])['results'][0]
        self.assertEqual(result['status'], 'accepted', result)
        return rid

    def erase(self, actor):
        self.lifecycle.request_deletion(actor, PASSWORD, 'DELETE')
        self.now += 86401
        self.assertTrue(self.lifecycle.process_one_deletion())
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM deletion_jobs WHERE user_id=?', (actor['id'],)).fetchone()['state'], 'completed')

    def test_google_only_fresh_subject_proof_deletes_and_cancels_without_password(self):
        actor, session = self.google_user()
        self.assertFalse(self.google.status(actor)['has_password'])
        with self.assertRaises(Failure): self.lifecycle.request_deletion(actor, PASSWORD, 'DELETE')
        proof = self.proof(actor)
        requested = dispatch(self.backend, 'POST', '/v1/account/lifecycle/deletion', {'reauth_token':proof,'confirmation':'DELETE'}, 'Bearer '+session['token'])
        self.assertEqual(requested['due_at'], self.now+86400)
        with self.assertRaises(Failure): self.lifecycle.cancel_deletion(actor, None, proof)
        self.lifecycle.cancel_deletion(actor, None, self.proof(actor))
        self.assertEqual(self.lifecycle.deletion_status(actor)['request']['state'], 'cancelled')
        self.lifecycle.request_deletion(actor, None, 'DELETE', self.proof(actor))
        self.now += 86401
        self.assertTrue(self.lifecycle.process_one_deletion())
        with self.assertRaises(Failure): self.backend.authenticate(session['token'])
        with self.assertRaises(Failure): self.backend.refresh_session(session['refresh_token'])

    def test_google_proof_rejects_different_subject_session_credential_version_and_expiry(self):
        actor, session = self.google_user()
        with self.assertRaises(Failure) as error: self.proof(actor, sub='unrelated-subject')
        self.assertEqual(error.exception.code, 'google_identity_mismatch')
        proof = self.proof(actor)
        second = self.google.finish((start:=self.google.start('android','fixture'))['challenge'],'android','fixture',id_token=self.provider.sign(start['nonce']))
        with self.assertRaises(Failure): dispatch(self.backend,'POST','/v1/account/lifecycle/deletion',{'reauth_token':proof,'confirmation':'DELETE'},'Bearer '+second['token'])
        with self.backend.transaction() as db: db.execute('UPDATE users SET salt=? WHERE id=?', ('ab'*16, actor['id']))
        with self.assertRaises(Failure): self.lifecycle.request_deletion(actor,None,'DELETE',proof)
        proof = self.proof(actor)
        self.now += 301
        with self.assertRaises(Failure): self.lifecycle.request_deletion(actor,None,'DELETE',proof)
        self.now -= 301
        start = self.google.start('android','fixture',actor=actor,auth_hash=actor['_auth_hash'],purpose='reauth')
        with self.backend.transaction() as db: self.backend.revoke_all_in(db,actor['id'])
        with self.assertRaises(Failure): self.google.finish(start['challenge'],'android','fixture',id_token=self.provider.sign(start['nonce']))

    def test_password_and_google_deletion_still_require_single_use_mfa(self):
        actor, session = self.google_user()
        secret = 'JBSWY3DPEHPK3PXP'
        with self.backend.transaction() as db:
            db.execute('INSERT INTO account_mfa VALUES(?,?,?)', (actor['id'], self.backend.cipher.encrypt(secret.encode()), -1))
        proof = self.proof(actor)
        with self.assertRaises(Failure) as error: self.lifecycle.request_deletion(actor,None,'DELETE',proof)
        self.assertEqual(error.exception.code,'mfa_invalid')
        self.lifecycle.request_deletion(actor,None,'DELETE',proof,totp(secret,self.now//30))
        with self.assertRaises(Failure): self.lifecycle.cancel_deletion(actor,None,self.proof(actor),totp(secret,self.now//30))
        # Existing password users receive exactly the same MFA requirement.
        with self.backend.transaction() as db:
            db.execute('INSERT INTO account_mfa VALUES(?,?,?)', (self.peer['id'], self.backend.cipher.encrypt(secret.encode()), -1))
        with self.assertRaises(Failure): self.lifecycle.request_deletion(self.peer,PASSWORD,'DELETE')
        self.lifecycle.request_deletion(self.peer,PASSWORD,'DELETE',code=totp(secret,self.now//30))

    def test_sole_parent_child_has_explicit_confirmed_close_family_path(self):
        wid = uid(); pid = uid()
        self.backend.family(self.owner,{'id':uid(),'workspace_id':wid,'action':'workspace.create','kind':'family','name':'Family'})
        self.backend.family(self.owner,{'id':uid(),'workspace_id':wid,'action':'child.save','profile_id':pid,'revision':0,'name':'Child','permissions':['create_tasks','edit_own']})
        invitation=self.backend.family(self.owner,{'id':uid(),'workspace_id':wid,'action':'invite.create','email':self.peer['email'],'role':'child','profile_id':pid})
        self.backend.accept(self.peer,{'id':uid(),'invitation':invitation['invitation']})
        record = self.put(self.peer,wid,'task',{'title':'Peer task remains','completed':0,'assignment':'any','assignees':[],'review':0},audience=[pid])
        plan=self.lifecycle.deletion_status(self.owner)['ownership_transfer_required'][0]
        self.assertIsNone(plan['eligible_parent_id']);self.assertTrue(plan['close_family_available'])
        with self.assertRaises(Failure): self.lifecycle.request_deletion(self.owner,PASSWORD,'DELETE')
        with self.assertRaises(Failure): self.lifecycle.close_family(self.owner,wid,plan['workspace_revision'],PASSWORD,'yes')
        self.assertEqual(self.backend.pull(self.peer,wid,0)['records'][0]['data']['title'],'Peer task remains')
        self.lifecycle.close_family(self.owner,wid,plan['workspace_revision'],PASSWORD,'CLOSE FAMILY')
        self.erase(self.owner)
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT title FROM tasks WHERE id=?',(record,)).fetchone()['title'],'Peer task remains')
            self.assertEqual(db.execute('SELECT email FROM users WHERE id=?',(self.peer['id'],)).fetchone()['email'],self.peer['email'])

    def test_all_owned_payloads_erase_peer_money_survives_and_structural_stubs_are_deleted_immutable(self):
        wid=self.family()
        own=self.put(self.owner,wid,'account',{'name':'Secret account owner name','currency':'USD','opening_minor':10000})
        target=self.put(self.peer,wid,'account',{'name':'Peer account','currency':'EUR','opening_minor':2000})
        private=self.put(self.owner,wid,'note',{'body':'Erase personal text'},'private')
        shared=self.put(self.owner,wid,'note',{'body':'Erase shared text too'})
        old_note=self.put(self.owner,wid,'note',{'body':'Erase retained recovery payload'})
        result=self.backend.batch(self.owner,wid,[{'id':uid(),'action':'record.delete','record_id':old_note,'revision':1}])
        self.assertEqual(result['results'][0]['status'],'accepted')
        peer_tx=self.put(self.peer,wid,'transaction',{'kind':'expense','amount_minor':350,'currency':'USD','date':'2026-11-01','label':'Peer expense preserved','account_id':own})
        peer_transfer=self.put(self.peer,wid,'transfer',{'from_id':own,'to_id':target,'sent_minor':700,'received_minor':650,'date':'2026-11-02'})
        own_transfer=self.put(self.owner,wid,'transfer',{'from_id':own,'to_id':target,'sent_minor':400,'received_minor':370,'date':'2026-11-03'})
        pid=uid();self.backend.family(self.peer,{'id':uid(),'action':'child.save','workspace_id':wid,'profile_id':pid,'revision':0,'name':'Peer child','permissions':[]})
        request=self.put(self.peer,wid,'request',{'profile_id':pid,'amount_minor':370,'currency':'EUR','label':'Peer request retained','state':'pending','movement_id':None},audience=[pid])
        with self.backend.transaction() as db:db.execute("UPDATE requests SET state='fulfilled',movement_id=? WHERE id=?",(own_transfer,request))
        before=self.backend.pull_incremental(self.peer,wid,0)
        self.erase(self.owner)
        after=self.backend.pull_incremental(self.peer,wid,before['cursor'],before['epoch'])
        self.assertTrue(after['reset'])
        byid={r['id']:r for r in after['records']}
        self.assertEqual(byid[peer_tx]['data'],{'kind':'expense','amount_minor':350,'currency':'USD','date':'2026-11-01','label':'Peer expense preserved','account_id':None})
        self.assertEqual(byid[peer_transfer]['data'],{'from_id':own,'to_id':target,'sent_minor':700,'received_minor':650,'date':'2026-11-02'})
        self.assertEqual(byid[request]['data']['amount_minor'],370);self.assertEqual(byid[request]['data']['state'],'fulfilled');self.assertIsNone(byid[request]['data']['movement_id'])
        self.assertTrue(byid[own]['deleted']);self.assertTrue(byid[own]['structural_reference']);self.assertEqual(byid[own]['reference_currency'],'USD');self.assertEqual(byid[own]['data'],{});self.assertFalse(byid[own]['editable'])
        for rid in (private,shared,old_note):
            with self.backend.connect() as db:self.assertIsNone(db.execute('SELECT body FROM notes WHERE id=?',(rid,)).fetchone())
        with self.backend.connect() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM transfers WHERE id=?',(own_transfer,)).fetchone())
            self.assertEqual(db.execute('SELECT name,opening_minor FROM accounts WHERE id=?',(own,)).fetchone()['opening_minor'],0)
            self.assertEqual(db.execute('SELECT opening_minor FROM accounts WHERE id=?',(target,)).fetchone()['opening_minor'],2000)
            if not hasattr(self.backend,'pool'):self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
        # Both a new operation and a cached stale outbox operation must fail.
        for action in ('record.put','record.delete','record.grant','record.restore'):
            result=self.backend.batch(self.peer,wid,[{'id':uid(),'action':action,'record_id':own,'revision':byid[own]['revision'],'kind':'account','visibility':'shared','audience':[],'data':{'name':'Restore forbidden','currency':'USD','opening_minor':99999}}])['results'][0]
            self.assertEqual(result['status'],'rejected',result)
        self.erase(self.peer)
        with self.backend.connect() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM accounts WHERE id=?',(own,)).fetchone())
            self.assertIsNone(db.execute('SELECT 1 FROM erased_financial_stubs WHERE record_id=?',(own,)).fetchone())

    def test_external_ledger_prevents_restored_snapshot_resurrection_and_is_monotonic_private(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        path=Path(folder.name)/'erasures.jsonl';path.touch(mode=0o600)
        wid=uid();self.backend.family(self.owner,{'id':uid(),'action':'workspace.create','workspace_id':wid,'kind':'personal','name':'Private workspace'})
        rid=self.put(self.owner,wid,'note',{'body':'Restored snapshot payload'},'private')
        # A restored DB intentionally has no deletion job or in-DB erasure row.
        append_ledger(path,self.owner['id'],self.now)
        initialize(self.backend,str(path))
        with self.backend.connect() as db:
            self.assertIsNone(db.execute('SELECT body FROM notes WHERE id=?',(rid,)).fetchone())
            row=db.execute('SELECT * FROM users WHERE id=?',(self.owner['id'],)).fetchone()
            self.assertEqual(row['created_at'],0);self.assertEqual(row['verified'],0);self.assertNotIn('owner@example',row['email'])
        self.assertEqual(apply_ledger(self.backend,read_ledger(path)),0)
        append_ledger(path,self.owner['id'],self.now-1)
        self.assertEqual(read_ledger(path)[self.owner['id']],self.now)
        self.assertNotIn(self.owner['email'],path.read_text());self.assertNotIn(token_hash(self.owner['email']),path.read_text())
        with self.assertRaises(FileNotFoundError):initialize(self.backend,str(path)+'missing')
        link=path.with_name('symlink');link.symlink_to(path)
        with self.assertRaises(OSError):read_ledger(link)
        path.chmod(0o644)
        with self.assertRaises(RuntimeError):read_ledger(path)

    def test_deletion_erases_session_provider_support_admission_recovery_and_email_capabilities(self):
        from backend.control import Control
        from backend.support import Support
        ticket=Support(self.backend,Control(self.backend)).create(self.owner,'privacy','Personal subject','Personal body')['ticket_id']
        with self.backend.transaction() as db:
            db.execute('INSERT INTO provider_purchases VALUES(?,?,?,?,?,?,?,?,?,?)',('google_play','reference',self.owner['id'],'product','Plus','active',self.now+10000,1,None,self.now))
            db.execute('INSERT INTO provider_events VALUES(?,?,?,?,?,?)',('google_play','event','digest','reference',self.now,'{}'))
            db.execute('INSERT INTO entitlement_grants VALUES(?,?,?,?,?,?,0,?,?)',(uid(),self.owner['id'],'Plus','manual',self.now,None,'Free private rationale',self.peer['id']))
            db.execute('INSERT INTO service_holds VALUES(?,?,?,?,?)',(self.owner['id'],'premium',self.now+100,'Private rationale',self.peer['id']))
            db.execute('INSERT INTO owner_setup VALUES(?,?,?,0)',('setup',self.owner['email'],self.now+100))
            db.execute("INSERT INTO early_access(id,email,state,created_at,updated_at,consent_version) VALUES(?,?,'approved',?,?,'fixture')",(uid(),self.owner['email'],self.now,self.now))
            for key in (token_hash(self.owner['email']),'recovery:'+token_hash(self.owner['email'])):db.execute('INSERT INTO auth_limits VALUES(?,1,?)',(key,self.now-1))
            db.execute('INSERT INTO email_changes VALUES(?,?,?,?)',(token_hash('not-a-real-code'),self.owner['id'],'new@example.test',self.now+100))
            self.backend._deliver(db,'new@example.test','not-a-real-code','email_change')
        self.backend.recover(self.owner['email'])
        self.erase(self.owner)
        with self.backend.connect() as db:
            for table in ('devices','refresh_tokens','web_sessions','sessions','google_identities','account_credentials','account_reauth_grants','oauth_challenges','account_mfa','account_recovery','login_challenges','budget_inbox_sources','budget_inbox_notifications','inbox_settings','inbox_notifications','announcement_states','announcement_recipients','web_push_subscriptions','verification','password_recovery','email_changes','operations','entitlement_grants','entitlement_overrides','service_holds','record_recovery_requests','provider_purchases','support_tickets'):
                self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM '+table+' WHERE user_id=?',(self.owner['id'],)).fetchone()['n'],0,table)
            self.assertIsNone(db.execute('SELECT 1 FROM provider_events WHERE reference_hash=?',('reference',)).fetchone())
            self.assertIsNone(db.execute('SELECT 1 FROM owner_setup WHERE email=?',(self.owner['email'],)).fetchone())
            self.assertIsNone(db.execute('SELECT 1 FROM early_access WHERE email=?',(self.owner['email'],)).fetchone())
            self.assertIsNone(db.execute('SELECT 1 FROM support_messages WHERE ticket_id=?',(ticket,)).fetchone())
            if hasattr(self.backend,'pool'):
                self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM email_jobs WHERE user_id=? AND octet_length(payload)>0',(self.owner['id'],)).fetchone()['n'],0)
        # Provider retries, email recovery, refresh and cached actors cannot revive it.
        from backend.entitlements import ProviderAdapter,VerifiedPurchase,reconcile
        class Adapter(ProviderAdapter):
            source='google_play'
            def verify(inner,notification):return VerifiedPurchase('google_play','again','again',self.owner['id'],'product','Plus','active',self.now+100,2)
        with self.assertRaises(Failure):reconcile(self.backend,Adapter(),{})
        with self.assertRaises(Failure):self.lifecycle.request_deletion(self.owner,PASSWORD,'DELETE')
        with self.assertRaises(Failure):self.backend.refresh_session(self.owner_session['refresh_token'])

    def test_leased_push_is_rechecked_and_never_sent_after_committed_erasure(self):
        from backend.web_push import WebPush,b64
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        receiver=ec.generate_private_key(ec.SECP256R1())
        subscription={'endpoint':'https://fcm.googleapis.com/fcm/send/privacy-synthetic','keys':{'p256dh':b64(receiver.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)),'auth':b64(os.urandom(16))}}
        actor=dict(self.owner,device_id=self.owner_session['device_id'])
        with self.backend.transaction() as db:
            db.execute('INSERT INTO web_sessions VALUES(?,?,?,?,?,?,?)',(token_hash('b'*43),actor['id'],actor['device_id'],self.now,self.now,self.now+900000,token_hash('fixture')))
        sent=[]
        push=WebPush(self.backend,self.settings.site_origin,transport=lambda *args:sent.append(True) or 201)
        push.subscribe(actor,{'subscription':subscription,'timezone':'UTC'})
        self.lifecycle.request_deletion(self.owner,PASSWORD,'DELETE');self.now+=86401
        push.test(actor);push.next_scan=self.now+100
        original=self.backend.delivery_transaction
        @contextlib.contextmanager
        def erase_after_lease(account_id):
            self.assertTrue(self.lifecycle.process_one_deletion())
            with original(account_id) as db:yield db
        with patch.object(self.backend,'delivery_transaction',erase_after_lease):self.assertTrue(push.tick())
        self.assertEqual(sent,[])
        with self.backend.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM web_push_deliveries').fetchone()['n'],0)

    def test_immutable_audit_minimizes_pii_while_encrypted_notes_erase_and_expire(self):
        from backend.control import Control, StaffPrincipal
        from backend.account_erasure import prune_ephemeral
        control=Control(self.backend);staff=StaffPrincipal(uid(),self.peer['id'],('owner',))
        secret='opaque-secret-material-with-43-characters-xx'
        detail='Sensitive health rationale '+self.owner['email']+' phone +1 234 567 8901 token='+secret
        with self.backend.transaction() as db:
            control.audit(db,staff,self.owner['id'],'user.moderate.account',{'email':self.owner['email'],'reason':'Never chain this detail'}, {'enabled':True},detail)
            control.audit(db,staff,self.peer['id'],'user.recovery.request',{}, {},'Other private note')
        with self.backend.connect() as db:
            row=db.execute('SELECT * FROM control_audit WHERE subject_id=?',(self.owner['id'],)).fetchone();immutable=dict(row)
            self.assertEqual(row['reason'],'event.user.moderate.account')
            self.assertNotIn(self.owner['email'],json.dumps(immutable));self.assertNotIn('Sensitive health',json.dumps(immutable));self.assertNotIn(secret,json.dumps(immutable))
            note=db.execute('SELECT note FROM control_audit_notes WHERE subject_id=?',(self.owner['id'],)).fetchone()
            raw=bytes(note['note']);self.assertNotIn(b'Sensitive health',raw)
            opened=self.backend.cipher.decrypt(raw).decode();self.assertIn('Sensitive health',opened);self.assertNotIn(self.owner['email'],opened);self.assertNotIn(secret,opened)
        self.erase(self.owner)
        with self.backend.connect() as db:
            self.assertEqual(dict(db.execute('SELECT * FROM control_audit WHERE id=?',(immutable['id'],)).fetchone()),immutable)
            self.assertIsNone(db.execute('SELECT 1 FROM control_audit_notes WHERE subject_id=?',(self.owner['id'],)).fetchone())
            self.assertIsNotNone(db.execute('SELECT 1 FROM control_audit_notes WHERE subject_id=?',(self.peer['id'],)).fetchone())
        self.now+=90*86400;prune_ephemeral(self.backend)
        with self.backend.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM control_audit_notes').fetchone()['n'],0)

    def test_actual_web_google_reauth_roundtrip_keeps_customer_session_and_checks_csrf(self):
        from backend.production import Application
        from urllib.parse import parse_qs,urlencode
        actor,session=self.google_user()
        app=Application(self.backend,self.settings);app.google.verifier=self.provider
        value,headers=app.web.customer_session(session,'privacy-browser',[])
        account=next(v.split(';')[0] for k,v in headers if k=='Set-Cookie')
        csrf=value['csrf']
        def request(path,body=None,cookie=account,csrf_value=csrf,query=''):
            payload=json.dumps(body).encode() if body is not None else b''
            env={'HTTP_HOST':'getuladim.space','PATH_INFO':path,'REQUEST_METHOD':'POST' if body is not None else 'GET','QUERY_STRING':query,'REMOTE_ADDR':'172.30.30.2','HTTP_X_FORWARDED_PROTO':'https','HTTP_USER_AGENT':'privacy-browser','HTTP_ORIGIN':self.settings.site_origin,'HTTP_COOKIE':cookie,'HTTP_X_CSRF_TOKEN':csrf_value,'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(payload)),'wsgi.input':io.BytesIO(payload)}
            captured=[]
            with patch.object(app,'limit'):
                raw=b''.join(app(env,lambda status,h:captured.append((int(status[:3]),h))))
            status,h=captured[0]
            return status,h,json.loads(raw) if raw else None
        status,_,metadata=request('/account/api/deletion')
        self.assertEqual(status,200);self.assertFalse(metadata['has_password']);self.assertTrue(metadata['google_reauth_available'])
        self.assertEqual(request('/account/api/google/reauth/start',{},csrf_value='')[0],403)
        status,h,start=request('/account/api/google/reauth/start',{})
        self.assertEqual(status,200,start)
        binding=next(v.split(';')[0] for k,v in h if k=='Set-Cookie')
        params=parse_qs(urlsplit(start['authorization_url']).query)
        self.assertEqual(params['max_age'],['0']);self.assertEqual(params['scope'],['openid email'])
        token=self.provider.sign(params['nonce'][0])
        query=urlencode({'state':params['state'][0],'code':token})
        status,h,_=request('/account/api/google/callback',cookie=account+'; '+binding,query=query)
        self.assertEqual(status,303)
        self.assertEqual(dict(h)['Location'],'/app?google=return')
        result_cookie=next(v.split(';')[0] for k,v in h if k=='Set-Cookie')
        status,h,proof=request('/account/api/google/complete',{},cookie=account+'; '+binding+'; '+result_cookie)
        self.assertEqual(status,200,proof);self.assertEqual(set(proof),{'reauth_token','expires_in'})
        self.assertFalse(any(v.startswith('__Host-uladim_account=') for k,v in h if k=='Set-Cookie'))
        status,_,identity=request('/account/api/session')
        self.assertEqual(status,200);self.assertEqual(identity['user_id'],actor['id'])
        status,_,requested=request('/account/api/deletion',{'reauth_token':proof['reauth_token'],'confirmation':'DELETE'})
        self.assertEqual(status,200,requested);self.assertEqual(requested['state'],'pending')
        self.assertEqual(request('/account/api/cancel-deletion',{'reauth_token':proof['reauth_token']})[0],401)

    def test_tombstone_email_cannot_be_reserved_to_block_another_users_erasure(self):
        reserved='deleted-'+self.owner['id']+'@invalid.example'
        attacker,_=self.user(reserved)
        self.erase(self.owner)
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT email FROM users WHERE id=?',(attacker['id'],)).fetchone()['email'],reserved)
            marker=db.execute('SELECT email FROM users WHERE id=?',(self.owner['id'],)).fetchone()['email']
            self.assertEqual(marker,'deleted:'+self.owner['id'])
        with self.assertRaises(Failure):self.backend.register(marker,PASSWORD)

    def test_independent_ack_failure_freezes_without_erasing_then_retries_without_global_lock(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        path=Path(folder.name)/'ledger';path.touch(mode=0o600)
        wid=uid();self.backend.family(self.owner,{'id':uid(),'action':'workspace.create','workspace_id':wid,'kind':'personal','name':'Private'})
        rid=self.put(self.owner,wid,'note',{'body':'Do not erase before independent acknowledgment'},'private')
        acknowledgments=[]
        def handler(request):
            if request['action']=='synchronize':return {'acknowledged':True,'ledger_bytes':path.stat().st_size}
            self.assertEqual(request['user_id'],self.owner['id']);self.assertIn(self.owner['id'],read_ledger(path))
            # This unrelated mutation executes while the actual Unix ACK waits.
            if not acknowledgments:self.assertEqual(self.lifecycle.request_deletion(self.peer,PASSWORD,'DELETE')['state'],'pending')
            acknowledgments.append(request)
            return {'acknowledged':len(acknowledgments)>1,'user_id':request['user_id'],'erased_at':request['erased_at']}
        server=SyntheticLedgerSocket(Path(folder.name)/'sync.sock',handler);self.addCleanup(server.close)
        initialize(self.backend,str(path),server.path)
        self.lifecycle.request_deletion(self.owner,PASSWORD,'DELETE');self.now+=86401
        self.assertTrue(self.lifecycle.process_one_deletion())
        with self.backend.connect() as db:
            self.assertIsNotNone(db.execute('SELECT body FROM notes WHERE id=?',(rid,)).fetchone())
            self.assertEqual(db.execute('SELECT state FROM deletion_jobs WHERE user_id=?',(self.owner['id'],)).fetchone()['state'],'erasing')
        with self.assertRaises(Failure):self.backend.authenticate(self.owner_session['token'])
        with self.assertRaises(Failure):self.backend.family(self.owner,{'id':uid(),'action':'workspace.create','workspace_id':uid(),'kind':'family','name':'Cannot race deletion'})
        self.assertTrue(self.lifecycle.process_one_deletion())
        with self.backend.connect() as db:
            self.assertIsNone(db.execute('SELECT body FROM notes WHERE id=?',(rid,)).fetchone())
            self.assertEqual(db.execute('SELECT state FROM deletion_jobs WHERE user_id=?',(self.owner['id'],)).fetchone()['state'],'completed')
        self.assertEqual(server.errors,[])
        self.assertEqual([r['action'] for r in server.requests],['synchronize','acknowledge','acknowledge'])
        with self.assertRaises(OSError):initialize(self.backend,str(path),str(Path(folder.name)/'missing.sock'))

    def test_startup_synchronizes_independent_truth_before_applying_restore(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        path=Path(folder.name)/'ledger';path.touch(mode=0o600)
        def handler(request):
            self.assertEqual(request,{'action':'synchronize'})
            append_ledger(path,self.owner['id'],self.now)
            return {'acknowledged':True,'ledger_bytes':path.stat().st_size}
        server=SyntheticLedgerSocket(Path(folder.name)/'sync.sock',handler);self.addCleanup(server.close)
        initialize(self.backend,str(path),server.path)
        with self.assertRaises(Failure):self.backend.authenticate(self.owner_session['token'])
        with self.backend.connect() as db:self.assertEqual(db.execute('SELECT deleted_at FROM account_state WHERE user_id=?',(self.owner['id'],)).fetchone()['deleted_at'],self.now)
        self.assertEqual(server.errors,[])

    def test_unverified_email_change_target_does_not_erase_another_users_metadata(self):
        target='independent@example.test';change_code='synthetic-own-change-code'
        with self.backend.transaction() as db:
            db.execute('INSERT INTO email_changes VALUES(?,?,?,?)',(token_hash(change_code),self.owner['id'],target,self.now+900))
            self.backend._deliver(db,target,change_code,'email_change')
        independent,_=self.user(target)
        with self.backend.transaction() as db:
            db.execute('INSERT INTO owner_setup VALUES(?,?,?,0)',('independent-setup',target,self.now+500))
            db.execute("INSERT INTO early_access(id,email,state,created_at,updated_at,consent_version) VALUES(?,?,'approved',?,?,'fixture')",(uid(),target,self.now,self.now))
        self.erase(self.owner)
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT email FROM users WHERE id=?',(independent['id'],)).fetchone()['email'],target)
            self.assertIsNotNone(db.execute('SELECT 1 FROM owner_setup WHERE email=?',(target,)).fetchone())
            self.assertIsNotNone(db.execute('SELECT 1 FROM early_access WHERE email=?',(target,)).fetchone())
            if hasattr(self.backend,'pool'):
                self.assertGreater(db.execute('SELECT COUNT(*) AS n FROM email_jobs WHERE user_id=?',(independent['id'],)).fetchone()['n'],0)
                payloads=[json.loads(self.backend.cipher.decrypt(bytes(r['payload']))) for r in db.execute('SELECT payload FROM email_jobs WHERE octet_length(payload)>0')]
                self.assertFalse(any(p.get('code')==change_code for p in payloads))

    def test_erasing_member_with_no_owned_records_still_invalidates_family_epoch(self):
        wid=self.family();before=self.backend.pull_incremental(self.peer,wid,0)
        self.erase(self.owner)
        after=self.backend.pull_incremental(self.peer,wid,before['cursor'],before['epoch'])
        self.assertTrue(after['reset']);self.assertGreater(after['cursor'],before['cursor'])
        self.assertEqual(after['records'],[])

    def test_startup_ignores_later_unacknowledged_suffix_and_rejects_bad_prefix(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        path=Path(folder.name)/'ledger';path.touch(mode=0o600)
        append_ledger(path,self.owner['id'],self.now)
        confirmed=path.stat().st_size
        def handler(request):
            # Simulate another worker appending after the root service's durable
            # snapshot but before initialize reads the shared inode.
            append_ledger(path,self.peer['id'],self.now)
            return {'acknowledged':True,'ledger_bytes':confirmed}
        server=SyntheticLedgerSocket(Path(folder.name)/'sync.sock',handler);self.addCleanup(server.close)
        initialize(self.backend,str(path),server.path)
        with self.assertRaises(Failure):self.backend.authenticate(self.owner_session['token'])
        self.assertEqual(self.backend.authenticate(self.peer_session['token'])['id'],self.peer['id'])
        self.assertEqual(read_ledger(path,confirmed),{self.owner['id']:self.now})
        for bad in (True,-1,confirmed-1,path.stat().st_size+1):
            with self.assertRaises(RuntimeError):read_ledger(path,bad)
        self.assertEqual(server.errors,[])

    def test_cancellation_is_only_available_before_due_time(self):
        self.lifecycle.request_deletion(self.owner,PASSWORD,'DELETE');self.now+=86400
        self.assertFalse(self.lifecycle.deletion_status(self.owner)['cancel_available'])
        with self.assertRaises(Failure) as error:self.lifecycle.cancel_deletion(self.owner,PASSWORD)
        self.assertEqual(error.exception.code,'deletion_started')


class AccountPrivacySQLiteTests(PrivacyScenarios,unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.backend=Backend(Path(folder.name)/'privacy.db',deliver=lambda e,c:None)
        self.backend.cipher=Fernet(Fernet.generate_key())
        self.fixtures()


DSN=os.environ.get('LIFEOS_TEST_DATABASE_URL','')
@unittest.skipUnless(DSN,'Requires isolated lifeos_test database')
class AccountPrivacyPostgresTests(PrivacyScenarios,unittest.TestCase):
    def setUp(self):
        if urlsplit(DSN).path!='/lifeos_test':raise RuntimeError('Refusing non-test database')
        import psycopg
        from psycopg import sql
        from backend.postgres import PostgresBackend
        self.schema='privacy_test_'+uuid.uuid4().hex
        with psycopg.connect(DSN,autocommit=True) as db:db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        def drop():
            with psycopg.connect(DSN,autocommit=True) as db:db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
        self.addCleanup(drop)
        self.backend=PostgresBackend(DSN,Fernet(Fernet.generate_key()),schema=self.schema,migrate=True)
        self.addCleanup(self.backend.close)
        self.fixtures()

    def test_leased_mail_is_rechecked_and_other_users_mail_remains_deliverable(self):
        from backend.mail import deliver_one
        self.lifecycle.request_deletion(self.owner,PASSWORD,'DELETE');self.now+=86401
        with self.backend.transaction() as db:
            db.execute('DELETE FROM email_jobs')
            self.backend._deliver(db,self.owner['email'],'synthetic-secret','recovery')
        original=self.backend.delivery_transaction
        sent=[]
        @contextlib.contextmanager
        def erase_after_lease(account_id):
            self.assertTrue(self.lifecycle.process_one_deletion())
            with original(account_id) as db:yield db
        with patch.object(self.backend,'delivery_transaction',erase_after_lease):self.assertTrue(deliver_one(self.backend,self.settings,send=lambda *args:sent.append(True)))
        self.assertEqual(sent,[])
        with self.backend.transaction() as db:self.backend._deliver(db,self.peer['email'],'synthetic-peer-code','recovery')
        self.assertTrue(deliver_one(self.backend,self.settings,send=lambda *args:sent.append(True)))
        self.assertEqual(sent,[True])

    def test_delivery_subject_lock_does_not_hold_global_mutation_lock(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.backend.delivery_transaction(self.owner['id']):
                pending=pool.submit(self.lifecycle.request_deletion,self.peer,PASSWORD,'DELETE')
                self.assertEqual(pending.result(timeout=4)['state'],'pending')

    def test_due_erasure_busy_with_same_subject_delivery_retries_without_attention(self):
        self.lifecycle.request_deletion(self.owner,PASSWORD,'DELETE');self.now+=86401
        with self.backend.delivery_transaction(self.owner['id']):
            self.assertFalse(self.lifecycle.process_one_deletion())
            self.assertEqual(self.lifecycle.deletion_status(self.owner)['request']['state'],'pending')
        self.assertTrue(self.lifecycle.process_one_deletion())
        self.assertEqual(self.lifecycle.deletion_status(self.owner)['request']['state'],'completed')

    def test_migration_019_is_additive_repeatable_and_old_mail_rows_remain_erasable(self):
        with self.backend.transaction() as db:
            for table in ('control_audit_notes','erased_financial_stubs','account_reauth_grants','account_erasure_ledger'):
                db.execute('DROP TABLE '+table)
            db.execute('ALTER TABLE email_jobs DROP COLUMN user_id')
            db.execute("DELETE FROM schema_migrations WHERE version='019_account_privacy.sql'")
        self.backend.migrate();self.backend.migrate()
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT email FROM users WHERE id=?',(self.owner['id'],)).fetchone()['email'],self.owner['email'])
            self.assertEqual(db.execute("SELECT COUNT(*) AS n FROM schema_migrations WHERE version='019_account_privacy.sql'").fetchone()['n'],1)
            self.assertGreater(db.execute('SELECT COUNT(*) AS n FROM email_jobs WHERE user_id IS NULL').fetchone()['n'],0)
        self.erase(self.owner)
        with self.backend.connect() as db:
            payloads=[json.loads(self.backend.cipher.decrypt(bytes(r['payload']))) for r in db.execute('SELECT payload FROM email_jobs WHERE octet_length(payload)>0')]
            self.assertFalse(any(p['email']==self.owner['email'] for p in payloads))
