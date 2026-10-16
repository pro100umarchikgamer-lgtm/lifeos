"""Optional customer TOTP, separate from mandatory staff MFA; no email bypass."""
import base64
import hmac
import json
import re
import secrets
from .control import totp
from .service import require, token_hash, canonical, Failure


def accept(backend, db, uid, code):
    row = db.execute('SELECT * FROM account_mfa WHERE user_id=?', (uid,)).fetchone()
    if row is None: return True
    if not isinstance(code, str): return False
    now = int(backend.clock())
    if re.fullmatch(r'[0-9]{6}', code):
        secret = backend.cipher.decrypt(bytes(row['secret'])).decode()
        counters = [c for c in range(now//30-1,now//30+2) if c>=0 and c>row['last_counter'] and hmac.compare_digest(totp(secret,c),code)]
        if not counters: return False
        db.execute('UPDATE account_mfa SET last_counter=? WHERE user_id=?', (max(counters),uid))
        return True
    if len(code)==32:
        recovery=db.execute('SELECT * FROM account_recovery WHERE hash=? AND user_id=? AND used_at=0',(token_hash(code),uid)).fetchone()
        if recovery:
            db.execute('UPDATE account_recovery SET used_at=? WHERE hash=?',(max(1,now),token_hash(code)))
            backend.revoke_all_in(db,uid)
            return True
    return False


class CustomerMFA:
    def __init__(self,backend):self.backend=backend

    def status(self,actor):
        with self.backend.connect() as db:
            enabled=db.execute('SELECT 1 FROM account_mfa WHERE user_id=?',(actor['id'],)).fetchone() is not None
            remaining=db.execute('SELECT COUNT(*) AS n FROM account_recovery WHERE user_id=? AND used_at=0',(actor['id'],)).fetchone()['n']
        return {'enabled':enabled,'recovery_codes_remaining':remaining}

    def begin(self,actor,password):
        require(actor['verified']==1,'verify_email',403)
        require(hasattr(self.backend,'cipher'),'mfa_unconfigured',503)
        self.backend.reserve_reauth(actor)
        with self.backend.transaction() as db:
            self.backend.reauthenticate(db,actor,password)
            require(not db.execute('SELECT 1 FROM account_mfa WHERE user_id=?',(actor['id'],)).fetchone(),'mfa_already_enabled',409)
        secret=base64.b32encode(secrets.token_bytes(20)).decode()
        capsule=self.backend.cipher.encrypt(canonical({'uid':actor['id'],'secret':secret}).encode()).decode()
        return {'totp_secret':secret,'enrollment':capsule,'expires_in':600}

    def enable(self,actor,password,capsule,code):
        self.backend.reserve_reauth(actor)
        require(isinstance(capsule,str) and len(capsule)<2048)
        try:value=json.loads(self.backend.cipher.decrypt(capsule.encode(),ttl=600))
        except Exception:raise Failure('enrollment_invalid',403)
        require(value['uid']==actor['id'] and isinstance(code,str) and re.fullmatch(r'[0-9]{6}',code),'mfa_invalid',403)
        now=int(self.backend.clock());counter=now//30
        require(hmac.compare_digest(totp(value['secret'],counter),code),'mfa_invalid',403)
        recovery=[secrets.token_urlsafe(24) for _ in range(8)]
        with self.backend.transaction() as db:
            self.backend.reauthenticate(db,actor,password)
            require(not db.execute('SELECT 1 FROM account_mfa WHERE user_id=?',(actor['id'],)).fetchone(),'mfa_already_enabled',409)
            db.execute('INSERT INTO account_mfa VALUES(?,?,?)',(actor['id'],self.backend.cipher.encrypt(value['secret'].encode()),counter))
            for item in recovery:db.execute('INSERT INTO account_recovery VALUES(?,?,0)',(token_hash(item),actor['id']))
            self.backend.revoke_all_in(db,actor['id'])
        return {'enabled':True,'recovery_codes':recovery,'sign_in_required':True}

    def disable(self,actor,password,code):
        self.backend.reserve_reauth(actor)
        valid=False
        with self.backend.transaction() as db:
            self.backend.reauthenticate(db,actor,password)
            require(db.execute('SELECT 1 FROM account_mfa WHERE user_id=?',(actor['id'],)).fetchone(),'mfa_not_enabled',409)
            valid=accept(self.backend,db,actor['id'],code)
            if valid:
                db.execute('DELETE FROM account_mfa WHERE user_id=?',(actor['id'],))
                db.execute('DELETE FROM account_recovery WHERE user_id=?',(actor['id'],))
                self.backend.revoke_all_in(db,actor['id'])
        require(valid,'mfa_invalid',403)
        return {'enabled':False,'sign_in_required':True}
