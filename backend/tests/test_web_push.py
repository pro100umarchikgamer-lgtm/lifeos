"""Focused delivery/security tests; no external provider or real user is contacted."""
import datetime as dt
import json
import os
import struct
import tempfile
import unittest
import uuid
from unittest.mock import patch
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
import jwt
from backend.service import Backend, Failure, token_hash
from backend.web_push import WebPush, b64, unb64, occurrences, validate_subscription, send_request, NoRedirect


def uid(): return str(uuid.uuid4())


class PushScenarios:
    def fixtures(self):
        self.now = int(dt.datetime(2026, 11, 13, 10, tzinfo=dt.timezone.utc).timestamp())
        self.backend.clock = lambda: self.now
        self.user, self.device, self.workspace = uid(), uid(), uid()
        self.actor = {'id':self.user, 'device_id':self.device, 'verified':1, 'email':'push@example.test'}
        with self.backend.transaction() as db:
            db.execute('INSERT INTO users VALUES(?,?,?,?,1,?)', (self.user,self.actor['email'],'unused','unused',self.now))
            db.execute('INSERT INTO devices VALUES(?,?,?,?,?,?,0)', (self.device,self.user,uid(),'Browser',self.now,self.now))
            db.execute('INSERT INTO web_sessions VALUES(?,?,?,?,?,?,?)', (token_hash('x'*43),self.user,self.device,self.now,self.now,self.now+86400,token_hash('fixture')))
            db.execute("INSERT INTO workspaces(id,name,creator_id,kind) VALUES(?,?,?,'personal')", (self.workspace,'Personal',self.user))
            db.execute("INSERT INTO memberships(workspace_id,user_id,role) VALUES(?,?,'owner')", (self.workspace,self.user))
        self.receiver = ec.generate_private_key(ec.SECP256R1())
        self.auth = os.urandom(16)
        self.subscription = {'endpoint':'https://fcm.googleapis.com/fcm/send/synthetic-only', 'keys':{'p256dh':b64(self.receiver.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)), 'auth':b64(self.auth)}}
        self.sent = []
        self.push = WebPush(self.backend, 'https://getuladim.space', transport=lambda endpoint, body, headers:self.sent.append((endpoint,body,headers)) or 201)

    def subscribe(self):
        return self.push.subscribe(self.actor, {'subscription':self.subscription,'lead_minutes':15,'priority':'high','timezone':'Europe/Moscow'})

    def event(self, local_start, **options):
        rid=uid()
        schedule={'localStart':local_start,'timezone':'UTC','allDay':False,'repeat':'none','interval':1,'until':None,**options}
        op={'id':uid(),'action':'record.put','record_id':rid,'revision':0,'kind':'event','visibility':'private','audience':[],'data':{'title':'Never in push payload','schedule':schedule}}
        self.assertEqual(self.backend.batch(self.actor,self.workspace,[op])['results'][0]['status'],'accepted')
        return rid

    def test_keys_encrypted_stable_device_ownership_and_logout_suppression(self):
        public=self.push.prepare(self.actor)['application_server_key']
        self.assertEqual(public,self.push.prepare(self.actor)['application_server_key'])
        state=self.subscribe(); self.assertTrue(state['enabled'])
        with self.backend.connect() as db:
            row=db.execute('SELECT * FROM web_push_subscriptions').fetchone()
            self.assertNotIn(b'fcm.googleapis.com',bytes(row['secret']))
            key=db.execute('SELECT * FROM web_push_keys').fetchone()
            self.assertNotIn(b'PRIVATE KEY',bytes(key['secret']))
        other={**self.actor,'id':uid()}
        with self.assertRaises(Failure): self.push.subscribe(other, {'subscription':self.subscription,'timezone':'UTC'})
        self.push.test(self.actor)
        with self.backend.transaction() as db: self.backend._revoke_device(db,self.user,self.device)
        self.push.tick()
        self.assertEqual(self.sent,[])
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM web_push_deliveries').fetchone()['state'],'cancelled')

    def test_real_encryption_provider_ack_and_token_bound_display_receipt(self):
        self.subscribe(); queued=self.push.test(self.actor)
        with self.assertRaises(Failure): self.push.test(self.actor)
        self.push.tick()
        self.assertEqual(len(self.sent),1)
        endpoint,body,headers=self.sent[0]
        self.assertEqual(headers['Urgency'],'high'); self.assertEqual(headers['Content-Encoding'],'aes128gcm')
        salt,rs,key_len=body[:16],struct.unpack('!I',body[16:20])[0],body[20]
        self.assertEqual(rs,4096);self.assertEqual(key_len,65)
        sender=body[21:86];shared=self.receiver.exchange(ec.ECDH(),ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(),sender))
        ua=self.receiver.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
        ikm=HKDF(algorithm=hashes.SHA256(),length=32,salt=self.auth,info=b'WebPush: info\0'+ua+sender).derive(shared)
        cek=HKDF(algorithm=hashes.SHA256(),length=16,salt=salt,info=b'Content-Encoding: aes128gcm\0').derive(ikm)
        nonce=HKDF(algorithm=hashes.SHA256(),length=12,salt=salt,info=b'Content-Encoding: nonce\0').derive(ikm)
        plain=AESGCM(cek).decrypt(nonce,body[86:],None)
        self.assertEqual(plain[-1:],b'\x02');payload=json.loads(plain[:-1])
        self.assertEqual(payload['recipient_user_id'],self.user)
        self.assertNotIn('Never in push payload',plain.decode())
        auth=headers['Authorization']; bearer,public=auth.removeprefix('vapid t=').split(',k=')
        claims=jwt.decode(bearer,ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(),unb64(public)),algorithms=['ES256'],audience='https://fcm.googleapis.com',options={'verify_exp':False})
        self.assertLessEqual(claims['exp'],self.now+86400)
        self.assertEqual(self.push.status(self.actor)['last_delivery']['state'],'accepted')
        with self.assertRaises(Failure):self.push.receipt({'delivery_id':queued['delivery_id'],'receipt_token':'x'*43,'state':'displayed'})
        self.push.receipt({'delivery_id':queued['delivery_id'],'receipt_token':payload['receipt_token'],'state':'displayed'})
        self.assertEqual(self.push.status(self.actor)['last_delivery']['state'],'displayed')

    def test_scheduler_only_authorized_events_dedupes_and_rechecks_revision(self):
        self.subscribe()
        # Large non-calendar histories must not consume the scheduler's page.
        with self.backend.transaction() as db:
            for number in range(1005):
                rid=uid();db.execute("INSERT INTO records VALUES(?,?,?,'transaction','private','[]',1,0,?)",(rid,self.workspace,self.user,number))
                db.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?)',(rid,'expense',100,'RUB','2026-11-13','irrelevant',None,None))
        rid=self.event('2026-11-13T10:15:00')
        self.push.scan(); self.push.scan()
        with self.backend.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM web_push_deliveries').fetchone()[0],1)
        with self.backend.transaction() as db:db.execute('UPDATE records SET deleted=1,revision=2 WHERE id=?',(rid,))
        self.push.tick();self.assertEqual(self.sent,[])
        self.assertEqual(self.push.status(self.actor)['last_delivery']['state'],'cancelled')

    def test_provider_expiry_and_retry_are_bounded(self):
        self.subscribe();self.push.test(self.actor)
        self.push.transport=lambda *args:503
        self.push.tick();self.push.tick()
        with self.backend.connect() as db:
            row=db.execute('SELECT * FROM web_push_deliveries').fetchone()
            self.assertEqual(row['attempts'],1);self.assertGreater(row['next_attempt'],self.now)
        self.now+=61;self.push.transport=lambda *args:410;self.push.tick()
        self.assertFalse(self.push.status(self.actor)['enabled'])
        self.assertEqual(self.push.status(self.actor)['last_delivery']['error_code'],'subscription_gone')

    def test_calendar_reminder_runs_at_lead_time_with_generic_content_and_link(self):
        self.subscribe();self.event('2026-11-13T10:16:00')
        self.push.tick();self.assertEqual(self.sent,[])
        self.now+=60
        self.push.scan()
        with self.backend.connect() as db:
            job=db.execute('SELECT * FROM web_push_deliveries').fetchone()
            payload=json.loads(self.backend.cipher.decrypt(bytes(job['payload'])))
        self.assertEqual(payload['body'],'Напоминание о событии календаря')
        self.assertEqual(payload['url'],'/app?notification=calendar&workspace='+self.workspace+'&day=2026-11-13')
        self.assertEqual(payload['subscription_id'],self.push.status(self.actor)['subscription_id'])
        self.push.tick();self.push.tick()
        self.assertEqual(len(self.sent),1)
        self.assertEqual(self.push.status(self.actor)['last_delivery']['state'],'accepted')

    def test_revision_edit_requeues_unsent_occurrence_but_does_not_replay_accepted(self):
        self.subscribe();rid=self.event('2026-11-13T10:15:00')
        self.push.scan()
        # A revision changes between scan and send, then cancellation is retried
        # under the current authorized event revision on the next scan.
        self.push.next_scan=self.now+15
        with self.backend.transaction() as db:db.execute('UPDATE records SET revision=revision+1 WHERE id=?',(rid,))
        self.push.tick();self.assertEqual(self.sent,[])
        self.now+=15;self.push.tick()
        self.assertEqual(len(self.sent),1)
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM web_push_deliveries').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT event_revision FROM web_push_deliveries').fetchone()[0],2)
        with self.backend.transaction() as db:db.execute('UPDATE records SET revision=revision+1 WHERE id=?',(rid,))
        self.now+=15;self.push.tick();self.assertEqual(len(self.sent),1)

    def test_startup_refresh_preserves_queue_and_changed_lead_reschedules(self):
        self.subscribe();self.event('2026-11-13T10:15:00');self.push.scan()
        self.now+=1;self.subscribe()
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM web_push_deliveries').fetchone()[0],'queued')
        self.push.subscribe(self.actor,{'subscription':self.subscription,'lead_minutes':5,'priority':'high','timezone':'Europe/Moscow'})
        self.push.tick();self.assertEqual(self.sent,[])
        self.now+=599;self.push.tick()
        self.assertEqual(len(self.sent),1)
        self.assertEqual(self.push.status(self.actor)['last_delivery']['state'],'accepted')

    def test_durable_scan_checkpoint_catches_late_calendar_page_and_worker_restart(self):
        self.subscribe()
        future={'localStart':'2026-12-13T10:00:00','timezone':'UTC','allDay':False,'repeat':'none','interval':1,'until':None}
        with self.backend.transaction() as db:
            for number in range(1,502):
                rid=str(uuid.UUID(int=number))
                db.execute("INSERT INTO records VALUES(?,?,?,'event','private','[]',1,0,?)",(rid,self.workspace,self.user,number))
                db.execute('INSERT INTO events VALUES(?,?,?)',(rid,'Future',json.dumps(future)))
            rid='ffffffff-ffff-4fff-bfff-ffffffffffff'
            db.execute("INSERT INTO records VALUES(?,?,?,'event','private','[]',1,0,502)",(rid,self.workspace,self.user))
            due={**future,'localStart':'2026-11-13T10:16:00'}
            db.execute('INSERT INTO events VALUES(?,?,?)',(rid,'Due on late page',json.dumps(due)))
        self.assertTrue(self.push.scan())
        self.now+=600
        # Reconstruct the worker to prove its completed checkpoint, not merely
        # an in-memory timestamp, protects due times older than five minutes.
        self.push=WebPush(self.backend,'https://getuladim.space',transport=lambda endpoint,body,headers:self.sent.append((endpoint,body,headers)) or 201)
        self.push.tick();self.assertEqual(self.sent,[])
        self.push.tick();self.assertEqual(len(self.sent),1)
        self.assertEqual(self.push.status(self.actor)['last_delivery']['state'],'accepted')

    def test_grant_revocation_and_account_disable_cancel_already_queued_push(self):
        self.subscribe()
        rid=self.event('2026-11-13T10:15:00')
        other=uid()
        with self.backend.transaction() as db:
            db.execute('INSERT INTO users VALUES(?,?,?,?,1,?)',(other,'other@example.test','unused','unused',self.now))
            db.execute('UPDATE records SET owner_id=? WHERE id=?',(other,rid))
        self.push.scan()
        with self.backend.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM web_push_deliveries').fetchone()[0],0)
        with self.backend.transaction() as db:db.execute('INSERT INTO grants VALUES(?,?,0)',(rid,self.user))
        self.push.scan()
        with self.backend.transaction() as db:db.execute('DELETE FROM grants WHERE record_id=?',(rid,))
        self.push.tick();self.assertEqual(self.sent,[])
        self.assertEqual(self.push.status(self.actor)['last_delivery']['state'],'cancelled')
        self.push.test(self.actor)
        with self.backend.transaction() as db:db.execute('INSERT INTO account_state VALUES(?,?,0)',(self.user,self.now+600))
        self.push.tick();self.assertEqual(self.sent,[])

    def test_receipt_expires_and_disable_erases_endpoint_and_cancels_queue(self):
        self.subscribe();job=self.push.test(self.actor)
        with self.backend.connect() as db:
            raw=db.execute('SELECT payload FROM web_push_deliveries WHERE id=?',(job['delivery_id'],)).fetchone()['payload']
            payload=json.loads(self.backend.cipher.decrypt(bytes(raw)))
        self.now+=3601
        with self.assertRaises(Failure):self.push.receipt({'delivery_id':job['delivery_id'],'receipt_token':payload['receipt_token'],'state':'displayed'})
        self.push.unsubscribe(self.actor)
        with self.backend.connect() as db:
            self.assertEqual(bytes(db.execute('SELECT secret FROM web_push_subscriptions').fetchone()['secret']),b'')
            self.assertEqual(db.execute('SELECT state FROM web_push_deliveries').fetchone()['state'],'cancelled')

    def test_additive_migration_preserves_data_and_restarts_with_same_vapid_key(self):
        public=self.push.prepare(self.actor)['application_server_key']
        self.subscribe()
        with self.backend.connect() as db:
            before=db.execute('SELECT email FROM users WHERE id=?',(self.user,)).fetchone()['email']
            self.assertEqual(db.execute('SELECT COUNT(*) FROM workspaces').fetchone()[0],1)
        restarted=WebPush(self.backend)
        self.assertEqual(restarted.prepare(self.actor)['application_server_key'],public)
        self.assertTrue(restarted.status(self.actor)['enabled'])
        with self.backend.connect() as db:self.assertEqual(db.execute('SELECT email FROM users WHERE id=?',(self.user,)).fetchone()['email'],before)


