"""Owner-consented trash payload erasure with independently confirmed suppression.

The separate record journal contains only record_id/erased_at. It is never passed
to the account erasure journal or protocol. Unconfigured durability disables this
feature; a local append is not an offsite acknowledgment.
"""
import fcntl
import hashlib
import hmac
import json
import os
import re
import socket
import stat
import struct
import uuid

from .record_recovery import RecordRecovery
from .service import Failure, TABLES, canonical, identifier, require, token_hash

PROTOCOL = 'uladim-record-erasure-v1'
MAX_LEDGER = 16 * 1024 * 1024
MAX_STAMP = 2**63 - 1


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value: raise ValueError('Duplicate record erasure field')
        value[key] = item
    return value


def acknowledge(path, action, record_id=None, erased_at=None):
    request = {'protocol': PROTOCOL, 'action': action}
    require(action in ('synchronize', 'acknowledge'), 'record_erasure_unavailable', 503)
    if action == 'acknowledge':
        request.update(record_id=identifier(record_id), erased_at=erased_at)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(20); client.connect(path)
        _, uid, _ = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i')))
        if uid != 0: raise RuntimeError('Record durability peer is not root')
        client.sendall((canonical(request) + '\n').encode('ascii'))
        data = b''
        while b'\n' not in data:
            part = client.recv(1025-len(data))
            if not part or len(data)+len(part)>1024: raise RuntimeError('Record acknowledgment exceeds bound')
            data += part
        if not data.endswith(b'\n') or data.count(b'\n') != 1: raise RuntimeError('Record acknowledgment framing differs')
    response = json.loads(data, object_pairs_hook=unique)
    fields = {'protocol', 'acknowledged', 'ledger_bytes', 'ledger_sha256'}
    if action == 'acknowledge': fields |= {'record_id', 'erased_at'}
    if (not isinstance(response, dict) or set(response) != fields or response['protocol'] != PROTOCOL
            or response['acknowledged'] is not True or type(response['ledger_bytes']) is not int
            or not 0 <= response['ledger_bytes'] <= MAX_LEDGER
            or not isinstance(response['ledger_sha256'], str) or not re.fullmatch('[a-f0-9]{64}', response['ledger_sha256'])):
        raise RuntimeError('Record acknowledgment identity differs')
    if action == 'acknowledge' and (response['record_id'] != record_id or type(response['erased_at']) is not int
                                    or not erased_at <= response['erased_at'] <= MAX_STAMP):
        raise RuntimeError('Record-specific acknowledgment differs')
    return response


def read_confirmed(path, response):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid not in (0, os.geteuid())
                or info.st_mode & 0o077 or info.st_nlink != 1):
            raise RuntimeError('Record journal must be a private regular file')
        fcntl.flock(fd, fcntl.LOCK_SH)
        remaining = response['ledger_bytes']
        if not 0 <= remaining <= min(info.st_size, MAX_LEDGER): raise RuntimeError('Record prefix exceeds journal')
        chunks = []
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk: raise RuntimeError('Record prefix is incomplete')
            chunks.append(chunk); remaining -= len(chunk)
        raw = b''.join(chunks)
        if not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), response['ledger_sha256']):
            raise RuntimeError('Record prefix acknowledgment digest differs')
        entries = {}
        if raw and not raw.endswith(b'\n'): raise RuntimeError('Incomplete record journal line')
        for line in raw.splitlines(keepends=True):
            if len(line)>256: raise RuntimeError('Record journal line exceeds bound')
            value = json.loads(line, object_pairs_hook=unique)
            if not isinstance(value,dict) or set(value) != {'record_id','erased_at'}:
                raise RuntimeError('Record journal scope differs')
            rid, stamp = identifier(value['record_id']), value['erased_at']
            if type(stamp) is not int or not 0 < stamp <= MAX_STAMP: raise RuntimeError('Record journal timestamp differs')
            entries[rid] = max(stamp, entries.get(rid, 0))
        return entries
    finally: os.close(fd)


