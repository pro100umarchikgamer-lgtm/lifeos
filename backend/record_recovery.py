"""User-consented tombstone recovery; staff see metadata and never record content."""
import hmac
import json
import secrets
import uuid
from .control import Control, scrub
from .service import Failure, TABLES, canonical, identifier, require, text, token_hash

DAY=86400
REQUEST_FIELDS=('id','user_id','workspace_id','record_id','kind','record_revision','consent_hash','state','revision','created_at','expires_at','approved_at','completed_at','decision_reason')

class RecordRecovery:
    def __init__(self, backend):
        self.backend=backend
        self.control=Control(backend)

    def _account(self, db, actor):
        require(actor.get('verified') == 1,'verify_email',403)
        self.backend._account_available(db,actor['id'])

    def _space(self, db, actor, wid):
        try:return self.backend._workspace(db,actor,identifier(wid))
        except Failure:raise Failure('not_found',404)

    def _owner_record(self, db, actor, rid):
        self._account(db,actor)
        row=db.execute('SELECT * FROM records WHERE id=? AND owner_id=? AND deleted=1',(identifier(rid),actor['id'])).fetchone()
        require(row is not None,'not_found',404)
        space=self._space(db,actor,row['workspace_id'])
        return row,space

    def _payload(self, db, row):
        require(row['kind'] in TABLES,'not_found',404)
        require(db.execute('SELECT 1 FROM '+TABLES[row['kind']]+' WHERE id=?',(row['id'],)).fetchone() is not None,'not_found',404)
        # Ordinary sync intentionally hides tombstone payloads. This projection is
        # reachable only after the exact owner/current workspace check above.
        value=self.backend._data(db,dict(row,deleted=0))
        value['deleted']=1
        return value

    def _hash(self, value):
        return token_hash(canonical({key:value[key] for key in ('id','workspace_id','owner_id','kind','visibility','audience','revision','data','progress') if key in value}))

    def _validate(self, db, actor, space, row, value):
        require(self.backend._editable(db,actor,space,row),'record_forbidden',403)
        data=value['data'];kind=row['kind'];audience=value['audience']
        if space['role']=='child':
            permissions=self.backend._permissions(db,space)
            require(row['visibility']=='shared' and audience==[space['profile_id']],'child_scope',403)
            require('edit_own' in permissions and ((kind=='transaction' and 'record_spending' in permissions and data.get('kind')=='expense') or (kind=='request' and 'request_money' in permissions and data.get('profile_id')==space['profile_id']) or (kind=='task' and 'create_tasks' in permissions)), 'child_permission',403)
        validation=data
        if kind=='request' and data.get('state')=='fulfilled':
            # Restoring a reference does not fulfill a request or create money.
            # Recheck the exact current movement/account and its unique binding.
            validation=dict(data,state='pending',movement_id=None)
            movement=self.backend._reference(db,row['workspace_id'],data['movement_id'],'transfer',actor=actor,space=space)
            self.backend._reference(db,row['workspace_id'],movement['to_id'],'account',currency=data['currency'],actor=actor,space=space)
            target=db.execute('SELECT audience FROM records WHERE id=?',(movement['to_id'],)).fetchone()
            require(data['profile_id'] in json.loads(target['audience']) and movement['received_minor']==data['amount_minor'],'fulfillment_mismatch')
            require(not db.execute("SELECT 1 FROM requests q JOIN records r ON r.id=q.id WHERE q.movement_id=? AND q.id<>? AND q.state='fulfilled' AND r.deleted=0",(data['movement_id'],row['id'])).fetchone(),'movement_already_used',409)
        self.backend._validate_data(db,row['workspace_id'],kind,validation,audience,actor,space)
        if kind=='task':
            require(all(mark['profile_id'] in data['assignees'] for mark in value.get('progress',[])),'invalid_participant')

    def _metadata(self, row):
        return {field:row[field] for field in REQUEST_FIELDS}

    def _cursor(self, before):
        if before is None:return 9223372036854775807,'ffffffff-ffff-ffff-ffff-ffffffffffff'
        require(isinstance(before,str) and len(before)<=64,'recovery_cursor_invalid')
        parts=before.split(':')
        require(len(parts)==2 and parts[0].isdigit() and len(parts[0])<=19,'recovery_cursor_invalid')
        stamp=int(parts[0]);require(stamp<=9223372036854775807,'recovery_cursor_invalid')
        return stamp,identifier(parts[1])

    def trash(self, actor, wid, before=None, record_id=None):
        stamp,last_id=self._cursor(before)
        with self.backend.connect() as db:
            self._account(db,actor);space=self._space(db,actor,wid)
            if record_id is not None:
                row, unused_space = self._owner_record(db, actor, record_id)
                require(row['workspace_id'] == wid, 'not_found', 404)
                rows = [row]
            else:
                rows=db.execute('SELECT * FROM records WHERE workspace_id=? AND owner_id=? AND deleted=1 AND (seq<? OR (seq=? AND id<?)) ORDER BY seq DESC,id DESC LIMIT 51',(wid,actor['id'],stamp,stamp,last_id)).fetchall()
            page=[]
            for row in rows[:50]:
                try:value=self._payload(db,row)
                except Failure:continue
                error=None
                try:self._validate(db,actor,space,row,value)
                except Failure as failure:error=failure.code
                page.append(dict(value,consent_hash=self._hash(value),restorable=error is None,restore_error=error))
        return {'records':page,'next_before':str(rows[49]['seq'])+':'+rows[49]['id'] if len(rows)>50 else None}

    def request(self, actor, body):
        rid=identifier(body.get('record_id'));revision=body.get('revision');digest=body.get('consent_hash')
        require(type(revision) is int and revision>0 and isinstance(digest,str) and len(digest)==64,'recovery_stale',409)
        now=int(self.backend.clock())
        with self.backend.transaction() as db:
            row,space=self._owner_record(db,actor,rid);value=self._payload(db,row)
            require(row['revision']==revision and hmac.compare_digest(self._hash(value),digest),'recovery_stale',409)
            self._validate(db,actor,space,row,value)
            old=db.execute("SELECT * FROM record_recovery_requests WHERE user_id=? AND record_id=? AND record_revision=? AND consent_hash=? AND state IN ('pending','approved') AND expires_at>? ORDER BY created_at DESC,id DESC LIMIT 1",(actor['id'],rid,revision,digest,now)).fetchone()
            if old:return {'request':self._metadata(old)}
            count=db.execute('SELECT COUNT(*) AS n FROM record_recovery_requests WHERE user_id=? AND created_at>?',(actor['id'],now-DAY)).fetchone()['n']
            require(count<10,'rate_limited',429)
            request_id=str(uuid.uuid4())
            db.execute("INSERT INTO record_recovery_requests(id,user_id,workspace_id,record_id,kind,record_revision,consent_hash,state,revision,created_at,expires_at) VALUES(?,?,?,?,?,?,?,'pending',1,?,?)",(request_id,actor['id'],row['workspace_id'],rid,row['kind'],revision,digest,now,now+7*DAY))
            self.control.audit(db,'user:'+actor['id'],actor['id'],'record.recovery.request',{}, {'request_id':request_id,'record_id':rid,'kind':row['kind'],'record_revision':revision},'Record owner explicitly requested recovery after private preview')
            return {'request':self._metadata(db.execute('SELECT * FROM record_recovery_requests WHERE id=?',(request_id,)).fetchone())}

    def requests(self, actor, before=None, staff=False):
        stamp,last_id=self._cursor(before)
        if staff:self.control.require(actor,'records.recover')
        with self.backend.connect() as db:
            if not staff:self._account(db,actor)
            sql='SELECT '+','.join(REQUEST_FIELDS)+' FROM record_recovery_requests WHERE (created_at<? OR (created_at=? AND id<?))'
            params=(stamp,stamp,last_id)
            if not staff:sql+=' AND user_id=?';params+=(actor['id'],)
            rows=db.execute(sql+' ORDER BY created_at DESC,id DESC LIMIT 101',params).fetchall()
        page=rows[:100]
        return {'requests':[self._metadata(row) for row in page],'next_before':str(page[-1]['created_at'])+':'+page[-1]['id'] if len(rows)>100 else None}

    def approve(self, actor, body):
        self.control.require(actor,'records.recover')
        request_id=identifier(body.get('request_id'));revision=body.get('revision');digest=body.get('consent_hash')
        require(type(revision) is int and isinstance(digest,str) and len(digest)==64,'revision_conflict',409)
        reason=scrub(text(body.get('reason'),500));now=int(self.backend.clock())
        with self.backend.transaction() as db:
            row=db.execute('SELECT * FROM record_recovery_requests WHERE id=?',(request_id,)).fetchone()
            require(row is not None,'not_found',404)
            require(row['revision']==revision and row['state']=='pending' and row['expires_at']>now and hmac.compare_digest(row['consent_hash'],digest),'revision_conflict',409)
            # Approval cannot read/mutate the record. The requester must still
            # redeem and commit in their own account; self/peer approval is safe
            # and avoids making the highest-rank owner's data unrecoverable.
            self.backend._account_available(db,row['user_id'])
            # Metadata only: approval never loads tasks/notes/financial payloads.
            current=db.execute('SELECT r.revision,r.kind FROM records r JOIN users u ON u.id=r.owner_id JOIN workspaces w ON w.id=r.workspace_id JOIN memberships m ON m.workspace_id=w.id AND m.user_id=u.id WHERE r.id=? AND r.owner_id=? AND r.workspace_id=? AND r.deleted=1 AND u.verified=1 AND w.dissolved=0 AND m.active=1',(row['record_id'],row['user_id'],row['workspace_id'])).fetchone()
            require(current and current['revision']==row['record_revision'] and current['kind']==row['kind'],'recovery_stale',409)
            db.execute("UPDATE record_recovery_requests SET state='approved',revision=revision+1,approved_at=?,approved_by=?,decision_reason=? WHERE id=?",(now,actor.id,reason,request_id))
            self.control.audit(db,actor,row['user_id'],'record.recovery.approve',{'request_id':request_id,'revision':revision},{'request_id':request_id,'state':'approved','revision':revision+1},reason)
            return {'request':self._metadata(db.execute('SELECT * FROM record_recovery_requests WHERE id=?',(request_id,)).fetchone())}

    def _own_request(self, db, actor, request_id):
        self._account(db,actor)
        row=db.execute('SELECT * FROM record_recovery_requests WHERE id=? AND user_id=?',(identifier(request_id),actor['id'])).fetchone()
        require(row is not None,'not_found',404);return row

    def prepare(self, actor, body):
        now=int(self.backend.clock());grant=secrets.token_urlsafe(32)
        with self.backend.transaction() as db:
            request=self._own_request(db,actor,body.get('request_id'))
            require(request['state']=='approved' and request['expires_at']>now,'recovery_unavailable',409)
            row,space=self._owner_record(db,actor,request['record_id']);value=self._payload(db,row)
            require(row['revision']==request['record_revision'] and hmac.compare_digest(self._hash(value),request['consent_hash']),'recovery_stale',409)
            self._validate(db,actor,space,row,value)
            expires=min(request['expires_at'],now+600)
            db.execute('UPDATE record_recovery_requests SET grant_hash=?,grant_expires_at=? WHERE id=?',(token_hash(grant),expires,request['id']))
        return {'request_id':request['id'],'grant':grant,'expires_at':expires}

    def cancel(self, actor, body):
        revision=body.get('revision');require(type(revision) is int,'revision_conflict',409)
        with self.backend.transaction() as db:
            row=self._own_request(db,actor,body.get('request_id'))
            require(row['revision']==revision and row['state'] in ('pending','approved'),'revision_conflict',409)
            db.execute("UPDATE record_recovery_requests SET state='cancelled',revision=revision+1,grant_hash='',grant_expires_at=0 WHERE id=?",(row['id'],))
            self.control.audit(db,'user:'+actor['id'],actor['id'],'record.recovery.cancel',{'request_id':row['id']},{'state':'cancelled'},'Record owner withdrew recovery consent')
            return {'request':self._metadata(db.execute('SELECT * FROM record_recovery_requests WHERE id=?',(row['id'],)).fetchone())}

    def commit(self, actor, body):
        grant=body.get('grant');require(isinstance(grant,str) and len(grant)==43,'recovery_invalid',409)
        operation=identifier(body.get('operation_id'))
        with self.backend.connect() as db:row=self._own_request(db,actor,body.get('request_id'))
        op={'id':operation,'action':'record.restore','record_id':row['record_id'],'revision':row['record_revision'],'recovery_request':row['id'],'grant':grant}
        return self.backend.batch(actor,row['workspace_id'],[op])

    def restore_in(self, db, actor, space, row, op):
        """Invoked inside canonical operation transaction, after idempotency check."""
        now=int(self.backend.clock());self._account(db,actor)
        require(row is not None and row['owner_id']==actor['id'] and row['deleted']==1,'not_found',404)
        grant=op.get('grant');require(isinstance(grant,str) and len(grant)==43,'recovery_invalid',409)
        request=db.execute('SELECT * FROM record_recovery_requests WHERE id=? AND user_id=? AND record_id=?',(identifier(op.get('recovery_request')),actor['id'],row['id'])).fetchone()
        require(request and request['state']=='approved' and request['expires_at']>now and request['grant_expires_at']>now and hmac.compare_digest(request['grant_hash'],token_hash(grant)),'recovery_invalid',409)
        value=self._payload(db,row)
        require(row['revision']==request['record_revision'] and hmac.compare_digest(self._hash(value),request['consent_hash']),'recovery_stale',409)
        self._validate(db,actor,space,row,value)
        db.execute('UPDATE records SET deleted=0 WHERE id=?',(row['id'],))
        db.execute("UPDATE record_recovery_requests SET state='completed',revision=revision+1,completed_at=?,grant_expires_at=0 WHERE id=?",(now,request['id']))
        self.control.audit(db,'user:'+actor['id'],actor['id'],'record.recovery.commit',{'request_id':request['id'],'record_revision':row['revision']},{'record_revision':row['revision']+1},'Record owner committed the approved one-use recovery grant')
