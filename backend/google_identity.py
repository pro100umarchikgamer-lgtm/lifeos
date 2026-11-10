"""Google OIDC for the existing account/session model. No email-only merging.

Google tokens and authorization codes are never persisted. Pending grants contain
only encrypted nonce/PKCE metadata and are consumed before network verification.
Neither this module nor Google customer sessions can grant Control authority.
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
import uuid
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

from .service import Failure, require, token_hash
from .login_flow import LoginFlow

ISSUERS = ('https://accounts.google.com', 'accounts.google.com')
JWKS = 'https://www.googleapis.com/oauth2/v3/certs'
TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token'
AUTHORIZE_ENDPOINT = 'https://accounts.google.com/o/oauth2/v2/auth'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class GoogleVerifier:
    def __init__(self):
        # A fixed trusted JWKS URL, bounded timeout and cache; never follow a jku
        # or x5u supplied by an untrusted token.
        import jwt
        self.jwt = jwt
        self.keys = jwt.PyJWKClient(JWKS, cache_jwk_set=True, lifespan=3600, timeout=8)

    def verify(self, token, audience):
        require(isinstance(token, str) and 100 < len(token) <= 16384, 'google_invalid', 401)
        try:
            header = self.jwt.get_unverified_header(token)
            require(header.get('alg') == 'RS256' and isinstance(header.get('kid'), str), 'google_invalid', 401)
            key = self.keys.get_signing_key_from_jwt(token)
            claims = self.jwt.decode(token, key.key, algorithms=['RS256'], audience=audience,
                issuer=ISSUERS, leeway=30, options={'require': ['iss', 'aud', 'sub', 'exp', 'iat', 'nonce', 'email', 'email_verified']})
        except Failure:
            raise
        except self.jwt.PyJWTError:
            raise Failure('google_invalid', 401) from None
        return claims

    def exchange(self, code, verifier, client_id, client_secret, redirect):
        require(isinstance(code, str) and 1 <= len(code) <= 4096, 'google_invalid', 401)
        request = Request(TOKEN_ENDPOINT, data=urlencode({'code': code, 'client_id': client_id,
            'client_secret': client_secret, 'redirect_uri': redirect, 'grant_type': 'authorization_code',
            'code_verifier': verifier}).encode(), headers={'Content-Type': 'application/x-www-form-urlencoded'})
        try:
            with build_opener(NoRedirect).open(request, timeout=8) as response:
                data = response.read(65537)
                require(len(data) <= 65536, 'google_unavailable', 503)
                token = json.loads(data).get('id_token')
                require(isinstance(token, str), 'google_invalid', 401)
                return token
        except Failure:
            raise
        except Exception:
            # Never log the response, request URL, code, secret or tokens.
            raise Failure('google_unavailable', 503) from None


class GoogleIdentity:
    def __init__(self, backend, settings, verifier=None):
        self.backend, self.settings = backend, settings
        self.verifier = verifier

    @property
    def enabled(self):
        return bool(getattr(self.settings, 'google_client_id', ''))

    @property
    def web_enabled(self):
        return self.enabled and bool(getattr(self.settings, 'google_client_secret', ''))

    @property
    def redirect(self):
        return self.settings.site_origin + '/account/api/google/callback'

    def _provider(self):
        if self.verifier is None:
            self.verifier = GoogleVerifier()
        return self.verifier

    def _reauth(self, actor, password, code):
        self.backend.reserve_reauth(actor)
        valid = False
        with self.backend.transaction() as db:
            self.backend.reauthenticate(db, actor, password)
            from .customer_mfa import accept
            valid = accept(self.backend, db, actor['id'], code)
        require(valid, 'invalid_credentials', 401)

    def start(self, client, agent='', binding='', invitation=None, actor=None, password=None, code=None, auth_hash=''):
        require(self.enabled and (client != 'web' or self.web_enabled), 'google_unconfigured', 503)
        require(client in ('web', 'android'), 'invalid_input')
        require(client != 'web' or (isinstance(binding, str) and len(binding) == 43), 'google_invalid', 401)
        if actor:
            require(actor['verified'], 'verify_email', 403)
            self._reauth(actor, password, code)
        state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
        now = int(self.backend.clock())
        payload = {'nonce_hash': token_hash(nonce), 'verifier': verifier,
                   'invitation': invitation if isinstance(invitation, str) and len(invitation) <= 128 else None}
        if actor:
            with self.backend.connect() as db:
                user, factor = LoginFlow(self.backend)._principal(db, actor['id'], False)
                payload.update(version=LoginFlow(self.backend)._version(user, factor, False), auth_hash=auth_hash)
        with self.backend.transaction() as db:
            db.execute('DELETE FROM oauth_challenges WHERE expires_at<=?', (now,))
            db.execute('INSERT INTO oauth_challenges VALUES(?,?,?,?,?,?,?,0)',
                (token_hash(state), client, token_hash(agent), token_hash(binding),
                 self.backend.cipher.encrypt(json.dumps(payload).encode()), actor['id'] if actor else None, now + 300))
        if client == 'android':
            return {'challenge': state, 'nonce': nonce, 'client_id': self.settings.google_client_id, 'expires_in': 300}
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        url = AUTHORIZE_ENDPOINT + '?' + urlencode({'client_id': self.settings.google_client_id,
            'redirect_uri': self.redirect, 'response_type': 'code', 'scope': 'openid email',
            'state': state, 'nonce': nonce, 'code_challenge': challenge, 'code_challenge_method': 'S256',
            'prompt': 'select_account'})
        return {'authorization_url': url, 'expires_in': 300}

    def _consume(self, state, client, agent, binding):
        require(isinstance(state, str) and len(state) == 43, 'google_invalid', 401)
        now = int(self.backend.clock())
        with self.backend.transaction() as db:
            row = db.execute('SELECT * FROM oauth_challenges WHERE hash=?', (token_hash(state),)).fetchone()
            require(row and row['client'] == client and row['expires_at'] > now and not row['used_at']
                and hmac.compare_digest(row['agent_hash'], token_hash(agent))
                and hmac.compare_digest(row['binding_hash'], token_hash(binding)), 'google_invalid', 401)
            db.execute('UPDATE oauth_challenges SET used_at=?,payload=? WHERE hash=?', (max(1, now), b'', row['hash']))
            payload = json.loads(self.backend.cipher.decrypt(bytes(row['payload'])))
        return dict(row), payload

    def finish(self, state, client, agent='', binding='', id_token=None, authorization_code=None, cancelled=False):
        require(self.enabled, 'google_unconfigured', 503)
        row, payload = self._consume(state, client, agent, binding)
        require(not cancelled, 'google_cancelled', 400)
        provider = self._provider()
        if client == 'web':
            id_token = provider.exchange(authorization_code, payload['verifier'], self.settings.google_client_id,
                                         self.settings.google_client_secret, self.redirect)
        claims = provider.verify(id_token, self.settings.google_client_id)
        # These policy checks are separate from cryptographic JWT verification so
        # test providers cannot accidentally bypass the account boundary rules.
        now = int(self.backend.clock())
        require(claims.get('iss') in ISSUERS and claims.get('aud') == self.settings.google_client_id
            and claims.get('azp', self.settings.google_client_id) == self.settings.google_client_id
            and type(claims.get('exp')) is int and claims['exp'] > now
            and type(claims.get('iat')) is int and now - 600 <= claims['iat'] <= now + 30
            and isinstance(claims.get('nonce'), str)
            and hmac.compare_digest(token_hash(claims['nonce']), payload['nonce_hash'])
            and isinstance(claims.get('sub'), str) and 1 <= len(claims['sub']) <= 255
            and claims.get('email_verified') is True, 'google_invalid', 401)
        email = claims.get('email')
        require(isinstance(email, str) and len(email) <= 254 and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email), 'google_invalid', 401)
        email = email.casefold()
        with self.backend.transaction() as db:
            identity = db.execute('SELECT * FROM google_identities WHERE subject=?', (claims['sub'],)).fetchone()
            if row['user_id']:
                uid = row['user_id']
                self.backend._account_available(db, uid)
                flow = LoginFlow(self.backend)
                user, factor = flow._principal(db, uid, False)
                require(user and hmac.compare_digest(flow._version(user, factor, False), payload['version']), 'invalid_credentials', 401)
                # Linking must still belong to an active originating session.
                auth = payload['auth_hash']
                active = db.execute('SELECT 1 FROM sessions WHERE hash=? AND user_id=? AND expires_at>?', (auth, uid, now)).fetchone()
                web = db.execute('SELECT 1 FROM web_sessions w JOIN devices d ON d.id=w.device_id WHERE w.hash=? AND w.user_id=? AND w.expires_at>? AND d.revoked_at=0', (auth, uid, now)).fetchone()
                require(active or web, 'unauthorized', 401)
                require(identity is None or identity['user_id'] == uid, 'google_already_linked', 409)
                existing = db.execute('SELECT subject FROM google_identities WHERE user_id=?', (uid,)).fetchone()
                require(existing is None or existing['subject'] == claims['sub'], 'google_already_linked', 409)
                if not existing:
                    db.execute('INSERT INTO google_identities VALUES(?,?,?)', (claims['sub'], uid, now))
                return {'linked': True}
            if identity:
                uid = identity['user_id']
            else:
                # A matching address is NOT proof of ownership of a legacy ULADIM
                # account. The user signs in with its existing method and links.
                require(not db.execute('SELECT 1 FROM users WHERE email=?', (email,)).fetchone(), 'google_link_required', 409)
                if self.settings.registration_mode != 'open':
                    from .early_access import EarlyAccess
                    from .owner_enrollment import OwnerEnrollment
                    # These helpers use their own read connections; no mutation.
                    allowed = email in self.settings.registration_allowlist
                    allowed = allowed or EarlyAccess(self.backend).invited(email, payload['invitation'])
                    allowed = allowed or OwnerEnrollment(self.backend).invited(email, payload['invitation'])
                    require(allowed, 'registration_closed', 403)
                uid = str(uuid.uuid4())
                # Unknowable random password; recovery may establish a password.
                salt = secrets.token_hex(16)
                digest = hashlib.pbkdf2_hmac('sha256', secrets.token_bytes(48), bytes.fromhex(salt), 600000).hex()
                # Google is authoritative for Gmail and managed Workspace domains.
                verified = int(email.endswith('@gmail.com') or bool(claims.get('hd')))
                db.execute('INSERT INTO users VALUES(?,?,?,?,?,?)', (uid, email, digest, salt, verified, now))
                db.execute('INSERT INTO account_credentials VALUES(?,0)', (uid,))
                db.execute('INSERT INTO google_identities VALUES(?,?,?)', (claims['sub'], uid, now))
                if not verified:
                    code = secrets.token_urlsafe(32)
                    db.execute('INSERT INTO verification VALUES(?,?,?)', (token_hash(code), uid, now + 3600))
                    self.backend._deliver(db, email, code, 'verification')
            self.backend._account_available(db, uid)
            result = LoginFlow(self.backend).customer_in(db, uid, agent)
            if not result.get('mfa_required'):
                result['email'] = db.execute('SELECT email FROM users WHERE id=?', (uid,)).fetchone()['email']
            return result

    def status(self, actor):
        with self.backend.connect() as db:
            linked = db.execute('SELECT created_at FROM google_identities WHERE user_id=?', (actor['id'],)).fetchone()
            password = db.execute('SELECT has_password FROM account_credentials WHERE user_id=?', (actor['id'],)).fetchone()
        return {'google_linked': bool(linked), 'has_password': password is None or bool(password['has_password']),
                'google_enabled': self.enabled, 'google_web_enabled': self.web_enabled}

    def unlink(self, actor, password, code):
        self._reauth(actor, password, code)
        with self.backend.transaction() as db:
            credential = db.execute('SELECT has_password FROM account_credentials WHERE user_id=?', (actor['id'],)).fetchone()
            require(credential is None or credential['has_password'], 'google_last_method', 409)
            db.execute('DELETE FROM google_identities WHERE user_id=?', (actor['id'],))
            self.backend.revoke_all_in(db, actor['id'])
        return {'unlinked': True, 'signed_out': True}
