import http.client
import json
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from http.server import ThreadingHTTPServer
from backend.service import Backend,Failure
from backend.http_server import handler

def uid():return str(uuid.uuid4())

class FamilyBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.mail={}
        self.backend=Backend(Path(self.temp.name)/'server.db',deliver=lambda email,code:self.mail.update({email:code}))
        self.p1=self.user('one@example.test');self.p2=self.user('two@example.test');self.child=self.user('child@example.test')
        self.wid=uid();self.backend.family(self.p1,self.op('workspace.create',kind='family',name='Family'))
        invite=self.backend.family(self.p1,self.op('invite.create',email=self.p2['email'],role='parent',profile_id=None))
        self.backend.accept(self.p2,{'id':uid(),'invitation':invite['invitation']})
    def user(self,email):
        result=self.backend.register(email,'a-valid-long-passphrase');actor=self.backend.authenticate(result['token']);self.backend.verify(actor,self.mail[email]);actor=self.backend.authenticate(result['token']);actor['token']=result['token'];return actor
    def op(self,action,**kwargs):return {'id':uid(),'workspace_id':self.wid,'action':action,**kwargs}
    def put(self,actor,kind,data,visibility='shared',audience=None,rid=None,revision=0):
        op={'id':uid(),'action':'record.put','record_id':rid or uid(),'revision':revision,'kind':kind,'visibility':visibility,'audience':audience or [],'data':data}
        return op,self.backend.batch(actor,self.wid,[op])['results'][0]
    def child_profile(self,permissions=None):
        pid=uid();self.backend.family(self.p2,self.op('child.save',profile_id=pid,name='Child',permissions=permissions or ['view_budget','record_spending','request_money','create_tasks','complete_tasks','edit_own'],revision=0))
        invite=self.backend.family(self.p1,self.op('invite.create',email=self.child['email'],role='child',profile_id=pid));self.backend.accept(self.child,{'id':uid(),'invitation':invite['invitation']});return pid
    def test_parents_equal_but_creator_exclusive_dissolution(self):
        roster=self.backend.roster(self.p2,self.wid);self.assertEqual({m['role'] for m in roster['members']},{'parent'})
        with self.assertRaises(Failure):self.backend.family(self.p2,self.op('workspace.dissolve',revision=1))
        with self.assertRaises(Failure):self.backend.family(self.p1,self.op('member.remove',user_id=self.p2['id'],revision=1))
        change=uid();self.backend.family(self.p1,self.op('parent.change.request',change_id=change,user_id=self.p2['id'],role='adult',revision=1))
        with self.assertRaises(Failure):self.backend.family(self.p1,self.op('parent.change.approve',change_id=change,revision=1))
        self.backend.family(self.p2,self.op('parent.change.approve',change_id=change,revision=1))
        self.backend.family(self.p1,self.op('workspace.dissolve',revision=1));self.assertEqual(self.backend.spaces(self.p2),[])
    def test_private_records_never_leak_to_other_parent_and_grants_revoke(self):
        op,result=self.put(self.p1,'note',{'body':'Private adult diary'},'private');rid=op['record_id'];self.assertEqual(result['status'],'accepted')
        self.assertEqual(self.backend.pull(self.p2,self.wid,0)['records'],[])
        spoof={**op,'id':uid(),'revision':1,'data':{'body':'stolen'}}
        self.assertEqual(self.backend.batch(self.p2,self.wid,[spoof])['results'][0]['error'],'record_forbidden')
        grant={'id':uid(),'action':'record.grant','record_id':rid,'revision':1,'user_id':self.p2['id'],'can_edit':False,'revoke':False}
        self.backend.batch(self.p1,self.wid,[grant]);self.assertEqual(len(self.backend.pull(self.p2,self.wid,0)['records']),1)
        grant={**grant,'id':uid(),'revision':2,'revoke':True};self.backend.batch(self.p1,self.wid,[grant]);pull=self.backend.pull(self.p2,self.wid,0)
        self.assertEqual(pull['visible_ids'],[]);self.assertEqual(pull['records'],[])

    def test_incremental_pages_visibility_changes_and_server_recovery(self):
        op,_=self.put(self.p1,'note',{'body':'shared'})
        first=self.backend.pull_incremental(self.p2,self.wid,0)
        self.assertTrue(first['reset']);self.assertNotIn('visible_ids',first)
        next_page=self.backend.pull_incremental(self.p2,self.wid,first['cursor'],first['epoch'])
        self.assertFalse(next_page['reset']);self.assertEqual(next_page['records'],[])
        self.backend.batch(self.p1,self.wid,[{**op,'id':uid(),'revision':1,'visibility':'private'}])
        revoked=self.backend.pull_incremental(self.p2,self.wid,next_page['cursor'],next_page['epoch'])
        self.assertTrue(revoked['reset']);self.assertEqual(revoked['records'],[])
        restored=self.backend.pull_incremental(self.p1,self.wid,999999,revoked['epoch'])
        self.assertTrue(restored['reset']);self.assertLess(restored['cursor'],999999)
        for i in range(4):self.put(self.p1,'note',{'body':str(i)})
        page=self.backend.pull_incremental(self.p2,self.wid,0,limit=2)
        records=list(page['records'])
        while page['more']:
            previous=page['cursor'];page=self.backend.pull_incremental(self.p2,self.wid,previous,page['epoch'],limit=2)
            self.assertGreater(page['cursor'],previous);self.assertFalse(page['reset']);records.extend(page['records'])
        self.assertEqual(len(records),4)
    def test_independent_additions_idempotency_and_concurrent_conflict(self):
        first,res=self.put(self.p1,'note',{'body':'First offline change'});self.put(self.p2,'note',{'body':'Independent addition'})
        self.backend.batch(self.p1,self.wid,[first]);self.assertEqual(len(self.backend.pull(self.p2,self.wid,0)['records']),2)
        updated={**first,'id':uid(),'revision':1,'data':{'body':'Parent one'}};self.backend.batch(self.p1,self.wid,[updated])
        other={**first,'id':uid(),'revision':1,'data':{'body':'Parent two'}};conflict=self.backend.batch(self.p2,self.wid,[other])['results'][0]
        self.assertEqual(conflict['status'],'conflict');self.assertEqual(conflict['server']['data']['body'],'Parent one')
        duplicate={**first,'data':{'body':'Different retry'}};self.assertEqual(self.backend.batch(self.p1,self.wid,[duplicate])['results'][0]['error'],'operation_conflict')
    def test_child_overspending_allowed_but_private_adult_data_forbidden(self):
        pid=self.child_profile();self.put(self.p1,'budget',{'name':'Allowance','currency':'RUB','limit_minor':100,'period':'month','start_on':'2026-10-01','end_on':None,'rollover':'negative','participants':[pid]},audience=[pid])
        self.put(self.p1,'note',{'body':'Private finance'},'private')
        _,result=self.put(self.child,'transaction',{'kind':'expense','amount_minor':99999,'currency':'RUB','date':'2026-10-13','label':'Over budget','account_id':None},audience=[pid]);self.assertEqual(result['status'],'accepted')
        _,result=self.put(self.child,'transaction',{'kind':'income','amount_minor':100,'currency':'RUB','date':'2026-10-13','label':'Fake income','account_id':None},audience=[pid]);self.assertEqual(result['status'],'rejected')
        visible=self.backend.pull(self.child,self.wid,0);self.assertEqual({r['kind'] for r in visible['records']},{'budget','transaction'})
    def test_revocation_blocks_cached_operation_replay_and_shared_pull(self):
        pid=self.child_profile();op,_=self.put(self.child,'note',{'body':'Denied'},audience=[pid]);self.assertEqual(self.backend.batch(self.child,self.wid,[op])['results'][0]['status'],'rejected')
        op,_=self.put(self.child,'transaction',{'kind':'expense','amount_minor':10,'currency':'RUB','date':'2026-10-13','label':'Own','account_id':None},audience=[pid])
        self.backend.family(self.p2,self.op('member.remove',user_id=self.child['id'],revision=1))
        self.assertEqual(self.backend.batch(self.child,self.wid,[op])['results'][0]['error'],'workspace_forbidden')
        with self.assertRaises(Failure):self.backend.pull(self.child,self.wid,0)
    def test_request_fulfillment_references_one_real_transfer(self):
        pid=self.child_profile();a,_=self.put(self.p1,'account',{'name':'Parent','currency':'RUB','opening_minor':0});b,_=self.put(self.p2,'account',{'name':'Child','currency':'RUB','opening_minor':0},audience=[pid])
        transfer,_=self.put(self.p1,'transfer',{'from_id':a['record_id'],'to_id':b['record_id'],'sent_minor':500,'received_minor':500,'date':'2026-10-13'})
        request,_=self.put(self.child,'request',{'profile_id':pid,'amount_minor':500,'currency':'RUB','label':'Books','state':'pending','movement_id':None},audience=[pid])
        fulfill={'id':uid(),'action':'request.fulfill','record_id':request['record_id'],'revision':1,'movement_id':transfer['record_id']}
        self.assertEqual(self.backend.batch(self.p1,self.wid,[fulfill])['results'][0]['status'],'accepted')
        self.assertEqual(self.backend.batch(self.p1,self.wid,[fulfill])['results'][0]['status'],'accepted')
        other={**fulfill,'id':uid()};self.assertEqual(self.backend.batch(self.p2,self.wid,[other])['results'][0]['status'],'conflict')
        self.assertEqual(len([r for r in self.backend.pull(self.p1,self.wid,0)['records'] if r['kind']=='transfer']),1)
    def test_real_isolated_http_backend_two_tokens_and_invalid_auth(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.backend));server.daemon_threads=True;thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def fetch(token,path):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5);conn.request('GET',path,headers={'Authorization':'Bearer '+token});reply=conn.getresponse();body=json.loads(reply.read());conn.close();return reply.status,body
        try:
            self.assertEqual(fetch(self.p1['token'],'/v1/me')[1]['user_id'],self.p1['id'])
            self.assertEqual(fetch(self.p2['token'],'/v1/me')[1]['user_id'],self.p2['id'])
            self.assertEqual(fetch('bad','/v1/spaces')[0],401)
            self.backend.logout(self.p2['token']);self.assertEqual(fetch(self.p2['token'],'/v1/me')[0],401)
        finally:server.shutdown();server.server_close();thread.join(timeout=5)

    def test_password_change_revokes_all_sessions_and_wrong_password_keeps_account(self):
        other=self.backend.login(self.p1['email'],'a-valid-long-passphrase')['token']
        with self.assertRaises(Failure):self.backend.password(self.p1,'wrong','a-different-valid-password')
        self.assertEqual(self.backend.authenticate(other)['id'],self.p1['id'])
        self.backend.password(self.p1,'a-valid-long-passphrase','a-different-valid-password')
        for token in [other,self.p1['token']]:
            with self.assertRaises(Failure):self.backend.authenticate(token)
        with self.assertRaises(Failure):self.backend.login(self.p1['email'],'a-valid-long-passphrase')
        self.assertEqual(self.backend.authenticate(self.backend.login(self.p1['email'],'a-different-valid-password')['token'])['id'],self.p1['id'])

    def test_malformed_batch_does_not_abort_valid_operation(self):
        op,_=self.put(self.p1,'note',{'body':'valid'})
        result=self.backend.batch(self.p1,self.wid,[None,{'record_id':op['record_id'],'action':'record.put'},op])['results']
        self.assertEqual([r['status'] for r in result],['rejected','rejected','accepted'])
        self.assertEqual(result[1]['error'],'invalid_id')

    def test_another_family_cannot_read_or_reference_records(self):
        account,_=self.put(self.p1,'account',{'name':'Private cash','currency':'RUB','opening_minor':0})
        outsider=self.user('outsider@example.test');wid=uid()
        self.backend.family(outsider,{'id':uid(),'workspace_id':wid,'action':'workspace.create','name':'Other','kind':'family'})
        with self.assertRaises(Failure):self.backend.pull(outsider,self.wid,0)
        edit={**account,'id':uid(),'revision':1}
        self.assertEqual(self.backend.batch(outsider,wid,[edit])['results'][0]['error'],'record_forbidden')
        op={'id':uid(),'action':'record.put','record_id':uid(),'revision':0,'kind':'transaction','visibility':'shared','audience':[],'data':{'kind':'expense','amount_minor':1,'currency':'RUB','date':'2026-10-13','label':'spoof','account_id':account['record_id']}}
        self.assertEqual(self.backend.batch(outsider,wid,[op])['results'][0]['error'],'invalid_reference')

    def test_child_can_complete_multi_audience_task_but_not_change_assignment(self):
        pid=self.child_profile();other=uid()
        self.backend.family(self.p1,self.op('child.save',profile_id=other,name='Sibling',permissions=['view_shared'],revision=0))
        task,_=self.put(self.p1,'task',{'title':'Together','completed':0,'assignment':'joint','assignees':[pid,other],'review':0},audience=[pid,other])
        changed={'id':uid(),'action':'task.complete','record_id':task['record_id'],'revision':1,'profile_id':pid,'completed':True}
        self.assertEqual(self.backend.batch(self.child,self.wid,[changed])['results'][0]['status'],'accepted')
        self.assertEqual(self.backend.pull(self.p1,self.wid,0)['records'][0]['data']['completed'],0)
        forged={**task,'id':uid(),'revision':2,'data':{**task['data'],'title':'Changed by child'}}
        self.assertEqual(self.backend.batch(self.child,self.wid,[forged])['results'][0]['error'],'completion_only')

    def test_transfer_cannot_fulfill_two_requests(self):
        pid=self.child_profile()
        a,_=self.put(self.p1,'account',{'name':'Parent','currency':'RUB','opening_minor':0})
        b,_=self.put(self.p1,'account',{'name':'Child','currency':'RUB','opening_minor':0},audience=[pid])
        movement,_=self.put(self.p1,'transfer',{'from_id':a['record_id'],'to_id':b['record_id'],'sent_minor':100,'received_minor':100,'date':'2026-10-13'})
        for index in range(2):
            request,_=self.put(self.child,'request',{'profile_id':pid,'amount_minor':100,'currency':'RUB','label':'Books','state':'pending','movement_id':None},audience=[pid])
            result=self.backend.batch(self.p1,self.wid,[{'id':uid(),'action':'request.fulfill','record_id':request['record_id'],'revision':1,'movement_id':movement['record_id']}])['results'][0]
            self.assertEqual(result['status'],'accepted' if index==0 else 'rejected')
            if index:self.assertEqual(result['error'],'movement_already_used')

    def test_either_parent_can_revoke_invitation_before_acceptance(self):
        invitation=self.backend.family(self.p1,self.op('invite.create',email='new@example.test',role='adult',profile_id=None))
        self.backend.family(self.p2,self.op('invite.revoke',invitation_id=invitation['invitation_id']))
        actor=self.user('new@example.test')
        with self.assertRaises(Failure):self.backend.accept(actor,{'id':uid(),'invitation':invitation['invitation']})
        self.assertEqual(self.backend.roster(self.p2,self.wid)['invitations'],[])

    def test_joint_task_requires_each_completion_review_and_title_edit_preserves_progress(self):
        pid=self.child_profile();sibling=self.user('sibling@example.test');other=uid()
        self.backend.family(self.p1,self.op('child.save',profile_id=other,name='Sibling',permissions=['complete_tasks','view_shared'],revision=0))
        invitation=self.backend.family(self.p2,self.op('invite.create',email=sibling['email'],role='child',profile_id=other))
        self.backend.accept(sibling,{'id':uid(),'invitation':invitation['invitation']})
        task,_=self.put(self.p1,'task',{'title':'Joint','completed':0,'assignment':'joint','assignees':[pid,other],'review':1},audience=[pid,other])
        def complete(actor,profile,revision,action='task.complete'):
            result=self.backend.batch(actor,self.wid,[{'id':uid(),'record_id':task['record_id'],'action':action,'revision':revision,'profile_id':profile,'completed':True}])['results'][0]
            self.assertEqual(result['status'],'accepted');return result['revision']
        complete(self.child,pid,1)
        changed={**task,'id':uid(),'revision':2,'data':{**task['data'],'title':'New title'}}
        self.assertEqual(self.backend.batch(self.p1,self.wid,[changed])['results'][0]['status'],'accepted')
        current=self.backend.pull(self.p1,self.wid,0)['records'][0]
        self.assertEqual(current['progress'][0]['completed'],1);self.assertEqual(current['data']['completed'],0)
        complete(self.p2,pid,3,'task.review');complete(sibling,other,4)
        current=self.backend.pull(self.p1,self.wid,0)['records'][0];self.assertEqual(current['data']['completed'],0)
        complete(self.p1,other,5,'task.review')
        self.assertEqual(self.backend.pull(self.p2,self.wid,0)['records'][0]['data']['completed'],1)

    def test_recovery_is_email_bound_single_use_and_revokes_sessions(self):
        self.assertEqual(self.backend.recover('unknown@example.test'),{'recovery_requested':True})
        self.backend.recover(self.p1['email']);code=self.mail[self.p1['email']]
        with self.assertRaises(Failure):self.backend.reset_password(self.p2['email'],code,'a-new-valid-long-password')
        self.backend.reset_password(self.p1['email'],code,'a-new-valid-long-password')
        with self.assertRaises(Failure):self.backend.authenticate(self.p1['token'])
        with self.assertRaises(Failure):self.backend.reset_password(self.p1['email'],code,'a-new-valid-long-password')
        self.assertTrue(self.backend.login(self.p1['email'],'a-new-valid-long-password')['verified'])
