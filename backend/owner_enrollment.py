"""Operator-issued first-owner capability, activated only after verified account + MFA."""
import base64
import json
import re
import secrets
import uuid
from .control import Control, totp
from .service import Failure, canonical, require, token_hash


class OwnerEnrollment:
    def __init__(self, backend):
        self.backend = backend
        self.control = Control(backend)

    def _empty(self, db):
        require(not db.execute("SELECT 1 FROM staff WHERE roles LIKE ?", ('%"owner"%',)).fetchone(), 'owner_already_exists', 409)

    def issue(self, email):
        require(isinstance(email, str) and len(email) <= 254 and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email), 'invalid_email')
        email, token, now = email.casefold(), secrets.token_urlsafe(32), int(self.backend.clock())
        with self.backend.transaction() as db:
            self._empty(db)
            # Reissuing invalidates earlier, unused capabilities, without granting authority.
            db.execute('UPDATE owner_setup SET used_at=? WHERE used_at=0', (max(1, now),))
            db.execute('INSERT INTO owner_setup VALUES(?,?,?,0)', (token_hash(token), email, now + 86400))
            self.control.audit(db, 'operator-cli', None, 'owner.setup.issue', {}, {'expires_at': now + 86400}, 'First owner setup issued; verified email and MFA required')
        return {'invitation': token, 'email': email, 'expires_at': now + 86400}

    def invited(self, email, token):
        if not isinstance(email, str) or not isinstance(token, str) or len(token) != 43: return False
        with self.backend.connect() as db:
            return bool(db.execute('SELECT 1 FROM owner_setup WHERE hash=? AND email=? AND used_at=0 AND expires_at>?', (token_hash(token), email.casefold(), int(self.backend.clock()))).fetchone())

    def begin(self, actor, invitation, password):
        require(actor['verified'] == 1, 'verify_email', 403)
        require(self.invited(actor['email'], invitation), 'invitation_invalid', 403)
        self.backend.reserve_reauth(actor)
        with self.backend.transaction() as db:
            self._empty(db)
            self.backend.reauthenticate(db, actor, password)
            require(not db.execute('SELECT 1 FROM staff WHERE user_id=?', (actor['id'],)).fetchone(), 'staff_exists', 409)
        secret = base64.b32encode(secrets.token_bytes(20)).decode()
        capsule = self.control._cipher().encrypt(canonical({'purpose': 'first-owner', 'uid': actor['id'], 'hash': token_hash(invitation), 'secret': secret}).encode()).decode()
        return {'totp_secret': secret, 'enrollment': capsule}

    def finish(self, actor, capsule, code):
        require(actor['verified'] == 1, 'verify_email', 403)
        self.backend.reserve_reauth(actor)
        require(isinstance(capsule, str) and len(capsule) < 2048 and isinstance(code, str) and re.fullmatch(r'[0-9]{6}', code), 'enrollment_invalid', 403)
        try: value = json.loads(self.control._cipher().decrypt(capsule.encode(), ttl=600))
        except Exception: raise Failure('enrollment_invalid', 403)
        require(value.get('purpose') == 'first-owner' and value.get('uid') == actor['id'], 'enrollment_invalid', 403)
        now, sid = int(self.backend.clock()), str(uuid.uuid4())
        counter = now // 30
        require(secrets.compare_digest(totp(value['secret'], counter), code), 'mfa_invalid', 403)
        recovery = [secrets.token_urlsafe(24) for _ in range(8)]
        with self.backend.transaction() as db:
            self._empty(db)
            row = db.execute('SELECT 1 FROM owner_setup WHERE hash=? AND email=? AND used_at=0 AND expires_at>?', (value['hash'], actor['email'], now)).fetchone()
            require(row, 'invitation_invalid', 403)
            self.backend._account_available(db, actor['id'])
            db.execute('INSERT INTO staff(id,user_id,roles,mfa_secret,last_counter,created_at) VALUES(?,?,?,?,?,?)', (sid, actor['id'], '["owner"]', self.control._cipher().encrypt(value['secret'].encode()), counter, now))
            db.execute('UPDATE owner_setup SET used_at=? WHERE hash=?', (max(1, now), value['hash']))
            for item in recovery: db.execute('INSERT INTO staff_recovery VALUES(?,?,0)', (token_hash(item), sid))
            self.control.audit(db, 'operator-cli', actor['id'], 'owner.setup.complete', {}, {'staff_id': sid}, 'Verified recipient confirmed first-owner MFA')
        return {'staff_id': sid, 'recovery_codes': recovery}
