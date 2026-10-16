"""Same-origin web surfaces with separate customer/staff cookies and server-side authority."""
import hashlib
import hmac
import json
import secrets
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .control import Control
from .support import Support
from .service import Failure, require, token_hash
from . import entitlements

ASSETS = Path(__file__).with_name('webassets')
CONTROL_COOKIE = '__Host-uladim_control'
ACCOUNT_COOKIE = '__Host-uladim_account'


class Web:
    def __init__(self, backend, settings):
        self.backend, self.settings = backend, settings
        self.control = Control(backend)
        self.support = Support(backend, self.control)
        self.site = getattr(settings, 'site_origin', 'https://getuladim.space')
        self.staff = getattr(settings, 'control_origin', 'https://control.getuladim.space')

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
            return {'id': row['user_id'], 'email': row['email'], 'verified': row['verified']}

    def request(self, env, body):
        path, method = env.get('PATH_INFO', ''), env.get('REQUEST_METHOD', '')
        staff = env.get('HTTP_HOST', '') == urlsplit(self.staff).netloc
        origin = self.staff if staff else self.site
        headers = [('Content-Type', 'application/json; charset=utf-8'), ('Cache-Control', 'no-store'), ('X-Robots-Tag', 'noindex, nofollow' if staff or path.startswith('/account') else 'index, follow'),
                   ('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"), ('X-Content-Type-Options', 'nosniff'), ('Referrer-Policy', 'no-referrer')]
        if method == 'GET' and path in ('/assets/web.js', '/assets/web.css'):
            headers[0] = ('Content-Type', 'text/javascript; charset=utf-8' if path.endswith('.js') else 'text/css; charset=utf-8')
            return (ASSETS / path.rsplit('/', 1)[-1]).read_bytes(), headers
        prefix = '/control/api/' if staff else '/account/api/'
        if method == 'GET' and not path.startswith(prefix):
            allowed = {'/'} if staff else {'/', '/account', '/plans', '/privacy', '/terms', '/support', '/delete-account', '/status', '/download', '/faq'}
            require(path in allowed, 'not_found', 404)
            page = (ASSETS / 'index.html').read_text().replace('__SURFACE__', 'control' if staff else 'site')
            return page.encode(), [('Content-Type', 'text/html; charset=utf-8')] + headers[1:]
        require(path.startswith(prefix), 'not_found', 404)
        action = path[len(prefix):]
        if method == 'POST':
            require(env.get('HTTP_ORIGIN') == origin, 'origin_forbidden', 403)
        if action == 'login' and method == 'POST':
            agent = env.get('HTTP_USER_AGENT', '')[:500]
            if staff:
                result = self.control.login(body.get('email'), body.get('password'), body.get('code'), agent)
                token = result['token']
            else:
                result = self.backend.login(body.get('email'), body.get('password'), body.get('code'))
                if result.get('mfa_required'):return result,headers
                token, now = secrets.token_urlsafe(32), int(self.backend.clock())
                with self.backend.transaction() as db:
                    db.execute('INSERT INTO web_sessions VALUES(?,?,?,?,?,?,?)', (token_hash(token), result['user_id'], result['device_id'], now, now, now + 2592000, token_hash(agent)))
                    db.execute("UPDATE devices SET label='Web browser' WHERE id=?", (result['device_id'],))
            return {'authenticated': True, 'csrf': self.csrf(token)}, headers + [self.cookie(token, staff)]
        if not staff and method == 'POST' and action in ('signup', 'confirm-signup', 'recovery', 'reset'):
            from .account_lifecycle import AccountLifecycle
            lifecycle = AccountLifecycle(self.backend)
            if action == 'signup':
                # Same exact closed-test gate as Android registration.
                from .production import Application
                Application.check_registration(self, body)
                return lifecycle.signup(body.get('email'), body.get('password')), headers
            if action == 'recovery': return self.backend.recover(body.get('email')), headers
            if action == 'reset': return self.backend.reset_password(body.get('email'), body.get('code'), body.get('password')), headers
            result = lifecycle.confirm_signup(body.get('email'), body.get('code'))
            self.backend.logout(result['token'])
            return {'verified': True, 'sign_in_required': True}, headers
        if not staff and action == 'plans' and method == 'GET':
            with self.backend.connect() as db: return entitlements.catalog(db), headers
        token = self.token(env, staff)
        actor = self.control.authenticate(token, env.get('HTTP_USER_AGENT', '')[:500]) if staff else self.account(token, env.get('HTTP_USER_AGENT', '')[:500])
        if method == 'POST': require(hmac.compare_digest(env.get('HTTP_X_CSRF_TOKEN', ''), self.csrf(token)), 'csrf_invalid', 403)
        if action == 'session' and method == 'GET':
            return ({'staff_id': actor.id, 'roles': list(actor.roles), 'permissions': sorted(actor.permissions), 'csrf': self.csrf(token)} if staff else {'user_id': actor['id'], 'email': actor['email'], 'verified': bool(actor['verified']), 'csrf': self.csrf(token)}), headers
        if action == 'logout' and method == 'POST':
            if staff: self.control.logout(token)
            else:
                with self.backend.transaction() as db:
                    row = db.execute('SELECT device_id FROM web_sessions WHERE hash=?', (token_hash(token),)).fetchone()
                    if row: self.backend._revoke_device(db, actor['id'], row['device_id'])
                    db.execute('DELETE FROM web_sessions WHERE hash=?', (token_hash(token),))
            return {'logged_out': True}, headers + [self.cookie('', staff, True)]
        query = parse_qs(env.get('QUERY_STRING', ''))
        if staff: value = self.staff_action(actor, action, method, body, query)
        else: value = self.account_action(actor, action, method, body, query)
        return value, headers

    def staff_action(self, actor, action, method, b, q):
        c = self.control
        if method == 'GET':
            if action == 'dashboard': return c.dashboard(actor)
            if action == 'users': return c.users(actor, q.get('search', [''])[0])
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
            if action == 'moderate': return c.moderate(actor, b.get('user_id'), b.get('service'), b.get('until_at'), b.get('reason'))
            if action == 'grant': return c.give_access(actor, b.get('user_id'), b.get('tier'), b.get('source'), b.get('valid_until'), b.get('reason'))
            if action == 'revoke-grant': return c.revoke_access(actor, b.get('grant_id'), b.get('reason'))
            if action == 'override': return c.override(actor, b.get('user_id'), b.get('feature'), b.get('enabled'), b.get('valid_until'), b.get('reason'))
            if action == 'catalog': return c.update_catalog(actor, b.get('catalog'), b.get('reason'))
            if action == 'staff/invite': return c.invite_staff(actor, b.get('email'), b.get('roles'), b.get('reason'))
            if action == 'staff/update': return c.update_staff(actor, b.get('staff_id'), b.get('roles'), b.get('active'), b.get('revision'), b.get('reason'))
            if action == 'support/reply': return self.support.reply(actor, b.get('ticket_id'), b.get('message'), b.get('state', 'waiting'), True)
            if action == 'support/triage': return self.support.triage(actor, b.get('ticket_id'), b.get('priority'), b.get('state'), b.get('reason'))
            if action == 'flags/preview': return c.preview_flag(actor, b.get('name'), b.get('enabled'), b.get('rollout'), b.get('revision'), b.get('reason'))
            if action == 'flags/commit': return c.commit_flag(actor, b.get('proposal_id'), b.get('digest'))
        raise Failure('not_found', 404)

    def account_action(self, actor, action, method, b, q):
        from .account_lifecycle import AccountLifecycle
        lifecycle = AccountLifecycle(self.backend)
        from .customer_mfa import CustomerMFA
        mfa=CustomerMFA(self.backend)
        if method == 'GET':
            if action == 'mfa':return mfa.status(actor)
            if action == 'deletion': return lifecycle.deletion_status(actor)
            if action == 'entitlements':
                with self.backend.connect() as db: return entitlements.resolve(db, actor['id'], int(self.backend.clock()))
            if action == 'devices': return self.backend.list_devices(actor, '')
            if action == 'support': return self.support.list(actor)
            if action == 'thread': return self.support.read(actor, q.get('id', [''])[0])
        elif method == 'POST':
            if action == 'transfer':return lifecycle.transfer(actor,b.get('workspace_id'),b.get('user_id'),b.get('password'))
            if action == 'accept-transfer':return lifecycle.accept_transfer(actor,b.get('transfer_id'),b.get('password'))
            if action == 'mfa/begin':return mfa.begin(actor,b.get('password'))
            if action == 'mfa/enable':return mfa.enable(actor,b.get('password'),b.get('enrollment'),b.get('code'))
            if action == 'mfa/disable':return mfa.disable(actor,b.get('password'),b.get('code'))
            if action == 'deletion': return lifecycle.request_deletion(actor, b.get('password'), b.get('confirmation'))
            if action == 'cancel-deletion': return lifecycle.cancel_deletion(actor, b.get('password'))
            if action == 'email': return lifecycle.change_email(actor, b.get('email'), b.get('password'))
            if action == 'confirm-email': return lifecycle.confirm_email(actor, b.get('code'), b.get('password'))
            if action == 'password': return self.backend.password(actor, b.get('old_password'), b.get('new_password'))
            if action == 'devices/revoke': return self.backend.revoke_device(actor, b.get('device_id'), b.get('password'))
            if action == 'logout-all': return self.backend.revoke_all(actor, b.get('password'))
            if action == 'support': return self.support.create(actor, b.get('category'), b.get('subject'), b.get('message'))
            if action == 'support/reply': return self.support.reply(actor, b.get('ticket_id'), b.get('message'), b.get('state', 'open'))
        raise Failure('not_found', 404)
