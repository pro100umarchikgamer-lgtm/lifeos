"""Separate MFA-protected staff authority. No user-content inspection or impersonation."""
from dataclasses import dataclass
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import struct
import uuid

from .service import Failure, canonical, identifier, require, text, token_hash
from . import entitlements

ROLE_RANK = {'owner': 100, 'admin': 80, 'billing_manager': 40, 'moderator': 30, 'support': 20, 'auditor': 10}
ROLE_PERMISSIONS = {
    'owner': {'dashboard.read', 'users.read', 'users.moderate', 'staff.manage', 'plans.grant', 'plans.catalog', 'support.read', 'support.reply', 'audit.read', 'flags.manage'},
    'admin': {'dashboard.read', 'users.read', 'users.moderate', 'staff.manage', 'plans.grant', 'support.read', 'support.reply', 'audit.read', 'flags.manage'},
    'billing_manager': {'users.read', 'plans.grant', 'audit.read'},
    'moderator': {'users.read', 'users.moderate', 'support.read', 'support.reply'},
    'support': {'users.read', 'support.read', 'support.reply'},
    'auditor': {'dashboard.read', 'audit.read'},
}
SAFE_FLAGS = {'compact_onboarding', 'chart_styles', 'support_entry'}


def totp(secret, counter):
    key = base64.b32decode(secret, casefold=False)
    digest = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 15
    return str((struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7fffffff) % 1000000).zfill(6)


def scrub(value):
    return re.sub(r'(?i)(bearer\s+|(?:password|token|secret|authorization)\s*[:=]\s*)[^\s,;]+', r'\1[redacted]', value)


@dataclass(frozen=True)
class StaffPrincipal:
    id: str
    user_id: str
    roles: tuple

    @property
    def permissions(self):
        return set().union(*(ROLE_PERMISSIONS[role] for role in self.roles))

    @property
    def rank(self):
        return max(ROLE_RANK[role] for role in self.roles)