def block_in(db, rid):
    require(not db.execute('SELECT 1 FROM record_erasure_ledger WHERE record_id=?', (rid,)).fetchone(), 'record_erased', 409)
    require(not db.execute('SELECT 1 FROM record_erasure_intents WHERE record_id=?', (rid,)).fetchone(), 'record_erasure_pending', 409)


def references_in(db, rid, erased=()):
    allowed = set(erased)
    for table, column in (('transactions','account_id'), ('transfers','from_id'), ('transfers','to_id'), ('requests','movement_id')):
        # Deleted payloads can still be restored; all retained references count.
        rows = db.execute('SELECT id FROM '+table+' WHERE '+column+'=?', (rid,)).fetchall()
        require(all(row['id'] in allowed for row in rows), 'record_erasure_linked', 409)


def erase_in(backend, db, rid, stamp):
    prior = db.execute('SELECT erased_at FROM record_erasure_ledger WHERE record_id=?', (rid,)).fetchone()
    row = db.execute('SELECT * FROM records WHERE id=?', (rid,)).fetchone()
    intent = db.execute('SELECT * FROM record_erasure_intents WHERE record_id=?', (rid,)).fetchone()
    if row and intent and row['owner_id'] != intent['user_id']: raise RuntimeError('Record intent owner changed')
    exists = row and any(db.execute('SELECT 1 FROM '+table+' WHERE id=?', (rid,)).fetchone() for table in TABLES.values())
    changed = not prior or prior['erased_at'] < stamp or row and (not row['deleted'] or exists or row['audience']!='[]'
        or db.execute('SELECT 1 FROM grants WHERE record_id=?',(rid,)).fetchone())
    db.execute('INSERT INTO record_erasure_ledger VALUES(?,?) ON CONFLICT(record_id) DO UPDATE SET erased_at=excluded.erased_at', (rid, max(stamp, prior['erased_at'] if prior else 0)))
    if row:
        operation = intent['operation_id'] if intent else str(uuid.uuid4())
        if changed:
            # Removing grants/audience revokes visibility. Offline peers that
            # missed the soft-delete must reset their formerly readable cache.
            backend._audit(db,row['workspace_id'],{'id':row['owner_id']},operation,'access.changed',rid)
        for table, field in (('grants','record_id'), ('task_progress','task_id'), ('task_reminders','task_id'),
                             ('record_recovery_requests','record_id'), ('web_push_deliveries','event_id'), ('erased_financial_stubs','record_id')):
            db.execute('DELETE FROM '+table+' WHERE '+field+'=?', (rid,))
        for prefix in ('event:'+rid+':%', 'task:'+rid+':%'):
            db.execute('DELETE FROM inbox_notifications WHERE source_key LIKE ?', (prefix,))
        for table in ('budget_inbox_notifications', 'budget_inbox_sources'):
            db.execute('DELETE FROM '+table+' WHERE source_key LIKE ?', (rid+':%',))
        for table in TABLES.values(): db.execute('DELETE FROM '+table+' WHERE id=?', (rid,))
        if changed:
            seq = backend._audit(db, row['workspace_id'], {'id':row['owner_id']}, operation, 'record.purge', rid)
            db.execute("UPDATE records SET deleted=1,audience='[]',revision=revision+1,seq=? WHERE id=?", (seq, rid))
        # Canonical operation receipts contain no record body. Replace old body
        # digests too; UUID suppression prevents an old operation recreating data.
        for receipt in db.execute('SELECT user_id,id,result FROM operations WHERE result LIKE ?', ('%"record_id":"'+rid+'"%',)).fetchall():
            result = json.loads(receipt['result'])
            if result.get('record_id') == rid and result.get('erased') is not True:
                db.execute('UPDATE operations SET digest=? WHERE user_id=? AND id=?', (token_hash('record-erased:'+rid+':'+receipt['id']), receipt['user_id'], receipt['id']))
        if intent:
            op = {'id':intent['operation_id'], 'action':'record.purge', 'record_id':rid,
                  'revision':intent['record_revision'], 'consent_hash':intent['consent_hash']}
            if token_hash(canonical(op)) != intent['operation_digest']: raise RuntimeError('Record intent operation differs')
            result = {'id':op['id'], 'status':'accepted', 'record_id':rid,
                      'revision':db.execute('SELECT revision FROM records WHERE id=?',(rid,)).fetchone()['revision'], 'erased':True}
            backend._remember(db, {'id':intent['user_id']}, op, result)
    db.execute('DELETE FROM record_erasure_intents WHERE record_id=?', (rid,))


