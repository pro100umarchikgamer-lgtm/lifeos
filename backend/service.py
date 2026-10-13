"""Replaceable isolated LifeOS reference backend. No third-party dependency or production deployment."""
import contextlib
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
import uuid

MAX_MINOR = 999999999999999
PERMISSIONS = {'view_budget', 'record_spending', 'edit_own', 'request_money', 'view_shared', 'create_tasks', 'complete_tasks'}
TABLES = {'task':'tasks','note':'notes','account':'accounts','transaction':'transactions','transfer':'transfers','budget':'budgets','event':'events','shopping':'shopping','request':'requests'}
FIELDS = {
 'task':{'title','completed','assignment','assignees','review'}, 'note':{'body'},
 'account':{'name','currency','opening_minor'},'transaction':{'kind','amount_minor','currency','date','label','account_id'},
 'transfer':{'from_id','to_id','sent_minor','received_minor','date'},
 'budget':{'name','currency','limit_minor','period','start_on','end_on','rollover','participants'},
 'event':{'title','schedule'},'shopping':{'name','items'},'request':{'profile_id','amount_minor','currency','label','state','movement_id'},
}
JSON_FIELDS = {'assignees','participants','schedule','items'}

class Failure(Exception):
    def __init__(self, code, status=400): self.code, self.status = code, status

def require(ok, code='invalid_input', status=400):
    if not ok: raise Failure(code, status)
def identifier(value):
    try: require(str(uuid.UUID(value))==value)
    except (ValueError,TypeError,AttributeError): raise Failure('invalid_id')
    return value

def minor(value, signed=False, zero=False):
    require(type(value) is int and abs(value)<=MAX_MINOR and (signed or value >= (0 if zero else 1)), 'invalid_amount')
    return value

def text(value, limit=2000):
    require(isinstance(value,str) and value.strip() and len(value)<=limit)
    return value

def civil(value):
    try: parsed=dt.date.fromisoformat(value)
    except (TypeError,ValueError): raise Failure('invalid_date')
    require(parsed.isoformat()==value and 1900<=parsed.year<=2200,'invalid_date');return value

def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def token_hash(value): return hashlib.sha256(value.encode()).hexdigest()

