"""Bounded privacy-review fixes on synthetic SQLite and isolated PostgreSQL."""
import json
import tempfile
import unittest
from pathlib import Path

from backend.account_erasure import initialize, prune_ephemeral, read_ledger
from backend.control import Control, StaffPrincipal
from backend.service import Failure
from backend.tests import test_account_privacy as privacy_tests

DSN, PASSWORD, uid = privacy_tests.DSN, privacy_tests.PASSWORD, privacy_tests.uid


class FollowupScenarios:
    fixtures=privacy_tests.PrivacyScenarios.fixtures
    user=privacy_tests.PrivacyScenarios.user
    family=privacy_tests.PrivacyScenarios.family
    put=privacy_tests.PrivacyScenarios.put
    erase=privacy_tests.PrivacyScenarios.erase

    def test_failed_ack_reuses_one_durable_intent_across_retries(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        path=Path(folder.name)/'ledger';path.touch(mode=0o600)
        initialize(self.backend,str(path))
        self.backend.erasure_ack_socket=str(Path(folder.name)/'missing.sock')
        self.lifecycle.request_deletion(self.owner,PASSWORD,'DELETE');self.now+=86401
        self.assertTrue(self.lifecycle.process_one_deletion())
        original=path.read_bytes();intent=read_ledger(path)[self.owner['id']]
        for _ in range(8):
            self.now+=2
            self.assertTrue(self.lifecycle.process_one_deletion())
        self.assertEqual(path.read_bytes(),original)
        self.assertEqual(len(original.splitlines()),1)
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM deletion_jobs WHERE user_id=?',(self.owner['id'],)).fetchone()['state'],'erasing')
            self.assertIsNone(db.execute('SELECT erased_at FROM account_erasure_ledger WHERE user_id=?',(self.owner['id'],)).fetchone())
        self.backend.erasure_ack_socket=''
        self.assertTrue(self.lifecycle.process_one_deletion())
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT erased_at FROM account_erasure_ledger WHERE user_id=?',(self.owner['id'],)).fetchone()['erased_at'],intent)
        self.assertEqual(path.read_bytes(),original)

    def test_flag_rationale_is_encrypted_then_consumed_and_expired_proposals_purged(self):
        control=Control(self.backend);actor=StaffPrincipal(uid(),self.owner['id'],('owner',))
        reason='Sensitive health rationale '+self.owner['email']+' phone +1 234 567 8901'
        proposal=control.preview_flag(actor,'compact_onboarding',True,50,0,reason)
        with self.backend.connect() as db:
            row=db.execute('SELECT body FROM flag_proposals WHERE id=?',(proposal['proposal_id'],)).fetchone()
            self.assertNotIn('Sensitive health',row['body']);self.assertNotIn(self.owner['email'],row['body'])
            stored=json.loads(row['body']);self.assertNotIn('reason',stored)
            opened=self.backend.cipher.decrypt(stored['reason_encrypted'].encode()).decode()
            self.assertIn('Sensitive health',opened);self.assertNotIn(self.owner['email'],opened)
        control.commit_flag(actor,proposal['proposal_id'],proposal['digest'])
        with self.backend.connect() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM flag_proposals WHERE id=?',(proposal['proposal_id'],)).fetchone())
        with self.assertRaises(Failure):control.commit_flag(actor,proposal['proposal_id'],proposal['digest'])
        expired=control.preview_flag(actor,'chart_styles',False,0,0,'Short pending reason')
        used=uid()
        with self.backend.transaction() as db:
            db.execute('INSERT INTO flag_proposals VALUES(?,?,?,?,?,?)',(used,actor.id,'{"reason":"legacy used plaintext"}','digest',self.now+5000,self.now))
        self.now+=601
        fresh=control.preview_flag(actor,'support_entry',True,100,0,'Fresh reason')
        prune_ephemeral(self.backend)
        with self.backend.connect() as db:
            for pid in (expired['proposal_id'],used):self.assertIsNone(db.execute('SELECT 1 FROM flag_proposals WHERE id=?',(pid,)).fetchone())
            self.assertIsNotNone(db.execute('SELECT 1 FROM flag_proposals WHERE id=?',(fresh['proposal_id'],)).fetchone())

    def test_erased_inactive_staff_proposals_are_removed_without_touching_peer(self):
        staff=uid();peer_staff=uid();own=uid();other=uid()
        with self.backend.transaction() as db:
            for sid,person in ((staff,self.owner),(peer_staff,self.peer)):
                db.execute('INSERT INTO staff(id,user_id,roles,mfa_secret,active,created_at) VALUES(?,?,?,?,0,?)',(sid,person['id'],'["support"]',b'',self.now))
            for pid,sid in ((own,staff),(other,peer_staff)):
                db.execute('INSERT INTO flag_proposals VALUES(?,?,?,?,?,0)',(pid,sid,'{"reason":"legacy personal text"}','digest',self.now+100000))
        self.erase(self.owner)
        with self.backend.connect() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM flag_proposals WHERE id=?',(own,)).fetchone())
            self.assertIsNotNone(db.execute('SELECT 1 FROM flag_proposals WHERE id=?',(other,)).fetchone())

    def test_all_erased_owner_tombstones_read_only_and_cached_peer_put_rejected(self):
        wid=self.family()
        rid=self.put(self.owner,wid,'note',{'body':'Owner original data'})
        peer_rid=self.put(self.peer,wid,'note',{'body':'Peer data survives'})
        old={'id':uid(),'action':'record.put','record_id':rid,'revision':1,'kind':'note','visibility':'shared','audience':[],'data':{'body':'Old cached owner content with peer edit'}}
        self.assertEqual(self.backend.batch(self.peer,wid,[old])['results'][0]['status'],'accepted')
        self.erase(self.owner)
        row=next(r for r in self.backend.pull(self.peer,wid,0)['records'] if r['id']==rid)
        self.assertTrue(row['privacy_erased']);self.assertTrue(row['deleted']);self.assertFalse(row['editable']);self.assertEqual(row['data'],{})
        for op in (old,dict(old,id=uid(),revision=row['revision']),*[
            {'id':uid(),'action':action,'record_id':rid,'revision':row['revision'],'user_id':self.peer['id'],'can_edit':True,'revoke':False}
            for action in ('record.delete','record.grant','record.restore')
        ]):
            result=self.backend.batch(self.peer,wid,[op])['results'][0]
            self.assertEqual(result['status'],'rejected')
            self.assertEqual(result['error'],'not_found' if op['action']=='record.restore' else 'record_forbidden')
        with self.backend.connect() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM notes WHERE id=?',(rid,)).fetchone())
            self.assertEqual(db.execute('SELECT body FROM notes WHERE id=?',(peer_rid,)).fetchone()['body'],'Peer data survives')


class PrivacyFollowupSQLiteTests(FollowupScenarios,unittest.TestCase):
    setUp=privacy_tests.AccountPrivacySQLiteTests.setUp


@unittest.skipUnless(DSN,'Requires isolated lifeos_test database')
class PrivacyFollowupPostgresTests(FollowupScenarios,unittest.TestCase):
    setUp=privacy_tests.AccountPrivacyPostgresTests.setUp
