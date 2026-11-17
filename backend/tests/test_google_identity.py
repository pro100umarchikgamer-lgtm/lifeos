"""Real RSA/JWT validation and existing-account security, using synthetic keys only."""
import io
import json
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs

import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa
from backend.config import Settings
from backend.service import Backend, Failure, token_hash
from backend.google_identity import GoogleIdentity, GoogleVerifier
from backend.production import Application
from backend.customer_mfa import CustomerMFA
from backend.control import totp

CLIENT = 'synthetic-google-client.apps.googleusercontent.com'
ANDROID_CLIENT = 'synthetic-android-client.apps.googleusercontent.com'


class SyntheticGoogle(GoogleVerifier):
    def __init__(self):
        self.jwt = jwt
        self.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.keys = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=self.private.public_key()))
        self.exchange_args = None

    def sign(self, requested_nonce, **changes):
        now = int(time.time())
        claims = {'iss':'https://accounts.google.com','aud':CLIENT,'sub':'synthetic-google-subject',
            'exp':now+300,'iat':now,'nonce':requested_nonce,'email':'synthetic@gmail.com','email_verified':True}
        claims.update(changes)
        return jwt.encode(claims, self.private, algorithm='RS256', headers={'kid':'synthetic-key'})

    def exchange(self, code, verifier, client_id, secret, redirect):
        self.exchange_args = (verifier, client_id, redirect)
        return code  # Test authorization code contains only a synthetic signed JWT.


