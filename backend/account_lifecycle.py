"""Verified account changes and reversible deletion requests; Android local data is untouched."""
import re
import hmac
import secrets
import uuid
from .service import require, token_hash, identifier, Failure

class AccountLifecycle:
    def __init__(self, backend): self.backend = backend

    def _reauthenticate(self, db, actor, password, reauth_token=None, code=None):
        self.backend._account_available(db, actor['id'])
        if reauth_token is not None:
            require(isinstance(reauth_token, str) and len(reauth_token) == 43, 'reauth_required', 401)
            row = db.execute('SELECT * FROM account_reauth_grants WHERE hash=? AND user_id=? AND expires_at>?', (token_hash(reauth_token), actor['id'], int(self.backend.clock()))).fetchone()
            require(row and actor.get('_auth_hash') and hmac.compare_digest(row['auth_hash'], actor['_auth_hash']), 'reauth_required', 401)
            from .google_identity import GoogleIdentity
            from .login_flow import LoginFlow
            GoogleIdentity(self.backend, None)._active_session(db, actor['id'], row['auth_hash'])
            flow = LoginFlow(self.backend)
            user, factor = flow._principal(db, actor['id'], False)
            require(user and hmac.compare_digest(row['credential_version'], flow._version(user, factor, False)), 'reauth_required', 401)
            db.execute('DELETE FROM account_reauth_grants WHERE hash=?', (row['hash'],))
        else:
            self.backend.reauthenticate(db, actor, password)
        from .customer_mfa import accept
        require(accept(self.backend, db, actor['id'], code), 'mfa_invalid', 403)

    def signup(self, email, password):
        # Same response for an existing address. Never invent a successful session.
        try:
            result = self.backend.register(email, password)
        except Failure as error:
            if error.code != 'account_exists': raise
            # Registration already performed the same password KDF as a new
            # address. Do not do a second login KDF (an address-existence oracle).
            # Explicit resend has its own generic, per-address/IP limited route.
            pass
        else:
            self.backend.logout(result['token'])
        return {'accepted': True, 'next': 'check_email'}

    def resend_signup(self, email):
        require(isinstance(email, str) and len(email) <= 254 and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email))
        email, now = email.casefold(), int(self.backend.clock())
        with self.backend.transaction() as db:
            key = token_hash('signup-resend:' + email)
            limit = db.execute('SELECT * FROM auth_limits WHERE key=?', (key,)).fetchone()
            require(limit is None or limit['until_at'] <= now, 'rate_limited', 429)
            db.execute('INSERT INTO auth_limits VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=excluded.count,until_at=excluded.until_at', (key, now + 60))
            user = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            if user and not user['verified']:
                self.backend._account_available(db, user['id'])
                code = secrets.token_urlsafe(32)
                db.execute('DELETE FROM verification WHERE user_id=?', (user['id'],))
                db.execute('INSERT INTO verification VALUES(?,?,?)', (token_hash(code), user['id'], now + 3600))
                self.backend._deliver(db, email, code, 'verification')
        return {'accepted': True, 'next': 'check_email'}

    def confirm_signup(self, email, code):
        require(isinstance(email, str) and len(email) <= 254 and isinstance(code, str) and len(code) == 43, 'verification_invalid')
        with self.backend.transaction() as db:
            user = db.execute('SELECT u.* FROM users u JOIN verification v ON v.user_id=u.id WHERE u.email=? AND u.verified=0 AND v.hash=? AND v.expires_at>?', (email.casefold(), token_hash(code), int(self.backend.clock()))).fetchone()
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
        now = int(self.backend.clock())
        with self.backend.connect() as db:
            job = db.execute('SELECT id,requested_at,due_at,state,last_error FROM deletion_jobs WHERE user_id=?', (actor['id'],)).fetchone()
            families = db.execute("SELECT w.id,w.name,w.revision AS workspace_revision FROM workspaces w WHERE w.creator_id=? AND w.kind='family' AND w.dissolved=0 AND EXISTS(SELECT 1 FROM memberships m WHERE m.workspace_id=w.id AND m.user_id<>? AND m.active=1)", (actor['id'], actor['id'])).fetchall()
            password = db.execute('SELECT has_password FROM account_credentials WHERE user_id=?', (actor['id'],)).fetchone()
            google = db.execute('SELECT 1 FROM google_identities WHERE user_id=?', (actor['id'],)).fetchone()
            mfa = db.execute('SELECT 1 FROM account_mfa WHERE user_id=?', (actor['id'],)).fetchone()
            staff = db.execute('SELECT 1 FROM staff WHERE user_id=? AND active=1', (actor['id'],)).fetchone()
            transfers=db.execute("SELECT t.id,t.workspace_id,w.name,t.from_id,t.expires_at FROM ownership_transfers t JOIN workspaces w ON w.id=t.workspace_id JOIN memberships m ON m.workspace_id=w.id AND m.user_id=t.to_id WHERE t.to_id=? AND t.expires_at>? AND t.accepted_at=0 AND w.creator_id=t.from_id AND w.dissolved=0 AND m.role='parent' AND m.active=1",(actor['id'],now)).fetchall()
            outgoing=[]
            for family in families:
                parent=db.execute("SELECT m.user_id,u.email FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.workspace_id=? AND m.user_id<>? AND m.role='parent' AND m.active=1 ORDER BY m.user_id LIMIT 1",(family['id'],actor['id'])).fetchone()
                recipient = parent['user_id'] if parent else None
                pending = db.execute(
                    'SELECT MAX(expires_at) AS deadline FROM ownership_transfers WHERE workspace_id=? AND from_id=? AND to_id=? AND accepted_at=0 AND expires_at>?',
                    (family['id'], actor['id'], recipient, now),
                ).fetchone() if recipient else None
                outgoing.append(dict(family, eligible_parent_id=recipient, eligible_parent_label=parent['email'] if parent else None, close_family_available=True,
                                     pending_until=pending['deadline'] if pending else None))
        durable=bool(getattr(self.backend,'erasure_ledger_path','') and getattr(self.backend,'erasure_ack_socket',''))
        return {'request': dict(job) if job else None, 'ownership_transfer_required': outgoing, 'incoming_transfers':[dict(t) for t in transfers], 'local_data_deleted': False, 'backup_erasure': 'independent_ledger_ack_configured' if durable else 'independent_ledger_ack_setup_required', 'has_password': password is None or bool(password['has_password']), 'google_linked': bool(google), 'mfa_required': bool(mfa), 'staff_offboarding_required': bool(staff), 'grace_seconds': 86400, 'cancel_available': bool(job and job['state'] == 'pending' and job['due_at'] > now)}

    def request_deletion(self, actor, password, confirmation, reauth_token=None, code=None):
        require(confirmation == 'DELETE', 'confirmation_required')
        self.backend.reserve_reauth(actor)
        with self.backend.transaction() as db:
            self._reauthenticate(db, actor, password, reauth_token, code)
            require(not db.execute("SELECT 1 FROM staff WHERE user_id=? AND active=1", (actor['id'],)).fetchone(), 'staff_offboarding_required', 409)
            blocked = db.execute("SELECT 1 FROM workspaces w WHERE w.creator_id=? AND w.kind='family' AND w.dissolved=0 AND EXISTS(SELECT 1 FROM memberships m WHERE m.workspace_id=w.id AND m.user_id<>? AND m.active=1)", (actor['id'], actor['id'])).fetchone()
            require(not blocked, 'ownership_transfer_required', 409)
            now = int(self.backend.clock())
            prior = db.execute('SELECT * FROM deletion_jobs WHERE user_id=?', (actor['id'],)).fetchone()
            if prior and prior['state'] == 'pending': return {'request_id': prior['id'], 'due_at': prior['due_at'], 'state': 'pending'}
            jid = str(uuid.uuid4())
            db.execute("INSERT INTO deletion_jobs VALUES(?,?,?,?,'pending',NULL) ON CONFLICT(user_id) DO UPDATE SET id=excluded.id,requested_at=excluded.requested_at,due_at=excluded.due_at,state='pending',last_error=NULL", (jid, actor['id'], now, now + 86400))
        return {'request_id': jid, 'due_at': now + 86400, 'state': 'pending'}

    def cancel_deletion(self, actor, password, reauth_token=None, code=None):
        self.backend.reserve_reauth(actor)
        with self.backend.transaction() as db:
            self._reauthenticate(db, actor, password, reauth_token, code)
            job = db.execute('SELECT due_at FROM deletion_jobs WHERE user_id=? AND state=\'pending\'', (actor['id'],)).fetchone()
            require(job is None or job['due_at'] > int(self.backend.clock()), 'deletion_started', 409)
            db.execute("UPDATE deletion_jobs SET state='cancelled' WHERE user_id=? AND state='pending'", (actor['id'],))
        return {'cancelled': True}

    def transfer(self, actor, wid, target, password, reauth_token=None, code=None):
        identifier(wid);identifier(target)
        self.backend.reserve_reauth(actor)
        now, tid = int(self.backend.clock()), str(uuid.uuid4())
        with self.backend.transaction() as db:
            self._reauthenticate(db, actor, password, reauth_token, code)
            row = db.execute("SELECT 1 FROM workspaces w JOIN memberships m ON m.workspace_id=w.id WHERE w.id=? AND w.creator_id=? AND w.kind='family' AND w.dissolved=0 AND m.user_id=? AND m.role='parent' AND m.active=1", (wid, actor['id'], target)).fetchone()
            require(row and target != actor['id'], 'transfer_forbidden', 403)
            pending = db.execute(
                'SELECT id FROM ownership_transfers WHERE workspace_id=? AND from_id=? AND to_id=? AND accepted_at=0 AND expires_at>? ORDER BY expires_at DESC,id LIMIT 1',
                (wid, actor['id'], target, now),
            ).fetchone()
            if pending:
                tid = pending['id']
            else:
                db.execute('INSERT INTO ownership_transfers VALUES(?,?,?,?,?,0)', (tid, wid, actor['id'], target, now + 86400))
        return {'transfer_id': tid, 'recipient_confirmation_required': True}

    def accept_transfer(self, actor, tid, password, reauth_token=None, code=None):
        identifier(tid);self.backend.reserve_reauth(actor)
        with self.backend.transaction() as db:
            self._reauthenticate(db, actor, password, reauth_token, code)
            row = db.execute('SELECT * FROM ownership_transfers WHERE id=? AND to_id=? AND expires_at>? AND accepted_at=0', (tid, actor['id'], int(self.backend.clock()))).fetchone()
            require(row is not None, 'transfer_invalid', 409)
            member = db.execute("SELECT 1 FROM memberships WHERE workspace_id=? AND user_id=? AND role='parent' AND active=1", (row['workspace_id'], actor['id'])).fetchone()
            space = db.execute('SELECT * FROM workspaces WHERE id=? AND creator_id=? AND dissolved=0', (row['workspace_id'], row['from_id'])).fetchone()
            require(member and space, 'transfer_invalid', 409)
            db.execute('UPDATE workspaces SET creator_id=?,revision=revision+1 WHERE id=?', (actor['id'], row['workspace_id']))
            db.execute('UPDATE ownership_transfers SET accepted_at=? WHERE id=?', (max(1, int(self.backend.clock())), tid))
            self.backend._audit(db, row['workspace_id'], actor, tid, 'workspace.ownership.transfer')
        return {'transferred': True}

    def close_family(self, actor, wid, revision, password, confirmation, reauth_token=None, code=None):
        identifier(wid)
        require(confirmation == 'CLOSE FAMILY', 'confirmation_required')
        self.backend.reserve_reauth(actor)
        with self.backend.transaction() as db:
            self._reauthenticate(db, actor, password, reauth_token, code)
            space = self.backend._workspace(db, actor, wid)
            require(space['kind'] == 'family' and space['creator_id'] == actor['id'], 'creator_only', 403)
            self.backend._revision(space, revision)
            # Identical to workspace.dissolve: explicitly close access for every
            # member, without erasing any other member's records or account.
            db.execute('UPDATE workspaces SET dissolved=1,revision=revision+1 WHERE id=?', (wid,))
            db.execute('UPDATE memberships SET active=0,revision=revision+1 WHERE workspace_id=?', (wid,))
            self.backend._audit(db, wid, actor, str(uuid.uuid4()), 'workspace.dissolve')
        return {'dissolved': True}

    def process_one_deletion(self):
        selected=[]
        try:
            return self._process_one_deletion(selected)
        except Exception as error:
            if not selected and isinstance(error, Failure) and error.code == 'privacy_delivery_busy': return False
            if not selected:raise
            # Rollback all payload changes before recording a bounded, non-secret
            # failure state. A bad request must not stop transactional mail delivery.
            with self.backend.transaction() as db:
                db.execute("UPDATE deletion_jobs SET state=CASE WHEN state='pending' THEN 'attention' ELSE state END,last_error=? WHERE id=? AND state IN ('pending','erasing')", (type(error).__name__,selected[0]))
            return True

    def _process_one_deletion(self, selected):
        """Freeze due consent, confirm independent durability, then erase."""
        now = int(self.backend.clock())
        with self.backend.connect() as db:
            candidate = db.execute("SELECT user_id FROM deletion_jobs WHERE state IN ('pending','erasing') AND due_at<=? ORDER BY due_at,id LIMIT 1", (now,)).fetchone()
        if not candidate: return False
        uid=candidate['user_id']
        # PostgreSQL holds only this subject's advisory lock during the remote
        # durability roundtrip. No global sync lock spans network latency.
        with self.backend.privacy_guard(uid):
            with self.backend.transaction() as db:
                job = db.execute("SELECT * FROM deletion_jobs WHERE user_id=? AND state IN ('pending','erasing') AND due_at<=?", (uid, now)).fetchone()
                if not job: return False
                selected.append(job['id'])
                if job['state']=='pending':
                    blocked = db.execute("SELECT 1 FROM workspaces w WHERE w.creator_id=? AND w.kind='family' AND w.dissolved=0 AND EXISTS(SELECT 1 FROM memberships m WHERE m.workspace_id=w.id AND m.user_id<>? AND m.active=1)", (uid, uid)).fetchone()
                    staff = db.execute('SELECT 1 FROM staff WHERE user_id=? AND active=1', (uid,)).fetchone()
                    if blocked or staff:
                        db.execute("UPDATE deletion_jobs SET state='attention',last_error='ownership_or_staff_changed' WHERE id=?", (job['id'],))
                        return True
                    # Cancellation already ended at due_at. Freeze old sessions
                    # before acknowledging an irreversible restore-suppression
                    # entry, so no new personal/family data can race this phase.
                    db.execute("UPDATE deletion_jobs SET state='erasing',last_error=NULL WHERE id=?",(job['id'],))
            from .account_erasure import append_ledger, acknowledge, erase_in
            path = getattr(self.backend, 'erasure_ledger_path', '')
            if path:
                append_ledger(path, uid, max(1, now))
                ack_socket=getattr(self.backend,'erasure_ack_socket','')
                if ack_socket:acknowledge(ack_socket,'acknowledge',uid,max(1,now))
            with self.backend.transaction() as db:
                erase_in(self.backend, db, uid, max(1, now))
        return True
