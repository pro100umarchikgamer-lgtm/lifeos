"""Run the actual Dart sync transport/engine against the isolated Python backend."""
import argparse,contextlib,json,os,subprocess,tempfile,threading,uuid
from pathlib import Path
from http.server import ThreadingHTTPServer
from backend.service import Backend
from backend.http_server import handler

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--dart',default='dart');parser.add_argument('--postgres',action='store_true');args=parser.parse_args()
    with contextlib.ExitStack() as stack:
        folder=stack.enter_context(tempfile.TemporaryDirectory());mail={}
        if args.postgres:
            import psycopg
            from psycopg import sql
            from urllib.parse import urlsplit
            from cryptography.fernet import Fernet
            from backend.postgres import PostgresBackend
            dsn=os.environ['LIFEOS_TEST_DATABASE_URL']
            if urlsplit(dsn).path!='/lifeos_test':raise RuntimeError('Requires isolated test database')
            schema='dart_'+uuid.uuid4().hex
            with psycopg.connect(dsn,autocommit=True) as db:db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
            def cleanup():
                with psycopg.connect(dsn,autocommit=True) as db:db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
            stack.callback(cleanup)
            backend=PostgresBackend(dsn,Fernet(Fernet.generate_key()),schema=schema,migrate=True)
            stack.callback(backend.close)
            deliver=backend._deliver
            def capture(db,email,code,purpose):deliver(db,email,code,purpose);mail[email]=code
            backend._deliver=capture
        else:backend=Backend(Path(folder)/'server.db',deliver=lambda e,c:mail.update({e:c}))
        actors=[]
        for email in ['one@example.test','two@example.test']:
            result=backend.register(email,'a-valid-long-passphrase');actor=backend.authenticate(result['token']);backend.verify(actor,mail[email]);actors.append((backend.authenticate(result['token']),result['token']))
        wid=str(uuid.uuid4());backend.family(actors[0][0],{'id':str(uuid.uuid4()),'workspace_id':wid,'action':'workspace.create','name':'Dart integration','kind':'family'})
        invite=backend.family(actors[0][0],{'id':str(uuid.uuid4()),'workspace_id':wid,'action':'invite.create','email':actors[1][0]['email'],'role':'parent','profile_id':None})
        backend.accept(actors[1][0],{'id':str(uuid.uuid4()),'invitation':invite['invitation']})
        if args.postgres:
            from wsgiref.simple_server import make_server,WSGIRequestHandler
            from backend.production import Application
            from backend.config import Settings
            class QuietHandler(WSGIRequestHandler):
                def log_message(self,*args):pass
            settings=Settings.load({'DATABASE_URL':dsn,'EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),
                'RATE_LIMIT_KEY':'synthetic-only-test-key-123456789012345','SMTP_HOST':'127.0.0.1',
                'SMTP_TLS':'none','EMAIL_FROM':'test@example.test','REQUIRE_HTTPS':'false'})
            server=make_server('127.0.0.1',0,Application(backend,settings),handler_class=QuietHandler)
        else:server=ThreadingHTTPServer(('127.0.0.1',0),handler(backend));server.daemon_threads=True
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            config={'endpoint':f'http://127.0.0.1:{server.server_port}','one':actors[0][1],'two':actors[1][1],'workspace':wid}
            packages=Path(folder)/'package_config.json'
            packages.write_text(json.dumps({'configVersion':2,'packages':[{'name':'lifeos','rootUri':Path(__file__).resolve().parents[1].as_uri()+'/', 'packageUri':'lib/','languageVersion':'3.4'}]}))
            result=subprocess.run([args.dart,'--packages='+str(packages),'tool/check_sync_protocol.dart'],input=json.dumps(config),text=True,timeout=60,capture_output=True)
            print(result.stdout,end='');print(result.stderr,end='');raise SystemExit(result.returncode)
        finally:server.shutdown();server.server_close();thread.join(timeout=5)
if __name__=='__main__':main()
