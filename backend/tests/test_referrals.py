"""Referral ownership/privacy boundaries; no real provider, mail or analytics."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlsplit
import uuid

from cryptography.fernet import Fernet
from backend.account_erasure import erase_in
from backend.config import Settings
from backend.control import StaffPrincipal
from backend.entitlements import ProviderAdapter, VerifiedPurchase, reconcile
from backend.service import Backend, Failure
from backend.web import Web

PASSWORD = 'Referral-foundation-7-secure'


def uid(): return str(uuid.uuid4())


class StoreProvider(ProviderAdapter):
    source = 'google_play'
    product_tiers = {'synthetic.plus': 'Plus'}
    def verify(self, value): return value


class ReferralScenarios:
    def prepare(self):
        self.now = 1800000000
        self.backend.clock = lambda: self.now
        self.mail = {}
        self.backend._deliver = lambda db, email, code, purpose: self.mail.__setitem__(email, code)
        self.settings = Settings.load({'DATABASE_URL':'postgresql://unused/test',
            'EMAIL_QUEUE_KEY':Fernet.generate_key().decode(), 'RATE_LIMIT_KEY':'r'*48,
            'SMTP_HOST':'localhost','SMTP_TLS':'none','EMAIL_FROM':'fixture@example.test'})
        self.web = Web(self.backend, self.settings)
        self.cookies, self.csrf = {}, {}
        self.inviter = self.user('inviter@example.test')
        self.invitee = self.user('invitee@example.test')
        self.other = self.user('other@example.test')

    def user(self, email, verified=True):
        session = self.backend.register(email, PASSWORD)
        actor = self.backend.authenticate(session['token'])
        if verified: self.backend.verify(actor, self.mail[email])
        actor = self.backend.authenticate(session['token'])
        value, headers = self.web.customer_session(session, 'referral-fixture', [])
        self.cookies[actor['id']] = next(value.split(';')[0] for key,value in headers if key=='Set-Cookie')
        self.csrf[actor['id']] = value['csrf']
        return actor

    def call(self, actor, action='referrals', method='GET', body=None, query='', csrf=True, origin=None):
        env={'HTTP_HOST':'getuladim.space','PATH_INFO':'/account/api/'+action,
             'REQUEST_METHOD':method,'HTTP_USER_AGENT':'referral-fixture','QUERY_STRING':query,
             'HTTP_ORIGIN':self.settings.site_origin if origin is None else origin}
        if actor:
            env['HTTP_COOKIE']=self.cookies[actor['id']]
            if csrf:env['HTTP_X_CSRF_TOKEN']=self.csrf[actor['id']]
        try:return 200,self.web.request(env,body or {})[0]
        except Failure as error:return error.status,{'error':error.code}

    def staff(self, actor=None, query=None):
        if actor is None: actor=StaffPrincipal(uid(),self.inviter['id'],('owner',))
        try:return 200,self.web.staff_action(actor,'referrals','GET',{},query or {})
        except Failure as error:return error.status,{'error':error.code}

    def code(self, actor):
        status,value=self.call(actor,'referrals/code','POST')
        self.assertEqual(status,200,value)
        return value['invite']['code']

    def claim(self, actor, code):
        return self.call(actor,'referrals/claim','POST',{'code':code})

    def test_own_link_is_post_only_idempotent_and_response_has_no_private_statistics(self):
        status,empty=self.call(self.inviter)
        self.assertEqual(status,200,empty)
        self.assertEqual(empty,{'confirmed_count':0,'invite':None,'people':[],'next_offset':None})
        code=self.code(self.inviter)
        self.assertEqual(len(code),43)
        self.assertEqual(self.code(self.inviter),code)
        status,value=self.call(self.inviter)
        self.assertEqual(set(value),{'confirmed_count','invite','people','next_offset'})
        self.assertEqual(value['invite']['url'],'https://getuladim.space/app?ref='+code)
        self.assertEqual(set(value['invite']),{'code','url'})
        self.assertEqual(self.call(self.other)[1]['invite'],None)
        self.assertEqual(self.call(self.other,query='user_id='+self.inviter['id'])[0],400)

    def test_auth_origin_csrf_and_verified_current_actor_are_required(self):
        self.assertEqual(self.call(None)[0],401)
        self.assertEqual(self.call(self.inviter,'referrals/code','POST',csrf=False)[0],403)
        self.assertEqual(self.call(self.inviter,'referrals/code','POST',origin='https://other.test')[0],403)
        pending=self.user('pending@example.test',False)
        self.assertEqual(self.call(pending,'referrals/code','POST')[0],403)
        code=self.code(self.inviter)
        self.assertEqual(self.claim(pending,code)[0],403)
        self.assertEqual(self.call(self.invitee,'referrals/claim','POST',{'code':code,'user_id':self.other['id']})[0],400)
        self.assertEqual(self.claim(self.invitee,code),(200,{'status':'confirmed'}))
        self.assertEqual(self.call(self.inviter)[1]['confirmed_count'],1)
        self.assertEqual(self.call(self.other)[1]['confirmed_count'],0)

    def test_self_invalid_and_reattribution_are_rejected_but_same_claim_replays(self):
        first=self.code(self.inviter);second=self.code(self.other)
        self.assertEqual(self.claim(self.inviter,first)[0],400)
        self.assertEqual(self.claim(self.invitee,'x'*43)[0],400)
        self.assertEqual(self.claim(self.invitee,first),(200,{'status':'confirmed'}))
        self.assertEqual(self.claim(self.invitee,first),(200,{'status':'confirmed'}))
        self.assertEqual(self.claim(self.invitee,second)[0],409)
        self.assertEqual(self.call(self.inviter)[1]['confirmed_count'],1)
        self.assertEqual(self.call(self.other)[1]['confirmed_count'],0)

    def test_inviter_sees_only_opted_short_alias_or_generic_label(self):
        self.assertEqual(self.claim(self.invitee,self.code(self.inviter))[0],200)
        self.assertEqual(self.call(self.inviter)[1]['people'],[{'display_name':'Участник'}])
        self.assertEqual(self.call(self.invitee,'referrals/alias','POST',{'first_name':'Умар','surname_initial':'u'}),
                         (200,{'display_name':'Умар U.'}))
        value=self.call(self.inviter)[1]
        self.assertEqual(value['people'],[{'display_name':'Умар U.'}])
        raw=json.dumps(value,ensure_ascii=False)
        for secret in (self.invitee['id'],self.invitee['email'],'purchase','activity','last_seen','referrer'):
            self.assertNotIn(secret,raw)
        self.assertEqual(self.call(self.other,'referrals/alias','GET')[1],{'display_name':'Участник'})
        self.assertEqual(self.call(self.other,'referrals/alias','POST',{'first_name':'Fake','surname_initial':'X','user_id':self.invitee['id']})[0],400)
        self.assertEqual(self.call(self.invitee,'referrals/alias','POST',{'first_name':'Умар','surname_initial':'FullSurname'})[0],400)
        self.assertEqual(self.call(self.invitee,'referrals/alias','POST',{'first_name':'<script>','surname_initial':''})[0],400)
        self.assertEqual(self.call(self.invitee,'referrals/alias','POST',{'first_name':'','surname_initial':''})[0],200)
        self.assertEqual(self.call(self.inviter)[1]['people'],[{'display_name':'Участник'}])

    def test_admin_permission_excludes_every_other_role_and_customer(self):
        self.assertEqual(self.staff(self.inviter)[0],403)
        self.assertEqual(self.staff({})[0],403)
        for role in ('support','moderator','billing_manager','auditor'):
            with self.subTest(role=role):
                self.assertEqual(self.staff(StaffPrincipal(uid(),self.inviter['id'],(role,)))[0],403)
        for role in ('owner','admin'):
            status,value=self.staff(StaffPrincipal(uid(),self.inviter['id'],(role,)))
            self.assertEqual(status,200,value)
            self.assertEqual(value['counts'],{'confirmed':0,'active':0,'inactive':0,'purchase_converted':0})
            self.assertFalse(value['sales_enabled']);self.assertFalse(value['rewards_enabled']);self.assertFalse(value['payouts_enabled'])

    def test_activity_reports_existing_device_time_not_moderation_labels(self):
        self.claim(self.invitee,self.code(self.inviter))
        with self.backend.transaction() as db:
            db.execute('INSERT INTO account_state VALUES(?,?,0)',(self.invitee['id'],self.now+9000))
        self.assertEqual(self.staff()[1]['counts'],{'confirmed':1,'active':1,'inactive':0,'purchase_converted':0})

    def test_short_alias_accepts_uzbek_typographic_apostrophe(self):
        self.assertEqual(self.call(self.invitee,'referrals/alias','POST',{'first_name':'O‘tkir','surname_initial':'u'}),
                         (200,{'display_name':'O‘tkir U.'}))

    def test_admin_activity_is_operational_and_conversion_excludes_manual_invoice_trial(self):
        code=self.code(self.inviter)
        self.claim(self.invitee,code);self.claim(self.other,code)
        with self.backend.transaction() as db:
            db.execute('UPDATE devices SET last_seen_at=? WHERE user_id=?',(self.now-31*86400,self.other['id']))
            db.execute('INSERT INTO entitlement_grants VALUES(?,?,?,?,?,?,0,?,?)',(uid(),self.other['id'],'Plus','manual',self.now,self.now+9000,'Synthetic manual access','fixture'))
        reconcile(self.backend,StoreProvider(),VerifiedPurchase('google_play','paid','paid-event',self.invitee['id'],'synthetic.plus','Plus','active',self.now+9000,1))
        provider=StoreProvider();provider.source='web'
        reconcile(self.backend,provider,VerifiedPurchase('web','invoice','invoice-event',self.other['id'],'synthetic.plus','Plus','active',self.now+9000,1))
        reconcile(self.backend,StoreProvider(),VerifiedPurchase('google_play','trial','trial-event',self.other['id'],'synthetic.plus','Plus','trial',self.now+9000,1,self.now+4000))
        value=self.staff()[1]
        self.assertEqual(value['counts'],{'confirmed':2,'active':1,'inactive':1,'purchase_converted':1})
        self.assertEqual({row['invitee_id'] for row in value['edges']},{self.invitee['id'],self.other['id']})
        self.assertEqual(len(self.staff(query={'activity':['inactive']})[1]['edges']),1)
        self.assertEqual(len(self.staff(query={'converted':['yes']})[1]['edges']),1)
        self.assertEqual(self.staff(query={'referrer':[self.other['id']]})[1]['counts']['confirmed'],0)
        reconcile(self.backend,StoreProvider(),VerifiedPurchase('google_play','paid','refund-event',self.invitee['id'],'synthetic.plus','Plus','refunded',self.now+9000,2))
        self.assertEqual(self.staff()[1]['counts']['purchase_converted'],0)

    def test_erasure_removes_alias_code_and_edges_without_allowing_reattribution(self):
        first=self.code(self.inviter);second=self.code(self.other)
        self.claim(self.invitee,first)
        self.call(self.inviter,'referrals/alias','POST',{'first_name':'Private','surname_initial':'P'})
        with self.backend.transaction() as db:erase_in(self.backend,db,self.inviter['id'],self.now)
        self.assertEqual(self.claim(self.other,first)[0],400)
        self.assertEqual(self.claim(self.invitee,second)[0],409)
        with self.backend.connect() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM referral_codes WHERE user_id=?',(self.inviter['id'],)).fetchone())
            self.assertIsNone(db.execute('SELECT 1 FROM referral_aliases WHERE user_id=?',(self.inviter['id'],)).fetchone())
            self.assertIsNone(db.execute('SELECT 1 FROM referral_attributions WHERE referrer_id=? OR invitee_id=?',(self.inviter['id'],self.inviter['id'])).fetchone())
        with self.backend.transaction() as db:erase_in(self.backend,db,self.invitee['id'],self.now)
        with self.backend.connect() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM referral_attributions WHERE invitee_id=?',(self.invitee['id'],)).fetchone())

    def test_own_alias_pages_are_bounded_and_have_no_identifier_cursor(self):
        self.code(self.inviter)
        with self.backend.transaction() as db:
            for number in range(51):
                person=uid()
                db.execute('INSERT INTO users VALUES(?,?,?,?,1,?)',(person,'person'+str(number)+'@example.test','fixture-hash','fixture-salt',self.now))
                db.execute('INSERT INTO referral_attributions VALUES(?,?,?)',(person,self.inviter['id'],self.now+number))
        first=self.call(self.inviter)[1]
        self.assertEqual(first['confirmed_count'],51);self.assertEqual(len(first['people']),50);self.assertEqual(first['next_offset'],50)
        second=self.call(self.inviter,query='offset=50')[1]
        self.assertEqual(second['people'],[{'display_name':'Участник'}]);self.assertIsNone(second['next_offset'])
        self.assertEqual(self.call(self.inviter,query='offset=-1')[0],400)
        self.assertEqual(self.staff(query={'before':['not-a-cursor']})[0],400)


class ReferralsSQLiteTests(ReferralScenarios,unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.backend=Backend(Path(folder.name)/'referrals.db',deliver=lambda e,c:None)
        self.backend.cipher=Fernet(Fernet.generate_key());self.prepare()


DSN=os.environ.get('LIFEOS_TEST_DATABASE_URL','')
@unittest.skipUnless(DSN,'Requires isolated lifeos_test PostgreSQL')
class ReferralsPostgresTests(ReferralScenarios,unittest.TestCase):
    def setUp(self):
        if urlsplit(DSN).path!='/lifeos_test':raise RuntimeError('Refusing non-test database')
        import psycopg
        from psycopg import sql
        from backend.postgres import PostgresBackend
        schema='referrals_test_'+uuid.uuid4().hex
        with psycopg.connect(DSN,autocommit=True) as db:db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        def drop():
            with psycopg.connect(DSN,autocommit=True) as db:db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
        self.addCleanup(drop)
        self.backend=PostgresBackend(DSN,Fernet(Fernet.generate_key()),schema=schema,migrate=True)
        self.addCleanup(self.backend.close);self.prepare()
