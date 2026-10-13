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
