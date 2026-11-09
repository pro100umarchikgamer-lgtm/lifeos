"""Password-first web login; opaque, bounded, single-use second-factor grants.

Legacy Android password+factor login remains compatible. No password, factor,
email or bearer session is embedded in the browser's challenge value.
"""
import hashlib
import hmac
import json
import re
import secrets

from .service import require, token_hash


class LoginFlow:
    def __init__(self, backend):
        self.backend = backend

    def _principal(self, db, uid, staff):
        user = db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
        factor = db.execute('SELECT * FROM staff WHERE user_id=?', (uid,)).fetchone() if staff else db.execute('SELECT * FROM account_mfa WHERE user_id=?', (uid,)).fetchone()
        return user, factor

    def _version(self, user, factor, staff):
        secret = bytes(factor['mfa_secret' if staff else 'secret']).hex() if factor else ''
        authority = str(factor['revision']) + ':' + factor['roles'] if staff and factor else ''
        return token_hash(user['password_hash'] + ':' + user['salt'] + ':' + secret + ':' + authority)

    def begin(self, email, password, agent, staff=False):
        require(isinstance(email, str) and len(email) <= 254 and isinstance(password, str) and len(password) <= 256)
        now = int(self.backend.clock())
        valid, result = False, None
        with self.backend.transaction() as db:
            # Share the customer's legacy account limiter, including failed attempts.
            key = token_hash(('control-login:' if staff else '') + email.casefold())
            limit = db.execute('SELECT * FROM auth_limits WHERE key=?', (key,)).fetchone()
            require(limit is None or limit['until_at'] <= now or limit['count'] < 10, 'rate_limited', 429)
            count = limit['count'] + 1 if limit and limit['until_at'] > now else 1
            db.execute('INSERT INTO auth_limits VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET count=excluded.count,until_at=excluded.until_at', (key, count, now + 900))
            user = db.execute('SELECT * FROM users WHERE email=?', (email.casefold(),)).fetchone()
            salt = bytes.fromhex(user['salt']) if user else bytes(16)
            digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000).hex()
            valid = user is not None and hmac.compare_digest(digest, user['password_hash'])
            if valid:
                self.backend._account_available(db, user['id'])
                user, factor = self._principal(db, user['id'], staff)
                valid = not staff or bool(factor and factor['active'] and user['verified'])
                if valid:
                    if factor is None:
                        result = self.backend.new_session(db, user['id'], user['verified'])
                    else:
                        raw = secrets.token_urlsafe(32)
                        scope = 'staff' if staff else 'account'
                        db.execute('DELETE FROM login_challenges WHERE expires_at<=? OR (user_id=? AND scope=?)', (now, user['id'], scope))
                        db.execute('INSERT INTO login_challenges VALUES(?,?,?,?,?,?,0,0)', (token_hash(raw), user['id'], scope, token_hash(agent), self._version(user, factor, staff), now + 300))
                        result = {'mfa_required': True, 'challenge': raw, 'expires_in': 300}
        require(valid, 'invalid_credentials', 401)
        return result

    def finish(self, challenge, code, agent, staff=False):
        require(isinstance(challenge, str) and len(challenge) == 43 and isinstance(code, str) and len(code) <= 64, 'invalid_credentials', 401)
        now, result, valid = int(self.backend.clock()), None, False
        with self.backend.transaction() as db:
            row = db.execute('SELECT * FROM login_challenges WHERE hash=?', (token_hash(challenge),)).fetchone()
            require(row and row['scope'] == ('staff' if staff else 'account') and row['expires_at'] > now and row['used_at'] == 0 and row['attempts'] < 5 and hmac.compare_digest(row['agent_hash'], token_hash(agent)), 'invalid_credentials', 401)
            user, factor = self._principal(db, row['user_id'], staff)
            require(user and factor and (not staff or (factor['active'] and user['verified'])) and hmac.compare_digest(row['credential_version'], self._version(user, factor, staff)), 'invalid_credentials', 401)
            self.backend._account_available(db, user['id'])
            db.execute('UPDATE login_challenges SET attempts=attempts+1 WHERE hash=?', (row['hash'],))
            if staff:
                valid = self._staff_factor(db, factor, code, now)
                if valid:
                    from .control import Control, StaffPrincipal
                    token = secrets.token_urlsafe(32)
                    db.execute('INSERT INTO control_sessions VALUES(?,?,?,?,?,?)', (token_hash(token), factor['id'], now, now, now + 28800, token_hash(agent)))
                    principal = StaffPrincipal(factor['id'], user['id'], tuple(json.loads(factor['roles'])))
                    Control(self.backend).audit(db, principal, user['id'], 'staff.login', {}, {}, 'Password and single-use MFA challenge verified')
                    result = {'token': token, 'expires_in': 28800, 'idle_seconds': 900}
            else:
                from .customer_mfa import accept
                valid = accept(self.backend, db, user['id'], code)
                if valid:
                    result = self.backend.new_session(db, user['id'], user['verified'])
            if valid:
                db.execute('UPDATE login_challenges SET used_at=? WHERE hash=?', (max(1, now), row['hash']))
        # An invalid code must commit the attempt counter without creating a session.
        require(valid, 'invalid_credentials', 401)
        return result

    def _staff_factor(self, db, staff, code, now):
        if re.fullmatch('[0-9]{6}', code):
            from .control import totp
            secret = self.backend.cipher.decrypt(bytes(staff['mfa_secret'])).decode()
            counters = [c for c in range(max(0, now // 30 - 1), now // 30 + 2) if c > staff['last_counter'] and hmac.compare_digest(totp(secret, c), code)]
            if not counters:
                return False
            db.execute('UPDATE staff SET last_counter=? WHERE id=?', (max(counters), staff['id']))
            return True
        if len(code) == 32:
            recovery = db.execute('SELECT 1 FROM staff_recovery WHERE hash=? AND staff_id=? AND used_at=0', (token_hash(code), staff['id'])).fetchone()
            if recovery:
                db.execute('UPDATE staff_recovery SET used_at=? WHERE hash=?', (max(1, now), token_hash(code)))
                self.backend.revoke_all_in(db, staff['user_id'])
                return True
        return False
