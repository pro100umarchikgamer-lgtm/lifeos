"""Account payload erasure and an independent, append-only restore suppression ledger.

Ledger lines contain only {user_id: UUID, erased_at: epoch seconds}. They contain
no email/address hash, provider identity, record content, credential or mail data.
The external file must survive independently of database backup/restore.
"""
import argparse
import fcntl
import json
import os
import secrets
import socket
import stat
import uuid

from .service import TABLES, identifier, token_hash


def mail_subject(db, email, code, purpose):
    # A prospective address is not proof of who owns an account. Attribute an
    # email-change job only through its exact one-use code, never UNION/LIMIT
    # across unrelated users who later register that address.
    if purpose == 'email_change' and isinstance(code,str):
        return db.execute('SELECT user_id FROM email_changes WHERE email=? AND hash=?', (email,token_hash(code))).fetchone()
    return db.execute('SELECT id AS user_id FROM users WHERE email=?', (email,)).fetchone()


def erase_in(backend, db, uid, now):
    """Erase one subject in the caller's serialized transaction; safe to repeat."""
    user = db.execute('SELECT email FROM users WHERE id=?', (uid,)).fetchone()
    db.execute('INSERT INTO account_erasure_ledger VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET erased_at=excluded.erased_at', (uid, now))
    if user is None:
        return
    email = user['email']
    emails = {email}
    reauth_hashes = {r['hash'] for r in db.execute('SELECT hash FROM account_reauth_grants WHERE user_id=?', (uid,))}
    login_hashes = {r['hash'] for r in db.execute('SELECT hash FROM login_challenges WHERE user_id=?', (uid,))}
    pending_changes = db.execute('SELECT email,hash FROM email_changes WHERE user_id=?', (uid,)).fetchall()
    pending_mail_hashes = {r['hash'] for r in pending_changes}
    subjects = {uid}
    subjects.update(r['id'] for r in db.execute('SELECT id FROM staff WHERE user_id=?', (uid,)))
    subjects.update(r['id'] for r in db.execute('SELECT id FROM support_tickets WHERE user_id=?', (uid,)))
    subjects.update(r['id'] for r in db.execute('SELECT id FROM record_recovery_requests WHERE user_id=?', (uid,)))
    for email in emails:
        subjects.update(r['id'] for r in db.execute('SELECT id FROM early_access WHERE email=?', (email,)))
    for subject in subjects:
        db.execute('DELETE FROM control_audit_notes WHERE subject_id=? OR actor_id=? OR actor_id=?', (subject,subject,'user:'+subject))
        db.execute('DELETE FROM flag_proposals WHERE actor_id=?', (subject,))
    # Block account-bound operations before erasing any payload. A failed outer
    # transaction rolls back every change; the independent ledger remains safe.
    db.execute('INSERT INTO account_state VALUES(?,0,?) ON CONFLICT(user_id) DO UPDATE SET disabled_until=0,deleted_at=excluded.deleted_at', (uid, max(1, now)))
    rows = db.execute('SELECT * FROM records WHERE owner_id=?', (uid,)).fetchall()
    released_references = set()
    for record in rows:
        rid = record['id']
        if record['kind'] == 'transfer':
            transfer = db.execute('SELECT from_id,to_id FROM transfers WHERE id=?', (rid,)).fetchone()
            if transfer: released_references.update((transfer['from_id'], transfer['to_id']))
        # Surviving participants' optional links can be detached without changing
        # their own amounts, currencies, dates, labels or fulfilled state.
        for table, field in (('transactions', 'account_id'), ('requests', 'movement_id')):
            peers = db.execute('SELECT r.* FROM '+table+' d JOIN records r ON r.id=d.id WHERE d.'+field+'=? AND r.owner_id<>?', (rid, uid)).fetchall()
            for peer in peers:
                db.execute('UPDATE '+table+' SET '+field+'=NULL WHERE id=?', (peer['id'],))
                seq = backend._audit(db, peer['workspace_id'], {'id': uid}, str(uuid.uuid4()), 'record.privacy.detach', peer['id'])
                db.execute('UPDATE records SET revision=revision+1,seq=? WHERE id=?', (seq, peer['id']))
                # Any old approval hashes refer to a previous exact preview.
                db.execute('DELETE FROM record_recovery_requests WHERE record_id=?', (peer['id'],))
        # An immutable peer transfer must keep its two structural account IDs.
        # Keep only a generic, read-only account shell (never the original name
        # or private opening value); every other owned payload is physically gone.
        stub = record['kind'] == 'account' and db.execute('SELECT 1 FROM transfers t JOIN records r ON r.id=t.id WHERE r.owner_id<>? AND (t.from_id=? OR t.to_id=?) LIMIT 1', (uid, rid, rid)).fetchone()
        db.execute('DELETE FROM grants WHERE record_id=?', (rid,))
        db.execute('DELETE FROM record_recovery_requests WHERE record_id=?', (rid,))
        backend._audit(db, record['workspace_id'], {'id': uid}, str(uuid.uuid4()), 'access.changed', rid)
        if stub:
            db.execute("UPDATE accounts SET name='Deleted account',opening_minor=0 WHERE id=?", (rid,))
            db.execute('INSERT INTO erased_financial_stubs VALUES(?,?) ON CONFLICT(record_id) DO NOTHING', (rid, now))
            seq = backend._audit(db, record['workspace_id'], {'id': uid}, str(uuid.uuid4()), 'record.privacy.stub', rid)
            db.execute("UPDATE records SET deleted=1,audience='[]',revision=revision+1,seq=? WHERE id=?", (seq, rid))
        else:
            db.execute('DELETE FROM task_progress WHERE task_id=?', (rid,))
            db.execute('DELETE FROM '+TABLES[record['kind']]+' WHERE id=?', (rid,))
            db.execute('DELETE FROM erased_financial_stubs WHERE record_id=?', (rid,))
            seq = backend._audit(db, record['workspace_id'], {'id': uid}, str(uuid.uuid4()), 'record.delete', rid)
            db.execute("UPDATE records SET deleted=1,audience='[]',revision=revision+1,seq=? WHERE id=?", (seq, rid))
    # A previously erased participant's currency shell ceases to be necessary
    # when this erasure removes its last recoverable peer transfer reference.
    for rid in released_references:
        stub = db.execute('SELECT r.* FROM erased_financial_stubs s JOIN records r ON r.id=s.record_id WHERE s.record_id=?', (rid,)).fetchone()
        linked = db.execute('SELECT 1 FROM transfers WHERE from_id=? OR to_id=? LIMIT 1', (rid,rid)).fetchone()
        if stub and not linked:
            db.execute('DELETE FROM accounts WHERE id=?', (rid,))
            db.execute('DELETE FROM erased_financial_stubs WHERE record_id=?', (rid,))
            seq=backend._audit(db,stub['workspace_id'],{'id':uid},str(uuid.uuid4()),'record.delete',rid)
            db.execute('UPDATE records SET revision=revision+1,seq=? WHERE id=?', (seq,rid))
    backend.revoke_all_in(db, uid)
    for table in ('budget_inbox_sources', 'budget_inbox_notifications', 'inbox_settings', 'inbox_notifications', 'announcement_states', 'announcement_recipients', 'web_push_subscriptions', 'verification', 'password_recovery', 'email_changes', 'web_sessions', 'operations', 'account_recovery', 'account_mfa', 'login_challenges', 'google_identities', 'account_credentials', 'oauth_challenges', 'account_reauth_grants', 'entitlement_grants', 'entitlement_overrides', 'service_holds', 'record_recovery_requests'):
        db.execute('DELETE FROM '+table+' WHERE user_id=?', (uid,))
    db.execute('DELETE FROM refresh_tokens WHERE user_id=?', (uid,))
    db.execute('DELETE FROM devices WHERE user_id=?', (uid,))
    db.execute('DELETE FROM grants WHERE user_id=?', (uid,))
    db.execute('DELETE FROM provider_events WHERE EXISTS(SELECT 1 FROM provider_purchases p WHERE p.user_id=? AND p.source=provider_events.source AND p.reference_hash=provider_events.reference_hash)', (uid,))
    db.execute('DELETE FROM provider_purchases WHERE user_id=?', (uid,))
    db.execute('DELETE FROM support_messages WHERE ticket_id IN (SELECT id FROM support_tickets WHERE user_id=?)', (uid,))
    db.execute('DELETE FROM support_tickets WHERE user_id=?', (uid,))
    # A former inactive staff member's replies on others' threads are their data;
    # remove only their contributed message text, preserving the other thread.
    db.execute('DELETE FROM support_messages WHERE actor_id=? OR actor_id IN (SELECT id FROM staff WHERE user_id=?)', (uid, uid))
    db.execute('DELETE FROM invitations WHERE issued_by=? OR used_by=?', (uid, uid))
    db.execute('DELETE FROM ownership_transfers WHERE from_id=? OR to_id=?', (uid, uid))
    db.execute('DELETE FROM parent_changes WHERE target_id=? OR requested_by=? OR approved_by=?', (uid, uid, uid))
    db.execute('DELETE FROM staff_invitations WHERE issued_by IN (SELECT id FROM staff WHERE user_id=?)', (uid,))
    db.execute('DELETE FROM staff_recovery WHERE staff_id IN (SELECT id FROM staff WHERE user_id=?)', (uid,))
    db.execute("UPDATE staff SET mfa_secret=?,roles='[]',active=0,last_counter=-1,created_at=0 WHERE user_id=?", (b'', uid))
    for email in emails:
        db.execute('DELETE FROM invitations WHERE email=?', (email,))
        db.execute('DELETE FROM staff_invitations WHERE email=?', (email,))
        db.execute('DELETE FROM early_access WHERE email=?', (email,))
        db.execute('DELETE FROM owner_setup WHERE email=?', (email,))
        for key in (token_hash(email), 'recovery:'+token_hash(email), token_hash('control-login:'+email), token_hash('signup-resend:'+email)):
            db.execute('DELETE FROM auth_limits WHERE key=?', (key,))
        for prefix in ('email:', 'confirm:'):
            db.execute('DELETE FROM early_access_limits WHERE key=?', (token_hash('early-access:'+prefix+email),))
    for prefix in ('reauth:', 'verify:'):
        db.execute('DELETE FROM auth_limits WHERE key=?', (token_hash(prefix+uid),))
    # Linked child profiles can carry the deleted account holder's display name.
    db.execute("UPDATE profiles SET name='Deleted member',permissions='[]',archived=1,revision=revision+1 WHERE id IN (SELECT profile_id FROM memberships WHERE user_id=?)", (uid,))
    db.execute('UPDATE memberships SET active=0,revision=revision+1 WHERE user_id=?', (uid,))
    for membership in db.execute('SELECT workspace_id FROM memberships WHERE user_id=?', (uid,)).fetchall():
        # Even an account with no owned records must invalidate cached roster,
        # profile identity and old granted access in the other members' mirrors.
        backend._audit(db,membership['workspace_id'],{'id':uid},str(uuid.uuid4()),'account.erase')
    for space in db.execute('SELECT id,kind FROM workspaces WHERE creator_id=?', (uid,)).fetchall():
        peers = db.execute('SELECT 1 FROM memberships WHERE workspace_id=? AND user_id<>? LIMIT 1', (space['id'], uid)).fetchone()
        db.execute("UPDATE workspaces SET name='Deleted workspace',revision=revision+1 WHERE id=?", (space['id'],))
        if space['kind'] == 'personal' or not peers:
            db.execute('UPDATE workspaces SET dissolved=1 WHERE id=?', (space['id'],))
    # No original address hash or account timestamps survive in the tombstone.
    # Outside the accepted email syntax, so another signup cannot reserve the
    # predictable marker and block this subject's erasure via UNIQUE(email).
    db.execute('UPDATE users SET email=?,password_hash=?,salt=?,verified=0,created_at=0 WHERE id=?', ('deleted:'+uid, secrets.token_hex(32), secrets.token_hex(16), uid))
    # Ephemeral encrypted OAuth results lack a user column. Clear only results
    # containing this account/session, never another user's active sign-in.
    for row in db.execute('SELECT hash,payload FROM oauth_web_results').fetchall():
        try:
            value = json.loads(backend.cipher.decrypt(bytes(row['payload'])))
        except Exception:
            # Invalid ciphertext must not remain an actionable credential.
            db.execute('DELETE FROM oauth_web_results WHERE hash=?', (row['hash'],))
            continue
        if value.get('user_id') == uid or (isinstance(value.get('reauth_token'), str) and token_hash(value['reauth_token']) in reauth_hashes) or (isinstance(value.get('challenge'), str) and token_hash(value['challenge']) in login_hashes):
            # Reauth proofs are already revoked; remove ephemeral wrappers too.
            db.execute('DELETE FROM oauth_web_results WHERE hash=?', (row['hash'],))
    if hasattr(db, 'raw'):
        db.execute('DELETE FROM email_jobs WHERE user_id=?', (uid,))
        for mail in db.execute('SELECT id,payload,user_id FROM email_jobs WHERE octet_length(payload)>0').fetchall():
            if mail['user_id'] not in (None,uid): continue
            try:
                payload = json.loads(backend.cipher.decrypt(bytes(mail['payload'])))
            except Exception:
                continue
            own_change = isinstance(payload.get('code'),str) and token_hash(payload['code']) in pending_mail_hashes
            if payload.get('email') == email or own_change:
                db.execute('DELETE FROM email_jobs WHERE id=?', (mail['id'],))
    db.execute("UPDATE deletion_jobs SET state='completed',last_error=NULL,requested_at=0 WHERE user_id=?", (uid,))