class GoogleIdentityScenarios:
    def prepare_google(self):
        # Other PostgreSQL suites use a far-future clock. JWT signatures are
        # validated against real time, so this fixture uses the same real epoch.
        self.now = int(time.time())
        self.backend.clock = lambda: self.now
        self.password = 'synthetic-valid-passphrase'
        self.settings = Settings.load({'DATABASE_URL':'postgresql://example/db',
            'EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),'RATE_LIMIT_KEY':'x'*48,
            'SMTP_HOST':'127.0.0.1','SMTP_TLS':'none','EMAIL_FROM':'test@example.test',
            'GOOGLE_OAUTH_CLIENT_ID':CLIENT,'GOOGLE_OAUTH_CLIENT_SECRET':'synthetic-secret',
            'REGISTRATION_MODE':'open'})
        self.provider = SyntheticGoogle()
        self.google = GoogleIdentity(self.backend, self.settings, self.provider)

    def start(self, **args):
        return self.google.start('android', 'test-device', **args)

    def finish(self, value, **claims):
        return self.google.finish(value['challenge'], 'android','test-device',
            id_token=self.provider.sign(value['nonce'], **claims))

    def user(self, email='legacy@gmail.com'):
        session=self.backend.register(email,self.password)
        actor=self.backend.authenticate(session['token'])
        self.backend.verify(actor,self.mail[email])
        return self.backend.authenticate(session['token']), session

    def test_google_creates_existing_model_session_and_reuses_uuid(self):
        value=self.start(); first=self.finish(value)
        self.assertTrue(first['verified'])
        self.assertEqual(self.backend.authenticate(first['token'])['id'],first['user_id'])
        second=self.finish(self.start())
        self.assertEqual(first['user_id'],second['user_id'])
        self.assertFalse(self.google.status(self.backend.authenticate(first['token']))['has_password'])
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM staff').fetchone()['n'],0)

    def test_nonce_audience_issuer_signature_expiry_iat_azp_verified_email(self):
        for changes in [{'nonce':'other'}, {'aud':'foreign-client'}, {'iss':'https://evil.invalid'},
                        {'exp':int(time.time())-600}, {'iat':int(time.time())+600},
                        {'azp':'foreign-client'}, {'email_verified':False}]:
            with self.subTest(changes=changes):
                with self.assertRaises(Failure): self.finish(self.start(),**changes)
        value=self.start(); token=self.provider.sign(value['nonce'])
        other=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        claims=jwt.decode(token,options={'verify_signature':False})
        forged=jwt.encode(claims,other,algorithm='RS256',headers={'kid':'synthetic-key'})
        with self.assertRaises(Failure):self.google.finish(value['challenge'],'android','test-device',id_token=forged)
        value=self.start()
        unsigned=jwt.encode(claims,key='',algorithm='none',headers={'kid':'synthetic-key'})
        with self.assertRaises(Failure):self.google.finish(value['challenge'],'android','test-device',id_token=unsigned)

    def test_one_use_even_after_failure_and_agent_expiry(self):
        value=self.start()
        with self.assertRaises(Failure):self.finish(value,nonce='wrong')
        with self.assertRaises(Failure):self.finish(value)
        value=self.start()
        with self.assertRaises(Failure):self.google.finish(value['challenge'],'android','other-device',id_token=self.provider.sign(value['nonce']))
        self.finish(value)
        with self.assertRaises(Failure):self.finish(value)
        value=self.start()
        with self.backend.transaction() as db:db.execute('UPDATE oauth_challenges SET expires_at=0')
        with self.assertRaises(Failure):self.finish(value)

    def test_android_hybrid_presenter_requires_exact_configured_client(self):
        self.google.settings = replace(self.settings, google_android_client_ids=(ANDROID_CLIENT,))
        first = self.finish(self.start(), azp=ANDROID_CLIENT)
        self.assertEqual(self.backend.authenticate(first['token'])['id'], first['user_id'])
        self.assertEqual(self.finish(self.start(), azp=CLIENT)['user_id'], first['user_id'])
        self.assertEqual(self.finish(self.start())['user_id'], first['user_id'])
        for unknown in ('unlisted-android.apps.googleusercontent.com', ANDROID_CLIENT + '.evil'):
            with self.subTest(azp=unknown):
                with self.assertRaises(Failure) as denied:
                    self.finish(self.start(), azp=unknown)
                self.assertEqual((denied.exception.code, denied.exception.status), ('google_android_client_untrusted', 403))
        self.google.settings = self.settings
        with self.assertRaises(Failure) as missing:
            self.finish(self.start(), azp=ANDROID_CLIENT)
        self.assertEqual((missing.exception.code, missing.exception.status), ('google_android_client_untrusted', 403))
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM staff').fetchone()['n'], 0)

    def test_android_presenter_allowlist_never_replaces_jwt_or_challenge_checks(self):
        self.google.settings = replace(self.settings, google_android_client_ids=(ANDROID_CLIENT,))
        for changes in ({'aud': 'wrong-client'}, {'nonce': 'wrong-nonce'}, {'iss': 'https://evil.invalid'},
                        {'email_verified': False}, {'azp': []}):
            with self.subTest(changes=changes):
                with self.assertRaises(Failure) as denied:
                    self.finish(self.start(), **dict({'azp': ANDROID_CLIENT}, **changes))
                self.assertEqual((denied.exception.code, denied.exception.status), ('google_invalid', 401))
        grant = self.start()
        self.finish(grant, azp=ANDROID_CLIENT)
        with self.assertRaises(Failure): self.finish(grant, azp=ANDROID_CLIENT)
        grant = self.start()
        with self.assertRaises(Failure):
            self.google.finish(grant['challenge'], 'android', 'other-device', id_token=self.provider.sign(grant['nonce'], azp=ANDROID_CLIENT))
        self.finish(grant, azp=ANDROID_CLIENT)

    def test_web_cannot_use_an_allowlisted_android_presenter(self):
        self.google.settings = replace(self.settings, google_android_client_ids=(ANDROID_CLIENT,))
        binding = 'b' * 43
        grant = self.google.start('web', 'browser', binding)
        params = parse_qs(urlsplit(grant['authorization_url']).query)
        token = self.provider.sign(params['nonce'][0], azp=ANDROID_CLIENT)
        with self.assertRaises(Failure) as denied:
            self.google.finish(params['state'][0], 'web', 'browser', binding, authorization_code=token)
        self.assertEqual((denied.exception.code, denied.exception.status), ('google_invalid', 401))

    def test_closed_registration_enforced_but_existing_identity_can_login(self):
        first=self.finish(self.start())
        self.google.settings=replace(self.settings,registration_mode='closed')
        self.assertEqual(self.finish(self.start())['user_id'],first['user_id'])
        with self.assertRaises(Failure) as e:self.finish(self.start(),sub='another-sub',email='another@gmail.com')
        self.assertEqual(e.exception.code,'registration_closed')

    def test_same_email_never_merges_and_explicit_link_needs_password(self):
        actor,session=self.user()
        with self.assertRaises(Failure) as e:self.finish(self.start(),email=actor['email'])
        self.assertEqual(e.exception.code,'google_link_required')
        with self.assertRaises(Failure):self.start(actor=actor,password='wrong-password',auth_hash=token_hash(session['token']))
        value=self.start(actor=actor,password=self.password,auth_hash=token_hash(session['token']))
        self.assertEqual(self.finish(value,email='different-owned@gmail.com'),{'linked':True})
        self.assertEqual(self.finish(self.start(),email='different-owned@gmail.com')['user_id'],actor['id'])
        self.assertTrue(self.google.status(actor)['google_linked'])
        other,other_session=self.user('second@gmail.com')
        value=self.start(actor=other,password=self.password,auth_hash=token_hash(other_session['token']))
        with self.assertRaises(Failure):self.finish(value)

    def test_link_rejects_revoked_originating_session(self):
        actor,session=self.user()
        value=self.start(actor=actor,password=self.password,auth_hash=token_hash(session['token']))
        self.backend.revoke_all(actor,self.password)
        with self.assertRaises(Failure):self.finish(value)

    def test_google_primary_still_requires_customer_mfa(self):
        self.google.settings = replace(self.settings, google_android_client_ids=(ANDROID_CLIENT,))
        actor,session=self.user()
        self.finish(self.start(actor=actor,password=self.password,auth_hash=token_hash(session['token'])))
        mfa=CustomerMFA(self.backend); enrollment=mfa.begin(actor,self.password)
        recovery=mfa.enable(actor,self.password,enrollment['enrollment'],totp(enrollment['totp_secret'],int(self.backend.clock())//30))
        result=self.finish(self.start(), azp=ANDROID_CLIENT)
        self.assertTrue(result['mfa_required']);self.assertNotIn('token',result)
        from backend.login_flow import LoginFlow
        session=LoginFlow(self.backend).finish(result['challenge'],recovery['recovery_codes'][0],'test-device')
        self.assertEqual(self.backend.authenticate(session['token'])['id'],actor['id'])

    def test_recovery_establishes_password_before_unlink_and_unlink_revokes(self):
        first=self.finish(self.start());actor=self.backend.authenticate(first['token'])
        # A Google-only user has no password that could pass reauthentication.
        with self.assertRaises(Failure):self.google.unlink(actor,self.password,None)
        self.backend.recover(actor['email'])
        self.backend.reset_password(actor['email'],self.mail[actor['email']],self.password)
        self.assertTrue(self.google.status(actor)['has_password'])
        fresh=self.backend.login(actor['email'],self.password)
        self.google.unlink(actor,self.password,None)
        self.assertFalse(self.google.status(actor)['google_linked'])
        with self.assertRaises(Failure):self.backend.authenticate(fresh['token'])

    def test_non_authoritative_external_email_requires_uladim_confirmation(self):
        result=self.finish(self.start(),email='external@example.test')
        self.assertFalse(result['verified'])
        self.assertIn('external@example.test',self.mail)

    def test_web_pkce_state_cookie_binding_and_no_credentials_in_redirect(self):
        app=Application(self.backend,self.settings);app.google.verifier=self.provider
        def request(path,body=None,query='',cookies='',origin='https://getuladim.space'):
            data=json.dumps(body).encode() if body is not None else b''
            env={'HTTP_HOST':'getuladim.space','PATH_INFO':path,'QUERY_STRING':query,
                'REQUEST_METHOD':'POST' if body is not None else 'GET','REMOTE_ADDR':'172.30.30.2',
                'HTTP_X_FORWARDED_PROTO':'https','HTTP_ORIGIN':origin,'HTTP_COOKIE':cookies,
                'HTTP_USER_AGENT':'browser','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(data)),
                'wsgi.input':io.BytesIO(data)}
            captured=[]
            with patch.object(app,'limit'):
                raw=b''.join(app(env,lambda s,h:captured.append((int(s[:3]),h))))
            return captured[0][0],captured[0][1],json.loads(raw) if raw else None
        status,headers,start=request('/account/api/google/start',{})
        self.assertEqual(status,200)
        binding=dict(headers)['Set-Cookie'].split(';')[0]
        params=parse_qs(urlsplit(start['authorization_url']).query)
        self.assertEqual(params['code_challenge_method'],['S256'])
        self.assertNotIn('secret',start['authorization_url'])
        token=self.provider.sign(params['nonce'][0])
        from urllib.parse import urlencode
        query=urlencode({'state':params['state'][0],'code':token})
        # A callback without its same-browser binding produces only a generic error.
        _,bad_headers,_=request('/account/api/google/callback',query=query)
        self.assertEqual(dict(bad_headers)['Location'],'/app?google=return')
        status,headers,_=request('/account/api/google/callback',query=query,cookies=binding)
        self.assertEqual(status,303);self.assertEqual(dict(headers)['Location'],'/app?google=return')
        result_cookie=dict(headers)['Set-Cookie'].split(';')[0]
        status,headers,result=request('/account/api/google/complete',{},cookies=binding+'; '+result_cookie)
        self.assertEqual(status,200);self.assertTrue(result['authenticated'])
        cookies=[v for k,v in headers if k=='Set-Cookie']
        self.assertEqual(len(cookies),2)
        account_cookie=next(c for c in cookies if c.startswith('__Host-uladim_account='))
        self.assertIn('HttpOnly; Secure; SameSite=Strict',account_cookie)
        self.assertEqual(request('/account/api/google/complete',{},cookies=binding+'; '+result_cookie)[0],401)
        self.assertEqual(request('/account/api/google/start',{},origin='https://evil.invalid')[0],403)
        verifier,client,redirect=self.provider.exchange_args
        import base64,hashlib
        self.assertEqual(base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='),params['code_challenge'][0])
        self.assertEqual(client,CLIENT)


class GoogleIdentityTests(GoogleIdentityScenarios, unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.mail={}
        self.backend=Backend(Path(folder.name)/'google.db',deliver=lambda e,c:self.mail.update({e:c}))
        self.backend.cipher=Fernet(Fernet.generate_key())
        self.prepare_google()

    def test_android_presenter_configuration_is_exact_bounded_and_not_public(self):
        env = {'DATABASE_URL': 'postgresql://unused/test', 'EMAIL_QUEUE_KEY': Fernet.generate_key().decode(),
               'RATE_LIMIT_KEY': 'r' * 48, 'SMTP_HOST': '127.0.0.1', 'SMTP_TLS': 'none',
               'EMAIL_FROM': 'fixture@example.test', 'GOOGLE_OAUTH_CLIENT_ID': CLIENT}
        settings = Settings.load(env)
        self.assertEqual(settings.google_android_client_ids, ())
        for raw in ('*', ANDROID_CLIENT + '.evil', 'https://' + ANDROID_CLIENT,
                    ANDROID_CLIENT + ',' + ANDROID_CLIENT, CLIENT,
                    ','.join(f'android-client-{i}.apps.googleusercontent.com' for i in range(9))):
            with self.subTest(value=raw):
                with self.assertRaises(ValueError): Settings.load(dict(env, GOOGLE_OAUTH_ANDROID_CLIENT_IDS=raw))
        settings = Settings.load(dict(env, GOOGLE_OAUTH_ANDROID_CLIENT_IDS=' ' + ANDROID_CLIENT + ' '))
        self.assertEqual(settings.google_android_client_ids, (ANDROID_CLIENT,))
        with self.assertRaises(ValueError):
            Settings.load(dict(env, GOOGLE_OAUTH_CLIENT_ID='', GOOGLE_OAUTH_ANDROID_CLIENT_IDS=ANDROID_CLIENT))
        path = {'PATH_INFO': '/v1/auth/google/config', 'REQUEST_METHOD': 'GET'}
        self.assertEqual(Application(None, self.settings).google_request(path, {}),
                         {'google_enabled': True, 'google_android_clients_configured': False})
        self.assertEqual(Application(None, settings).google_request(path, {}),
                         {'google_enabled': True, 'google_android_clients_configured': True})

    def test_native_api_reports_untrusted_presenter_without_token_or_claims(self):
        app = Application(self.backend, self.settings)
        app.google.verifier = self.provider
        grant = self.start()
        body = json.dumps({'challenge': grant['challenge'], 'id_token': self.provider.sign(grant['nonce'], azp=ANDROID_CLIENT)}).encode()
        env = {'PATH_INFO': '/v1/auth/google/finish', 'REQUEST_METHOD': 'POST', 'REMOTE_ADDR': '172.30.30.2',
               'HTTP_X_FORWARDED_PROTO': 'https', 'HTTP_USER_AGENT': 'test-device',
               'CONTENT_TYPE': 'application/json', 'CONTENT_LENGTH': str(len(body)), 'wsgi.input': io.BytesIO(body)}
        captured = []
        with patch.object(app, 'limit'):
            result = b''.join(app(env, lambda status, headers: captured.append(status)))
        self.assertEqual(captured, ['403 Forbidden'])
        self.assertEqual(json.loads(result), {'error': 'google_android_client_untrusted'})
