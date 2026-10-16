"""Bounded WSGI API behind a trusted HTTPS proxy, with private operational metrics."""
import hashlib
import hmac
import ipaddress
import json
import logging
import time
import uuid
from http import HTTPStatus

from .http_server import dispatch, MAX_BODY
from .service import Failure

log=logging.getLogger('lifeos.api')

def decode_json(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise Failure('duplicate_field')
            result[key]=value
        return result
    value=json.loads(raw,object_pairs_hook=unique)
    if not isinstance(value,dict):raise Failure('invalid_input')
    return value

class Application:
    def __init__(self, backend, settings):
        self.backend,self.settings=backend,settings
        from .web import Web
        self.web=Web(backend,settings)
        self.started=time.time()
        self.networks=[ipaddress.ip_network(v.strip()) for v in settings.trusted_proxy_cidrs.split(',')]
    def trusted(self,environ):
        try:return any(ipaddress.ip_address(environ.get('REMOTE_ADDR','')) in n for n in self.networks)
        except ValueError:return False
    def client(self,environ):
        address=environ.get('REMOTE_ADDR','unknown')
        if self.trusted(environ):
            candidate=environ.get('HTTP_X_FORWARDED_FOR','')
            try:address=str(ipaddress.ip_address(candidate))
            except ValueError:pass
        return address
    def check_registration(self, body):
        # Only new account creation is gated. Existing sessions, account recovery,
        # family permissions and durable sync continue when the allowlist changes.
        if self.settings.registration_mode == 'open': return
        email = body.get('email')
        if not isinstance(email, str) or email.casefold() not in self.settings.registration_allowlist:
            raise Failure('registration_closed',403)
    def limit(self,environ,path):
        now=int(self.backend.clock())
        category='auth' if path.startswith('/v1/auth/') else 'api'
        maximum=30 if category=='auth' else 240
        key=hmac.new(self.settings.rate_limit_key.encode(),(category+'|'+self.client(environ)).encode(),hashlib.sha256).hexdigest()
        # A single autocommit UPSERT avoids repeatable-read serialization failures
        # when two phones behind the same NAT hit the limit counter together.
        db=self.backend.connect()
        try:
            row=db.execute('INSERT INTO http_limits VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=CASE WHEN http_limits.until_at<=? THEN 1 ELSE http_limits.count+1 END,until_at=CASE WHEN http_limits.until_at<=? THEN excluded.until_at ELSE http_limits.until_at END RETURNING count',(key,now+60,now,now)).fetchone()
        finally:db.close()
        if row['count']>maximum:raise Failure('rate_limited',429)
    def __call__(self,environ,start_response):
        status=200
        headers={'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store',
            'X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'",'X-Request-ID':str(uuid.uuid4())}
        path=environ.get('PATH_INFO','')
        method=environ.get('REQUEST_METHOD','')
        try:
            if method not in ('GET','POST'):raise Failure('method_not_allowed',405)
            if path=='/health/live' and method=='GET':value={'status':'ok'}
            elif path=='/health/ready' and method=='GET':
                with self.backend.connect() as db:
                    if not db.execute('SELECT version FROM schema_migrations LIMIT 1').fetchone():
                        raise Failure('schema_not_ready',503)
                value={'status':'ready'}
            elif path=='/metrics' and method=='GET':
                headers['Content-Type']='text/plain; version=0.0.4'
                value=self.metrics()
            else:
                if self.settings.require_https and not (self.trusted(environ) and environ.get('HTTP_X_FORWARDED_PROTO')=='https'):
                    raise Failure('https_required',426)
                is_web=self.web.handles(environ)
                if not is_web and not path.startswith('/v1/'):raise Failure('not_found',404)
                self.limit(environ,path)
                body={}
                if method=='POST':
                    if environ.get('CONTENT_TYPE','').split(';')[0].strip().lower()!='application/json':raise Failure('content_type',415)
                    length=int(environ.get('CONTENT_LENGTH','0'))
                    if not 0<length<=MAX_BODY:raise Failure('body_limit',413)
                    raw=environ['wsgi.input'].read(length)
                    if len(raw)!=length:raise Failure('invalid_input')
                    body=decode_json(raw)
                if is_web:
                    value,web_headers=self.web.request(environ,body)
                    headers.update(dict(web_headers))
                else:
                    if method=='POST' and path in ('/v1/auth/register','/v1/auth/signup'):self.check_registration(body)
                    target=path+('?' +environ['QUERY_STRING'] if environ.get('QUERY_STRING') else '')
                    value=dispatch(self.backend,method,target,body,environ.get('HTTP_AUTHORIZATION',''))
        except Failure as error:status=error.status;value={'error':error.code}
        except (ValueError,TypeError,KeyError):status=400;value={'error':'invalid_input'}
        except Exception as error:
            log.error('request_failed class=%s',type(error).__name__)
            status=503;value={'error':'server_unavailable'}
        output=value if isinstance(value,bytes) else (value.encode() if isinstance(value,str) else json.dumps(value,ensure_ascii=False).encode())
        headers['Content-Length']=str(len(output))
        if status==429:headers['Retry-After']='60'
        start_response(str(status)+' '+HTTPStatus(status).phrase,list(headers.items()))
        return [output]
    def metrics(self):
        now=int(self.backend.clock())
        with self.backend.connect() as db:
            queue=db.execute('SELECT COUNT(*) AS pending,COALESCE(MIN(next_attempt),?) AS oldest FROM email_jobs WHERE delivered_at IS NULL AND expires_at>?',(now,now)).fetchone()
            worker=db.execute("SELECT last_seen FROM worker_health WHERE name='mail'").fetchone()
            size=db.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        return f'lifeos_uptime_seconds {int(time.time()-self.started)}\nlifeos_email_pending {queue["pending"]}\nlifeos_email_oldest_seconds {max(0,now-queue["oldest"])}\nlifeos_mail_worker_age_seconds {now-worker["last_seen"] if worker else 86400}\nlifeos_database_bytes {size}\n'

def create_app():
    from cryptography.fernet import Fernet
    from .config import Settings
    from .postgres import PostgresBackend
    settings=Settings.load()
    return Application(PostgresBackend(settings.database_url,Fernet(settings.email_queue_key.encode()),pool_size=settings.pool_size),settings)

def main():
    import sys
    from cryptography.fernet import Fernet
    from .config import Settings
    from .postgres import PostgresBackend
    settings=Settings.load()
    backend=PostgresBackend(settings.database_url,Fernet(settings.email_queue_key.encode()))
    try:
        if sys.argv[1:] == ['migrate']:backend.migrate()
        else:raise SystemExit('Usage: python -m backend.production migrate')
    finally:backend.close()

if __name__=='__main__':main()
