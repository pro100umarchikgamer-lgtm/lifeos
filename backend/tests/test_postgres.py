"""Run the same authorization/recovery suite against a real, disposable PostgreSQL DB."""
import io
import os
import threading
import unittest
import uuid
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
import psycopg
from psycopg import sql
from cryptography.fernet import Fernet
import test_family_backend as fixtures
from test_account_sessions import SessionScenarios
from backend.postgres import PostgresBackend
from backend.mail import deliver_one
from backend.production import Application
from backend.config import Settings
from backend.import_sqlite import import_server
from backend.service import Backend,Failure

DSN=os.environ.get('LIFEOS_TEST_DATABASE_URL','')

@unittest.skipUnless(DSN,'Requires isolated lifeos_test PostgreSQL database')
class PostgresTests(SessionScenarios,fixtures.FamilyBackendTests):
    def setUp(self):
        if urlsplit(DSN).path!='/lifeos_test':raise RuntimeError('Tests refuse a non-test database')
        self.schema='test_'+uuid.uuid4().hex
        with psycopg.connect(DSN,autocommit=True) as db:
            db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.addCleanup(self.drop_schema)
        self.mail={};self.cipher=Fernet(Fernet.generate_key())
        self.backend=PostgresBackend(DSN,self.cipher,schema=self.schema,migrate=True)
        self.addCleanup(self.backend.close)
        deliver=self.backend._deliver
        def capture(db,email,code,purpose):
            deliver(db,email,code,purpose)
            self.mail[email]=code
        self.backend._deliver=capture
        self.p1=self.user('one@example.test');self.p2=self.user('two@example.test');self.child=self.user('child@example.test')
        self.wid=fixtures.uid();self.backend.family(self.p1,self.op('workspace.create',kind='family',name='Family'))
        invite=self.backend.family(self.p1,self.op('invite.create',email=self.p2['email'],role='parent',profile_id=None))
        self.backend.accept(self.p2,{'id':fixtures.uid(),'invitation':invite['invitation']})
    def drop_schema(self):
        with psycopg.connect(DSN,autocommit=True) as db:
            db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
    def settings(self):
        return Settings.load({'DATABASE_URL':DSN,'EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),
            'RATE_LIMIT_KEY':'synthetic-test-only-key-123456789012345','SMTP_HOST':'127.0.0.1',
            'SMTP_TLS':'none','EMAIL_FROM':'LifeOS <test@example.test>'})
    def test_application_database_role_has_no_admin_privileges(self):
        with self.backend.connect() as db:
            row=db.execute('SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user').fetchone()
            self.assertEqual(list(row.values()),[False,False,False])
    def test_server_import_preserves_uuid_history_and_refuses_overwrite(self):
        target_schema='import_'+uuid.uuid4().hex
        with psycopg.connect(DSN,autocommit=True) as db:db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(target_schema)))
        target=PostgresBackend(DSN,self.cipher,schema=target_schema,migrate=True)
        try:
            with tempfile.TemporaryDirectory() as folder:
                source=Path(folder)/'old.db';mail={}
                old=Backend(source,deliver=lambda email,code:mail.update({email:code}))
                result=old.register('migration@example.test','a-valid-long-passphrase')
                actor=old.authenticate(result['token']);old.verify(actor,mail[actor['email']]);actor=old.authenticate(result['token'])
                wid=fixtures.uid();old.family(actor,{'id':fixtures.uid(),'workspace_id':wid,'action':'workspace.create','name':'Preserved','kind':'personal'})
                operation={'id':fixtures.uid(),'record_id':fixtures.uid(),'action':'record.put','revision':0,'kind':'account','visibility':'private','audience':[],
                    'data':{'name':'History','currency':'RUB','opening_minor':999999999999998}}
                self.assertEqual(old.batch(actor,wid,[operation])['results'][0]['status'],'accepted')
                # Historical SQL storage can contain the full signed 64-bit range.
                # Import must preserve it without reinterpreting an old operation receipt.
                with old.connect() as db:db.execute('UPDATE accounts SET opening_minor=? WHERE id=?',(9223372036854775806,operation['record_id']))
                preview=import_server(target,source);self.assertEqual(preview['users'],1)
                self.assertEqual(import_server(target,source,True),preview)
                imported=target.authenticate(result['token']);self.assertEqual(imported['id'],actor['id'])
                row=target.pull(imported,wid,0)['records'][0]
                self.assertEqual(row['id'],operation['record_id']);self.assertEqual(row['data']['opening_minor'],9223372036854775806)
                self.assertEqual(target.batch(imported,wid,[operation]),old.batch(actor,wid,[operation]))
                with self.assertRaises(Failure):import_server(target,source,True)
        finally:
            target.close()
            with psycopg.connect(DSN,autocommit=True) as db:db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(target_schema)))
    def test_mail_queue_encrypted_retry_and_restart(self):
        with self.backend.connect() as db:
            row=db.execute('SELECT * FROM email_jobs ORDER BY id LIMIT 1').fetchone()
            self.assertNotIn(b'example.test',bytes(row['payload']))
        def failure(*args):raise OSError('provider secret must not be stored')
        self.assertTrue(deliver_one(self.backend,self.settings(),failure))
        with self.backend.connect() as db:
            failed=db.execute('SELECT * FROM email_jobs WHERE attempts=1').fetchone()
            self.assertEqual(failed['last_error'],'OSError')
            db.execute('UPDATE email_jobs SET next_attempt=0 WHERE id=?',(failed['id'],))
        recovered=PostgresBackend(DSN,self.cipher,schema=self.schema)
        try:
            sent=[]
            self.assertTrue(deliver_one(recovered,self.settings(),lambda settings,message:sent.append(message)))
            self.assertEqual(len(sent),1)
            with recovered.connect() as db:
                self.assertEqual(db.execute('SELECT payload FROM email_jobs WHERE id=?',(failed['id'],)).fetchone()['payload'],b'')
        finally:recovered.close()
    def test_parallel_writers_and_migration_integrity(self):
        errors=[]
        def put(i):
            try:self.put(self.p1,'note',{'body':str(i)})
            except Exception as error:errors.append(error)
        threads=[threading.Thread(target=put,args=(i,)) for i in range(6)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(20)
        self.assertFalse(any(thread.is_alive() for thread in threads));self.assertEqual(errors,[])
        response=self.backend.pull(self.p2,self.wid,0)
        self.assertEqual(len(response['records']),6)
        self.backend.migrate()
        with self.backend.connect() as db:db.execute("UPDATE schema_migrations SET digest='tampered' WHERE version='001_core.sql'")
        with self.assertRaises(RuntimeError):self.backend.migrate()
    def test_https_proxy_rate_limits_and_health(self):
        app=Application(self.backend,self.settings())
        def request(path,remote='172.30.30.2',forwarded='https'):
            result=[]
            app({'REQUEST_METHOD':'GET','PATH_INFO':path,'REMOTE_ADDR':remote,
                'HTTP_X_FORWARDED_PROTO':forwarded,'HTTP_X_FORWARDED_FOR':'198.51.100.8',
                'HTTP_AUTHORIZATION':'Bearer '+self.p1['token'],'wsgi.input':io.BytesIO()},
                lambda status,headers:result.append(status))
            return int(result[0].split()[0])
        self.assertEqual(request('/health/ready','127.0.0.1','http'),200)
        self.assertEqual(request('/v1/me','198.51.100.4'),426)
        self.assertEqual(request('/v1/me'),200)
        for i in range(240):last=request('/v1/me')
        self.assertEqual(last,429)

    def test_concurrent_http_clients_share_rate_counter_without_failures(self):
        app=Application(self.backend,self.settings());statuses=[]
        def request():
            app({'REQUEST_METHOD':'GET','PATH_INFO':'/v1/me','REMOTE_ADDR':'172.30.30.2',
                'HTTP_X_FORWARDED_PROTO':'https','HTTP_X_FORWARDED_FOR':'198.51.100.9',
                'HTTP_AUTHORIZATION':'Bearer '+self.p1['token'],'wsgi.input':io.BytesIO()},
                lambda status,headers:statuses.append(int(status.split()[0])))
        threads=[threading.Thread(target=request) for i in range(12)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(15)
        self.assertEqual(statuses,[200]*12)