def apply_ledger(backend, entries):
    with backend.transaction() as db:
        # A restored backup can contain references whose deletion was separately
        # confirmed. Surviving references outside this confirmed set stop startup.
        for rid in entries: references_in(db, rid, entries)
        for rid, stamp in entries.items(): erase_in(backend, db, rid, stamp)


def synchronize(backend):
    path, endpoint = getattr(backend,'record_erasure_ledger_path',''), getattr(backend,'record_erasure_ack_socket','')
    if not path or not endpoint: raise RuntimeError('Record durability is not configured')
    response = acknowledge(endpoint, 'synchronize')
    entries = read_confirmed(path, response)
    with backend.connect() as db:
        for prior in db.execute('SELECT record_id,erased_at FROM record_erasure_ledger'):
            if entries.get(prior['record_id'],0) < prior['erased_at']:
                raise RuntimeError('Independent record suppression was rewound')
    apply_ledger(backend, entries)
    backend.record_erasure_ready = True
    return entries


def initialize(backend, path='', ack_socket='', required=False):
    backend.record_erasure_ready = False
    if not path and not ack_socket:
        with backend.connect() as db:
            prior = db.execute('SELECT 1 FROM record_erasure_ledger LIMIT 1').fetchone() or db.execute('SELECT 1 FROM record_erasure_intents LIMIT 1').fetchone()
        if required or prior: raise RuntimeError('Existing record erasure requires independent suppression before startup')
        return
    if not path or not ack_socket: raise RuntimeError('Record durability requires journal and root acknowledgment')
    backend.record_erasure_ledger_path, backend.record_erasure_ack_socket = path, ack_socket
    synchronize(backend)


def resume_pending(backend):
    """Finish one already-consented intent after a crash before the first IPC."""
    if not getattr(backend,'record_erasure_ledger_path','') or not getattr(backend,'record_erasure_ack_socket',''):
        return False
    with backend.transaction() as db:
        intent=db.execute('SELECT * FROM record_erasure_intents ORDER BY erased_at,record_id LIMIT 1').fetchone()
        if not intent:return False
        row=db.execute('SELECT * FROM records WHERE id=?',(intent['record_id'],)).fetchone()
        require(row and row['owner_id']==intent['user_id'] and row['deleted']==1
                and row['revision']==intent['record_revision'],'record_erasure_stale',409)
        recovery=RecordRecovery(backend)
        require(hmac.compare_digest(recovery._hash(recovery._payload(db,row)),intent['consent_hash']),'record_erasure_stale',409)
        references_in(db,intent['record_id'])
    response=acknowledge(backend.record_erasure_ack_socket,'acknowledge',intent['record_id'],intent['erased_at'])
    entries=read_confirmed(backend.record_erasure_ledger_path,response)
    if entries.get(intent['record_id'],0)<intent['erased_at']:raise RuntimeError('Pending record is absent from durable journal')
    apply_ledger(backend,entries)
    return True


