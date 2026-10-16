"""Rotating device sessions; compatible with retained pre-refresh access tokens.

Only token hashes are persisted. A reused refresh token revokes its whole device
family, including its newly issued access token. Never log credential payloads.
"""
import hashlib
import hmac
import secrets
import uuid

ACCESS_SECONDS = 900
REFRESH_SECONDS = 30 * 86400


class AccountSessions:
    def _account_available(self, db, uid):
        from .service import require
        row = db.execute('SELECT * FROM account_state WHERE user_id=?', (uid,)).fetchone()
        require(row is None or (not row['deleted_at'] and row['disabled_until'] <= int(self.clock())), 'account_unavailable', 403)

    def authenticate(self, token):
        from .service import require, token_hash
        require(isinstance(token, str) and len(token) == 43, 'unauthorized', 401)
        with self.connect() as db:
            row = db.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.hash=? AND s.expires_at>?', (token_hash(token), int(self.clock()))).fetchone()
            require(row is not None, 'unauthorized', 401)
            self._account_available(db, row['id'])
        return dict(row)

    def new_session(self, db, uid, verified, label='ULADIM'):
        from .service import require
        self._account_available(db, uid)
        now = int(self.clock())
        count = db.execute('SELECT COUNT(*) AS n FROM devices WHERE user_id=? AND revoked_at=0 AND created_at>?', (uid, now - REFRESH_SECONDS)).fetchone()['n']
        require(count < 20, 'device_limit', 409)
        did, family = str(uuid.uuid4()), str(uuid.uuid4())
        db.execute('INSERT INTO devices VALUES(?,?,?,?,?,?,0)', (did, uid, family, label[:80], now, now))
        return self._rotate_tokens(db, uid, did, family, now + REFRESH_SECONDS, verified)

    def _rotate_tokens(self, db, uid, did, family, until, verified):
        from .service import token_hash
        now = int(self.clock())
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE hash IN (SELECT hash FROM session_devices WHERE device_id=?)', (did,))
        db.execute('INSERT INTO sessions VALUES(?,?,?)', (token_hash(access), uid, now + ACCESS_SECONDS))
        db.execute('INSERT INTO session_devices VALUES(?,?)', (token_hash(access), did))
        db.execute('INSERT INTO refresh_tokens VALUES(?,?,?,?,?,0,0)', (token_hash(refresh), uid, did, family, until))
        db.execute('UPDATE devices SET last_seen_at=? WHERE id=?', (now, did))
        return {'user_id': uid, 'token': access, 'refresh_token': refresh, 'device_id': did,
                'expires_in': ACCESS_SECONDS, 'refresh_expires_in': max(0, until - now), 'verified': bool(verified)}

    def _revoke_device(self, db, uid, did):
        now = max(1, int(self.clock()))
        db.execute('DELETE FROM sessions WHERE user_id=? AND hash IN (SELECT hash FROM session_devices WHERE device_id=?)', (uid, did))
        db.execute('UPDATE refresh_tokens SET revoked_at=? WHERE user_id=? AND device_id=?', (now, uid, did))
        db.execute('UPDATE devices SET revoked_at=? WHERE user_id=? AND id=?', (now, uid, did))

    def revoke_all_in(self, db, uid):
        now = max(1, int(self.clock()))
        db.execute('DELETE FROM sessions WHERE user_id=?', (uid,))
        db.execute('UPDATE refresh_tokens SET revoked_at=? WHERE user_id=?', (now, uid))
        db.execute('UPDATE devices SET revoked_at=? WHERE user_id=?', (now, uid))

    def refresh_session(self, token):
        from .service import require, token_hash, Failure
        require(isinstance(token, str) and len(token) == 43, 'unauthorized', 401)
        replay = False
        with self.transaction() as db:
            row = db.execute('SELECT r.*,u.verified FROM refresh_tokens r JOIN users u ON u.id=r.user_id WHERE r.hash=?', (token_hash(token),)).fetchone()
            now = int(self.clock())
            require(row is not None, 'unauthorized', 401)
            if row['used_at']:
                self._revoke_device(db, row['user_id'], row['device_id'])
                replay = True
            else:
                require(not row['revoked_at'] and row['expires_at'] > now, 'unauthorized', 401)
                self._account_available(db, row['user_id'])
                db.execute('UPDATE refresh_tokens SET used_at=? WHERE hash=?', (max(1, now), token_hash(token)))
                result = self._rotate_tokens(db, row['user_id'], row['device_id'], row['family_id'], row['expires_at'], row['verified'])
        # Revocation must commit before reporting the replay failure.
        if replay:
            raise Failure('refresh_replay', 401)
        return result

    def reauthenticate(self, db, actor, password):
        from .service import require, token_hash
        require(isinstance(password, str) and len(password) <= 256, 'invalid_credentials', 401)
        now = int(self.clock())
        key = token_hash('reauth:' + actor['id'])
        row = db.execute('SELECT * FROM auth_limits WHERE key=?', (key,)).fetchone()
        require(row is None or row['until_at'] <= now or row['count'] <= 10, 'rate_limited', 429)
        # The attempt is reserved in a separate committed transaction by callers
        # before entering a mutation, so failed password checks cannot reset it.
        user = db.execute('SELECT * FROM users WHERE id=?', (actor['id'],)).fetchone()
        require(user is not None, 'unauthorized', 401)
        digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(user['salt']), 600000).hex()
        require(hmac.compare_digest(digest, user['password_hash']), 'invalid_credentials', 401)

    def reserve_reauth(self, actor):
        from .service import require, token_hash
        with self.transaction() as db:
            now, key = int(self.clock()), token_hash('reauth:' + actor['id'])
            row = db.execute('SELECT * FROM auth_limits WHERE key=?', (key,)).fetchone()
            require(row is None or row['until_at'] <= now or row['count'] < 10, 'rate_limited', 429)
            count = row['count'] + 1 if row and row['until_at'] > now else 1
            db.execute('INSERT INTO auth_limits VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET count=excluded.count,until_at=excluded.until_at', (key, count, now + 900))

    def list_devices(self, actor, token):
        from .service import token_hash
        with self.connect() as db:
            current = db.execute('SELECT device_id FROM session_devices WHERE hash=?', (token_hash(token),)).fetchone()
            rows = db.execute('SELECT id,label,created_at,last_seen_at,revoked_at FROM devices WHERE user_id=? ORDER BY created_at DESC LIMIT 100', (actor['id'],)).fetchall()
        return {'devices': [dict(row, current=bool(current and row['id'] == current['device_id'])) for row in rows]}

    def revoke_device(self, actor, device_id, password):
        from .service import identifier, require
        identifier(device_id)
        self.reserve_reauth(actor)
        with self.transaction() as db:
            self.reauthenticate(db, actor, password)
            require(db.execute('SELECT 1 FROM devices WHERE id=? AND user_id=?', (device_id, actor['id'])).fetchone() is not None, 'not_found', 404)
            self._revoke_device(db, actor['id'], device_id)
        return {'revoked': True}

    def revoke_all(self, actor, password):
        self.reserve_reauth(actor)
        with self.transaction() as db:
            self.reauthenticate(db, actor, password)
            self.revoke_all_in(db, actor['id'])
        return {'signed_out': True}

    def logout(self, token):
        from .service import token_hash
        with self.transaction() as db:
            row = db.execute('SELECT s.user_id,d.device_id FROM sessions s LEFT JOIN session_devices d ON d.hash=s.hash WHERE s.hash=?', (token_hash(token),)).fetchone()
            if row and row['device_id']:
                self._revoke_device(db, row['user_id'], row['device_id'])
            else:
                db.execute('DELETE FROM sessions WHERE hash=?', (token_hash(token),))
        return {'signed_out': True}
