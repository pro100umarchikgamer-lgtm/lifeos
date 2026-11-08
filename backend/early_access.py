"""Verified closed-test applications; no account is created by an application.

Capabilities are hashed at rest. Mail tokens use the existing encrypted outbox.
GET never consumes tokens, so link scanners cannot approve or cancel requests.
"""
import re
import secrets
import uuid
from .service import Failure, require, token_hash, identifier

CONSENT_VERSION = '2026-11-08'


class EarlyAccess:
    def __init__(self, backend):
        self.backend = backend

    def _email(self, email):
        require(isinstance(email, str) and len(email) <= 254 and
                re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email), 'invalid_email')
        return email.casefold()

    def _limit(self, key, maximum):
        now = int(self.backend.clock())
        with self.backend.connect() as db:
            row = db.execute('INSERT INTO early_access_limits VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=CASE WHEN early_access_limits.until_at<=? THEN 1 ELSE early_access_limits.count+1 END,until_at=CASE WHEN early_access_limits.until_at<=? THEN excluded.until_at ELSE early_access_limits.until_at END RETURNING count',
                             (token_hash('early-access:' + key), now + 3600, now, now)).fetchone()
        require(row['count'] <= maximum, 'rate_limited', 429)

    def apply(self, email, consent, website='', client='unknown'):
        require(consent == CONSENT_VERSION, 'consent_required')
        require(isinstance(website, str) and len(website) <= 500)
        self._limit('ip:' + client, 10)
        accepted = {'accepted': True, 'next': 'check_email'}
        if website: return accepted  # Honeypot; identical response, no mail or account.
        email = self._email(email)
        self._limit('email:' + email, 3)
        now, code = int(self.backend.clock()), secrets.token_urlsafe(32)
        with self.backend.transaction() as db:
            row = db.execute('SELECT * FROM early_access WHERE email=?', (email,)).fetchone()
            if row and row['updated_at'] > now - 300: return accepted
            if not row:
                db.execute("INSERT INTO early_access(id,email,state,created_at,updated_at,consent_version,verification_hash,verification_until) VALUES(?,?,'unverified',?,?,?,?,?)",
                           (str(uuid.uuid4()), email, now, now, CONSENT_VERSION, token_hash(code), now + 900))
            else:
                # Reapplying cannot reset a rejection, approval or cancellation.
                db.execute('UPDATE early_access SET verification_hash=?,verification_until=?,updated_at=? WHERE id=?',
                           (token_hash(code), now + 900, now, row['id']))
            self.backend._deliver(db, email, code, 'early_verify')
        return accepted

    def confirm(self, email, code):
        email = self._email(email)
        require(isinstance(code, str) and len(code) == 43, 'verification_invalid')
        self._limit('confirm:' + email, 12)
        now, management = int(self.backend.clock()), secrets.token_urlsafe(32)
        with self.backend.transaction() as db:
            row = db.execute('SELECT * FROM early_access WHERE email=? AND verification_hash=? AND verification_until>?',
                             (email, token_hash(code), now)).fetchone()
            require(row is not None, 'verification_invalid')
            state = 'pending' if row['state'] == 'unverified' else row['state']
            db.execute('UPDATE early_access SET state=?,verified_at=?,verification_hash=NULL,verification_until=0,management_hash=?,management_until=?,updated_at=?,revision=revision+1 WHERE id=?',
                       (state, now, token_hash(management), now + 86400, now, row['id']))
        return {'state': state, 'management_token': management, 'expires_in': 86400}

    def manage(self, token, cancel=False):
        require(isinstance(token, str) and len(token) == 43, 'unauthorized', 401)
        now = int(self.backend.clock())
        with self.backend.transaction() as db:
            row = db.execute('SELECT * FROM early_access WHERE management_hash=? AND management_until>?', (token_hash(token), now)).fetchone()
            require(row is not None, 'unauthorized', 401)
            state = row['state']
            if cancel:
                state = 'cancelled'
                db.execute("UPDATE early_access SET state='cancelled',invitation_hash=NULL,invitation_until=0,updated_at=?,revision=revision+1 WHERE id=?", (now, row['id']))
        return {'state': state, 'updated_at': now if cancel else row['updated_at']}

    def list(self, actor, control, state='pending', before=None):
        control.require(actor, 'applications.manage')
        require(state in {'unverified', 'pending', 'approved', 'rejected', 'cancelled'})
        if before is not None: identifier(before)
        with self.backend.connect() as db:
            rows = db.execute('SELECT id,email,state,created_at,updated_at,verified_at,consent_version,invitation_until,revision FROM early_access WHERE state=? AND id>? ORDER BY id LIMIT 101', (state, before or '')).fetchall()
        return {'applications': [dict(row) for row in rows[:100]], 'next': rows[99]['id'] if len(rows) > 100 else None}

    def decide(self, actor, control, request_id, decision, revision, reason):
        control.require(actor, 'applications.manage')
        identifier(request_id)
        require(decision in {'approved', 'rejected'} and type(revision) is int)
        now, code = int(self.backend.clock()), secrets.token_urlsafe(32)
        with self.backend.transaction() as db:
            row = db.execute('SELECT * FROM early_access WHERE id=?', (request_id,)).fetchone()
            require(row is not None, 'not_found', 404)
            require(row['state'] == 'pending' and row['verified_at'] and row['revision'] == revision, 'revision_conflict', 409)
            changed = db.execute('UPDATE early_access SET state=?,invitation_hash=?,invitation_until=?,updated_at=?,revision=revision+1 WHERE id=? AND revision=?',
                                 (decision, token_hash(code) if decision == 'approved' else None, now + 604800 if decision == 'approved' else 0, now, request_id, revision))
            require(changed.rowcount == 1, 'revision_conflict', 409)
            control.audit(db, actor, request_id, 'application.' + decision, {'state': row['state']}, {'state': decision}, reason)
            self.backend._deliver(db, row['email'], code if decision == 'approved' else '', 'early_invite' if decision == 'approved' else 'early_rejected')
        return {'state': decision, 'invitation_expires_in': 604800 if decision == 'approved' else 0}

    def invited(self, email, token):
        if not isinstance(email, str) or not isinstance(token, str) or len(token) != 43: return False
        with self.backend.connect() as db:
            row = db.execute("SELECT 1 FROM early_access WHERE email=? AND state='approved' AND invitation_hash=? AND invitation_until>?", (email.casefold(), token_hash(token), int(self.backend.clock()))).fetchone()
        return bool(row)