class WebPushTests(PushScenarios,unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.backend=Backend(Path(folder.name)/'push.db');self.backend.cipher=Fernet(Fernet.generate_key())
        self.fixtures()

    def test_endpoint_validation(self):
        validate_subscription(self.subscription)
        for endpoint in ['http://fcm.googleapis.com/a','https://127.0.0.1/a','https://fcm.googleapis.com.evil.test/a','https://user@fcm.googleapis.com/a','https://fcm.googleapis.com:444/a','https://fcm.googleapis.com/a#fragment','https://fcm.googleapis.com:443/a','https://updates.push.services.mozilla.com.evil.test/a']:
            with self.subTest(endpoint=endpoint),self.assertRaises(Failure):validate_subscription({**self.subscription,'endpoint':endpoint})
        with patch('backend.web_push.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]),self.assertRaises(Failure):
            send_request(self.subscription['endpoint'],b'',{})
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'',{},'http://127.0.0.1/secret'))

    def test_routes_reuse_session_origin_csrf_and_receipt_has_bound_token(self):
        from backend.config import Settings
        from backend.web import Web, ACCOUNT_COOKIE
        settings=Settings.load({'DATABASE_URL':'postgresql://example/db','EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),'RATE_LIMIT_KEY':'x'*48,'SMTP_HOST':'127.0.0.1','SMTP_TLS':'none','EMAIL_FROM':'test@example.test'})
        web=Web(self.backend,settings)
        def request(action,body=None,**extra):
            env={'HTTP_HOST':'getuladim.space','REQUEST_METHOD':'POST' if body is not None else 'GET','PATH_INFO':'/account/api/'+action,'HTTP_ORIGIN':'https://getuladim.space','HTTP_USER_AGENT':'fixture','HTTP_COOKIE':ACCOUNT_COOKIE+'='+'x'*43,'HTTP_X_CSRF_TOKEN':web.csrf('x'*43),**extra}
            return web.request(env,body or {})[0]
        self.assertFalse(request('notifications')['enabled'])
        with self.assertRaises(Failure):request('notifications/prepare',{},HTTP_ORIGIN='https://evil.test')
        with self.assertRaises(Failure):request('notifications/prepare',{},HTTP_X_CSRF_TOKEN='')
        self.assertIn('application_server_key',request('notifications/prepare',{}))
        request('notifications/subscribe',{'subscription':self.subscription,'timezone':'Europe/Moscow'})
        job=request('notifications/test',{})
        with self.backend.connect() as db:
            raw=db.execute('SELECT payload FROM web_push_deliveries WHERE id=?',(job['delivery_id'],)).fetchone()['payload']
            payload=json.loads(self.backend.cipher.decrypt(bytes(raw)))
            db.execute("UPDATE web_push_deliveries SET state='sending' WHERE id=?",(job['delivery_id'],))
        receipt={'delivery_id':job['delivery_id'],'receipt_token':payload['receipt_token'],'state':'suppressed'}
        self.assertTrue(request('notifications/receipt',receipt,HTTP_COOKIE='',HTTP_X_CSRF_TOKEN='')['accepted'])
        with self.assertRaises(Failure):request('notifications/receipt',receipt,HTTP_COOKIE='',HTTP_ORIGIN='https://evil.test')

    def test_recurrences_month_end_dst_gap_overlap_and_all_day(self):
        def stamps(schedule,start,end,zone='Europe/Moscow'):
            return [dt.datetime.fromtimestamp(at,dt.timezone.utc).isoformat() for at,day in occurrences(schedule,zone,dt.datetime.fromisoformat(start).timestamp(),dt.datetime.fromisoformat(end).timestamp())]
        s={'localStart':'2026-01-31T10:00:00','timezone':'UTC','allDay':False,'repeat':'monthly','interval':1,'until':None}
        self.assertEqual(stamps(s,'2026-02-27T00:00:00+00:00','2026-03-01T00:00:00+00:00'),['2026-02-28T10:00:00+00:00'])
        s.update(localStart='2026-03-08T02:30:00',timezone='America/New_York',repeat='none')
        self.assertEqual(stamps(s,'2026-03-08T00:00:00+00:00','2026-03-09T00:00:00+00:00'),['2026-03-08T07:30:00+00:00'])
        s.update(localStart='2026-11-01T01:30:00')
        self.assertEqual(stamps(s,'2026-11-01T00:00:00+00:00','2026-11-02T00:00:00+00:00'),['2026-11-01T05:30:00+00:00'])
        s.update(localStart='2026-11-13T00:00:00',allDay=True)
        self.assertEqual(stamps(s,'2026-11-13T00:00:00+00:00','2026-11-14T00:00:00+00:00'),['2026-11-13T06:00:00+00:00'])
