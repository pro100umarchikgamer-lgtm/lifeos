"""Run the actual Dart sync transport/engine against the isolated Python backend."""
import argparse,json,subprocess,tempfile,threading,uuid
from pathlib import Path
from http.server import ThreadingHTTPServer
from backend.service import Backend
from backend.http_server import handler

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--dart',default='dart');args=parser.parse_args()
    with tempfile.TemporaryDirectory() as folder:
        mail={};backend=Backend(Path(folder)/'server.db',deliver=lambda e,c:mail.update({e:c}))
        actors=[]
        for email in ['one@example.test','two@example.test']:
            result=backend.register(email,'a-valid-long-passphrase');actor=backend.authenticate(result['token']);backend.verify(actor,mail[email]);actors.append((backend.authenticate(result['token']),result['token']))
        wid=str(uuid.uuid4());backend.family(actors[0][0],{'id':str(uuid.uuid4()),'workspace_id':wid,'action':'workspace.create','name':'Dart integration','kind':'family'})
        invite=backend.family(actors[0][0],{'id':str(uuid.uuid4()),'workspace_id':wid,'action':'invite.create','email':actors[1][0]['email'],'role':'parent','profile_id':None})
        backend.accept(actors[1][0],{'id':str(uuid.uuid4()),'invitation':invite['invitation']})
        server=ThreadingHTTPServer(('127.0.0.1',0),handler(backend));server.daemon_threads=True;thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            config={'endpoint':f'http://127.0.0.1:{server.server_port}','one':actors[0][1],'two':actors[1][1],'workspace':wid}
            packages=Path(folder)/'package_config.json'
            packages.write_text(json.dumps({'configVersion':2,'packages':[{'name':'lifeos','rootUri':Path(__file__).resolve().parents[1].as_uri()+'/', 'packageUri':'lib/','languageVersion':'3.4'}]}))
            result=subprocess.run([args.dart,'--packages='+str(packages),'tool/check_sync_protocol.dart'],input=json.dumps(config),text=True,timeout=60,capture_output=True)
            print(result.stdout,end='');print(result.stderr,end='');raise SystemExit(result.returncode)
        finally:server.shutdown();server.server_close();thread.join(timeout=5)
if __name__=='__main__':main()
