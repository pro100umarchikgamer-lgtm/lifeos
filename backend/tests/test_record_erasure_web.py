"""Owner trash purge HTTP boundaries, independent synthetic journal, no real data."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
from cryptography.fernet import Fernet
from backend.service import Backend
from backend.record_erasure import initialize
from backend.tests.test_referrals import ReferralScenarios
from backend.tests.test_record_erasure import IndependentJournal


class RecordErasureHTTPTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.f=ReferralScenarios();self.f.backend=Backend(Path(temp.name)/'erasure-http.db',deliver=lambda e,c:None)
        self.f.backend.cipher=Fernet(Fernet.generate_key());self.f.prepare()
        self.actor=self.f.inviter;self.wid=str(uuid4());self.rid=str(uuid4())
        journal=IndependentJournal(Path(temp.name)/'records.jsonl')
        transport=patch('backend.record_erasure.acknowledge',journal.call);transport.start();self.addCleanup(transport.stop)
        initialize(self.f.backend,str(journal.path),'synthetic-root-socket',True)
        self.f.backend.family(self.actor,{'id':str(uuid4()),'action':'workspace.create','workspace_id':self.wid,'kind':'personal','name':'Test'})
        self.f.backend.batch(self.actor,self.wid,[{'id':str(uuid4()),'action':'record.put','record_id':self.rid,'revision':0,'kind':'note','visibility':'private','audience':[],'data':{'body':'SYNTHETIC PRIVATE BODY'}}])
        self.f.backend.batch(self.actor,self.wid,[{'id':str(uuid4()),'action':'record.delete','record_id':self.rid,'revision':1}])

    def test_owner_scope_csrf_strict_fields_and_exact_purge_route(self):
        query='record='+self.rid
        self.assertEqual(self.f.call(None,'recovery/purge-preview',query=query)[0],401)
        self.assertEqual(self.f.call(self.f.other,'recovery/purge-preview',query=query)[0],404)
        for bad in ('record='+self.rid+'&record='+self.rid,query+'&extra=',query+'&owner=x',''):
            self.assertEqual(self.f.call(self.actor,'recovery/purge-preview',query=bad)[0],400)
        status,preview=self.f.call(self.actor,'recovery/purge-preview',query=query)
        self.assertEqual(status,200,preview);self.assertTrue(preview['permanent_delete_available'])
        body={'operation_id':str(uuid4()),'record_id':self.rid,'revision':preview['record']['revision'],'consent_hash':preview['record']['consent_hash']}
        self.assertEqual(self.f.call(self.actor,'recovery/purge','POST',body,csrf=False)[0],403)
        self.assertEqual(self.f.call(self.actor,'recovery/purge','POST',body,origin='https://other.test')[0],403)
        self.assertEqual(self.f.call(self.actor,'recovery/purge','POST',body,query='extra=')[0],400)
        self.assertEqual(self.f.call(self.actor,'recovery/purge','POST',{**body,'owner':self.actor['id']})[0],400)
        self.assertEqual(self.f.call(self.actor,'recovery/purge','GET')[0],404)
        status,result=self.f.call(self.actor,'recovery/purge','POST',body)
        self.assertEqual(status,200,result);self.assertTrue(result['erased'])
        self.assertEqual(self.f.call(self.actor,'recovery/purge','POST',body),(200,result))
        with self.f.backend.connect() as db:self.assertIsNone(db.execute('SELECT 1 FROM notes WHERE id=?',(self.rid,)).fetchone())


if __name__=='__main__':unittest.main()
