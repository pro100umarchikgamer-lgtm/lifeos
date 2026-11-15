"""Actual bearer dispatch for the native referral and task schedule adapters."""
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from cryptography.fernet import Fernet
from backend.http_server import dispatch
from backend.service import Backend,Failure
from backend.tests.test_referrals import ReferralScenarios,PASSWORD


class NativeFeedbackRoutes(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.f=ReferralScenarios();self.f.backend=Backend(Path(temp.name)/'native-routes.db',deliver=lambda e,c:None)
        self.f.backend.cipher=Fernet(Fernet.generate_key());self.f.prepare()
        self.auth='Bearer '+self.f.backend.login(self.f.inviter['email'],PASSWORD)['token']

    def test_bearer_referral_privacy_strict_queries_and_task_scope(self):
        with self.assertRaises(Failure):dispatch(self.f.backend,'GET','/v1/referrals',{},'')
        code=dispatch(self.f.backend,'POST','/v1/referrals/code',{},self.auth)['invite']['code']
        self.assertEqual(len(code),43)
        self.assertEqual(set(dispatch(self.f.backend,'GET','/v1/referrals',{},self.auth)),{'confirmed_count','invite','people','next_offset'})
        alias=dispatch(self.f.backend,'POST','/v1/referrals/alias',{'first_name':'Умар','surname_initial':'U'},self.auth)
        self.assertEqual(alias['display_name'],'Умар U.')
        for path in ('/v1/referrals/code?extra=','/v1/referrals?offset=0&offset=1','/v1/task-reminders?workspace=x&extra='):
            with self.assertRaises(Failure):dispatch(self.f.backend,'GET',path,{},self.auth)
        wid,rid=str(uuid4()),str(uuid4())
        self.f.backend.family(self.f.inviter,{'id':str(uuid4()),'action':'workspace.create','workspace_id':wid,'kind':'personal','name':'Test'})
        self.f.backend.batch(self.f.inviter,wid,[{'id':str(uuid4()),'action':'record.put','record_id':rid,'revision':0,'kind':'task','visibility':'private','audience':[],'data':{'title':'Native private task','completed':0,'assignment':'any','assignees':[],'review':0}}])
        body={'workspace_id':wid,'task_id':rid,'revision':0,'schedule':None,'reminder':False}
        saved=dispatch(self.f.backend,'POST','/v1/task-reminders',body,self.auth)
        self.assertEqual(saved['task_id'],rid)
        self.assertEqual(dispatch(self.f.backend,'GET','/v1/task-reminders?workspace='+wid+'&task_id='+rid,{},self.auth),saved)
        other='Bearer '+self.f.backend.login(self.f.other['email'],PASSWORD)['token']
        with self.assertRaises(Failure):dispatch(self.f.backend,'GET','/v1/task-reminders?workspace='+wid,{},other)


if __name__=='__main__':unittest.main()
