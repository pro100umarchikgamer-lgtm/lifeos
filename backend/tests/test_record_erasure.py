"""Synthetic record purge, durability failures and real SQLite backup suppression."""
import hashlib
import json
import os
import socket
import struct
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from backend.service import Backend, Failure, canonical
from backend.record_recovery import RecordRecovery
from backend.record_erasure import RecordErasure, PROTOCOL, initialize, read_confirmed, resume_pending, acknowledge as real_acknowledge


class IndependentJournal:
    """Synthetic root transport: remote bytes are separate from every DB backup."""
    def __init__(self, path):
        self.path, self.remote, self.local = path, {}, {}
        self.offline = self.fail_ack = self.lose_ack = self.fail_before = False
        path.write_bytes(b''); path.chmod(0o600)

    def call(self, socket, action, record_id=None, erased_at=None):
        if self.offline: raise OSError('synthetic service offline')
        if action == 'acknowledge':
            if self.fail_before:raise OSError('synthetic crash before root append')
            self.local[record_id] = max(erased_at, self.local.get(record_id,0))
            self.write_local()
            if self.fail_ack: raise OSError('synthetic offsite failure')
        self.remote.update(self.local)
        self.local.update(self.remote)
        self.write_local()
        data = self.path.read_bytes()
        result = {'protocol':PROTOCOL,'acknowledged':True,'ledger_bytes':len(data),'ledger_sha256':hashlib.sha256(data).hexdigest()}
        if action == 'acknowledge':
            result.update(record_id=record_id,erased_at=self.remote[record_id])
            if self.lose_ack: raise OSError('synthetic lost acknowledgment')
        return result

    def write_local(self):
        self.path.write_bytes(b''.join((canonical({'record_id':rid,'erased_at':stamp})+'\n').encode() for rid,stamp in sorted(self.local.items())))


class RecordErasureTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.folder=Path(folder.name);self.now=1800000000;self.mail={}
        self.backend=self.make_backend(self.folder/'db.sqlite')
        self.backend.cipher=Fernet(Fernet.generate_key())
        self.password='Synthetic-valid-owner-passphrase-2026!'
        self.user=self.make_user('owner@example.test');self.other=self.make_user('other@example.test')
        self.wid=str(uuid.uuid4())
        self.backend.family(self.user,{'id':str(uuid.uuid4()),'action':'workspace.create','workspace_id':self.wid,'kind':'personal','name':'Local fixture'})
        self.journal=IndependentJournal(self.folder/'records.jsonl')
        p=patch('backend.record_erasure.acknowledge',self.journal.call);p.start();self.addCleanup(p.stop)
        initialize(self.backend,str(self.journal.path),'synthetic-root-socket',True)
        self.erasure=RecordErasure(self.backend)

    def make_backend(self,path):
        return Backend(path,deliver=lambda e,c:self.mail.update({e:c}),clock=lambda:self.now)

    def make_user(self,email):
        result=self.backend.register(email,self.password);actor=self.backend.authenticate(result['token'])
        self.backend.verify(actor,self.mail[email]);return self.backend.authenticate(result['token'])

    def put(self,kind='note',data=None):
        rid=str(uuid.uuid4());body=data if data is not None else {'body':'PRIVATE-CONTENT-ONLY-IN-SYNTHETIC-FIXTURE'}
        result=self.backend.batch(self.user,self.wid,[{'id':str(uuid.uuid4()),'action':'record.put','record_id':rid,'revision':0,'kind':kind,'visibility':'private','audience':[],'data':body}])['results'][0]
        self.assertEqual(result['status'],'accepted',result);return rid

    def deleted(self,rid):
        with self.backend.connect() as db:revision=db.execute('SELECT revision FROM records WHERE id=?',(rid,)).fetchone()['revision']
        result=self.backend.batch(self.user,self.wid,[{'id':str(uuid.uuid4()),'action':'record.delete','record_id':rid,'revision':revision}])['results'][0]
        self.assertEqual(result['status'],'accepted',result)

    def consent(self,rid):
        value=self.erasure.preview(self.user,rid)['record']
        return {'operation_id':str(uuid.uuid4()),'record_id':rid,'revision':value['revision'],'consent_hash':value['consent_hash']}

    def test_purge_removes_payload_keeps_tombstone_and_is_idempotent(self):
        rid=self.put();self.deleted(rid);body=self.consent(rid)
        accepted=self.erasure.purge(self.user,body)
        self.assertTrue(accepted['erased']);self.assertEqual(self.erasure.purge(self.user,body),accepted)
        with self.backend.connect() as db:
            self.assertIsNone(db.execute('SELECT * FROM notes WHERE id=?',(rid,)).fetchone())
            row=db.execute('SELECT * FROM records WHERE id=?',(rid,)).fetchone()
            self.assertEqual((row['deleted'],row['revision'],row['audience']),(1,body['revision']+1,'[]'))
            self.assertFalse(db.execute('SELECT 1 FROM record_erasure_intents WHERE record_id=?',(rid,)).fetchone())
        self.assertIn(rid,self.journal.remote)
        for line in self.journal.path.read_text().splitlines():
            self.assertEqual(set(json.loads(line)),{'record_id','erased_at'})
        self.assertNotIn('PRIVATE',self.journal.path.read_text())
        self.assertTrue(self.erasure.preview(self.user,rid)['erased'])

    def test_owner_verified_current_membership_deleted_revision_and_hash_are_required(self):
        active=self.put()
        with self.assertRaises(Failure):self.erasure.purge(self.user,{'operation_id':str(uuid.uuid4()),'record_id':active,'revision':1,'consent_hash':'a'*64})
        self.deleted(active);body=self.consent(active)
        for actor,changed in [(self.other,body),(dict(self.user,verified=0),body),
                              (self.user,dict(body,revision=body['revision']+1)),(self.user,dict(body,consent_hash='0'*64))]:
            with self.subTest(actor=actor['id'],changed=changed):
                with self.assertRaises(Failure):self.erasure.purge(actor,changed)
        with self.backend.transaction() as db:db.execute('UPDATE memberships SET active=0 WHERE workspace_id=? AND user_id=?',(self.wid,self.user['id']))
        with self.assertRaises(Failure):self.erasure.purge(self.user,body)
        self.assertNotIn(active,self.journal.remote)

    def test_failure_before_durable_ack_keeps_content_and_blocks_restore(self):
        rid=self.put();self.deleted(rid);body=self.consent(rid)
        self.journal.fail_ack=True
        with self.assertRaises(Failure) as denied:self.erasure.purge(self.user,body)
        self.assertEqual(denied.exception.code,'record_erasure_unavailable')
        self.assertNotIn(rid,self.journal.remote)
        with self.backend.connect() as db:
            self.assertIsNotNone(db.execute('SELECT body FROM notes WHERE id=?',(rid,)).fetchone())
            self.assertIsNotNone(db.execute('SELECT 1 FROM record_erasure_intents WHERE record_id=?',(rid,)).fetchone())
        with self.assertRaises(Failure) as denied:RecordRecovery(self.backend).request(self.user,{k:body[k] for k in ('record_id','revision','consent_hash')})
        self.assertEqual(denied.exception.code,'record_erasure_pending')
        self.journal.offline=True
        preview=self.erasure.preview(self.user,rid)
        self.assertFalse(preview['permanent_delete_available']);self.assertEqual(preview['pending_operation_id'],body['operation_id'])
        self.journal.fail_ack=self.journal.offline=False
        self.assertTrue(self.erasure.purge(self.user,body)['erased'])

    def test_lost_ack_replays_exact_operation_without_second_payload_mutation(self):
        rid=self.put();self.deleted(rid);body=self.consent(rid);self.journal.lose_ack=True
        with self.assertRaises(Failure):self.erasure.purge(self.user,body)
        self.assertIn(rid,self.journal.remote)
        with self.backend.connect() as db:self.assertTrue(db.execute('SELECT 1 FROM notes WHERE id=?',(rid,)).fetchone())
        self.journal.lose_ack=False
        first=self.erasure.purge(self.user,body);second=self.erasure.purge(self.user,body)
        self.assertEqual(first,second)

    def test_worker_resumes_consented_intent_after_crash_before_first_root_append(self):
        rid=self.put();self.deleted(rid);body=self.consent(rid);self.journal.fail_before=True
        with self.assertRaises(Failure):self.erasure.purge(self.user,body)
        self.assertNotIn(rid,self.journal.local)
        self.journal.fail_before=False
        self.assertTrue(resume_pending(self.backend))
        self.assertFalse(resume_pending(self.backend))
        self.assertTrue(self.erasure.purge(self.user,body)['erased'])

    def test_pending_purge_operation_uuid_is_reserved_across_record_and_family_actions(self):
        rid=self.put();self.deleted(rid);body=self.consent(rid);self.journal.fail_ack=True
        with self.assertRaises(Failure):self.erasure.purge(self.user,body)
        second=str(uuid.uuid4())
        put={'id':body['operation_id'],'action':'record.put','record_id':second,'revision':0,'kind':'note','visibility':'private','audience':[],'data':{'body':'Unrelated active record'}}
        self.assertEqual(self.backend.batch(self.user,self.wid,[put])['results'][0].get('error'),'operation_conflict')
        with self.assertRaises(Failure) as denied:
            self.backend.family(self.user,{'id':body['operation_id'],'action':'workspace.create','workspace_id':str(uuid.uuid4()),'kind':'personal','name':'Unrelated workspace'})
        self.assertEqual(denied.exception.code,'operation_conflict')
        self.journal.fail_ack=False
        initialize(self.backend,str(self.journal.path),'synthetic-root-socket',True)
        self.assertTrue(self.erasure.purge(self.user,body)['erased'])

    def test_offline_grantee_epoch_changes_after_missed_soft_delete_and_purge(self):
        self.wid=str(uuid.uuid4())
        self.backend.family(self.user,{'id':str(uuid.uuid4()),'action':'workspace.create','workspace_id':self.wid,'kind':'family','name':'Shared fixture'})
        invite=self.backend.family(self.user,{'id':str(uuid.uuid4()),'action':'invite.create','workspace_id':self.wid,'email':self.other['email'],'role':'adult','profile_id':None})
        self.backend.accept(self.other,{'id':str(uuid.uuid4()),'invitation':invite['invitation']})
        rid=self.put()
        grant={'id':str(uuid.uuid4()),'action':'record.grant','record_id':rid,'revision':1,'user_id':self.other['id'],'can_edit':False,'revoke':False}
        self.assertEqual(self.backend.batch(self.user,self.wid,[grant])['results'][0]['status'],'accepted')
        before=self.backend.pull_incremental(self.other,self.wid,0)
        self.assertTrue(any(r['id']==rid and r['data'] for r in before['records']))
        self.deleted(rid);self.erasure.purge(self.user,self.consent(rid))
        after=self.backend.pull_incremental(self.other,self.wid,before['cursor'],before['epoch'])
        self.assertTrue(after['reset'])
        self.assertNotEqual(after['epoch'],before['epoch'])
        self.assertFalse(any(r['id']==rid for r in after['records']))

    def test_retained_soft_deleted_financial_reference_blocks_account_purge(self):
        account=self.put('account',{'name':'Private account','currency':'USD','opening_minor':0})
        transaction=self.put('transaction',{'kind':'expense','amount_minor':100,'currency':'USD','date':'2026-11-15','label':'Private expense','account_id':account})
        self.deleted(transaction);self.deleted(account)
        with self.assertRaises(Failure) as denied:self.erasure.purge(self.user,self.consent(account))
        self.assertEqual(denied.exception.code,'record_erasure_linked')
        self.assertNotIn(account,self.journal.remote)
        self.erasure.purge(self.user,self.consent(transaction))
        self.assertTrue(self.erasure.purge(self.user,self.consent(account))['erased'])

    def test_real_old_sqlite_backup_cannot_resurrect_confirmed_payload(self):
        if not hasattr(self.backend,'path'):self.skipTest('Physical SQLite backup; separate SQL rollback test also covers PostgreSQL')
        rid=self.put();backup=self.folder/'old-backup.sqlite'
        with self.backend.connect() as source:
            import sqlite3
            with sqlite3.connect(backup) as target:source.backup(target)
        self.deleted(rid);self.erasure.purge(self.user,self.consent(rid))
        restored=Backend(self.folder/'restored.sqlite',deliver=lambda *_:None,clock=lambda:self.now)
        with restored.connect() as target:
            import sqlite3
            with sqlite3.connect(backup) as source:source.backup(target)
        with restored.connect() as db:
            self.assertEqual(db.execute('SELECT deleted FROM records WHERE id=?',(rid,)).fetchone()['deleted'],0)
            self.assertIsNotNone(db.execute('SELECT body FROM notes WHERE id=?',(rid,)).fetchone())
        initialize(restored,str(self.journal.path),'synthetic-root-socket',True)
        with restored.connect() as db:
            self.assertIsNone(db.execute('SELECT body FROM notes WHERE id=?',(rid,)).fetchone())
            self.assertEqual(db.execute('SELECT deleted FROM records WHERE id=?',(rid,)).fetchone()['deleted'],1)
        op={'id':str(uuid.uuid4()),'action':'record.put','record_id':rid,'revision':0,'kind':'note','visibility':'private','audience':[],'data':{'body':'MUST NOT RETURN'}}
        result=restored.batch(self.user,self.wid,[op])['results'][0]
        self.assertEqual(result['error'],'record_erased')

    def test_sql_restored_payload_and_pre_creation_snapshot_are_suppressed(self):
        rid=self.put();self.deleted(rid);self.erasure.purge(self.user,self.consent(rid))
        with self.backend.transaction() as db:
            db.execute('DELETE FROM record_erasure_ledger WHERE record_id=?',(rid,))
            db.execute('UPDATE records SET deleted=0,revision=1 WHERE id=?',(rid,))
            db.execute('INSERT INTO notes VALUES(?,?)',(rid,'RESTORED PRIVATE BODY'))
        initialize(self.backend,str(self.journal.path),'synthetic-root-socket',True)
        absent=str(uuid.uuid4());self.journal.remote[absent]=self.now
        initialize(self.backend,str(self.journal.path),'synthetic-root-socket',True)
        with self.backend.connect() as db:self.assertIsNone(db.execute('SELECT 1 FROM notes WHERE id=?',(rid,)).fetchone())
        op={'id':str(uuid.uuid4()),'action':'record.put','record_id':absent,'revision':0,'kind':'note','visibility':'private','audience':[],'data':{'body':'MUST NOT RETURN'}}
        self.assertEqual(self.backend.batch(self.user,self.wid,[op])['results'][0]['error'],'record_erased')

    def test_unavailable_configuration_and_rewound_truth_fail_closed(self):
        rid=self.put();self.deleted(rid);self.erasure.purge(self.user,self.consent(rid))
        with self.assertRaises(RuntimeError):initialize(self.backend)
        self.journal.local.clear();self.journal.remote.clear();self.journal.write_local()
        with self.assertRaises(RuntimeError):initialize(self.backend,str(self.journal.path),'synthetic-root-socket',True)
        self.journal.offline=True
        self.assertFalse(RecordRecovery(self.backend).trash(self.user,self.wid)['permanent_delete_available'])

    def test_account_ledger_cannot_be_read_as_record_journal_and_hash_mismatch_rejects(self):
        data=(canonical({'user_id':self.user['id'],'erased_at':self.now})+'\n').encode()
        self.journal.path.write_bytes(data)
        proof={'ledger_bytes':len(data),'ledger_sha256':hashlib.sha256(data).hexdigest()}
        with self.assertRaises(RuntimeError):read_confirmed(str(self.journal.path),proof)
        self.journal.path.write_bytes(b'')
        with self.assertRaises(RuntimeError):read_confirmed(str(self.journal.path),{'ledger_bytes':0,'ledger_sha256':'0'*64})


