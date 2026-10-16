import tempfile
import unittest
import uuid
from pathlib import Path
from backend.account_lifecycle import AccountLifecycle
from backend.service import Backend, Failure

PASSWORD='a-valid-long-passphrase'

class LifecycleScenarios:
    def setup_lifecycle(self):
        self.lifecycle=AccountLifecycle(self.backend)
        self.now=int(self.backend.clock());self.backend.clock=lambda:self.now

    def test_signup_does_not_enumerate_or_issue_credentials_before_verification(self):
        first=self.lifecycle.signup('new@example.test',PASSWORD)
        duplicate=self.lifecycle.signup('new@example.test',PASSWORD)
        self.assertEqual(first,duplicate);self.assertNotIn('token',first)
        with self.assertRaises(Failure):self.lifecycle.confirm_signup('new@example.test','x'*43)
        result=self.lifecycle.confirm_signup('new@example.test',self.mail['new@example.test'])
        self.assertTrue(self.backend.authenticate(result['token'])['verified'])
        with self.assertRaises(Failure):self.lifecycle.confirm_signup('new@example.test',self.mail['new@example.test'])

    def test_email_change_is_scoped_one_use_and_revokes_every_device(self):
        login=self.backend.login(self.p1['email'],PASSWORD)
        self.lifecycle.change_email(self.p1,'newmail@example.test',PASSWORD)
        code=self.mail['newmail@example.test']
        with self.assertRaises(Failure):self.lifecycle.confirm_email(self.p2,code,PASSWORD)
        self.lifecycle.confirm_email(self.p1,code,PASSWORD)
        with self.assertRaises(Failure):self.backend.authenticate(login['token'])
        with self.assertRaises(Failure):self.backend.refresh_session(login['refresh_token'])
        self.assertEqual(self.backend.login('newmail@example.test',PASSWORD)['user_id'],self.p1['id'])
        with self.assertRaises(Failure):self.lifecycle.confirm_email(self.p1,code,PASSWORD)

    def test_deletion_requires_confirmation_has_grace_and_does_not_delete_other_user(self):
        with self.assertRaises(Failure):self.lifecycle.request_deletion(self.p2,PASSWORD,'yes')
        request=self.lifecycle.request_deletion(self.p2,PASSWORD,'DELETE')
        self.assertFalse(self.lifecycle.process_one_deletion())
        self.lifecycle.cancel_deletion(self.p2,PASSWORD)
        self.assertEqual(self.lifecycle.deletion_status(self.p2)['request']['state'],'cancelled')
        self.now+=901 # reauthentication budget is independent and bounded
        self.lifecycle.request_deletion(self.p2,PASSWORD,'DELETE')
        self.now+=86401
        self.assertTrue(self.lifecycle.process_one_deletion())
        self.assertFalse(self.lifecycle.process_one_deletion())
        with self.assertRaises(Failure):self.backend.login(self.p2['email'],PASSWORD)
        with self.backend.connect() as db:
            self.assertNotEqual(db.execute('SELECT email FROM users WHERE id=?',(self.p2['id'],)).fetchone()['email'],self.p2['email'])
            self.assertEqual(db.execute('SELECT email FROM users WHERE id=?',(self.p1['id'],)).fetchone()['email'],self.p1['email'])

    def test_deletion_erases_private_payload_preserves_shared_history_and_sync(self):
        ids = {}
        for visibility in ('private', 'shared'):
            rid = str(uuid.uuid4());ids[visibility] = rid
            result = self.backend.batch(self.p1,self.wid,[{'id':str(uuid.uuid4()),'record_id':rid,'action':'record.put','revision':0,'kind':'note','visibility':visibility,'audience':[],'data':{'body':visibility+' synthetic note'}}])
            self.assertEqual(result['results'][0]['status'],'accepted')
        tid = self.lifecycle.transfer(self.p1,self.wid,self.p2['id'],PASSWORD)['transfer_id']
        self.lifecycle.accept_transfer(self.p2,tid,PASSWORD)
        self.lifecycle.request_deletion(self.p1,PASSWORD,'DELETE');self.now+=86401
        self.assertTrue(self.lifecycle.process_one_deletion())
        records = self.backend.pull(self.p2,self.wid,0)['records']
        self.assertEqual([r['data']['body'] for r in records if not r['deleted']],['shared synthetic note'])
        with self.backend.connect() as db:
            self.assertIsNone(db.execute('SELECT body FROM notes WHERE id=?',(ids['private'],)).fetchone())
            self.assertEqual(db.execute('SELECT deleted FROM records WHERE id=?',(ids['private'],)).fetchone()['deleted'],1)

    def test_creator_deletion_requires_consented_parent_transfer(self):
        with self.assertRaises(Failure):self.lifecycle.request_deletion(self.p1,PASSWORD,'DELETE')
        tid=self.lifecycle.transfer(self.p1,self.wid,self.p2['id'],PASSWORD)['transfer_id']
        with self.assertRaises(Failure):self.lifecycle.accept_transfer(self.p1,tid,PASSWORD)
        self.lifecycle.accept_transfer(self.p2,tid,PASSWORD)
        with self.assertRaises(Failure):self.lifecycle.accept_transfer(self.p2,tid,PASSWORD)
        self.lifecycle.request_deletion(self.p1,PASSWORD,'DELETE')
        self.now+=86401
        self.assertTrue(self.lifecycle.process_one_deletion())
        with self.backend.connect() as db:self.assertEqual(db.execute('SELECT creator_id FROM workspaces WHERE id=?',(self.wid,)).fetchone()['creator_id'],self.p2['id'])


class AccountLifecycleTests(LifecycleScenarios,unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup);self.mail={}
        self.backend=Backend(Path(folder.name)/'lifecycle.db',deliver=lambda e,c:self.mail.update({e:c}))
        self.p1=self.user('owner@example.test');self.p2=self.user('second@example.test')
        self.wid=str(uuid.uuid4())
        self.backend.family(self.p1,{'id':str(uuid.uuid4()),'action':'workspace.create','workspace_id':self.wid,'name':'Family','kind':'family'})
        invite=self.backend.family(self.p1,{'id':str(uuid.uuid4()),'action':'invite.create','workspace_id':self.wid,'email':self.p2['email'],'role':'parent','profile_id':None})
        self.backend.accept(self.p2,{'id':str(uuid.uuid4()),'invitation':invite['invitation']})
        self.setup_lifecycle()

    def user(self,email):
        result=self.backend.register(email,PASSWORD);actor=self.backend.authenticate(result['token']);self.backend.verify(actor,self.mail[email]);return self.backend.authenticate(result['token'])
