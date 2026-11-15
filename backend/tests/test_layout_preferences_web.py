"""Exact authenticated customer routing and CSRF for personal list order."""
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from cryptography.fernet import Fernet
from backend.service import Backend
from backend.tests.test_referrals import ReferralScenarios


class LayoutOrderHTTPTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.f=ReferralScenarios();self.f.backend=Backend(Path(temp.name)/'layout-http.db',deliver=lambda e,c:None)
        self.f.backend.cipher=Fernet(Fernet.generate_key());self.f.prepare()
        self.actor=self.f.inviter;self.wid=str(uuid4());self.rid=str(uuid4())
        self.f.backend.family(self.actor,{'id':str(uuid4()),'action':'workspace.create','workspace_id':self.wid,'kind':'personal','name':'Test'})
        self.f.backend.batch(self.actor,self.wid,[{'id':str(uuid4()),'action':'record.put','record_id':self.rid,'revision':0,'kind':'account','visibility':'private','audience':[],'data':{'name':'Private account','currency':'RUB','opening_minor':123}}])

    def call(self,actor=None,method='GET',body=None,query=None,**kw):
        return self.f.call(self.actor if actor=='self' else actor,'layout-order',method,body,
            query='workspace='+self.wid+'&kind=account' if query is None and method=='GET' else query or '',**kw)

    def test_auth_origin_csrf_foreign_actor_and_strict_fields(self):
        body={'workspace_id':self.wid,'kind':'account','order':[self.rid],'revision':0}
        self.assertEqual(self.call()[0],401)
        self.assertEqual(self.call('self','POST',body,csrf=False)[0],403)
        self.assertEqual(self.call('self','POST',body,origin='https://other.test')[0],403)
        self.assertEqual(self.call(self.f.other)[0],403)
        for query in ('workspace='+self.wid,'workspace='+self.wid+'&kind=account&kind=budget','workspace='+self.wid+'&kind=account&user_id='+self.f.other['id'],'workspace='+self.wid+'&kind=account&unknown='):
            self.assertEqual(self.call('self',query=query)[0],400)
        for bad in ({**body,'user_id':self.f.other['id']},{'workspace_id':self.wid,'kind':'account'},{**body,'workspace':self.wid}):
            self.assertEqual(self.call('self','POST',bad)[0],400)
        self.assertEqual(self.call('self','POST',body,query='extra=1')[0],400)
        self.assertEqual(self.call('self','POST',body,query='extra=')[0],400)
        self.assertEqual(self.call('self')[1]['order'],[])
        status,value=self.call('self','POST',body)
        self.assertEqual(status,200,value);self.assertEqual(value['revision'],1)
        self.assertEqual(self.call('self')[1],value)
        self.assertEqual(self.call('self','POST',body)[0],409)


if __name__=='__main__':unittest.main()
