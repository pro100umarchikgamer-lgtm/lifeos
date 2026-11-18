"""Same-origin web surfaces with separate customer/staff cookies and server-side authority."""
import hashlib
import hmac
import json
import secrets
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .control import Control
from .control_admission import ControlAdmission, COOKIE as ADMISSION_COOKIE
from .support import Support
from .service import Failure, require, token_hash
from . import entitlements

ASSETS = Path(__file__).with_name('webassets')
CONTROL_COOKIE = '__Host-uladim_control'
ACCOUNT_COOKIE = '__Host-uladim_account'


class Web:
    def __init__(self, backend, settings, *, native_download=None):
        self.backend, self.settings = backend, settings
        from .google_identity import GoogleIdentity
        self.google = GoogleIdentity(backend, settings)
        self.control = Control(backend)
        self.admission = ControlAdmission(backend)
        self.support = Support(backend, self.control)
        self.site = getattr(settings, 'site_origin', 'https://getuladim.space')
        self.staff = getattr(settings, 'control_origin', 'https://control.getuladim.space')
        from .web_push import WebPush
        self.push = WebPush(backend, self.site)
        from .native_download import NativeDownload
        self.native_download = native_download or NativeDownload(getattr(settings, 'native_download_dir', ''))
        self._android = None
        self._pages = None

    def android(self):
        if self._android is None:
            from .android_releases import AndroidReleases
            self._android = AndroidReleases(self.backend, self.settings, self.native_download)
        return self._android

    def pages(self):
        if self._pages is None:
            from .public_pages import PublicPages
            self._pages = PublicPages(self.backend)
        return self._pages

    def upload_android(self, env):
        """Authenticate the ordinary Control principal before consuming bytes."""
        require(self.is_control(env) and env.get('uladim.admitted'), 'not_found', 404)
        require(env.get('REQUEST_METHOD') == 'POST' and not env.get('QUERY_STRING'), 'not_found', 404)
        require(env.get('HTTP_ORIGIN') == self.staff, 'origin_forbidden', 403)
        token = self.token(env, True)
        actor = self.control.authenticate(token, env.get('HTTP_USER_AGENT', '')[:500])
        require(actor.user_id == env['uladim.admitted']['user_id'], 'not_found', 404)
        require(hmac.compare_digest(env.get('HTTP_X_CSRF_TOKEN', ''), self.csrf(token)), 'csrf_invalid', 403)
        self.control.require(actor, 'android.upload')
        value = self.android().upload(actor, env)
        return value, [('Content-Type', 'application/json; charset=utf-8'), ('Cache-Control', 'no-store')]

    def is_control(self, env):
        return env.get('HTTP_HOST', '') == urlsplit(self.staff).netloc

    def admitted(self, env):
        cookie = SimpleCookie()
        try: cookie.load(env.get('HTTP_COOKIE', ''))
        except Exception: raise Failure('not_found', 404)
        value = cookie.get(ADMISSION_COOKIE)
        return self.admission.authenticate(value.value if value else '', env.get('HTTP_USER_AGENT', '')[:500])

    def redeem_admission(self, env, ticket):
        require(env.get('HTTP_ORIGIN') == self.site, 'not_found', 404)
        raw, seconds = self.admission.redeem(ticket, env.get('HTTP_USER_AGENT', '')[:500])
        return b'', [('X-ULADIM-Status', '303'), ('Location', '/'), ('Referrer-Policy', 'no-referrer'), ('Set-Cookie', ADMISSION_COOKIE + '=' + raw + '; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=' + str(seconds))]

    def handles(self, env):
        return env.get('HTTP_HOST', '') in (urlsplit(self.site).netloc, urlsplit(self.staff).netloc)

    def csrf(self, token):
        return hmac.new(self.settings.rate_limit_key.encode(), ('csrf:' + token).encode(), hashlib.sha256).hexdigest()

    def cookie(self, token, staff=False, clear=False):
        return ('Set-Cookie', (CONTROL_COOKIE if staff else ACCOUNT_COOKIE) + '=' + token + '; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=' + ('0' if clear else ('28800' if staff else '2592000')))

    def token(self, env, staff):
        cookie = SimpleCookie()
        try: cookie.load(env.get('HTTP_COOKIE', ''))
        except Exception: raise Failure('unauthorized', 401)
        item = cookie.get(CONTROL_COOKIE if staff else ACCOUNT_COOKIE)
        token = item.value if item else ''
        require(len(token) == 43, 'unauthorized', 401)
        return token

    def account(self, token, agent):
        now = int(self.backend.clock())
        with self.backend.transaction() as db:
            row = db.execute('SELECT w.*,u.email,u.verified,d.revoked_at FROM web_sessions w JOIN users u ON u.id=w.user_id JOIN devices d ON d.id=w.device_id WHERE w.hash=?', (token_hash(token),)).fetchone()
            require(row and not row['revoked_at'] and row['expires_at'] > now and row['agent_hash'] == token_hash(agent), 'unauthorized', 401)
            self.backend._account_available(db, row['user_id'])
            db.execute('UPDATE web_sessions SET last_seen_at=? WHERE hash=?', (now, token_hash(token)))
            db.execute('UPDATE devices SET last_seen_at=? WHERE id=?', (now, row['device_id']))
            return {'id': row['user_id'], 'email': row['email'], 'verified': row['verified'], 'device_id': row['device_id']}

    def request(self, env, body):
        path, method = env.get('PATH_INFO', ''), env.get('REQUEST_METHOD', '')
        staff = self.is_control(env)
        admitted = env.get('uladim.admitted') if staff else None
        if staff:
            require(admitted, 'not_found', 404)
        origin = self.staff if staff else self.site
        headers = [('Content-Type', 'application/json; charset=utf-8'), ('Cache-Control', 'no-store'), ('X-Robots-Tag', 'noindex, nofollow' if staff or path.startswith('/account') else 'index, follow'),
                   ('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"), ('X-Content-Type-Options', 'nosniff'), ('Referrer-Policy', 'no-referrer')]
        if not staff:
            headers = [(key, value.replace("form-action 'self'", "form-action 'self' " + self.staff) if key == 'Content-Security-Policy' else value) for key, value in headers]
        if not staff and method == 'GET' and (path in ('/app', '/app/') or path.startswith('/app/assets/') or path == '/app/sw.js'):
            return self.app_asset(path, headers)
        if method == 'GET' and path in ('/assets/public-pages.js', '/assets/control-publishing.css'):
            headers[0] = ('Content-Type', 'text/javascript; charset=utf-8' if path.endswith('.js') else 'text/css; charset=utf-8')
            return (ASSETS / path.rsplit('/', 1)[-1]).read_bytes(), headers
        if staff and method == 'GET' and path in ('/assets/control-publishing.js', '/assets/control-publishing-copy.json'):
            headers[0] = ('Content-Type', 'application/json; charset=utf-8' if path.endswith('.json') else 'text/javascript; charset=utf-8')
            return (ASSETS / path.rsplit('/', 1)[-1]).read_bytes(), headers
        if not staff and method == 'GET' and path == '/public-pages/document':
            query = parse_qs(env.get('QUERY_STRING', ''), keep_blank_values=True)
            require(set(query) == {'page', 'lang'} and all(len(values) == 1 for values in query.values()), 'invalid_fields')
            return self.pages().public_document(query['page'][0], query['lang'][0]), headers
        if not staff and method == 'GET' and path.startswith('/public-pages/media/'):
            require(not env.get('QUERY_STRING'), 'not_found', 404)
            raw, mime = self.pages().public_media(path[len('/public-pages/media/'):])
            headers[0] = ('Content-Type', mime)
            return raw, headers
        if not staff and method == 'GET' and path == '/download/release.json':
            require(not env.get('QUERY_STRING'), 'not_found', 404)
            value = self.android().public_manifest()
            require(value is not None, 'release_unavailable', 503)
            return value, headers
        # The Control document uses only these shared UI assets. Admission above
        # still gates every Control-host request, including these static files.
        if staff and method == 'GET' and path in {'/app/assets/' + name for name in ('i18n.js', 'translations.json', 'referrals.js', 'referrals.css', 'password-policy.js', 'install.js', 'field-menu.js', 'field-menu.css', 'appearance-boot.js')}:
            return self.app_asset(path, headers)
        if staff and method == 'GET' and path == '/assets/control-workbench.js':
            headers[0] = ('Content-Type', 'text/javascript; charset=utf-8')
            return (ASSETS / 'control-workbench.js').read_bytes(), headers
        if method == 'GET' and path == '/assets/locales.json':
            return (ASSETS / 'app' / 'locales.json').read_bytes(), headers
        if method == 'GET' and path in ('/assets/web.js', '/assets/web.css', '/assets/design.css'):
            headers[0] = ('Content-Type', 'text/javascript; charset=utf-8' if path.endswith('.js') else 'text/css; charset=utf-8')
            return (ASSETS / path.rsplit('/', 1)[-1]).read_bytes(), headers
        prefix = '/control/api/' if staff else '/account/api/'
        if not staff and path.startswith('/early-access/api/'):
            require(method == 'POST', 'method_not_allowed', 405)
            require(env.get('HTTP_ORIGIN') == self.site, 'origin_forbidden', 403)
            from .early_access import EarlyAccess
            applications = EarlyAccess(self.backend)
            action = path.rsplit('/', 1)[-1]
            if action == 'recover':
                from .early_access import CONSENT_VERSION
                return applications.apply(body.get('email'), CONSENT_VERSION, body.get('website', ''), env.get('uladim.client', 'unknown'), existing_only=True), headers
            if action == 'apply':
                return applications.apply(body.get('email'), body.get('consent_version'), body.get('website', ''), env.get('uladim.client', 'unknown')), headers
            if action == 'confirm': return applications.confirm(body.get('email'), body.get('code')), headers
            if action in ('status', 'cancel'): return applications.manage(body.get('management_token'), action == 'cancel'), headers
            raise Failure('not_found', 404)
        if not staff and path == '/account/api/google/callback' and method == 'GET':
            return self.google_callback(env, headers)
        if method == 'GET' and not path.startswith(prefix):
            allowed = {'/'} if staff else {'/', '/account', '/plans', '/privacy', '/terms', '/support', '/delete-account', '/status', '/download', '/faq', '/early-access', '/docs'}
            require(path in allowed, 'not_found', 404)
            page = (ASSETS / 'index.html').read_text().replace('__SURFACE__', 'control' if staff else 'site')
            if not staff:
                headers = [(key, value.replace("default-src 'none';", "default-src 'none'; manifest-src 'self';") if key == 'Content-Security-Policy' else value) for key, value in headers]
            return page.encode(), [('Content-Type', 'text/html; charset=utf-8')] + headers[1:]
        require(path.startswith(prefix), 'not_found', 404)
        action = path[len(prefix):]
        if method == 'POST':
            require(env.get('HTTP_ORIGIN') == origin, 'origin_forbidden', 403)
        if not staff and action == 'config' and method == 'GET':
            return {'registration_open': self.settings.registration_mode == 'open', 'payments_enabled': False, 'google_enabled': self.google.web_enabled}, headers
        if not staff and action in ('google/start', 'google/complete') and method == 'POST':
            if action == 'google/complete': return self.google_complete(env, headers)
            binding=secrets.token_urlsafe(32)
            value=self.google.start('web', env.get('HTTP_USER_AGENT','')[:500], binding, body.get('invitation'))
            return value, headers + [self.google_cookie('binding', binding)]
        if action in ('login', 'login/mfa') and method == 'POST':
            agent = env.get('HTTP_USER_AGENT', '')[:500]
            from .login_flow import LoginFlow
            if staff:
                if action == 'login/mfa':
                    require(isinstance(body.get('challenge'), str) and len(body['challenge']) == 43, 'not_found', 404)
                    with self.backend.connect() as db:
                        pending = db.execute('SELECT user_id FROM login_challenges WHERE hash=?', (token_hash(body.get('challenge', '')),)).fetchone()
                    require(pending and pending['user_id'] == admitted['user_id'], 'not_found', 404)
                else:
                    require(isinstance(body.get('email'), str) and body['email'].casefold() == admitted['email'], 'not_found', 404)
            if action == 'login/mfa':
                result = LoginFlow(self.backend).finish(body.get('challenge'), body.get('code'), agent, staff)
            elif body.get('code'):
                # Compatibility for previously installed clients; same factor rules.
                result = self.control.login(body.get('email'), body.get('password'), body.get('code'), agent) if staff else self.backend.login(body.get('email'), body.get('password'), body.get('code'))
            else:
                result = LoginFlow(self.backend).begin(body.get('email'), body.get('password'), agent, staff)
            if result.get('mfa_required'): return result, headers
            if not staff: return self.customer_session(result, agent, headers, env)
            token=result['token']
            return {'authenticated': True, 'csrf': self.csrf(token)}, headers + [self.cookie(token, True)]
        if not staff and method == 'POST' and action in ('signup', 'confirm-signup', 'resend-signup', 'recovery', 'reset'):
            from .account_lifecycle import AccountLifecycle
            lifecycle = AccountLifecycle(self.backend)
            if action == 'signup':
                # Same exact closed-test gate as Android registration.
                from .production import Application
                Application.check_registration(self, body)
                return lifecycle.signup(body.get('email'), body.get('password')), headers
            if action == 'resend-signup': return lifecycle.resend_signup(body.get('email')), headers
            if action == 'recovery': return self.backend.recover(body.get('email')), headers
            if action == 'reset': return self.backend.reset_password(body.get('email'), body.get('code'), body.get('password')), headers
            result = lifecycle.confirm_signup(body.get('email'), body.get('code'))
            self.backend.logout(result['token'])
            return {'verified': True, 'sign_in_required': True}, headers
        if not staff and action == 'plans' and method == 'GET':
            with self.backend.connect() as db: return entitlements.catalog(db), headers
        if not staff and action == 'notifications/receipt' and method == 'POST':
            # Exact same-origin POST above, authenticated by one expiring,
            # delivery-bound random token. The service worker has no CSRF token.
            return self.push.receipt(body), headers
        token = self.token(env, staff)
        actor = self.control.authenticate(token, env.get('HTTP_USER_AGENT', '')[:500]) if staff else self.account(token, env.get('HTTP_USER_AGENT', '')[:500])
        if not staff: actor['_auth_hash'] = token_hash(token)
        if staff: require(actor.user_id == admitted['user_id'], 'not_found', 404)
        if method == 'POST': require(hmac.compare_digest(env.get('HTTP_X_CSRF_TOKEN', ''), self.csrf(token)), 'csrf_invalid', 403)
        if not staff and action == 'control/access' and method == 'POST':
            return {'ticket': self.admission.issue(token, env.get('HTTP_USER_AGENT', '')[:500]), 'control_url': self.staff + '/admit', 'expires_in': 60}, headers
        if not staff and action == 'google' and method == 'GET':
            return self.google.status(actor), headers
        if not staff and action == 'google/link' and method == 'POST':
            binding=secrets.token_urlsafe(32)
            value=self.google.start('web', env.get('HTTP_USER_AGENT','')[:500], binding, actor=actor,
                password=body.get('password'), code=body.get('code'), auth_hash=token_hash(token))
            return value, headers + [self.google_cookie('binding', binding)]
        if not staff and action == 'google/reauth/start' and method == 'POST':
            binding=secrets.token_urlsafe(32)
            value=self.google.start('web', env.get('HTTP_USER_AGENT','')[:500], binding, actor=actor,
                auth_hash=token_hash(token), purpose='reauth')
            return value, headers + [self.google_cookie('binding', binding)]
        if not staff and action == 'google/unlink' and method == 'POST':
            return self.google.unlink(actor, body.get('password'), body.get('code')), headers + [self.cookie('', clear=True)]
        if action == 'session' and method == 'GET':
            if staff:
                from .staff_permissions import authority
                return dict({'staff_id': actor.id, 'user_id': actor.user_id, 'roles': list(actor.roles), 'csrf': self.csrf(token)}, **authority(actor)), headers
            return {'user_id': actor['id'], 'email': actor['email'], 'verified': bool(actor['verified']), 'csrf': self.csrf(token), 'control_available': self.admission.available(actor), 'record_recovery_available': bool(actor['verified']), 'interface_flags': self.control.flags(actor['id'])}, headers
        if action == 'logout' and method == 'POST':
            if staff: self.control.logout(token)
            else:
                with self.backend.transaction() as db:
                    row = db.execute('SELECT device_id FROM web_sessions WHERE hash=?', (token_hash(token),)).fetchone()
                    if row: self.backend._revoke_device(db, actor['id'], row['device_id'])
                    db.execute('DELETE FROM web_sessions WHERE hash=?', (token_hash(token),))
            return {'logged_out': True}, headers + [self.cookie('', staff, True)]
        query = parse_qs(env.get('QUERY_STRING', ''), keep_blank_values=(
            action in ('layout-order', 'recovery/purge-preview', 'recovery/purge')
            or action == 'pages' or action.startswith('pages/')
            or action == 'android-releases' or action.startswith('android-releases/')))
        if staff and method == 'GET' and action.startswith('pages/media/'):
            require(not env.get('QUERY_STRING'), 'not_found', 404)
            raw, mime = self.pages().preview_media(actor, action[len('pages/media/'):])
            headers[0] = ('Content-Type', mime)
            return raw, headers
        if staff: value = self.staff_action(actor, action, method, body, query)
        else: value = self.account_action(actor, action, method, body, query)
        return value, headers

    def google_cookie(self, name, value, clear=False):
        # Lax is required only for the short-lived cross-site OAuth return binding.
        # The customer session itself remains HttpOnly Secure SameSite=Strict.
        return ('Set-Cookie', '__Host-uladim_google_' + name + '=' + value + '; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=' + ('0' if clear else '300'))

    def google_cookie_value(self, env, name):
        cookie=SimpleCookie()
        try: cookie.load(env.get('HTTP_COOKIE',''))
        except Exception: return ''
        item=cookie.get('__Host-uladim_google_' + name)
        return item.value if item and len(item.value)==43 else ''

    def customer_session(self, result, agent, headers, env=None):
        # Recheck underlying session: a revoked intermediate result cannot create
        # a new browser session after a password change, deletion or device revoke.
        actor=self.backend.authenticate(result['token'])
        token, now=secrets.token_urlsafe(32), int(self.backend.clock())
        with self.backend.transaction() as db:
            # Replacing this browser's customer login invalidates its previous
            # Control admission without changing customer device/session rules.
            try: previous = self.token(env or {}, False)
            except Failure: previous = ''
            if previous:
                db.execute('DELETE FROM control_admissions WHERE parent_hash=?', (token_hash(previous),))
                db.execute('DELETE FROM control_handoffs WHERE parent_hash=?', (token_hash(previous),))
            db.execute('INSERT INTO web_sessions VALUES(?,?,?,?,?,?,?)', (token_hash(token), actor['id'], result['device_id'], now, now, now+2592000, token_hash(agent)))
            db.execute("UPDATE devices SET label='Web browser' WHERE id=?", (result['device_id'],))
        return {'authenticated':True, 'csrf':self.csrf(token)}, headers+[self.cookie(token)]

    def google_callback(self, env, headers):
        query=parse_qs(env.get('QUERY_STRING',''), keep_blank_values=True)
        binding=self.google_cookie_value(env,'binding')
        agent=env.get('HTTP_USER_AGENT','')[:500]
        def single(key):
            values=query.get(key,[])
            return values[0] if len(values)==1 else None
        try:
            value=self.google.finish(single('state'),'web',agent,binding,
                authorization_code=single('code'),cancelled=bool(single('error')))
        except Failure as error:
            value={'error':error.code}
        raw, now=secrets.token_urlsafe(32),int(self.backend.clock())
        with self.backend.transaction() as db:
            db.execute('DELETE FROM oauth_web_results WHERE expires_at<=?',(now,))
            db.execute('INSERT INTO oauth_web_results VALUES(?,?,?,?,?)',(token_hash(raw),token_hash(agent),token_hash(binding),self.backend.cipher.encrypt(json.dumps(value).encode()),now+120))
        # No token, challenge or code in the next URL, HTML or browser history.
        return b'', headers+[('X-ULADIM-Status','303'),('Location','/app?google=return'), self.google_cookie('result',raw)]

    def google_complete(self, env, headers):
        raw=self.google_cookie_value(env,'result')
        binding=self.google_cookie_value(env,'binding')
        agent=env.get('HTTP_USER_AGENT','')[:500]
        with self.backend.transaction() as db:
            row=db.execute('SELECT * FROM oauth_web_results WHERE hash=?',(token_hash(raw),)).fetchone()
            require(row and row['expires_at']>int(self.backend.clock())
                and hmac.compare_digest(row['agent_hash'],token_hash(agent))
                and hmac.compare_digest(row['binding_hash'],token_hash(binding)), 'google_invalid',401)
            value=json.loads(self.backend.cipher.decrypt(bytes(row['payload'])))
            db.execute('DELETE FROM oauth_web_results WHERE hash=?',(token_hash(raw),))
        # Use one clear header to avoid duplicate Set-Cookie collapse in WSGI.
        headers=headers+[self.google_cookie('result','',True)]
        if value.get('error'): return value,headers
        if value.get('mfa_required') or value.get('linked') or value.get('reauth_token'): return value,headers
        # customer_session adds a second Set-Cookie; Application must preserve them.
        return self.customer_session(value,agent,headers,env)

    def staff_action(self, actor, action, method, b, q):
        c = self.control
        if action == 'pages' or action.startswith('pages/'):
            return self.pages().handle(actor, action, method, b, q)
        if action == 'android-releases' or action.startswith('android-releases/'):
            return self.android().handle(actor, action, method, b, q)
        if action == 'permissions' and method == 'GET':
            from .staff_permissions import catalog
            return catalog(actor)
        if action in ('recovery-cases', 'recovery-case', 'recovery-cases/update'):
            from .recovery_cases import RecoveryCases
            cases = RecoveryCases(self.backend)
            if action == 'recovery-cases' and method == 'GET': return cases.listing(actor, q, True)
            if action == 'recovery-cases' and method == 'POST': return cases.create(actor, b)
            if action == 'recovery-case' and method == 'GET':
                require(set(q) == {'id'} and len(q['id']) == 1, 'invalid_fields')
                return cases.read(actor, q['id'][0], True)
            if action == 'recovery-cases/update' and method == 'POST': return cases.update(actor, b)
            raise Failure('not_found', 404)
        if action == 'referrals' and method == 'GET':
            from .referrals import Referrals
            return Referrals(self.backend, self.site).graph(actor, q)
        if action.startswith('announcements'):
            from .inbox import Inbox
            inbox = Inbox(self.backend)
            if action == 'announcements' and method == 'GET': return inbox.announcements(actor)
            if method == 'POST':
                if action == 'announcements': return inbox.compose(actor, b)
                if action == 'announcements/preview': return inbox.compose(actor, b, preview=True)
                if action == 'announcements/publish': return inbox.transition(actor, b)
                if action == 'announcements/cancel': return inbox.transition(actor, b, cancel=True)
            raise Failure('not_found', 404)

        if action == 'record-recovery' and method == 'GET':
            from .record_recovery import RecordRecovery
            require(set(q) <= {'before', 'user_id', 'state'} and all(len(v) == 1 for v in q.values()), 'invalid_fields')
            return RecordRecovery(self.backend).requests(actor, q.get('before', [None])[0], True,
                q.get('user_id', [None])[0], q.get('state', [None])[0])
        if action == 'record-recovery/approve' and method == 'POST':
            from .record_recovery import RecordRecovery
            return RecordRecovery(self.backend).approve(actor, b)
        if method == 'GET':
            if action == 'applications':
                from .early_access import EarlyAccess
                return EarlyAccess(self.backend).list(actor, c, q.get('state', ['pending'])[0], q.get('before', [None])[0])
            if action == 'dashboard': return c.dashboard(actor)
            if action == 'users':
                require(set(q) <= {'search', 'before', 'limit'} and all(len(v) == 1 for v in q.values()), 'invalid_fields')
                raw_limit = q.get('limit', ['50'])[0]
                require(raw_limit.isdecimal() and len(raw_limit) <= 3, 'invalid_cursor')
                return c.users(actor, q.get('search', [''])[0], q.get('before', [None])[0], int(raw_limit))
            if action == 'user': return c.user(actor, q.get('id', [''])[0])
            if action == 'staff': return c.staff_list(actor)
            if action == 'audit': return c.audit_log(actor, int(q['before'][0]) if 'before' in q else None)
            if action == 'support': return self.support.list(actor, True)
            if action == 'thread': return self.support.read(actor, q.get('id', [''])[0], True)
            if action == 'catalog':
                c.require(actor, 'plans.grant')
                with self.backend.connect() as db: return entitlements.catalog(db)
            if action == 'flags':
                c.require(actor, 'flags.manage')
                return c.flags()
        elif method == 'POST':
            if action == 'applications/decide':
                from .early_access import EarlyAccess
                return EarlyAccess(self.backend).decide(actor, c, b.get('id'), b.get('decision'), b.get('revision'), b.get('reason'))
            if action == 'user/recovery': return c.request_recovery(actor, b.get('user_id'), b.get('reason'))
            if action == 'moderate': return c.moderate(actor, b.get('user_id'), b.get('service'), b.get('until_at'), b.get('reason'))
            if action == 'grant': return c.give_access(actor, b.get('user_id'), b.get('tier'), b.get('source'), b.get('valid_until'), b.get('reason'))
            if action == 'revoke-grant': return c.revoke_access(actor, b.get('grant_id'), b.get('reason'))
            if action == 'override': return c.override(actor, b.get('user_id'), b.get('feature'), b.get('enabled'), b.get('valid_until'), b.get('reason'))
            if action == 'catalog': return c.update_catalog(actor, b.get('catalog'), b.get('reason'))
            if action == 'staff/invite': return c.invite_staff(actor, b.get('email'), b.get('roles'), b.get('reason'), b.get('denied_permissions'))
            if action == 'staff/update': return c.update_staff(actor, b.get('staff_id'), b.get('roles'), b.get('active'), b.get('revision'), b.get('reason'), b.get('denied_permissions'))
            if action == 'support/reply': return self.support.reply(actor, b.get('ticket_id'), b.get('message'), b.get('state', 'waiting'), True)
            if action == 'support/triage': return self.support.triage(actor, b.get('ticket_id'), b.get('priority'), b.get('state'), b.get('reason'))
            if action == 'flags/preview': return c.preview_flag(actor, b.get('name'), b.get('enabled'), b.get('rollout'), b.get('revision'), b.get('reason'))
            if action == 'flags/commit': return c.commit_flag(actor, b.get('proposal_id'), b.get('digest'))
        raise Failure('not_found', 404)

    def account_action(self, actor, action, method, b, q):
        if action == 'identity' and method in ('GET', 'POST'):
            from .account_identity import AccountIdentity
            require(not q, 'invalid_fields')
            return AccountIdentity(self.backend).identity(actor, b if method == 'POST' else None)
        if action in ('recovery-cases', 'recovery-case', 'recovery-cases/confirm'):
            from .recovery_cases import RecoveryCases
            cases = RecoveryCases(self.backend)
            if action == 'recovery-cases' and method == 'GET': return cases.listing(actor, q)
            if action == 'recovery-case' and method == 'GET':
                require(set(q) == {'id'} and len(q['id']) == 1, 'invalid_fields')
                return cases.read(actor, q['id'][0])
            if action == 'recovery-cases/confirm' and method == 'POST':
                require(not q, 'invalid_fields')
                return cases.confirm(actor, b)
            raise Failure('not_found', 404)
        if action == 'layout-order':
            from .layout_preferences import LayoutPreferences
            layouts = LayoutPreferences(self.backend)
            if method == 'GET':
                require(set(q) == {'workspace', 'kind'} and all(len(values) == 1 for values in q.values()), 'invalid_fields')
                return layouts.get(actor, q['workspace'][0], q['kind'][0])
            if method == 'POST':
                require(not q and isinstance(b, dict) and {'workspace_id', 'kind', 'order'} <= set(b) <= {'workspace_id', 'kind', 'order', 'revision'}, 'invalid_fields')
                return layouts.put(actor, b['workspace_id'], b['kind'], b['order'], b.get('revision'))
            raise Failure('not_found', 404)
        if action == 'task-reminders':
            from .task_reminders import TaskReminders
            reminders = TaskReminders(self.backend)
            if method == 'GET':
                require('workspace' in q and set(q) <= {'workspace', 'task_id'} and all(len(values) == 1 for values in q.values()), 'invalid_fields')
                workspace = q['workspace'][0]
                return reminders.get(actor, workspace, q['task_id'][0]) if 'task_id' in q else reminders.list(actor, workspace)
            if method == 'POST':
                require(not q, 'invalid_fields')
                return reminders.save(actor, b)
            raise Failure('not_found', 404)
        if action.startswith('referrals'):
            from .referrals import Referrals
            referrals = Referrals(self.backend, self.site)
            if action == 'referrals' and method == 'GET': return referrals.summary(actor, q)
            require(not q, 'invalid_fields')
            if action == 'referrals/alias' and method == 'GET': return referrals.alias(actor)
            if method == 'POST':
                if action == 'referrals/code': return referrals.create_code(actor, b)
                if action == 'referrals/claim': return referrals.claim(actor, b)
                if action == 'referrals/alias': return referrals.alias(actor, b)
            raise Failure('not_found', 404)
        from .account_lifecycle import AccountLifecycle
        lifecycle = AccountLifecycle(self.backend)
        from .customer_mfa import CustomerMFA
        mfa=CustomerMFA(self.backend)
        if action.startswith('inbox'):
            from .inbox import Inbox
            inbox = Inbox(self.backend)
            if action == 'inbox/settings' and method in ('GET', 'POST'): return inbox.settings(actor, b if method == 'POST' else None)
            if action == 'inbox' and method == 'GET': return inbox.list(actor, q.get('before', [None])[0], int(q.get('limit', ['50'])[0]))
            if method == 'POST' and action in ('inbox/read', 'inbox/dismiss', 'inbox/presented'):
                return inbox.mutate(actor, action.rsplit('/', 1)[-1], b)
            raise Failure('not_found', 404)

        if action == 'trash' and method == 'GET':
            from .record_recovery import RecordRecovery
            return RecordRecovery(self.backend).trash(actor, q.get('workspace', [''])[0], q.get('before', [None])[0], q.get('record', [None])[0])
        if action.startswith('recovery/'):
            if action in ('recovery/purge-preview', 'recovery/purge'):
                from .record_erasure import RecordErasure
                erasure = RecordErasure(self.backend)
                if action == 'recovery/purge-preview' and method == 'GET':
                    require(set(q) == {'record'} and len(q['record']) == 1, 'invalid_fields')
                    return erasure.preview(actor, q['record'][0])
                if action == 'recovery/purge' and method == 'POST':
                    require(not q, 'invalid_fields')
                    return erasure.purge(actor, b)
                raise Failure('not_found', 404)
            from .record_recovery import RecordRecovery
            recovery = RecordRecovery(self.backend)
            if action == 'recovery/requests' and method == 'GET': return recovery.requests(actor, q.get('before', [None])[0])
            handlers = {'recovery/request': recovery.request, 'recovery/prepare': recovery.prepare, 'recovery/commit': recovery.commit, 'recovery/cancel': recovery.cancel}
            if method == 'POST' and action in handlers: return handlers[action](actor, b)
        if action == 'notifications' and method == 'GET': return self.push.status(actor)
        if method == 'POST':
            if action == 'notifications/prepare': return self.push.prepare(actor)
            if action == 'notifications/subscribe': return self.push.subscribe(actor, b)
            if action == 'notifications/unsubscribe': return self.push.unsubscribe(actor)
            if action == 'notifications/test': return self.push.test(actor)
        if method == 'GET':
            if action == 'spaces': return {'spaces': self.backend.spaces(actor)}
            if action == 'roster': return self.backend.roster(actor, q.get('workspace', [''])[0])
            if action == 'sync': return self.backend.pull_incremental(actor, q.get('workspace', [''])[0], int(q.get('cursor', ['0'])[0]), q.get('epoch', [''])[0])
            if action == 'mfa':return mfa.status(actor)
            if action == 'deletion':
                value=lifecycle.deletion_status(actor)
                value['google_reauth_available']=bool(value['google_linked'] and self.google.web_enabled)
                return value
            if action == 'entitlements':
                with self.backend.connect() as db: return entitlements.resolve(db, actor['id'], int(self.backend.clock()))
            if action == 'devices':
                result = self.backend.list_devices(actor, '')
                for device in result['devices']:
                    device['current'] = device['id'] == actor['device_id']
                return result
            if action == 'support': return self.support.list(actor)
            if action == 'thread': return self.support.read(actor, q.get('id', [''])[0])
        elif method == 'POST':
            if action == 'sync': return self.backend.batch(actor, b.get('workspace_id'), b.get('operations'))
            if action == 'family': return self.backend.family(actor, b)
            if action == 'invitations/accept': return self.backend.accept(actor, b)
            if action == 'staff/enrollment':
                from .owner_enrollment import OwnerEnrollment
                if b.get('owner'): return OwnerEnrollment(self.backend).begin(actor, b.get('invitation'), b.get('password'))
                return self.control.prepare_enrollment(actor, b.get('invitation'), b.get('password'))
            if action == 'staff/confirm':
                from .owner_enrollment import OwnerEnrollment
                if b.get('owner'): return OwnerEnrollment(self.backend).finish(actor, b.get('enrollment'), b.get('code'))
                return self.control.finish_enrollment(actor, b.get('enrollment'), b.get('code'))
            if action == 'transfer':return lifecycle.transfer(actor,b.get('workspace_id'),b.get('user_id'),b.get('password'), b.get('reauth_token'), b.get('code'))
            if action == 'accept-transfer':return lifecycle.accept_transfer(actor,b.get('transfer_id'),b.get('password'), b.get('reauth_token'), b.get('code'))
            if action == 'mfa/begin':return mfa.begin(actor,b.get('password'))
            if action == 'mfa/enable':return mfa.enable(actor,b.get('password'),b.get('enrollment'),b.get('code'))
            if action == 'mfa/disable':return mfa.disable(actor,b.get('password'),b.get('code'))
            if action == 'deletion': return lifecycle.request_deletion(actor, b.get('password'), b.get('confirmation'), b.get('reauth_token'), b.get('code'))
            if action == 'cancel-deletion': return lifecycle.cancel_deletion(actor, b.get('password'), b.get('reauth_token'), b.get('code'))
            if action == 'close-family': return lifecycle.close_family(actor, b.get('workspace_id'), b.get('revision'), b.get('password'), b.get('confirmation'), b.get('reauth_token'), b.get('code'))
            if action == 'email': return lifecycle.change_email(actor, b.get('email'), b.get('password'))
            if action == 'confirm-email': return lifecycle.confirm_email(actor, b.get('code'), b.get('password'))
            if action == 'password': return self.backend.password(actor, b.get('old_password'), b.get('new_password'))
            if action == 'devices/revoke': return self.backend.revoke_device(actor, b.get('device_id'), b.get('password'))
            if action == 'logout-all': return self.backend.revoke_all(actor, b.get('password'))
            if action == 'support': return self.support.create(actor, b.get('category'), b.get('subject'), b.get('message'))
            if action == 'support/reply': return self.support.reply(actor, b.get('ticket_id'), b.get('message'), b.get('state', 'open'))
        raise Failure('not_found', 404)

    def app_asset(self, path, headers):
        """An explicit static allowlist; no API, cookie or user data is cached."""
        import mimetypes
        root = ASSETS / 'app'
        relative = 'index.html' if path in ('/app', '/app/') else ('sw.js' if path == '/app/sw.js' else path[len('/app/assets/'):])
        allowed = {'index.html', 'app.js', 'domain.js', 'money.js', 'statement-formats.js', 'statement-pdf.js', 'statement-xlsx.js', 'personal-import.js', 'pdf-lib.mjs', 'pdf-worker.mjs', 'import.js', 'statement-worker.js', 'app.css', 'auth-texture.webp', 'manifest.webmanifest', 'icon-192.png', 'icon-512.png', 'apple-touch-icon.png', 'offline.html', 'offline.js', 'sw.js', 'locales.json'}
        allowed.update({'inbox.js', 'inbox.css'})
        allowed.update({'password-policy.js', 'appearance-intensity.js', 'install.js', 'field-menu.js', 'field-menu.css', 'appearance-boot.js'})
        allowed.update({'task-reminders.js', 'layout-order.js', 'referrals.js', 'referrals.css'})
        allowed.update({'i18n.js', 'translations.json', 'record-erasure.js'})

        allowed.update({'recovery.js', 'recovery.css'})
        allowed.update({'account-deletion.js', 'account-deletion.css'})
        require(relative in allowed and (root / relative).is_file(), 'not_found', 404)
        mime = {'.js': 'text/javascript', '.mjs': 'text/javascript', '.webmanifest': 'application/manifest+json', '.json': 'application/json'}.get(Path(relative).suffix, mimetypes.guess_type(relative)[0] or 'application/octet-stream')
        result = dict(headers)
        result.update({'Content-Type': mime, 'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex, nofollow',
                       'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; manifest-src 'self'; worker-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"})
        result['Content-Security-Policy'] = result['Content-Security-Policy'].replace("form-action 'self'", "form-action 'self' " + self.staff)
        # Cross-origin same-site form handoff must carry the exact site Origin.
        # no-referrer serializes that Origin as null in Chromium; retain origin
        # only, never a path/query, for the app document.
        if relative == 'index.html': result['Referrer-Policy'] = 'strict-origin'
        if relative == 'sw.js': result['Service-Worker-Allowed'] = '/app'
        return (root / relative).read_bytes(), list(result.items())

