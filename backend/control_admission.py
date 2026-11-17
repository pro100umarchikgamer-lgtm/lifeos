"""Host-only Control admission, tied to one live customer browser session.

This is a visibility gate, never staff authentication. Staff MFA, CSRF and RBAC
remain mandatory. Only digests of the one-use POST ticket/cookie are persisted.
"""
import hmac
import json
import secrets
from .control import Control, StaffPrincipal
from .service import require, token_hash

COOKIE='__Host-uladim_control_admission'

class ControlAdmission:
    def __init__(self, backend):
        self.backend=backend

    def _parent(self, db, parent_hash, agent, now):
        row=db.execute('SELECT w.user_id,w.expires_at,w.agent_hash,u.email,u.verified,d.revoked_at,s.id AS staff_id,s.roles,s.active,COALESCE(a.disabled_until,0) AS disabled_until,COALESCE(a.deleted_at,0) AS deleted_at FROM web_sessions w JOIN users u ON u.id=w.user_id JOIN devices d ON d.id=w.device_id JOIN staff s ON s.user_id=w.user_id LEFT JOIN account_state a ON a.user_id=w.user_id WHERE w.hash=?',(parent_hash,)).fetchone()
        require(row and row['expires_at']>now and not row['revoked_at'] and row['verified'] and row['active'] and not row['deleted_at'] and row['disabled_until']<=now and hmac.compare_digest(row['agent_hash'],token_hash(agent)), 'not_found',404)
        return row

    def available(self, user):
        with self.backend.connect() as db:
            return bool(user.get('verified') and db.execute('SELECT 1 FROM staff WHERE user_id=? AND active=1',(user['id'],)).fetchone())

    def issue(self, parent_token, agent):
        now=int(self.backend.clock()); ticket=secrets.token_urlsafe(32)
        with self.backend.transaction() as db:
            row=self._parent(db,token_hash(parent_token),agent,now)
            db.execute('DELETE FROM control_handoffs WHERE expires_at<=? OR parent_hash=?',(now,token_hash(parent_token)))
            db.execute('DELETE FROM control_admissions WHERE expires_at<=?',(now,))
            db.execute('INSERT INTO control_handoffs VALUES(?,?,?,?,0)',(token_hash(ticket),token_hash(parent_token),token_hash(agent),now+60))
            principal=StaffPrincipal(row['staff_id'],row['user_id'],tuple(json.loads(row['roles'])))
            Control(self.backend).audit(db,principal,row['user_id'],'control.admission.issue',{}, {},'One-use browser admission issued; staff MFA still required')
        return ticket

    def redeem(self, ticket, agent):
        require(isinstance(ticket,str) and len(ticket)==43,'not_found',404)
        now=int(self.backend.clock()); raw=secrets.token_urlsafe(32)
        with self.backend.transaction() as db:
            row=db.execute('SELECT * FROM control_handoffs WHERE hash=?',(token_hash(ticket),)).fetchone()
            require(row and not row['used_at'] and row['expires_at']>now and hmac.compare_digest(row['agent_hash'],token_hash(agent)), 'not_found',404)
            parent=self._parent(db,row['parent_hash'],agent,now)
            expires=min(parent['expires_at'],now+28800)
            db.execute('UPDATE control_handoffs SET used_at=? WHERE hash=?',(max(1,now),token_hash(ticket)))
            db.execute('INSERT INTO control_admissions VALUES(?,?,?,?)',(token_hash(raw),row['parent_hash'],token_hash(agent),expires))
        return raw,expires-now

    def authenticate(self, cookie, agent):
        require(isinstance(cookie,str) and len(cookie)==43,'not_found',404)
        now=int(self.backend.clock())
        with self.backend.connect() as db:
            row=db.execute('SELECT * FROM control_admissions WHERE hash=?',(token_hash(cookie),)).fetchone()
            require(row and row['expires_at']>now and hmac.compare_digest(row['agent_hash'],token_hash(agent)), 'not_found',404)
            return dict(self._parent(db,row['parent_hash'],agent,now))
