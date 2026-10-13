"""Loopback-only disposable server for two actual SQLCipher Android clients."""
import contextlib
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import signal
import tempfile
from urllib.parse import urlsplit
import uuid

from backend.service import Backend
from backend.http_server import handler


def main():
    with contextlib.ExitStack() as stack:
        folder=stack.enter_context(tempfile.TemporaryDirectory(prefix='lifeos-family-ci-'))
        mailbox={};dsn=os.environ.get('LIFEOS_TEST_DATABASE_URL','')
        if dsn:
            import psycopg
            from psycopg import sql
            from cryptography.fernet import Fernet
            from backend.postgres import PostgresBackend
            if urlsplit(dsn).path!='/lifeos_test':raise RuntimeError('Refusing non-test database')
            schema='android_'+uuid.uuid4().hex
            with psycopg.connect(dsn,autocommit=True) as db:db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
            def cleanup():
                with psycopg.connect(dsn,autocommit=True) as db:db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
            stack.callback(cleanup)
            backend=PostgresBackend(dsn,Fernet(Fernet.generate_key()),schema=schema,migrate=True)
            stack.callback(backend.close)
            deliver=backend._deliver
            def capture(db,email,code,purpose):deliver(db,email,code,purpose);mailbox[email]=code
            backend._deliver=capture
        else:backend=Backend(Path(folder)/'server.db',deliver=lambda e,c:mailbox.update({e:c}))
        actors=[]
        for email in ('android-one@example.test','android-two@example.test'):
            result=backend.register(email,'isolated-integration-test-password')
            actor=backend.authenticate(result['token']);backend.verify(actor,mailbox[email])
            actors.append(backend.authenticate(result['token']))
        workspace=str(uuid.uuid4())
        backend.family(actors[0],{'id':str(uuid.uuid4()),'workspace_id':workspace,'action':'workspace.create','name':'Disposable integration family','kind':'family'})
        invite=backend.family(actors[0],{'id':str(uuid.uuid4()),'workspace_id':workspace,'action':'invite.create','email':actors[1]['email'],'role':'parent','profile_id':None})
        backend.accept(actors[1],{'id':str(uuid.uuid4()),'invitation':invite['invitation']})
        if dsn:
            from wsgiref.simple_server import make_server,WSGIRequestHandler
            from backend.production import Application
            from backend.config import Settings
            class QuietHandler(WSGIRequestHandler):
                def log_message(self,*args):pass
            settings=Settings.load({'DATABASE_URL':dsn,'EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),
                'RATE_LIMIT_KEY':'synthetic-only-test-key-123456789012345','SMTP_HOST':'127.0.0.1',
                'SMTP_TLS':'none','EMAIL_FROM':'test@example.test','REQUIRE_HTTPS':'false'})
            server=make_server('127.0.0.1',8787,Application(backend,settings),handler_class=QuietHandler)
            print('Disposable Android backend: production WSGI + PostgreSQL, loopback only',flush=True)
        else:server=ThreadingHTTPServer(('127.0.0.1',8787),handler(backend))
        stack.callback(server.server_close)
        def stop(*args):raise SystemExit(0)
        signal.signal(signal.SIGTERM,stop)
        server.serve_forever()

if __name__=='__main__':main()