class RecordErasure:
    def __init__(self, backend):
        self.backend, self.recovery = backend, RecordRecovery(backend)

    def available(self):
        try:
            synchronize(self.backend)
            return True
        except Exception:
            self.backend.record_erasure_ready = False
            return False

    def _account(self, db, actor):
        self.recovery._account(db,actor)
        current = db.execute('SELECT verified FROM users WHERE id=?',(actor['id'],)).fetchone()
        require(current and current['verified']==1,'verify_email',403)

    def _owner(self,db,actor,rid):
        self._account(db,actor)
        row=db.execute('SELECT * FROM records WHERE id=? AND owner_id=?',(rid,actor['id'])).fetchone()
        require(row is not None,'not_found',404)
        space=self.recovery._space(db,actor,row['workspace_id'])
        require(self.backend._editable(db,actor,space,row),'record_forbidden',403)
        return row,space

    def _sync(self):
        try: return synchronize(self.backend)
        except Exception:
            self.backend.record_erasure_ready = False
            raise Failure('record_erasure_unavailable', 503) from None

    def preview(self, actor, rid):
        rid=identifier(rid)
        with self.backend.connect() as db:self._owner(db,actor,rid)
        available = self.available()
        with self.backend.transaction() as db:
            row,space=self._owner(db,actor,rid)
            if db.execute('SELECT 1 FROM record_erasure_ledger WHERE record_id=?',(rid,)).fetchone():
                return {'erased':True,'record_id':rid,'permanent_delete_available':available,'pending_operation_id':None}
            row, space = self.recovery._owner_record(db, actor, rid)
            require(self.backend._editable(db,actor,space,row), 'record_forbidden',403)
            value = self.recovery._payload(db,row)
            value['consent_hash'] = self.recovery._hash(value)
            intent = db.execute('SELECT operation_id FROM record_erasure_intents WHERE record_id=?',(rid,)).fetchone()
            return {'record':value, 'permanent_delete_available':available,
                    'pending_operation_id':intent['operation_id'] if intent else None}

    def purge(self, actor, body):
        require(isinstance(body,dict) and set(body)=={'operation_id','record_id','revision','consent_hash'})
        rid, operation = identifier(body['record_id']), identifier(body['operation_id'])
        require(type(body['revision']) is int and body['revision']>0 and isinstance(body['consent_hash'],str)
                and re.fullmatch('[a-f0-9]{64}',body['consent_hash']), 'record_erasure_stale',409)
        op = {'id':operation, 'action':'record.purge', 'record_id':rid,
              'revision':body['revision'], 'consent_hash':body['consent_hash']}
        with self.backend.connect() as db:self._owner(db,actor,rid)
        self._sync()
        with self.backend.transaction() as db:
            row,space=self._owner(db,actor,rid)
            prior = self.backend._idempotent(db,actor,op)
            if prior: return prior
            require(not db.execute('SELECT 1 FROM record_erasure_ledger WHERE record_id=?',(rid,)).fetchone(),'record_erased',409)
            intent = db.execute('SELECT * FROM record_erasure_intents WHERE record_id=?',(rid,)).fetchone()
            if intent:
                require(intent['user_id']==actor['id'] and intent['operation_id']==operation
                        and intent['operation_digest']==token_hash(canonical(op)), 'record_erasure_pending',409)
            else:
                require(row['deleted']==1,'not_found',404)
                value = self.recovery._payload(db,row)
                require(row['revision']==body['revision'] and hmac.compare_digest(self.recovery._hash(value),body['consent_hash']), 'record_erasure_stale',409)
                references_in(db,rid)
                stamp = max(1,int(self.backend.clock()))
                db.execute('INSERT INTO record_erasure_intents VALUES(?,?,?,?,?,?,?)',
                           (rid,actor['id'],operation,row['revision'],body['consent_hash'],stamp,token_hash(canonical(op))))
                db.execute("UPDATE record_recovery_requests SET state='cancelled',grant_hash='',grant_expires_at=0 WHERE record_id=?",(rid,))
                intent = db.execute('SELECT * FROM record_erasure_intents WHERE record_id=?',(rid,)).fetchone()
        try:
            response = acknowledge(self.backend.record_erasure_ack_socket,'acknowledge',rid,intent['erased_at'])
            entries = read_confirmed(self.backend.record_erasure_ledger_path,response)
            if entries.get(rid,0) < intent['erased_at']: raise RuntimeError('Record is absent from acknowledged journal')
            apply_ledger(self.backend, entries)
        except Exception:
            self.backend.record_erasure_ready = False
            raise Failure('record_erasure_unavailable',503) from None
        with self.backend.transaction() as db:
            self._account(db,actor)
            result = self.backend._idempotent(db,actor,op)
            require(result is not None,'record_erasure_unavailable',503)
            return result