DSN=os.environ.get('LIFEOS_TEST_DATABASE_URL','')
@unittest.skipUnless(DSN,'Requires isolated lifeos_test PostgreSQL')
class PostgresRecordErasureTests(RecordErasureTests):
    def make_backend(self,path):
        if urlsplit(DSN).path!='/lifeos_test':raise RuntimeError('Record tests refuse a non-test database')
        import psycopg
        from psycopg import sql
        from backend.postgres import PostgresBackend
        schema='record_erasure_'+uuid.uuid4().hex
        with psycopg.connect(DSN,autocommit=True) as db:db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        def cleanup():
            with psycopg.connect(DSN,autocommit=True) as db:db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
        self.addCleanup(cleanup)
        backend=PostgresBackend(DSN,Fernet(Fernet.generate_key()),schema=schema,migrate=True,clock=lambda:self.now)
        self.addCleanup(backend.close)
        backend._deliver=lambda db,email,code,purpose:self.mail.update({email:code})
        return backend


class RecordACKProtocolTests(unittest.TestCase):
    def transport(self,response,uid=0):
        class Client:
            sent=False
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def settimeout(self,_):pass
            def connect(self,_):pass
            def getsockopt(self,*_):return struct.pack('3i',123,uid,0)
            def sendall(self,_):self.sent=True
            def recv(self,_):return response
        return Client()

    def test_nonroot_peer_rejected_before_any_uuid_is_sent(self):
        client=self.transport(b'{}\n',uid=10001)
        with patch('backend.record_erasure.socket.socket',return_value=client):
            with self.assertRaises(RuntimeError):real_acknowledge('/synthetic/socket','acknowledge',str(uuid.uuid4()),1)
        self.assertFalse(client.sent)

    def test_only_exact_record_protocol_and_specific_ack_are_accepted(self):
        rid=str(uuid.uuid4())
        value={'protocol':PROTOCOL,'acknowledged':True,'ledger_bytes':0,'ledger_sha256':hashlib.sha256(b'').hexdigest(),'record_id':rid,'erased_at':1}
        for changes in ({'protocol':'uladim-erasure-ack-v1'},{'record_id':str(uuid.uuid4())},{'erased_at':0},{'ledger_bytes':True},{'extra':'untrusted'}):
            data=(json.dumps(dict(value,**changes))+'\n').encode()
            with self.subTest(changes=changes),patch('backend.record_erasure.socket.socket',return_value=self.transport(data)):
                with self.assertRaises(RuntimeError):real_acknowledge('/synthetic/socket','acknowledge',rid,1)
        for raw in ((json.dumps(value)[:-1]+',"acknowledged":true}\n').encode(),json.dumps(value).encode()+b'\n{}\n'):
            with patch('backend.record_erasure.socket.socket',return_value=self.transport(raw)):
                with self.assertRaises((ValueError,RuntimeError)):real_acknowledge('/synthetic/socket','acknowledge',rid,1)
        with patch('backend.record_erasure.socket.socket',return_value=self.transport((json.dumps(value)+'\n').encode())):
            self.assertEqual(real_acknowledge('/synthetic/socket','acknowledge',rid,1),value)
