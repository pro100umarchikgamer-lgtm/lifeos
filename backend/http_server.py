"""Isolated development HTTP API. Public deployments require TLS and a real verification delivery adapter."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import urllib.parse
from .service import Backend, Failure

MAX_BODY=2*1024*1024

def dispatch(backend,method,path,body,auth):
    split=urllib.parse.urlsplit(path);route=split.path;query=urllib.parse.parse_qs(split.query)
    if route=='/v1/auth/register' and method=='POST':result=backend.register(body.get('email'),body.get('password'))
    elif route=='/v1/auth/recovery' and method=='POST':result=backend.recover(body.get('email'))
    elif route=='/v1/auth/reset' and method=='POST':result=backend.reset_password(body.get('email'),body.get('code'),body.get('password'))
    elif route=='/v1/auth/login' and method=='POST':result=backend.login(body.get('email'),body.get('password'))
    else:
        token=auth[7:] if auth.startswith('Bearer ') else '';actor=backend.authenticate(token)
        if route=='/v1/auth/verify' and method=='POST':result=backend.verify(actor,body.get('code'))
        elif route=='/v1/auth/password' and method=='POST':result=backend.password(actor,body.get('old_password'),body.get('new_password'))
        elif route=='/v1/auth/logout' and method=='POST':result=backend.logout(token)
        elif route=='/v1/me' and method=='GET':result={'user_id':actor['id'],'email':actor['email'],'verified':bool(actor['verified'])}
        elif route=='/v1/spaces' and method=='GET':result={'spaces':backend.spaces(actor)}
        elif route=='/v1/family' and method=='POST':result=backend.family(actor,body)
        elif route=='/v1/invitations/accept' and method=='POST':result=backend.accept(actor,body)
        elif route=='/v1/roster' and method=='GET':result=backend.roster(actor,query['workspace'][0])
        elif route=='/v1/sync/push' and method=='POST':result=backend.batch(actor,body.get('workspace_id'),body.get('operations'))
        elif route=='/v1/sync/pull' and method=='GET':result=backend.pull(actor,query['workspace'][0],int(query.get('cursor',['0'])[0]))
        else:raise Failure('not_found',404)
    return result

def handler(backend):
    class API(BaseHTTPRequestHandler):
        def log_message(self,*args): pass # Never log passwords, invitation codes, source data or bearer tokens.
        def respond(self,status,value):
            body=json.dumps(value,ensure_ascii=False).encode();self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def run_request(self,method):
            try:
                split=urllib.parse.urlsplit(self.path);route=split.path;query=urllib.parse.parse_qs(split.query)
                body={}
                if method=='POST':
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=MAX_BODY:raise Failure('body_limit',413)
                    self.connection.settimeout(15)
                    def unique(pairs):
                        value={}
                        for key,item in pairs:
                            if key in value:raise Failure('duplicate_field')
                            value[key]=item
                        return value
                    body=json.loads(self.rfile.read(length),object_pairs_hook=unique)
                    if not isinstance(body,dict):raise Failure('invalid_input')
                result=dispatch(backend,method,self.path,body,self.headers.get('Authorization',''))
                self.respond(200,result)
            except Failure as error:self.respond(error.status,{'error':error.code})
            except (ValueError,TypeError,KeyError):self.respond(400,{'error':'invalid_input'})
            except Exception:self.respond(500,{'error':'server_error'})
        def do_POST(self):self.run_request('POST')
        def do_GET(self):self.run_request('GET')
    return API

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data',default='backend/.dev/server.db');parser.add_argument('--port',type=int,default=8787)
    args=parser.parse_args();root=Path(args.data).resolve().parent;root.mkdir(parents=True,exist_ok=True);os.chmod(root,0o700)
    def deliver(email,code):
        # Isolated mailbox, deliberately not a production email sender.
        folder=root/'mailbox';folder.mkdir(exist_ok=True);os.chmod(folder,0o700)
        import hashlib
        path=folder/(hashlib.sha256(email.encode()).hexdigest()+'.json');path.write_text(json.dumps({'email':email,'code':code}));os.chmod(path,0o600)
    backend=Backend(args.data,deliver=deliver)
    ThreadingHTTPServer(('127.0.0.1',args.port),handler(backend)).serve_forever()
if __name__=='__main__':main()
