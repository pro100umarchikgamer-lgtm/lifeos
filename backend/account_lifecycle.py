"""Verified account changes and reversible deletion requests; Android local data is untouched."""
import re
import secrets
import uuid
from .service import require, text, token_hash, identifier, Failure, TABLES

class AccountLifecycle:
    def __init__(self, backend): self.backend = backend

    def signup(self, email, password):
        # Same response for an existing address. Never invent a successful session.
        try:
            result = self.backend.register(email, password)
        except Failure as error:
            if error.code != 'account_exists': raise
            try:
                pending = self.backend.login(email, password)
                if pending.get('mfa_required'):return {'accepted': True, 'next': 'check_email'}
                try:
                    actor = self.backend.authenticate(pending['token'])
                    if not actor['verified']: self.backend.resend_verification(actor)
                finally:
                    self.backend.logout(pending['token'])
            except Failure:
                pass # Identical response; existing addresses and password guesses are not disclosed.
        else:
            self.backend.logout(result['token'])
        return {'accepted': True, 'next': 'check_email'}

    def confirm_signup(self, email, code):
        require(isinstance(email, str) and len(email) <= 254 and isinstance(code, str) and len(code) == 43, 'verification_invalid')
        with self.backend.transaction() as db:
            user = db.execute('SELECT u.* FROM users u JOIN verification v ON v.user_id=u.id WHERE u.email=? AND v.hash=? AND v.expires_at>?', (email.casefold(), token_hash(code), int(self.backend.clock()))).fetchone()
            require(user is not None, 'verification_invalid')
            self.backend._account_available(db, user['id'])
            db.execute('UPDATE users SET verified=1 WHERE id=?', (user['id'],))
            db.execute('DELETE FROM verification WHERE user_id=?', (user['id'],))
            return self.backend.new_session(db, user['id'], True)

    def change_email(self, actor, email, password):
        require(isinstance(email, str) and len(email) <= 254 and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email))
        email = email.casefold()
        self.backend.reserve_reauth(actor)
        now, code = int(self.backend.clock()), secrets.token_urlsafe(32)
        with self.backend.transaction() as db:
            self.backend.reauthenticate(db, actor, password)
            db.execute('DELETE FROM email_changes WHERE user_id=?', (actor['id'],))
            # No address-existence oracle. Conflicts also produce accepted=True.
            if not db.execute('SELECT 1 FROM users WHERE email=?', (email,)).fetchone():
                db.execute('INSERT INTO email_changes VALUES(?,?,?,?)', (token_hash(code), actor['id'], email, now + 900))
                self.backend._deliver(db, email, code, 'email_change')
        return {'accepted': True, 'expires_in': 900}

    def confirm_email(self, actor, code, password):
        require(isinstance(code, str) and len(code) == 43, 'verification_invalid')
        self.backend.reserve_reauth(actor)
        with self.backend.transaction() as db:
            self.backend.reauthenticate(db, actor, password)
            row = db.execute('SELECT * FROM email_changes WHERE hash=? AND user_id=? AND expires_at>?', (token_hash(code), actor['id'], int(self.backend.clock()))).fetchone()
            require(row and not db.execute('SELECT 1 FROM users WHERE email=?', (row['email'],)).fetchone(), 'verification_invalid')
            db.execute('UPDATE users SET email=?,verified=1 WHERE id=?', (row['email'], actor['id']))
            db.execute('DELETE FROM email_changes WHERE user_id=?', (actor['id'],))
            self.backend.revoke_all_in(db, actor['id'])
        return {'updated': True, 'sign_in_required': True}

    def deletion_status(self, actor):
        with self.backend.connect() as db:
            job = db.execute('SELECT id,requested_at,due_at,state,last_error FROM deletion_jobs WHERE user_id=?', (actor['id'],)).fetchone()
            families = db.execute("SELECT w.id,w.name FROM workspaces w WHERE w.creator_id=? AND w.kind='family' AND w.dissolved=0 AND EXISTS(SELECT 1 FROM memberships m WHERE m.workspace_id=w.id AND m.user_id<>? AND m.active=1)", (actor['id'], actor['id'])).fetchall()
        return {'request': dict(job) if job else None, 'ownership_transfer_required': [dict(w) for w in families], 'local_data_deleted': False, 'backup_erasure': 'operator_retention_review_required'}

    def request_deletion(self, actor, password, confirmation):
        require(confirmation == 'DELETE', 'confirmation_required')
        self.backend.reserve_reauth(actor)
        with self.backend.transaction() as db:
            self.backend.reauthenticate(db, actor, password)
            require(not db.execute("SELECT 1 FROM staff WHERE user_id=? AND active=1", (actor['id'],)).fetchone(), 'staff_offboarding_required', 409)
            blocked = db.execute("SELECT 1 FROM workspaces w WHERE w.creator_id=? AND w.kind='family' AND w.dissolved=0 AND EXISTS(SELECT 1 FROM memberships m WHERE m.workspace_id=w.id AND m.user_id<>? AND m.active=1)", (actor['id'], actor['id'])).fetchone()
            require(not blocked, 'ownership_transfer_required', 409)
            now = int(self.backend.clock())
            prior = db.execute('SELECT * FROM deletion_jobs WHERE user_id=?', (actor['id'],)).fetchone()
            if prior and prior['state'] == 'pending': return {'request_id': prior['id'], 'due_at': prior['due_at'], 'state': 'pending'}
            jid = str(uuid.uuid4())
            db.execute("INSERT INTO deletion_jobs VALUES(?,?,?,?,'pending',NULL) ON CONFLICT(user_id) DO UPDATE SET id=excluded.id,requested_at=excluded.requested_at,due_at=excluded.due_at,state='pending',last_error=NULL", (jid, actor['id'], now, now + 86400))
        return {'request_id': jid, 'due_at': now + 86400, 'state': 'pending'}

    def cancel_deletion(self, actor, password):
        self.backend.reserve_reauth(actor)
        with self.backend.transaction() as db:
            self.backend.reauthenticate(db, actor, password)
            db.execute("UPDATE deletion_jobs SET state='cancelled' WHERE user_id=? AND state='pending'", (actor['id'],))
        return {'cancelled': True}

    def transfer(self, actor, wid, target, password):
        identifier(wid);identifier(target)
        self.backend.reserve_reauth(actor)
        now, tid = int(self.backend.clock()), str(uuid.uuid4())
        with self.backend.transaction() as db:
            self.backend.reauthenticate(db, actor, password)
            row = db.execute("SELECT 1 FROM workspaces w JOIN memberships m ON m.workspace_id=w.id WHERE w.id=? AND w.creator_id=? AND w.kind='family' AND w.dissolved=0 AND m.user_id=? AND m.role='parent' AND m.active=1", (wid, actor['id'], target)).fetchone()
            require(row and target != actor['id'], 'transfer_forbidden', 403)
            db.execute('INSERT INTO ownership_transfers VALUES(?,?,?,?,?,0)', (tid, wid, actor['id'], target, now + 86400))
        return {'transfer_id': tid, 'recipient_confirmation_required': True}

    def accept_transfer(self, actor, tid, password):
        identifier(tid);self.backend.reserve_reauth(actor)
        with self.backend.transaction() as db:
            self.backend.reauthenticate(db, actor, password)
            row = db.execute('SELECT * FROM ownership_transfers WHERE id=? AND to_id=? AND expires_at>? AND accepted_at=0', (tid, actor['id'], int(self.backend.clock()))).fetchone()
            require(row is not None, 'transfer_invalid', 409)
            member = db.execute("SELECT 1 FROM memberships WHERE workspace_id=? AND user_id=? AND role='parent' AND active=1", (row['workspace_id'], actor['id'])).fetchone()
            space = db.execute('SELECT * FROM workspaces WHERE id=? AND creator_id=? AND dissolved=0', (row['workspace_id'], row['from_id'])).fetchone()
            require(member and space, 'transfer_invalid', 409)
            db.execute('UPDATE workspaces SET creator_id=?,revision=revision+1 WHERE id=?', (actor['id'], row['workspace_id']))
            db.execute('UPDATE ownership_transfers SET accepted_at=? WHERE id=?', (max(1, int(self.backend.clock())), tid))
            self.backend._audit(db, row['workspace_id'], actor, tid, 'workspace.ownership.transfer')
        return {'transferred': True}

    def process_one_deletion(self):
        """Worker consumes only explicit, due user requests; no automatic history pruning."""
        now = int(self.backend.clock())
        with self.backend.transaction() as db:
            job = db.execute("SELECT * FROM deletion_jobs WHERE state='pending' AND due_at<=? ORDER BY due_at,id LIMIT 1", (now,)).fetchone()
            if not job: return False
            uid = job['user_id']
            # Recheck authority at execution, including families created during grace.
            blocked = db.execute("SELECT 1 FROM workspaces w WHERE w.creator_id=? AND w.kind='family' AND w.dissolved=0 AND EXISTS(SELECT 1 FROM memberships m WHERE m.workspace_id=w.id AND m.user_id<>? AND m.active=1)", (uid, uid)).fetchone()
            staff = db.execute('SELECT 1 FROM staff WHERE user_id=? AND active=1', (uid,)).fetchone()
            if blocked or staff:
                db.execute("UPDATE deletion_jobs SET state='attention',last_error=? WHERE id=?", ('ownership_or_staff_changed', job['id']))
                return True
            user = db.execute('SELECT email FROM users WHERE id=?', (uid,)).fetchone()
            # Preserve UUID tombstones and shared records; erase only private payloads
            # and records in the requesting user's personal space.
            rows = db.execute("SELECT r.* FROM records r JOIN workspaces w ON w.id=r.workspace_id WHERE r.owner_id=? AND (r.visibility='private' OR w.kind='personal')", (uid,)).fetchall()
            private_ids = {r['id'] for r in rows}
            for record in rows:
                for table, field in (('transactions','account_id'),('transfers','from_id'),('transfers','to_id'),('requests','movement_id')):
                    linked = db.execute('SELECT r.id FROM '+table+' d JOIN records r ON r.id=d.id WHERE d.'+field+'=? AND r.deleted=0', (record['id'],)).fetchall()
                    if any(r['id'] not in private_ids for r in linked):
                        db.execute("UPDATE deletion_jobs SET state='attention',last_error='shared_reference_review_required' WHERE id=?", (job['id'],))
                        return True
            for record in rows:
                rid = record['id']
                db.execute('DELETE FROM task_progress WHERE task_id=?', (rid,))
                db.execute('DELETE FROM grants WHERE record_id=?', (rid,))
                db.execute('DELETE FROM '+TABLES[record['kind']]+' WHERE id=?', (rid,))
                seq = self.backend._audit(db, record['workspace_id'], {'id': uid}, str(uuid.uuid4()), 'record.delete', rid)
                db.execute('UPDATE records SET deleted=1,revision=revision+1,seq=? WHERE id=?', (seq, rid))
            self.backend.revoke_all_in(db, uid)
            for table in ('verification', 'password_recovery', 'email_changes', 'web_sessions', 'operations', 'account_recovery', 'account_mfa'):
                db.execute('DELETE FROM '+table+' WHERE user_id=?', (uid,))
            db.execute('DELETE FROM grants WHERE user_id=?', (uid,))
            db.execute('UPDATE memberships SET active=0,revision=revision+1 WHERE user_id=?', (uid,))
            db.execute("UPDATE devices SET label='Deleted account' WHERE user_id=?", (uid,))
            # Per-user pseudonym keeps shared FK history valid; no login is possible.
            db.execute('UPDATE users SET email=?,password_hash=?,salt=? WHERE id=?', ('deleted-'+uid+'@invalid.example', secrets.token_hex(32), secrets.token_hex(16), uid))
            db.execute('INSERT INTO account_state VALUES(?,0,?) ON CONFLICT(user_id) DO UPDATE SET deleted_at=excluded.deleted_at', (uid, max(1, now)))
            # SQLite development has no email_jobs. Production queues contain only
            # encrypted ephemeral verification/recovery material; clear matching jobs.
            if hasattr(db, 'raw'):
                for mail in db.execute('SELECT id,payload FROM email_jobs WHERE octet_length(payload)>0').fetchall():
                    import json
                    try: payload = json.loads(self.backend.cipher.decrypt(bytes(mail['payload'])))
                    except Exception: continue
                    if payload.get('email') == user['email']: db.execute('DELETE FROM email_jobs WHERE id=?', (mail['id'],))
            db.execute("UPDATE deletion_jobs SET state='completed',last_error=NULL WHERE id=?", (job['id'],))
        return True
