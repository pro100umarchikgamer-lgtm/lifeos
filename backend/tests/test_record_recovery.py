"""Owner consent + opaque staff approval + user-only canonical restore."""
import io
import json
import unittest
import uuid
from urllib.parse import urlsplit

class RecordRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f=self.make_fixture()
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.backend=self.f.backend;self.user=self.f.user2;self.cookie,self.csrf=self.f.login_customer()
        with self.backend.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS http_limits(key TEXT PRIMARY KEY,count BIGINT NOT NULL,until_at BIGINT NOT NULL)')
        self.wid=str(uuid.uuid4())
        self.backend.family(self.user,{'id':str(uuid.uuid4()),'workspace_id':self.wid,'action':'workspace.create','kind':'personal','name':'Private recovery workspace'})
        self.rid=self.put('note',{'body':'Private note never visible to staff'})
        self.delete(self.rid)

    def make_fixture(self):
        from backend.tests.test_control_web import WebControlTests
        return WebControlTests(methodName='test_staff_cookie_is_not_a_customer_bearer_and_mfa_required')

    def put(self,kind,data,wid=None,visibility='private',audience=None):
        rid=str(uuid.uuid4());op={'id':str(uuid.uuid4()),'action':'record.put','record_id':rid,'revision':0,'kind':kind,'visibility':visibility,'audience':audience or [],'data':data}
        result=self.backend.batch(self.user,wid or self.wid,[op])['results'][0]
        self.assertEqual(result['status'],'accepted',result);return rid

    def delete(self,rid,wid=None):
        with self.backend.connect() as db:revision=db.execute('SELECT revision FROM records WHERE id=?',(rid,)).fetchone()['revision']
        result=self.backend.batch(self.user,wid or self.wid,[{'id':str(uuid.uuid4()),'action':'record.delete','record_id':rid,'revision':revision}])['results'][0]
        self.assertEqual(result['status'],'accepted',result)

    def request(self,path,body=None,staff=False,other=False):
        parsed=urlsplit(path);cookie,csrf=(self.f.admission+'; __Host-uladim_control='+self.f.staff_login['token'],self.f.app.web.csrf(self.f.staff_login['token'])) if staff else (self.cookie,self.csrf)
        if other:cookie,csrf=self.f.owner_customer
        data=json.dumps(body).encode() if body is not None else b''
        host='control.getuladim.space' if staff else 'getuladim.space'
        env={'HTTP_HOST':host,'REQUEST_METHOD':'POST' if body is not None else 'GET','PATH_INFO':parsed.path,'QUERY_STRING':parsed.query,'REMOTE_ADDR':'172.30.30.2','HTTP_X_FORWARDED_PROTO':'https','HTTP_USER_AGENT':'fixture','HTTP_ORIGIN':'https://'+host,'HTTP_COOKIE':cookie,'HTTP_X_CSRF_TOKEN':csrf,'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(data)),'wsgi.input':io.BytesIO(data)}
        response=[];raw=b''.join(self.f.app(env,lambda s,h:response.append(int(s.split()[0]))))
        return response[0],json.loads(raw)

    def consent(self,rid=None,wid=None):
        status,body=self.request('/account/api/trash?workspace='+(wid or self.wid))
        self.assertEqual(status,200,body)
        record=next(r for r in body['records'] if r['id']==(rid or self.rid))
        status,result=self.request('/account/api/recovery/request',{'record_id':record['id'],'revision':record['revision'],'consent_hash':record['consent_hash']})
        self.assertEqual(status,200,result);return result['request']

    def approve(self,request):
        status,body=self.request('/control/api/record-recovery/approve',{'request_id':request['id'],'revision':request['revision'],'consent_hash':request['consent_hash'],'reason':'Verified user explicitly requested this record'},staff=True)
        self.assertEqual(status,200,body);return body['request']

    def grant(self,request):
        status,body=self.request('/account/api/recovery/prepare',{'request_id':request['id']})
        self.assertEqual(status,200,body);self.assertEqual(len(body['grant']),43);return body

    def commit(self,request,grant,operation=None):
        body={'request_id':request['id'],'grant':grant['grant'],'operation_id':operation or str(uuid.uuid4())}
        status,result=self.request('/account/api/recovery/commit',body)
        self.assertEqual(status,200,result);return result['results'][0],body

    def test_trash_and_requests_are_owner_only_staff_queue_contains_no_payload(self):
        # A different logged-in account cannot select the record owner via IDs.
        _,headers,session=self.f.request('/account/api/login',{'email':self.f.owner_user['email'],'password':'a-valid-long-passphrase'},origin='https://getuladim.space')
        self.f.owner_customer=headers['Set-Cookie'].split(';')[0],session['csrf']
        self.assertEqual(self.request('/account/api/trash?workspace='+self.wid,other=True)[0],404)
        self.assertEqual(self.request('/account/api/recovery/request',{'record_id':self.rid,'revision':2,'consent_hash':'a'*64},other=True)[0],404)
        own=self.consent();status,queue=self.request('/control/api/record-recovery',staff=True)
        self.assertEqual(status,200,queue);self.assertEqual(queue['requests'][0]['id'],own['id'])
        self.assertNotIn('Private note never visible to staff',json.dumps(queue))
        self.assertNotIn('data',queue['requests'][0]);self.assertNotIn('title',queue['requests'][0]);self.assertNotIn('amount_minor',queue['requests'][0])
        self.assertEqual(self.request('/account/api/recovery/prepare',{'request_id':own['id']},other=True)[0],404)

    def test_staff_approval_never_restores_and_user_commit_syncs_once_with_idempotent_retry(self):
        request=self.consent();approved=self.approve(request)
        self.assertEqual(approved['state'],'approved')
        with self.backend.connect() as db:self.assertEqual(db.execute('SELECT deleted FROM records WHERE id=?',(self.rid,)).fetchone()['deleted'],1)
        self.assertEqual(self.request('/control/api/record-recovery/approve',{'request_id':request['id'],'revision':request['revision'],'consent_hash':request['consent_hash'],'reason':'Repeated approval'},staff=True)[0],409)
        rejected,_=self.commit(approved,{'grant':'x'*43});self.assertEqual(rejected.get('error'),'recovery_invalid')
        before=self.backend.pull_incremental(self.user,self.wid,0)
        grant=self.grant(approved);result,body=self.commit(approved,grant)
        self.assertEqual(result['status'],'accepted',result);self.assertEqual(result['revision'],3)
        status,replay=self.request('/account/api/recovery/commit',body);self.assertEqual(status,200);self.assertEqual(replay['results'][0],result)
        newer=self.backend.pull_incremental(self.user,self.wid,before['cursor'],before['epoch'])
        self.assertEqual(len(newer['records']),1);self.assertEqual(newer['records'][0]['deleted'],0)
        self.assertEqual(newer['records'][0]['data']['body'],'Private note never visible to staff')
        self.assertEqual(self.backend.pull_incremental(self.user,self.wid,newer['cursor'],newer['epoch'])['records'],[])
        with self.backend.connect() as db:self.assertEqual(db.execute("SELECT COUNT(*) AS n FROM changes WHERE record_id=? AND kind='record.restore'",(self.rid,)).fetchone()['n'],1)
        another,_=self.commit(approved,grant);self.assertNotEqual(another['status'],'accepted')

    def test_request_and_grant_reject_stale_revision_or_changed_retained_content(self):
        request=self.consent()
        bad={'request_id':request['id'],'revision':request['revision'],'consent_hash':'0'*64,'reason':'Wrong consent'}
        self.assertEqual(self.request('/control/api/record-recovery/approve',bad,staff=True)[0],409)
        approved=self.approve(request);grant=self.grant(approved)
        with self.backend.transaction() as db:db.execute('UPDATE notes SET body=? WHERE id=?',('Changed since user consent',self.rid))
        result,_=self.commit(approved,grant);self.assertEqual(result.get('error'),'recovery_stale')
        with self.backend.connect() as db:self.assertEqual(db.execute('SELECT deleted FROM records WHERE id=?',(self.rid,)).fetchone()['deleted'],1)

    def test_deleted_reference_and_dissolved_workspace_prevent_restore(self):
        account=self.put('account',{'name':'Own account','currency':'RUB','opening_minor':1000})
        movement=self.put('transaction',{'kind':'expense','amount_minor':100,'currency':'RUB','date':'2026-11-13','label':'Private expense','account_id':account})
        self.delete(movement);request=self.approve(self.consent(movement));grant=self.grant(request)
        self.delete(account);result,_=self.commit(request,grant)
        self.assertEqual(result.get('error'),'invalid_reference')
        request=self.approve(self.consent());grant=self.grant(request)
        with self.backend.transaction() as db:db.execute('UPDATE workspaces SET dissolved=1 WHERE id=?',(self.wid,))
        status,body=self.request('/account/api/recovery/commit',{'request_id':request['id'],'grant':grant['grant'],'operation_id':str(uuid.uuid4())})
        self.assertTrue(status in (404,200));self.assertNotEqual(body.get('results',[{}])[0].get('status'),'accepted')

    def test_cancelled_or_expired_grants_cannot_restore(self):
        request=self.approve(self.consent());grant=self.grant(request)
        status,body=self.request('/account/api/recovery/cancel',{'request_id':request['id'],'revision':request['revision']})
        self.assertEqual(status,200,body);self.assertEqual(body['request']['state'],'cancelled')
        result,_=self.commit(request,grant);self.assertNotEqual(result['status'],'accepted')

    def test_current_child_permissions_are_checked_again_at_commit(self):
        wid=str(uuid.uuid4());self.backend.family(self.user,{'id':str(uuid.uuid4()),'workspace_id':wid,'action':'workspace.create','kind':'family','name':'Family recovery'})
        pid=str(uuid.uuid4());self.backend.family(self.user,{'id':str(uuid.uuid4()),'workspace_id':wid,'action':'child.save','profile_id':pid,'name':'Synthetic child','permissions':['edit_own','record_spending'],'revision':0})
        budget=self.put('budget',{'name':'Private budget','currency':'RUB','limit_minor':100,'period':'month','start_on':'2026-11-01','end_on':None,'rollover':'none','participants':[]},wid=wid,visibility='shared',audience=[pid])
        self.delete(budget,wid);request=self.approve(self.consent(budget,wid));grant=self.grant(request)
        with self.backend.transaction() as db:db.execute("UPDATE memberships SET role='child',profile_id=? WHERE workspace_id=? AND user_id=?",(pid,wid,self.user['id']))
        result,_=self.commit(request,grant);self.assertEqual(result.get('error'),'child_permission')

    def test_account_erasure_cannot_be_reversed_using_an_old_restore_grant(self):
        request=self.approve(self.consent());grant=self.grant(request)
        from backend.account_lifecycle import AccountLifecycle
        lifecycle=AccountLifecycle(self.backend);lifecycle.request_deletion(self.user,'a-valid-long-passphrase','DELETE')
        self.f.now+=86401;self.assertTrue(lifecycle.process_one_deletion())
        status,_=self.request('/account/api/recovery/commit',{'request_id':request['id'],'grant':grant['grant'],'operation_id':str(uuid.uuid4())})
        self.assertIn(status,(401,403,404))
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM record_recovery_requests WHERE user_id=?',(self.user['id'],)).fetchone()['n'],0)
            self.assertIsNone(db.execute('SELECT body FROM notes WHERE id=?',(self.rid,)).fetchone())
            self.assertEqual(db.execute('SELECT deleted FROM records WHERE id=?',(self.rid,)).fetchone()['deleted'],1)

    def test_exact_preview_is_owner_scoped_and_expired_grant_is_rejected(self):
        status,value=self.request('/account/api/trash?workspace='+self.wid+'&record='+self.rid)
        self.assertEqual(status,200,value);self.assertEqual(len(value['records']),1)
        self.assertEqual(self.request('/account/api/trash?workspace='+self.wid+'&record='+str(uuid.uuid4()))[0],404)
        request=self.approve(self.consent());grant=self.grant(request);self.f.now+=601
        result,_=self.commit(request,grant);self.assertEqual(result.get('error'),'recovery_invalid')

    def test_only_recovery_staff_roles_see_opaque_queue_and_stale_revision_is_rejected(self):
        from backend.control import StaffPrincipal
        from backend.record_recovery import RecordRecovery
        from backend.service import Failure
        recovery=RecordRecovery(self.backend);request=self.consent()
        for role in ('moderator','auditor','billing_manager'):
            with self.assertRaises(Failure) as denied:recovery.requests(StaffPrincipal('synthetic',self.f.owner_user['id'],(role,)),staff=True)
            self.assertEqual(denied.exception.status,403)
        with self.backend.transaction() as db:db.execute('UPDATE records SET revision=revision+1 WHERE id=?',(self.rid,))
        self.assertEqual(self.request('/control/api/record-recovery/approve',{'request_id':request['id'],'revision':request['revision'],'consent_hash':request['consent_hash'],'reason':'Stale record'},staff=True)[0],409)

    def test_all_record_kinds_restore_through_current_schema_and_both_pull_protocols(self):
        wid=str(uuid.uuid4());self.backend.family(self.user,{'id':str(uuid.uuid4()),'workspace_id':wid,'action':'workspace.create','kind':'family','name':'Kind fixtures'})
        pid=str(uuid.uuid4());self.backend.family(self.user,{'id':str(uuid.uuid4()),'workspace_id':wid,'action':'child.save','profile_id':pid,'name':'Synthetic profile','permissions':['view_budget'],'revision':0})
        def put(kind,data):return self.put(kind,data,wid=wid,audience=[pid])
        a=put('account',{'name':'A','currency':'RUB','opening_minor':1000});b=put('account',{'name':'B','currency':'RUB','opening_minor':0})
        movement=put('transaction',{'kind':'expense','amount_minor':100,'currency':'RUB','date':'2026-11-13','label':'Amount retained','account_id':a})
        transfer=put('transfer',{'from_id':a,'to_id':b,'sent_minor':100,'received_minor':100,'date':'2026-11-13'})
        values=[put('note',{'body':'Own note'}),put('task',{'title':'Own task','completed':0,'assignment':'any','assignees':[],'review':0}),put('event',{'title':'Own event','schedule':{'localStart':'2026-11-13T09:00:00','timezone':'UTC','allDay':False,'repeat':'none','interval':1,'until':None}}),put('shopping',{'name':'Own shopping','items':[]}),put('budget',{'name':'Own budget','currency':'RUB','limit_minor':100,'period':'month','start_on':'2026-11-01','end_on':None,'rollover':'none','participants':[pid]}),put('request',{'profile_id':pid,'amount_minor':100,'currency':'RUB','label':'Own request','state':'pending','movement_id':None})]
        for rid in values+[movement,transfer,a,b]:self.delete(rid,wid)
        before=self.backend.pull_incremental(self.user,wid,0)
        for rid in [a,b,movement,transfer]+values:
            request=self.approve(self.consent(rid,wid));result,_=self.commit(request,self.grant(request));self.assertEqual(result['status'],'accepted',result)
        delta=self.backend.pull_incremental(self.user,wid,before['cursor'],before['epoch'])
        legacy=self.backend.pull(self.user,wid,before['cursor'])
        self.assertEqual(len(delta['records']),10);self.assertEqual(len(legacy['records']),10)
        self.assertEqual({r['kind'] for r in delta['records']},{'note','task','event','shopping','budget','request','account','transaction','transfer'})
        self.assertTrue(all(not row['deleted'] for row in delta['records']))

    def test_fulfilled_request_restores_only_with_unchanged_current_financial_references(self):
        wid=str(uuid.uuid4());self.backend.family(self.user,{'id':str(uuid.uuid4()),'workspace_id':wid,'action':'workspace.create','kind':'family','name':'Fulfillment fixtures'})
        pid=str(uuid.uuid4());self.backend.family(self.user,{'id':str(uuid.uuid4()),'workspace_id':wid,'action':'child.save','profile_id':pid,'name':'Synthetic profile','permissions':['view_budget'],'revision':0})
        def put(kind,data):return self.put(kind,data,wid=wid,audience=[pid])
        a=put('account',{'name':'A','currency':'RUB','opening_minor':1000});b=put('account',{'name':'B','currency':'RUB','opening_minor':0})
        transfer=put('transfer',{'from_id':a,'to_id':b,'sent_minor':100,'received_minor':100,'date':'2026-11-13'})
        rid=put('request',{'profile_id':pid,'amount_minor':100,'currency':'RUB','label':'Own fulfilled request','state':'pending','movement_id':None})
        result=self.backend.batch(self.user,wid,[{'id':str(uuid.uuid4()),'action':'request.fulfill','record_id':rid,'revision':1,'movement_id':transfer}])['results'][0]
        self.assertEqual(result['status'],'accepted');self.delete(rid,wid)
        request=self.approve(self.consent(rid,wid));result,_=self.commit(request,self.grant(request));self.assertEqual(result['status'],'accepted',result)
        with self.backend.connect() as db:
            data=dict(db.execute('SELECT state,movement_id,amount_minor FROM requests WHERE id=?',(rid,)).fetchone())
            self.assertEqual(data,{'state':'fulfilled','movement_id':transfer,'amount_minor':100})
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM transfers').fetchone()['n'],1)
        self.delete(rid,wid);request=self.approve(self.consent(rid,wid));grant=self.grant(request)
        self.delete(transfer,wid);result,_=self.commit(request,grant);self.assertEqual(result.get('error'),'invalid_reference')

    def test_self_staff_can_approve_own_consent_without_staff_content_or_silent_restore(self):
        self.user=self.f.owner_user
        _,headers,session=self.f.request('/account/api/login',{'email':self.user['email'],'password':'a-valid-long-passphrase'},origin='https://getuladim.space')
        self.cookie,self.csrf=headers['Set-Cookie'].split(';')[0],session['csrf']
        self.wid=str(uuid.uuid4());self.backend.family(self.user,{'id':str(uuid.uuid4()),'workspace_id':self.wid,'action':'workspace.create','kind':'personal','name':'Owner private workspace'})
        self.rid=self.put('note',{'body':'Owner private content'});self.delete(self.rid)
        request=self.consent();approved=self.approve(request)
        self.assertNotIn('Owner private content',json.dumps(approved))
        with self.backend.connect() as db:self.assertEqual(db.execute('SELECT deleted FROM records WHERE id=?',(self.rid,)).fetchone()['deleted'],1)
        result,_=self.commit(approved,self.grant(approved));self.assertEqual(result['status'],'accepted',result)

    def test_staff_cannot_invent_or_commit_someone_elses_request(self):
        request=self.consent()
        self.assertEqual(self.request('/control/api/recovery/request',{'record_id':self.rid,'revision':2,'consent_hash':request['consent_hash']},staff=True)[0],404)
        self.assertEqual(self.request('/control/api/recovery/prepare',{'request_id':request['id']},staff=True)[0],404)
        self.assertEqual(self.request('/control/api/recovery/commit',{'request_id':request['id'],'grant':'x'*43,'operation_id':str(uuid.uuid4())},staff=True)[0],404)
        self.approve(request)
        _,headers,session=self.f.request('/account/api/login',{'email':self.f.owner_user['email'],'password':'a-valid-long-passphrase'},origin='https://getuladim.space')
        self.f.owner_customer=headers['Set-Cookie'].split(';')[0],session['csrf']
        self.assertEqual(self.request('/account/api/recovery/prepare',{'request_id':request['id']},other=True)[0],404)
        self.assertEqual(self.request('/account/api/recovery/commit',{'request_id':request['id'],'grant':'x'*43,'operation_id':str(uuid.uuid4())},other=True)[0],404)

    def test_lower_staff_can_approve_owner_request_but_only_owner_can_commit_it(self):
        from backend.control import StaffPrincipal, totp
        from backend.record_recovery import RecordRecovery
        self.user=self.f.owner_user
        _,headers,session=self.f.request('/account/api/login',{'email':self.user['email'],'password':'a-valid-long-passphrase'},origin='https://getuladim.space')
        self.cookie,self.csrf=headers['Set-Cookie'].split(';')[0],session['csrf']
        self.wid=str(uuid.uuid4());self.backend.family(self.user,{'id':str(uuid.uuid4()),'workspace_id':self.wid,'action':'workspace.create','kind':'personal','name':'Owner recovery'})
        self.rid=self.put('note',{'body':'Never exposed to support'});self.delete(self.rid);request=self.consent()
        invitation=self.f.control.invite_staff(self.f.owner,self.f.user2['email'],['support'],'Synthetic coverage')
        enrollment=self.f.control.prepare_enrollment(self.f.user2,invitation['invitation'],'a-valid-long-passphrase')
        staff=self.f.control.finish_enrollment(self.f.user2,enrollment['enrollment'],totp(enrollment['totp_secret'],self.f.now//30))
        support=StaffPrincipal(staff['staff_id'],self.f.user2['id'],('support',))
        approved=RecordRecovery(self.backend).approve(support,{'request_id':request['id'],'revision':request['revision'],'consent_hash':request['consent_hash'],'reason':'User explicitly consented'})['request']
        self.assertEqual(approved['state'],'approved');self.assertNotIn('Never exposed to support',json.dumps(approved))
        result,_=self.commit(approved,self.grant(approved));self.assertEqual(result['status'],'accepted',result)