def _open_ledger(path, flags):
    fd = os.open(path, flags | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        os.close(fd)
        raise RuntimeError('Erasure ledger must be a private regular file')
    return fd


def append_ledger(path, uid, erased_at):
    """Commit restore suppression before DB erasure. No silent file creation."""
    identifier(uid)
    entry = json.dumps({'user_id': uid, 'erased_at': erased_at}, separators=(',', ':')) + '\n'
    fd = _open_ledger(path, os.O_WRONLY | os.O_APPEND)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        data = entry.encode('ascii')
        if os.write(fd, data) != len(data): raise RuntimeError('Incomplete erasure ledger write')
        os.fsync(fd)
    finally:
        os.close(fd)


def read_ledger(path, confirmed_bytes=None):
    fd = _open_ledger(path, os.O_RDONLY)
    fcntl.flock(fd, fcntl.LOCK_SH)
    entries = {}
    with os.fdopen(fd, 'rb') as stream:
        size=os.fstat(stream.fileno()).st_size
        if confirmed_bytes is not None and (type(confirmed_bytes) is not int or not 0<=confirmed_bytes<=size):
            raise RuntimeError('Invalid acknowledged ledger prefix')
        remaining=size if confirmed_bytes is None else confirmed_bytes
        while remaining:
            line=stream.readline(min(257,remaining))
            remaining-=len(line)
            if not line or len(line) > 256 or not line.endswith(b'\n'): raise RuntimeError('Invalid erasure ledger entry')
            value = json.loads(line)
            if set(value) != {'user_id', 'erased_at'}: raise RuntimeError('Invalid erasure ledger fields')
            uid = identifier(value['user_id'])
            stamp = value['erased_at']
            if type(stamp) is not int or stamp < 1: raise RuntimeError('Invalid erasure timestamp')
            entries[uid] = max(stamp, entries.get(uid, 0))
    return entries


def apply_ledger(backend, entries):
    count = 0
    for uid, stamp in entries.items():
        with backend.transaction(account_id=uid) as db:
            prior = db.execute('SELECT erased_at FROM account_erasure_ledger WHERE user_id=?', (uid,)).fetchone()
            state = db.execute('SELECT deleted_at FROM account_state WHERE user_id=?', (uid,)).fetchone()
            if not prior or prior['erased_at'] < stamp or (state and not state['deleted_at']):
                erase_in(backend, db, uid, stamp)
                count += 1
    return count


def acknowledge(socket_path, action, user_id=None, erased_at=None):
    """Root-owned local service confirms independently durable encrypted copy.

    No remote credential, path, email, token or record payload crosses this API.
    """
    request={'action':action}
    if action == 'acknowledge': request.update(user_id=identifier(user_id),erased_at=erased_at)
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(20)
        client.connect(socket_path)
        client.sendall((json.dumps(request,separators=(',',':'))+'\n').encode('ascii'))
        data=b''
        while b'\n' not in data:
            part=client.recv(1025-len(data))
            if not part or len(data)+len(part)>1024:raise RuntimeError('Invalid erasure durability acknowledgment')
            data+=part
        response=json.loads(data.split(b'\n',1)[0])
    if response.get('acknowledged') is not True:raise RuntimeError('Erasure durability acknowledgment unavailable')
    if action == 'acknowledge' and (response.get('user_id')!=user_id or type(response.get('erased_at')) is not int or response['erased_at']<erased_at):
        raise RuntimeError('Erasure durability acknowledgment mismatch')
    if action == 'synchronize' and (type(response.get('ledger_bytes')) is not int or response['ledger_bytes']<0):
        raise RuntimeError('Missing acknowledged ledger prefix')
    return response


def initialize(backend, path, ack_socket=''):
    """Fail closed before an API or worker starts on a restored database."""
    if not path:
        if ack_socket:raise RuntimeError('Erasure durability service requires a ledger')
        return
    response=acknowledge(ack_socket,'synchronize') if ack_socket else None
    entries = read_ledger(path,response['ledger_bytes'] if response else None)
    apply_ledger(backend, entries)
    backend.erasure_ledger_path = path
    backend.erasure_ack_socket = ack_socket


def prune_ephemeral(backend):
    """Physical expiry of auth metadata and detailed, erasable security notes."""
    now = int(backend.clock())
    if now < getattr(backend, '_privacy_prune_at', 0): return
    with backend.transaction() as db:
        db.execute('DELETE FROM control_audit_notes WHERE expires_at<=?', (now,))
        db.execute('DELETE FROM flag_proposals WHERE used_at>0 OR expires_at<=?', (now,))
        for table in ('auth_limits','early_access_limits'):
            db.execute('DELETE FROM '+table+' WHERE until_at<=?', (now,))
        for table in ('account_reauth_grants','oauth_challenges','oauth_web_results','login_challenges','verification','password_recovery','email_changes'):
            db.execute('DELETE FROM '+table+' WHERE expires_at<=?', (now,))
    backend._privacy_prune_at = now + 900


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('export-ledger', 'apply-ledger'):
        item = sub.add_parser(command)
        item.add_argument('--ledger', required=True)
    sub.add_parser('legacy-audit-inventory')
    args = parser.parse_args()
    from cryptography.fernet import Fernet
    from .config import Settings
    from .postgres import PostgresBackend
    settings = Settings.load()
    backend = PostgresBackend(settings.database_url, Fernet(settings.email_queue_key.encode()), pool_size=1)
    try:
        if args.command == 'legacy-audit-inventory':
            with backend.connect() as db:
                total=db.execute('SELECT COUNT(*) AS n FROM control_audit').fetchone()['n']
                legacy=db.execute('SELECT COUNT(*) AS n FROM control_audit WHERE format_version<2').fetchone()['n']
                legacy_accounts=db.execute('SELECT COUNT(*) AS n FROM account_state a WHERE a.deleted_at>0 AND NOT EXISTS(SELECT 1 FROM account_erasure_ledger e WHERE e.user_id=a.user_id)').fetchone()['n']
                payloads=sum(db.execute('SELECT COUNT(*) AS n FROM '+table+' d JOIN records r ON r.id=d.id JOIN account_state a ON a.user_id=r.owner_id WHERE a.deleted_at>0 AND NOT EXISTS(SELECT 1 FROM account_erasure_ledger e WHERE e.user_id=a.user_id)').fetchone()['n'] for table in TABLES.values())
            print(json.dumps({'security_events':total,'legacy_freeform_events':legacy,'legacy_deleted_accounts':legacy_accounts,'legacy_deleted_owned_payloads':payloads}))
            return
        # Export is a monotonic merge: never replace/drop independent entries.
        response=acknowledge(settings.account_erasure_ack_socket,'synchronize') if args.command=='apply-ledger' and settings.account_erasure_ack_socket else None
        entries = read_ledger(args.ledger,response['ledger_bytes'] if response else None)
        if args.command == 'export-ledger':
            with backend.connect() as db:
                for row in db.execute('SELECT user_id,erased_at FROM account_erasure_ledger'):
                    if row['erased_at'] > entries.get(row['user_id'], 0):
                        append_ledger(args.ledger, row['user_id'], row['erased_at'])
            print('Erasure ledger merged')
        else:
            count = apply_ledger(backend, entries)
            print('Erasure ledger applied:', count)
    finally:
        backend.close()


if __name__ == '__main__': main()