class Control:
    def __init__(self, backend):
        self.backend = backend

    def require(self, actor, permission):
        require(isinstance(actor, StaffPrincipal) and permission in actor.permissions, 'staff_forbidden', 403)

    def audit(self, db, actor, subject, action, before, after, reason):
        text(reason, 500)
        # Diffs are assembled by handlers from explicit safe fields, never from a
        # request body, credential structure, financial record or support message.
        for obj in [before, after]:
            require(isinstance(obj, dict) and not ({'password', 'token', 'secret', 'body', 'mfa_secret'} & set(obj)))
        previous = db.execute('SELECT entry_hash FROM control_audit ORDER BY seq DESC LIMIT 1').fetchone()
        prior_hash = previous['entry_hash'] if previous else '0' * 64
        event = {'id': str(uuid.uuid4()), 'actor_id': actor.id if isinstance(actor, StaffPrincipal) else actor,
                 'subject_id': subject, 'action': action, 'before': before, 'after': after,
                 'reason': scrub(reason), 'created_at': int(self.backend.clock()), 'request_id': str(uuid.uuid4())}
        digest = token_hash(prior_hash + canonical(event))
        db.execute('INSERT INTO control_audit(id,actor_id,subject_id,action,before_value,after_value,reason,created_at,request_id,previous_hash,entry_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                   (event['id'], event['actor_id'], subject, action, canonical(before), canonical(after), event['reason'], event['created_at'], event['request_id'], prior_hash, digest))

    def _cipher(self):
        require(hasattr(self.backend, 'cipher'), 'staff_encryption_unconfigured', 503)
        return self.backend.cipher

    def bootstrap(self, email):
        """Operator-only CLI entry. Not exposed by any HTTP route."""
        cipher = self._cipher()
        secret = base64.b32encode(secrets.token_bytes(20)).decode()
        recovery = [secrets.token_urlsafe(24) for _ in range(8)]
        now = int(self.backend.clock())
        with self.backend.transaction() as db:
            require(db.execute("SELECT 1 FROM staff WHERE roles LIKE ?", ('%"owner"%',)).fetchone() is None, 'owner_already_exists', 409)
            user = db.execute('SELECT id FROM users WHERE email=? AND verified=1', (text(email, 254).casefold(),)).fetchone()
            require(user is not None, 'verified_account_required', 409)
            self.backend._account_available(db, user['id'])
            sid = str(uuid.uuid4())
            db.execute('INSERT INTO staff(id,user_id,roles,mfa_secret,created_at) VALUES(?,?,?,?,?)', (sid, user['id'], '["owner"]', cipher.encrypt(secret.encode()), now))
            for code in recovery:
                db.execute('INSERT INTO staff_recovery VALUES(?,?,0)', (token_hash(code), sid))
            self.audit(db, 'operator-cli', user['id'], 'owner.bootstrap', {}, {'staff_id': sid}, 'First owner enrollment; MFA required')
        return {'staff_id': sid, 'totp_secret': secret, 'recovery_codes': recovery}

    def _attempt(self, email):
        now = int(self.backend.clock())
        key = token_hash('control-login:' + email)
        with self.backend.transaction() as db:
            row = db.execute('SELECT * FROM auth_limits WHERE key=?', (key,)).fetchone()
            require(row is None or row['until_at'] <= now or row['count'] < 10, 'rate_limited', 429)
            count = row['count'] + 1 if row and row['until_at'] > now else 1
            db.execute('INSERT INTO auth_limits VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET count=excluded.count,until_at=excluded.until_at', (key, count, now + 900))

    def login(self, email, password, code, agent):
        require(isinstance(email, str) and len(email) <= 254 and isinstance(password, str) and len(password) <= 256)
        self._attempt(email.casefold())
        now = int(self.backend.clock())
        with self.backend.transaction() as db:
            row = db.execute('SELECT s.*,u.email,u.password_hash,u.salt,u.verified FROM staff s JOIN users u ON u.id=s.user_id WHERE u.email=?', (email.casefold(),)).fetchone()
            salt = bytes.fromhex(row['salt']) if row else bytes(16)
            digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000).hex()
            valid = row and row['active'] == 1 and row['verified'] == 1 and hmac.compare_digest(digest, row['password_hash'])
            require(valid, 'invalid_credentials', 401)
            self.backend._account_available(db, row['user_id'])
            require(isinstance(code, str) and re.fullmatch('[0-9]{6}', code), 'invalid_credentials', 401)
            secret = self._cipher().decrypt(bytes(row['mfa_secret'])).decode()
            counters = [counter for counter in range(now // 30 - 1, now // 30 + 2) if counter >= 0 and counter > row['last_counter'] and hmac.compare_digest(totp(secret, counter), code)]
            require(bool(counters), 'invalid_credentials', 401)
            db.execute('UPDATE staff SET last_counter=? WHERE id=?', (max(counters), row['id']))
            raw = secrets.token_urlsafe(32)
            db.execute('INSERT INTO control_sessions VALUES(?,?,?,?,?,?)', (token_hash(raw), row['id'], now, now, now + 8 * 3600, token_hash(text(agent, 500))))
            actor = StaffPrincipal(row['id'], row['user_id'], tuple(json.loads(row['roles'])))
            self.audit(db, actor, row['user_id'], 'staff.login', {}, {}, 'MFA session established')
        return {'token': raw, 'expires_in': 8 * 3600, 'idle_seconds': 900}

    def authenticate(self, token, agent):
        require(isinstance(token, str) and len(token) == 43 and isinstance(agent, str), 'staff_unauthorized', 401)
        now = int(self.backend.clock())
        with self.backend.transaction() as db:
            row = db.execute('SELECT s.*,c.agent_hash,c.created_at AS login_at,c.last_seen_at,c.expires_at FROM control_sessions c JOIN staff s ON s.id=c.staff_id WHERE c.hash=?', (token_hash(token),)).fetchone()
            require(row is not None and row['active'] == 1 and row['expires_at'] > now and row['last_seen_at'] > now - 900 and hmac.compare_digest(row['agent_hash'], token_hash(agent)), 'staff_unauthorized', 401)
            self.backend._account_available(db, row['user_id'])
            db.execute('UPDATE control_sessions SET last_seen_at=? WHERE hash=?', (now, token_hash(token)))
        return StaffPrincipal(row['id'], row['user_id'], tuple(json.loads(row['roles'])))

    def logout(self, raw):
        with self.backend.transaction() as db:
            db.execute('DELETE FROM control_sessions WHERE hash=?', (token_hash(raw),))
        return {'signed_out': True}

    def dashboard(self, actor):
        self.require(actor, 'dashboard.read')
        now = int(self.backend.clock())
        with self.backend.connect() as db:
            users = db.execute('SELECT COUNT(*) AS n FROM users u LEFT JOIN account_state a ON a.user_id=u.id WHERE COALESCE(a.deleted_at,0)=0').fetchone()['n']
            recent = db.execute('SELECT COUNT(*) AS n FROM users WHERE created_at>?', (now - 86400,)).fetchone()['n']
            active = db.execute('SELECT COUNT(DISTINCT user_id) AS n FROM devices WHERE revoked_at=0 AND last_seen_at>?', (now - 86400,)).fetchone()['n']
            queue = db.execute('SELECT COUNT(*) AS n FROM email_jobs WHERE delivered_at IS NULL AND expires_at>?', (now,)).fetchone()['n'] if hasattr(db, 'raw') else None
            pending = db.execute("SELECT COUNT(*) AS n FROM support_tickets WHERE state NOT IN ('resolved','closed')").fetchone()['n']
        disk = os.statvfs('/')
        return {'accounts': users, 'new_24h': recent, 'active_24h': active, 'mail_pending': queue, 'support_pending': pending,
                'load_1m': os.getloadavg()[0], 'disk_free_bytes': disk.f_bavail * disk.f_frsize,
                'api_latency_ms': None, 'sync_errors': None, 'backup_last_success': None,
                'metrics_scope': 'current_runtime', 'payments_enabled': False}

    def users(self, actor, query=''):
        self.require(actor, 'users.read')
        require(isinstance(query, str) and len(query) <= 254)
        pattern = '%' + query.casefold().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        with self.backend.connect() as db:
            rows = db.execute("SELECT u.id,u.email,u.verified,u.created_at,COALESCE(a.disabled_until,0) AS disabled_until,COALESCE(a.deleted_at,0) AS deleted_at FROM users u LEFT JOIN account_state a ON a.user_id=u.id WHERE (LOWER(u.email) LIKE ? ESCAPE '\\' OR u.id=?) ORDER BY u.created_at DESC,u.id LIMIT 50", (pattern, query)).fetchall()
        return {'users': [dict(row) for row in rows], 'limit': 50}

    def user(self, actor, uid):
        self.require(actor, 'users.read')
        identifier(uid)
        with self.backend.connect() as db:
            row = db.execute('SELECT id,email,verified,created_at FROM users WHERE id=?', (uid,)).fetchone()
            require(row is not None, 'not_found', 404)
            devices = db.execute('SELECT id,label,created_at,last_seen_at,revoked_at FROM devices WHERE user_id=? ORDER BY created_at DESC LIMIT 30', (uid,)).fetchall()
            access = entitlements.resolve(db, uid, int(self.backend.clock()))
        return {'user': dict(row), 'devices': [dict(device) for device in devices], 'entitlements': access}

    def _target_rank(self, db, actor, uid):
        target = db.execute('SELECT roles FROM staff WHERE user_id=?', (uid,)).fetchone()
        if target:
            require(uid != actor.user_id and max(ROLE_RANK[r] for r in json.loads(target['roles'])) < actor.rank, 'staff_hierarchy', 403)

    def moderate(self, actor, uid, service, until, reason):
        self.require(actor, 'users.moderate')
        identifier(uid)
        require(service in {'account', 'family_write', 'premium', 'support_write'})
        now = int(self.backend.clock())
        require(type(until) is int and (until == 0 or now < until <= now + 30 * 86400))
        text(reason, 500)
        with self.backend.transaction() as db:
            require(db.execute('SELECT 1 FROM users WHERE id=?', (uid,)).fetchone() is not None, 'not_found', 404)
            self._target_rank(db, actor, uid)
            if service == 'account':
                previous = db.execute('SELECT disabled_until FROM account_state WHERE user_id=?', (uid,)).fetchone()
                before = {'disabled_until': previous['disabled_until'] if previous else 0}
                db.execute('INSERT INTO account_state VALUES(?,?,0) ON CONFLICT(user_id) DO UPDATE SET disabled_until=excluded.disabled_until', (uid, until))
                if until: self.backend.revoke_all_in(db, uid)
            else:
                previous = db.execute('SELECT until_at FROM service_holds WHERE user_id=? AND service=?', (uid, service)).fetchone()
                before = {'until_at': previous['until_at'] if previous else 0}
                db.execute('INSERT INTO service_holds VALUES(?,?,?,?,?) ON CONFLICT(user_id,service) DO UPDATE SET until_at=excluded.until_at,reason=excluded.reason,actor_id=excluded.actor_id', (uid, service, until, scrub(reason), actor.id))
            self.audit(db, actor, uid, 'user.moderate.' + service, before, {'until_at': until}, reason)
        return {'updated': True, 'records_deleted': False}

    def give_access(self, actor, uid, tier, source, until, reason):
        self.require(actor, 'plans.grant')
        with self.backend.transaction() as db:
            result = entitlements.grant(db, uid, tier, source, until, scrub(text(reason, 500)), actor.id, int(self.backend.clock()))
            self.audit(db, actor, uid, 'entitlement.grant', {}, result, reason)
        return result

    def revoke_access(self, actor, gid, reason):
        self.require(actor, 'plans.grant')
        identifier(gid)
        text(reason, 500)
        with self.backend.transaction() as db:
            row = db.execute('SELECT * FROM entitlement_grants WHERE id=?', (gid,)).fetchone()
            require(row is not None, 'not_found', 404)
            db.execute('UPDATE entitlement_grants SET revoked_at=? WHERE id=?', (max(1, int(self.backend.clock())), gid))
            self.audit(db, actor, row['user_id'], 'entitlement.revoke', {'grant_id': gid, 'tier': row['tier']}, {'revoked': True}, reason)
        return {'revoked': True, 'billing_cancelled': False}

    def override(self, actor, uid, feature, enabled, until, reason):
        self.require(actor, 'plans.grant')
        identifier(uid)
        require(type(enabled) is bool)
        now = int(self.backend.clock())
        require(until is None or (type(until) is int and now < until <= now + 10 * 366 * 86400))
        text(reason, 500)
        with self.backend.transaction() as db:
            require(feature in entitlements.catalog(db)['features'] and feature != 'personal_core', 'protected_feature', 403)
            prior = db.execute('SELECT enabled,valid_until FROM entitlement_overrides WHERE user_id=? AND feature=?', (uid, feature)).fetchone()
            db.execute('INSERT INTO entitlement_overrides VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,feature) DO UPDATE SET enabled=excluded.enabled,valid_until=excluded.valid_until,reason=excluded.reason,actor_id=excluded.actor_id', (uid, feature, int(enabled), until, scrub(reason), actor.id))
            self.audit(db, actor, uid, 'entitlement.override', dict(prior) if prior else {}, {'feature': feature, 'enabled': enabled, 'valid_until': until}, reason)
        return {'updated': True}

    def update_catalog(self, actor, value, reason):
        self.require(actor, 'plans.catalog')
        with self.backend.transaction() as db:
            prior = entitlements.catalog(db)
            entitlements.validate_catalog(value, prior)
            db.execute('INSERT INTO plan_catalog VALUES(?,?,?,?)', (value['version'], canonical(value), int(self.backend.clock()), actor.id))
            self.audit(db, actor, None, 'catalog.update', {'version': prior['version']}, {'version': value['version'], 'tiers': value['tiers']}, reason)
        return {'version': value['version']}

    def audit_log(self, actor, before=None):
        self.require(actor, 'audit.read')
        require(before is None or (type(before) is int and before > 0))
        with self.backend.connect() as db:
            rows = db.execute('SELECT * FROM control_audit WHERE seq<? ORDER BY seq DESC LIMIT 100', (before or 9223372036854775807,)).fetchall()
        return {'events': [dict(row) for row in rows], 'next_before': rows[-1]['seq'] if rows else None}

    def staff_list(self, actor):
        self.require(actor, 'staff.manage')
        with self.backend.connect() as db:
            rows = db.execute('SELECT s.id,s.user_id,u.email,s.roles,s.active,s.revision FROM staff s JOIN users u ON u.id=s.user_id ORDER BY s.created_at,s.id').fetchall()
        return {'staff': [dict(row, roles=json.loads(row['roles'])) for row in rows]}

    def update_staff(self, actor, sid, roles, active, revision, reason):
        self.require(actor, 'staff.manage')
        identifier(sid)
        require(isinstance(roles, list) and roles and len(roles) == len(set(roles)) and set(roles) <= set(ROLE_RANK) - {'owner'})
        require(type(active) is bool and type(revision) is int)
        with self.backend.transaction() as db:
            row = db.execute('SELECT * FROM staff WHERE id=?', (sid,)).fetchone()
            require(row is not None, 'not_found', 404)
            self._target_rank(db, actor, row['user_id'])
            require(max(ROLE_RANK[r] for r in roles) < actor.rank, 'staff_hierarchy', 403)
            require(row['revision'] == revision, 'revision_conflict', 409)
            old = {'roles': json.loads(row['roles']), 'active': bool(row['active'])}
            db.execute('UPDATE staff SET roles=?,active=?,revision=revision+1 WHERE id=?', (canonical(roles), int(active), sid))
            db.execute('DELETE FROM control_sessions WHERE staff_id=?', (sid,))
            self.audit(db, actor, row['user_id'], 'staff.update', old, {'roles': roles, 'active': active}, reason)
        return {'revision': revision + 1}

    def invite_staff(self, actor, email, roles, reason):
        self.require(actor, 'staff.manage')
        email = text(email, 254).casefold()
        require(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email))
        require(isinstance(roles, list) and roles and all(isinstance(r, str) for r in roles) and len(roles) == len(set(roles)) and set(roles) <= set(ROLE_RANK) - {'owner'})
        require(max(ROLE_RANK[r] for r in roles) < actor.rank, 'staff_hierarchy', 403)
        code, now = secrets.token_urlsafe(32), int(self.backend.clock())
        with self.backend.transaction() as db:
            db.execute('INSERT INTO staff_invitations VALUES(?,?,?,?,?,0)', (token_hash(code), email, canonical(roles), actor.id, now + 86400))
            self.audit(db, actor, None, 'staff.invite', {}, {'roles': roles, 'expires_at': now + 86400}, reason)
        # Shared explicitly by the issuing owner; never sent to an arbitrary recipient.
        return {'invitation': code, 'expires_at': now + 86400}

    def prepare_enrollment(self, user, invitation, password):
        require(user['verified'] == 1, 'verify_email', 403)
        require(isinstance(invitation, str) and len(invitation) == 43)
        self.backend.reserve_reauth(user)
        with self.backend.transaction() as db:
            self.backend.reauthenticate(db, user, password)
            row = db.execute('SELECT * FROM staff_invitations WHERE hash=?', (token_hash(invitation),)).fetchone()
            require(row and not row['used_at'] and row['expires_at'] > int(self.backend.clock()) and row['email'] == user['email'], 'invitation_invalid', 403)
            require(not db.execute('SELECT 1 FROM staff WHERE user_id=?', (user['id'],)).fetchone(), 'staff_exists', 409)
        # Bind the encrypted short-lived enrollment to the verified account and invite.
        secret = base64.b32encode(secrets.token_bytes(20)).decode()
        capsule = self._cipher().encrypt(canonical({'uid': user['id'], 'invitation': token_hash(invitation), 'secret': secret}).encode()).decode()
        return {'totp_secret': secret, 'enrollment': capsule}

    def finish_enrollment(self, user, capsule, code):
        self.backend.reserve_reauth(user)
        require(isinstance(capsule, str) and len(capsule) < 2048)
        try: value = json.loads(self._cipher().decrypt(capsule.encode(), ttl=600))
        except Exception: raise Failure('enrollment_invalid', 403)
        require(value['uid'] == user['id'] and isinstance(code, str) and re.fullmatch(r'[0-9]{6}', code), 'enrollment_invalid', 403)
        now, sid = int(self.backend.clock()), str(uuid.uuid4())
        counter = now // 30
        require(hmac.compare_digest(totp(value['secret'], counter), code), 'mfa_invalid', 403)
        recovery = [secrets.token_urlsafe(24) for _ in range(8)]
        with self.backend.transaction() as db:
            invite = db.execute('SELECT * FROM staff_invitations WHERE hash=?', (value['invitation'],)).fetchone()
            require(invite and not invite['used_at'] and invite['expires_at'] > now and invite['email'] == user['email'], 'invitation_invalid', 403)
            issuer = db.execute('SELECT * FROM staff WHERE id=? AND active=1', (invite['issued_by'],)).fetchone()
            roles = json.loads(invite['roles'])
            require(issuer is not None, 'invitation_invalid', 403)
            principal = StaffPrincipal(issuer['id'], issuer['user_id'], tuple(json.loads(issuer['roles'])))
            self.require(principal, 'staff.manage')
            require(max(ROLE_RANK[r] for r in roles) < principal.rank, 'staff_hierarchy', 403)
            require(not db.execute('SELECT 1 FROM staff WHERE user_id=?', (user['id'],)).fetchone(), 'staff_exists', 409)
            db.execute('INSERT INTO staff(id,user_id,roles,mfa_secret,last_counter,created_at) VALUES(?,?,?,?,?,?)', (sid, user['id'], canonical(roles), self._cipher().encrypt(value['secret'].encode()), counter, now))
            db.execute('UPDATE staff_invitations SET used_at=? WHERE hash=?', (now, value['invitation']))
            for item in recovery: db.execute('INSERT INTO staff_recovery VALUES(?,?,0)', (token_hash(item), sid))
            self.audit(db, principal, user['id'], 'staff.enroll', {}, {'staff_id': sid, 'roles': roles}, 'Recipient confirmed MFA enrollment')
        return {'staff_id': sid, 'recovery_codes': recovery}

    def flags(self, uid=None):
        with self.backend.connect() as db:
            rows = db.execute('SELECT name,body,revision FROM feature_flags ORDER BY name').fetchall()
        result = {}
        for row in rows:
            value = json.loads(row['body'])
            bucket = int(token_hash(row['name'] + ':' + str(uid))[:8], 16) % 100
            result[row['name']] = dict(value, revision=row['revision'], active=bool(value['enabled'] and bucket < value['rollout']))
        return result

    def preview_flag(self, actor, name, enabled, rollout, revision, reason):
        self.require(actor, 'flags.manage')
        require(name in SAFE_FLAGS and type(enabled) is bool and type(rollout) is int and 0 <= rollout <= 100 and type(revision) is int and revision >= 0)
        value = {'name': name, 'enabled': enabled, 'rollout': rollout, 'revision': revision, 'reason': scrub(text(reason, 500))}
        pid, now = str(uuid.uuid4()), int(self.backend.clock())
        digest = token_hash(canonical(value))
        with self.backend.transaction() as db:
            db.execute('INSERT INTO flag_proposals VALUES(?,?,?,?,?,0)', (pid, actor.id, canonical(value), digest, now + 600))
        return {'proposal_id': pid, 'digest': digest, 'preview': value, 'expires_at': now + 600}

    def commit_flag(self, actor, pid, digest):
        self.require(actor, 'flags.manage')
        identifier(pid)
        with self.backend.transaction() as db:
            row = db.execute('SELECT * FROM flag_proposals WHERE id=?', (pid,)).fetchone()
            require(row and row['actor_id'] == actor.id and not row['used_at'] and row['expires_at'] > int(self.backend.clock()) and hmac.compare_digest(row['digest'], str(digest)), 'proposal_invalid', 409)
            value = json.loads(row['body'])
            prior = db.execute('SELECT body,revision FROM feature_flags WHERE name=?', (value['name'],)).fetchone()
            require((prior['revision'] if prior else 0) == value['revision'], 'revision_conflict', 409)
            after = {'enabled': value['enabled'], 'rollout': value['rollout']}
            db.execute('INSERT INTO feature_flags VALUES(?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET body=excluded.body,revision=excluded.revision,actor_id=excluded.actor_id,updated_at=excluded.updated_at', (value['name'], canonical(after), value['revision'] + 1, actor.id, int(self.backend.clock())))
            db.execute('UPDATE flag_proposals SET used_at=? WHERE id=?', (max(1, int(self.backend.clock())), pid))
            self.audit(db, actor, value['name'], 'flag.update', json.loads(prior['body']) if prior else {}, after, value['reason'])
        return {'revision': value['revision'] + 1}