class Backend:
    def __init__(self,path,deliver=None,clock=time.time):
        self.path,self.deliver,self.clock=str(path),deliver,clock
        with self.connect() as db: db.executescript(Path(__file__).with_name('schema.sql').read_text())
        os.chmod(self.path,0o600)
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON');return db
    @contextlib.contextmanager
    def transaction(self):
        db=self.connect()
        try:
            db.execute('BEGIN IMMEDIATE');yield db;db.commit()
        except Exception: db.rollback();raise
        finally: db.close()
    def authenticate(self,token):
        require(isinstance(token,str) and len(token)==43,'unauthorized',401)
        with self.connect() as db:
            row=db.execute('SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.hash=? AND s.expires_at>?',(token_hash(token),int(self.clock()))).fetchone()
        require(row is not None,'unauthorized',401);return dict(row)
    def _session(self,db,uid):
        token=secrets.token_urlsafe(32);db.execute('INSERT INTO sessions VALUES(?,?,?)',(token_hash(token),uid,int(self.clock())+86400));return token
    def register(self,email,password):
        require(isinstance(email,str) and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) and len(email)<=254)
        require(isinstance(password,str) and 12<=len(password)<=256,'password_length')
        require(self.deliver is not None,'verification_delivery_unconfigured',503)
        uid=str(uuid.uuid4());salt=secrets.token_hex(16);now=int(self.clock())
        encoded=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()
        verify=secrets.token_urlsafe(32)
        with self.transaction() as db:
            require(not db.execute('SELECT id FROM users WHERE email=?',(email.casefold(),)).fetchone(),'account_exists',409)
            db.execute('INSERT INTO users VALUES(?,?,?,?,0,?)',(uid,email.casefold(),encoded,salt,now))
            db.execute('INSERT INTO verification VALUES(?,?,?)',(token_hash(verify),uid,now+3600))
            session=self._session(db,uid)
        self.deliver(email.casefold(),verify)
        return {'user_id':uid,'token':session,'verified':False}
    def verify(self,actor,code):
        require(isinstance(code,str) and len(code)==43)
        with self.transaction() as db:
            row=db.execute('SELECT * FROM verification WHERE hash=? AND user_id=? AND expires_at>?',(token_hash(code),actor['id'],int(self.clock()))).fetchone()
            require(row is not None,'verification_invalid');db.execute('UPDATE users SET verified=1 WHERE id=?',(actor['id'],));db.execute('DELETE FROM verification WHERE user_id=?',(actor['id'],))
        return {'verified':True}
    def login(self,email,password):
        require(isinstance(email,str) and isinstance(password,str) and len(password)<=256)
        with self.transaction() as db:
            key=token_hash(email.casefold());now=int(self.clock());limit=db.execute('SELECT * FROM auth_limits WHERE key=?',(key,)).fetchone()
            require(limit is None or limit['until_at']<=now or limit['count']<10,'rate_limited',429)
            count=limit['count']+1 if limit and limit['until_at']>now else 1
            db.execute('INSERT OR REPLACE INTO auth_limits VALUES(?,?,?)',(key,count,now+900))
            row=db.execute('SELECT * FROM users WHERE email=?',(email.casefold(),)).fetchone()
            salt=bytes.fromhex(row['salt']) if row else bytes(16)
            actual=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,600000).hex()
            valid=row is not None and hmac.compare_digest(actual,row['password_hash'])
            # Commit failed-attempt counters rather than rolling them back with the error.
            result={'user_id':row['id'],'token':self._session(db,row['id']),'verified':bool(row['verified'])} if valid else None
        require(valid,'invalid_credentials',401);return result
    def logout(self,token):
        with self.transaction() as db:db.execute('DELETE FROM sessions WHERE hash=?',(token_hash(token),))
        return {'signed_out':True}
    def _workspace(self,db,actor,wid,parent=False):
        require(actor['verified']==1,'verify_email',403)
        row=db.execute('SELECT w.*,m.role,m.profile_id,m.revision AS member_revision FROM workspaces w JOIN memberships m ON m.workspace_id=w.id WHERE w.id=? AND m.user_id=? AND m.active=1 AND w.dissolved=0',(wid,actor['id'])).fetchone()
        require(row is not None,'workspace_forbidden',403)
        if parent: require(row['role'] in ('parent','owner'),'parent_required',403)
        return dict(row)
    def _audit(self,db,wid,actor,op,kind,rid=None):
        return db.execute('INSERT INTO changes(workspace_id,record_id,actor_id,operation_id,kind) VALUES(?,?,?,?,?)',(wid,rid,actor['id'],op,kind)).lastrowid
    def _revision(self,row,expected): require(type(expected) is int and row['revision']==expected,'revision_conflict',409)
    def _idempotent(self,db,actor,op):
        identifier(op['id']);digest=token_hash(canonical(op));row=db.execute('SELECT * FROM operations WHERE user_id=? AND id=?',(actor['id'],op['id'])).fetchone()
        if row: require(row['digest']==digest,'operation_conflict',409);return json.loads(row['result'])
        return None
    def _remember(self,db,actor,op,result):
        db.execute('INSERT INTO operations VALUES(?,?,?,?)',(actor['id'],op['id'],token_hash(canonical(op)),canonical(result)))
    def family(self,actor,op):
        """Every family mutation is a UUID operation with audited revision checks."""
        require(actor['verified']==1,'verify_email',403);kind=op.get('action')
        with self.transaction() as db:
            wid=identifier(op.get('workspace_id'))
            space=None if kind=='workspace.create' else self._workspace(db,actor,wid,parent=kind not in ('workspace.leave',))
            prior=self._idempotent(db,actor,op)
            if prior:return prior
            if kind=='workspace.create':
                require(op.get('kind') in ('personal','family'));text(op.get('name'),100)
                db.execute('INSERT INTO workspaces(id,name,creator_id,kind) VALUES(?,?,?,?)',(wid,op['name'],actor['id'],op['kind']))
                db.execute('INSERT INTO memberships(workspace_id,user_id,role) VALUES(?,?,?)',(wid,actor['id'],'parent' if op['kind']=='family' else 'owner'))
                result={'workspace_id':wid,'revision':1}
            elif kind=='invite.create':
                role=op.get('role');require(role in ('parent','adult','child'))
                email=text(op.get('email'),254).casefold();require(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email))
                profile=op.get('profile_id')
                require(space['kind']=='family','family_required');
                if role=='child':require(db.execute('SELECT id FROM profiles WHERE id=? AND workspace_id=? AND archived=0',(profile,wid)).fetchone() is not None)
                else: require(profile is None)
                if role=='parent':require(db.execute("SELECT COUNT(*) FROM memberships WHERE workspace_id=? AND role='parent' AND active=1",(wid,)).fetchone()[0]<2,'parent_slots_full')
                invite=secrets.token_urlsafe(32);db.execute('INSERT INTO invitations VALUES(?,?,?,?,?,?,?,NULL)',(token_hash(invite),wid,email,role,profile,actor['id'],int(self.clock())+86400))
                # Code is returned only to its issuing parent; the issuer shares it explicitly.
                result={'workspace_id':wid,'invitation':invite,'expires_in':86400}
            elif kind=='child.save':
                pid=identifier(op.get('profile_id'));text(op.get('name'),100);perms=op.get('permissions');require(isinstance(perms,list) and len(perms)==len(set(perms)) and set(perms)<=PERMISSIONS)
                row=db.execute('SELECT * FROM profiles WHERE id=? AND workspace_id=?',(pid,wid)).fetchone()
                if row:self._revision(row,op.get('revision'));db.execute('UPDATE profiles SET name=?,permissions=?,revision=revision+1 WHERE id=?',(op['name'],canonical(perms),pid))
                else:require(op.get('revision')==0);db.execute('INSERT INTO profiles(id,workspace_id,name,permissions) VALUES(?,?,?,?)',(pid,wid,op['name'],canonical(perms)))
                result={'profile_id':pid,'revision':row['revision']+1 if row else 1}
            elif kind=='member.remove':
                row=db.execute('SELECT * FROM memberships WHERE workspace_id=? AND user_id=? AND active=1',(wid,op.get('user_id'))).fetchone();require(row is not None)
                require(row['role'] not in ('parent','owner'),'parent_change_requires_consent',403);self._revision(row,op.get('revision'))
                db.execute('UPDATE memberships SET active=0,revision=revision+1 WHERE workspace_id=? AND user_id=?',(wid,row['user_id']));result={'removed':True}
            elif kind=='parent.change.request':
                target=op.get('user_id');row=db.execute("SELECT * FROM memberships WHERE workspace_id=? AND user_id=? AND role='parent' AND active=1",(wid,target)).fetchone();require(row is not None and target!=space['creator_id'],'creator_role_immutable',403)
                require(op.get('role')=='adult');self._revision(row,op.get('revision'))
                request=identifier(op.get('change_id'));db.execute('INSERT INTO parent_changes(id,workspace_id,target_id,new_role,requested_by) VALUES(?,?,?,?,?)',(request,wid,target,'adult',actor['id']));result={'change_id':request,'revision':1}
            elif kind=='parent.change.approve':
                row=db.execute('SELECT * FROM parent_changes WHERE id=? AND workspace_id=?',(op.get('change_id'),wid)).fetchone();require(row is not None and row['target_id']==actor['id'],'target_consent_required',403);self._revision(row,op.get('revision'));require(row['approved_by'] is None)
                db.execute('UPDATE memberships SET role=?,revision=revision+1 WHERE workspace_id=? AND user_id=?',(row['new_role'],wid,row['target_id']));db.execute('UPDATE parent_changes SET approved_by=?,revision=revision+1 WHERE id=?',(actor['id'],row['id']));result={'approved':True}
            elif kind=='workspace.leave':
                require(space['creator_id']!=actor['id'] or space['kind']=='personal','creator_must_dissolve',409)
                require(space['kind']=='family');self._revision({'revision':space['member_revision']},op.get('revision'))
                db.execute('UPDATE memberships SET active=0,revision=revision+1 WHERE workspace_id=? AND user_id=?',(wid,actor['id']));result={'left':True}
            elif kind=='workspace.dissolve':
                require(space['creator_id']==actor['id'],'creator_only',403);self._revision(space,op.get('revision'))
                db.execute('UPDATE workspaces SET dissolved=1,revision=revision+1 WHERE id=?',(wid,));db.execute('UPDATE memberships SET active=0,revision=revision+1 WHERE workspace_id=?',(wid,));result={'dissolved':True}
            else:raise Failure('unknown_action')
            self._audit(db,wid,actor,op['id'],kind);self._remember(db,actor,op,result);return result
    def accept(self,actor,op):
        require(actor['verified']==1,'verify_email',403);identifier(op.get('id'))
        code=op.get('invitation');require(isinstance(code,str) and len(code)==43)
        with self.transaction() as db:
            prior=self._idempotent(db,actor,op)
            if prior:
                self._workspace(db,actor,prior['workspace_id']);return prior
            invite=db.execute('SELECT i.*,w.dissolved FROM invitations i JOIN workspaces w ON w.id=i.workspace_id WHERE i.hash=?',(token_hash(code),)).fetchone()
            require(invite is not None and not invite['dissolved'] and invite['used_by'] is None and invite['expires_at']>int(self.clock()) and invite['email']==actor['email'],'invitation_invalid',403)
            require(db.execute("SELECT 1 FROM memberships WHERE workspace_id=? AND user_id=? AND active=1 AND role='parent'",(invite['workspace_id'],invite['issued_by'])).fetchone() is not None,'invitation_invalid',403)
            current=db.execute('SELECT role FROM memberships WHERE workspace_id=? AND user_id=? AND active=1',(invite['workspace_id'],actor['id'])).fetchone()
            require(current is None,'already_member',409)
            if invite['role']=='parent':require(db.execute("SELECT COUNT(*) FROM memberships WHERE workspace_id=? AND role='parent' AND active=1",(invite['workspace_id'],)).fetchone()[0]<2,'parent_slots_full')
            if invite['role']=='child':require(not db.execute('SELECT user_id FROM memberships WHERE profile_id=? AND active=1',(invite['profile_id'],)).fetchone(),'profile_already_linked',409)
            db.execute('INSERT INTO memberships(workspace_id,user_id,role,profile_id) VALUES(?,?,?,?) ON CONFLICT(workspace_id,user_id) DO UPDATE SET role=excluded.role,profile_id=excluded.profile_id,active=1,revision=memberships.revision+1',(invite['workspace_id'],actor['id'],invite['role'],invite['profile_id']))
            db.execute('UPDATE invitations SET used_by=? WHERE hash=?',(actor['id'],invite['hash']));result={'workspace_id':invite['workspace_id']}
            self._audit(db,invite['workspace_id'],actor,op['id'],'invite.accept');self._remember(db,actor,op,result);return result
    def spaces(self,actor):
        require(actor['verified']==1,'verify_email',403)
        with self.connect() as db:
            rows=db.execute('SELECT w.*,m.role,m.profile_id,m.revision AS member_revision FROM workspaces w JOIN memberships m ON m.workspace_id=w.id WHERE m.user_id=? AND m.active=1 AND w.dissolved=0',(actor['id'],)).fetchall()
            return [dict(r) for r in rows]
    def roster(self,actor,wid):
        with self.connect() as db:
            space=self._workspace(db,actor,wid)
            members=[dict(r) for r in db.execute('SELECT user_id,role,profile_id,revision FROM memberships WHERE workspace_id=? AND active=1',(wid,))]
            profiles=[dict(r) for r in db.execute('SELECT * FROM profiles WHERE workspace_id=? AND archived=0',(wid,))]
            if space['role']=='child':profiles=[p for p in profiles if p['id']==space['profile_id']]
            for p in profiles:p['permissions']=json.loads(p['permissions'])
            return {'members':members,'profiles':profiles,'space':space}
    def _permissions(self,db,space):
        if space['role']!='child':return PERMISSIONS
        row=db.execute('SELECT permissions FROM profiles WHERE id=? AND workspace_id=? AND archived=0',(space['profile_id'],space['id'])).fetchone()
        require(row is not None,'profile_forbidden',403);return set(json.loads(row['permissions']))
    def _readable(self,db,actor,space,row):
        if row['owner_id']==actor['id']:return True
        grant=db.execute('SELECT can_edit FROM grants WHERE record_id=? AND user_id=?',(row['id'],actor['id'])).fetchone()
        if row['visibility']=='private':return grant is not None
        if space['role']!='child':return True
        perms=self._permissions(db,space);audience=json.loads(row['audience']);own=space['profile_id'] in audience
        return ('view_shared' in perms and row['kind'] in ('task','event','shopping')) or own and ((row['kind'] in ('budget','account') and 'view_budget' in perms) or row['kind'] in ('transaction','request') or row['kind']=='task' and 'complete_tasks' in perms)
    def _editable(self,db,actor,space,row):
        if row['visibility']=='private':
            grant=db.execute('SELECT can_edit FROM grants WHERE record_id=? AND user_id=?',(row['id'],actor['id'])).fetchone()
            return row['owner_id']==actor['id'] or grant is not None and grant['can_edit']==1
        if space['role'] in ('parent','owner','adult'):return True
        p=self._permissions(db,space)
        return row['owner_id']==actor['id'] and 'edit_own' in p or row['kind']=='task' and 'complete_tasks' in p and space['profile_id'] in json.loads(row['audience'])
    def _data(self,db,row):
        result=dict(row);result['audience']=json.loads(result['audience']);data=dict(db.execute('SELECT * FROM '+TABLES[row['kind']]+' WHERE id=?',(row['id'],)).fetchone());data.pop('id')
        for key in JSON_FIELDS & data.keys(): data[key]=json.loads(data[key])
        result['data']=data;return result
    def _validate_data(self,db,wid,kind,data,audience,actor,space):
        require(isinstance(data,dict) and set(data)==FIELDS[kind],'invalid_fields')
        for pid in audience: require(db.execute('SELECT id FROM profiles WHERE id=? AND workspace_id=? AND archived=0',(pid,wid)).fetchone() is not None,'invalid_participant')
        for key in ('name','title','body'):
            if key in data:text(data[key],20000 if key=='body' else 2000)
        if 'currency' in data:require(isinstance(data['currency'],str) and re.fullmatch(r'[A-Z]{3}',data['currency']))
        for key in ('amount_minor','sent_minor','received_minor'): 
            if key in data:minor(data[key])
        if 'opening_minor' in data:minor(data['opening_minor'],signed=True)
        if 'limit_minor' in data:minor(data['limit_minor'],zero=True)
        for key in ('date','start_on','end_on'):
            if data.get(key) is not None:civil(data[key])
        if 'label' in data:require(isinstance(data['label'],str) and len(data['label'])<=2000)
        if kind=='transaction':
            require(data['kind'] in ('income','expense'));aid=data['account_id']
            if aid is not None:self._reference(db,wid,aid,'account',currency=data['currency'],actor=actor,space=space)
        if kind=='transfer':
            require(data['from_id']!=data['to_id']);a=self._reference(db,wid,data['from_id'],'account',actor=actor,space=space);b=self._reference(db,wid,data['to_id'],'account',actor=actor,space=space)
            if a['currency']==b['currency']:require(data['sent_minor']==data['received_minor'],'currency_mismatch')
        if kind=='budget':
            require(data['period'] in ('week','month','year','custom') and data['rollover'] in ('none','positive','negative','both'))
            require(isinstance(data['participants'],list) and len(set(data['participants']))==len(data['participants']) and set(data['participants'])<=set(audience))
            if data['period']=='custom':require(data['end_on'] is not None and data['end_on']>=data['start_on'])
        if kind=='task':
            require(type(data['completed']) is int and data['completed'] in (0,1) and type(data['review']) is int and data['review'] in (0,1))
            require(data['assignment'] in ('single','each','joint','any') and isinstance(data['assignees'],list) and len(set(data['assignees']))==len(data['assignees']) and set(data['assignees'])<=set(audience))
        if kind=='event':
            s=data['schedule'];require(isinstance(s,dict) and set(s)=={'localStart','timezone','allDay','repeat','interval','until'})
            require(s['repeat'] in ('none','daily','weekly','monthly','yearly') and type(s['interval']) is int and 1<=s['interval']<=365 and type(s['allDay']) is bool)
            try:
                stamp=dt.datetime.fromisoformat(s['localStart']);from zoneinfo import ZoneInfo
                if s['timezone']!='device':ZoneInfo(s['timezone'])
            except (ValueError,TypeError,KeyError):raise Failure('invalid_schedule')
            require(1900<=stamp.year<=2200 and stamp.tzinfo is None)
            if s['until'] is not None:civil(s['until']);require(s['until']>=stamp.date().isoformat())
        if kind=='shopping':
            require(isinstance(data['items'],list) and len(data['items'])<=500)
            ids=set()
            for i in data['items']:
                require(isinstance(i,dict) and set(i)=={'id','name','completed','quantity'});identifier(i['id']);text(i['name']);require(i['id'] not in ids and type(i['completed']) is bool and isinstance(i['quantity'],str) and len(i['quantity'])<=100);ids.add(i['id'])
        if kind=='request':
            require(data['profile_id'] in audience and data['state']=='pending' and data['movement_id'] is None,'request_state')
    def _reference(self,db,wid,rid,kind,currency=None,actor=None,space=None):
        identifier(rid);row=db.execute('SELECT * FROM records WHERE id=? AND workspace_id=? AND kind=? AND deleted=0',(rid,wid,kind)).fetchone();require(row is not None,'invalid_reference')
        if actor:require(self._readable(db,actor,space,row),'reference_forbidden',403)
        value=self._data(db,row)['data']
        if currency:require(value.get('currency')==currency,'currency_mismatch')
        return value
    def batch(self,actor,wid,ops):
        require(isinstance(ops,list) and 1<=len(ops)<=100,'batch_limit')
        results=[]
        # Each operation is atomic; the batch may resume after any acknowledged prefix.
        for op in ops:
            try: results.append(self._record_operation(actor,wid,op))
            except Failure as error: results.append({'id':op.get('id'),'status':'rejected','error':error.code})
        return {'results':results}
    def _record_operation(self,actor,wid,op):
        require(isinstance(op,dict));action=op.get('action');require(action in ('record.put','record.delete','record.grant','request.fulfill'))
        rid=identifier(op.get('record_id'))
        with self.transaction() as db:
            space=self._workspace(db,actor,wid);row=db.execute('SELECT * FROM records WHERE id=?',(rid,)).fetchone()
            if row:
                require(row['workspace_id']==wid and self._readable(db,actor,space,row),'record_forbidden',403)
                require(self._editable(db,actor,space,row),'record_forbidden',403)
            prior=self._idempotent(db,actor,op)
            if prior:return prior
            expected=op.get('revision');require(type(expected) is int and expected>=0)
            if (row['revision'] if row else 0)!=expected:
                return {'id':op['id'],'status':'conflict','record_id':rid,'server':self._data(db,row) if row else None}
            if action=='record.put':
                kind=op.get('kind');visibility=op.get('visibility');audience=op.get('audience')
                require(kind in TABLES and visibility in ('private','shared') and isinstance(audience,list) and len(audience)<=50 and len(set(audience))==len(audience))
                if row:
                    require(row['kind']==kind and row['deleted']==0)
                    if row['owner_id']!=actor['id']:require(row['visibility']==visibility and json.loads(row['audience'])==audience,'owner_controls_visibility',403)
                if space['role']=='child':
                    p=self._permissions(db,space);require(visibility=='shared' and audience==[space['profile_id']],'child_scope',403)
                    if row is None:require(kind=='transaction' and 'record_spending' in p and op['data'].get('kind')=='expense' or kind=='request' and 'request_money' in p and op['data'].get('profile_id')==space['profile_id'] or kind=='task' and 'create_tasks' in p,'child_permission',403)
                    elif row['owner_id']!=actor['id'] or 'edit_own' not in p:
                        old=self._data(db,row)['data'];require(kind=='task' and all(op['data'].get(k)==v for k,v in old.items() if k!='completed'),'completion_only',403)
                self._validate_data(db,wid,kind,op.get('data'),audience,actor,space)
                if row and kind=='request':require(self._data(db,row)['data']['state']=='pending','request_closed',409)
                if row and kind=='account' and self._data(db,row)['data']['currency']!=op['data']['currency']:
                    require(not db.execute('SELECT 1 FROM transactions WHERE account_id=? UNION ALL SELECT 1 FROM transfers WHERE from_id=? OR to_id=? LIMIT 1',(rid,rid,rid)).fetchone(),'currency_mismatch')
                data=op['data'];seq=self._audit(db,wid,actor,op['id'],action,rid)
                if row:db.execute('UPDATE records SET visibility=?,audience=?,revision=revision+1,seq=? WHERE id=?',(visibility,canonical(audience),seq,rid));db.execute('DELETE FROM '+TABLES[kind]+' WHERE id=?',(rid,))
                else:db.execute('INSERT INTO records VALUES(?,?,?,?,?,?,1,0,?)',(rid,wid,actor['id'],kind,visibility,canonical(audience),seq))
                columns=list(data);db.execute('INSERT INTO '+TABLES[kind]+'(id,'+','.join(columns)+') VALUES('+','.join('?' for _ in range(len(columns)+1))+')',[rid]+[canonical(data[k]) if k in JSON_FIELDS else data[k] for k in columns])
            else:
                require(row is not None and not row['deleted'],'record_missing')
                if action=='record.delete':
                    require(space['role']!='child' or row['owner_id']==actor['id'],'record_forbidden',403)
                    for table,field in [('transactions','account_id'),('transfers','from_id'),('transfers','to_id'),('requests','movement_id')]:
                        require(not db.execute('SELECT 1 FROM '+table+' d JOIN records r ON r.id=d.id WHERE d.'+field+'=? AND r.deleted=0',(rid,)).fetchone(),'linked_record')
                    db.execute('UPDATE records SET deleted=1 WHERE id=?',(rid,))
                elif action=='record.grant':
                    require(row['owner_id']==actor['id'],'owner_only',403);uid=identifier(op.get('user_id'));require(db.execute('SELECT 1 FROM memberships WHERE workspace_id=? AND user_id=? AND active=1',(wid,uid)).fetchone() is not None)
                    require(type(op.get('can_edit')) is bool and type(op.get('revoke')) is bool)
                    db.execute('DELETE FROM grants WHERE record_id=? AND user_id=?',(rid,uid))
                    if not op['revoke']:db.execute('INSERT INTO grants VALUES(?,?,?)',(rid,uid,int(op['can_edit'])))
                elif action=='request.fulfill':
                    require(space['role'] in ('parent','owner'),'parent_required',403);require(row['kind']=='request');request=self._data(db,row)['data'];require(request['state']=='pending','request_closed',409)
                    movement=identifier(op.get('movement_id'));transfer=self._reference(db,wid,movement,'transfer',actor=actor,space=space);account=self._reference(db,wid,transfer['to_id'],'account',currency=request['currency'],actor=actor,space=space)
                    target=db.execute('SELECT audience FROM records WHERE id=?',(transfer['to_id'],)).fetchone();require(request['profile_id'] in json.loads(target['audience']) and transfer['received_minor']==request['amount_minor'],'fulfillment_mismatch')
                    db.execute("UPDATE requests SET state='fulfilled',movement_id=? WHERE id=?",(movement,rid))
                seq=self._audit(db,wid,actor,op['id'],action,rid);db.execute('UPDATE records SET revision=revision+1,seq=? WHERE id=?',(seq,rid))
            if row and row['kind']=='transfer':
                for link in db.execute("SELECT q.* FROM requests q JOIN records r ON r.id=q.id WHERE q.movement_id=? AND q.state='fulfilled' AND r.deleted=0",(rid,)):
                    transfer=self._reference(db,wid,rid,'transfer');account=self._reference(db,wid,transfer['to_id'],'account')
                    require(transfer['received_minor']==link['amount_minor'] and account['currency']==link['currency'],'fulfillment_mismatch')
            revision=db.execute('SELECT revision FROM records WHERE id=?',(rid,)).fetchone()[0]
            result={'id':op['id'],'status':'accepted','record_id':rid,'revision':revision};self._remember(db,actor,op,result);return result
    def pull(self,actor,wid,cursor,limit=100):
        require(type(cursor) is int and cursor>=0 and type(limit) is int and 1<=limit<=100)
        with self.connect() as db:
            space=self._workspace(db,actor,wid);visible=[r for r in db.execute('SELECT * FROM records WHERE workspace_id=? ORDER BY seq',(wid,)) if self._readable(db,actor,space,r)]
            changed=[r for r in visible if r['seq']>cursor][:limit]
            maximum=db.execute('SELECT COALESCE(MAX(seq),0) FROM changes WHERE workspace_id=?',(wid,)).fetchone()[0]
            more=any(r['seq']>(changed[-1]['seq'] if changed else cursor) for r in visible)
            return {'records':[self._data(db,r) for r in changed],'cursor':changed[-1]['seq'] if more else max(cursor,maximum),'more':more,'visible_ids':[r['id'] for r in visible if not r['deleted']],'membership':space}
