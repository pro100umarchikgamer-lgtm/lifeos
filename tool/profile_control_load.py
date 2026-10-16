"""Bounded service-persistence profile, not a VPS or 5,000-concurrent-user claim."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import resource
import statistics
import time
import uuid
from urllib.parse import urlsplit
import psycopg
from psycopg import sql
from cryptography.fernet import Fernet
from backend.postgres import PostgresBackend
from backend.control import Control,totp
from backend.entitlements import resolve


def main():
    dsn=os.environ['LIFEOS_TEST_DATABASE_URL']
    assert urlsplit(dsn).path=='/lifeos_test','Refusing a non-test database'
    schema='profile_'+uuid.uuid4().hex
    with psycopg.connect(dsn,autocommit=True) as db:db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    backend=PostgresBackend(dsn,Fernet(Fernet.generate_key()),schema=schema,migrate=True,pool_size=4)
    results=[]
    try:
        mail={};deliver=backend._deliver
        def capture(db,email,code,purpose):deliver(db,email,code,purpose);mail[email]=code
        backend._deliver=capture
        password='synthetic-profile-passphrase'
        initial=backend.register('owner@example.test',password)
        actor=backend.authenticate(initial['token']);backend.verify(actor,mail[actor['email']]);actor=backend.authenticate(initial['token'])
        control=Control(backend);secret=control.bootstrap(actor['email'])
        login=control.login(actor['email'],password,totp(secret['totp_secret'],int(backend.clock())//30),'profile')
        owner=control.authenticate(login['token'],'profile')
        # Model existing registered accounts without spending 5,000 PBKDF rounds
        # seeding. Actual password verification is measured separately below.
        salt='00'*16;digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()
        seeded=1
        for total in (100,1000,5000):
            with backend.transaction() as db:
                for i in range(seeded,total):db.execute('INSERT INTO users VALUES(?,?,?,?,1,?)',(str(uuid.uuid5(uuid.NAMESPACE_URL,'uladim-load-'+str(i))),f'fixture-{i}@example.test',digest,salt,int(backend.clock())))
            seeded=total
            usage=resource.getrusage(resource.RUSAGE_SELF);start=time.monotonic()
            def read(i):
                begun=time.perf_counter()
                if i%2:control.users(owner,'fixture-'+str(i))
                else:
                    with backend.connect() as db:resolve(db,actor['id'],int(backend.clock()))
                return (time.perf_counter()-begun)*1000
            with ThreadPoolExecutor(max_workers=4) as executor:latencies=list(executor.map(read,range(100)))
            auth=[]
            for _ in range(3):
                begun=time.perf_counter();session=backend.login(actor['email'],password);auth.append((time.perf_counter()-begun)*1000);backend.logout(session['token'])
            with backend.connect() as db:
                count=db.execute('SELECT COUNT(*) AS n FROM users').fetchone()['n']
                size=db.execute("SELECT COALESCE(SUM(pg_total_relation_size(c.oid)),0) AS bytes FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=current_schema() AND c.relkind='r'").fetchone()['bytes']
            assert count==total
            used=resource.getrusage(resource.RUSAGE_SELF)
            results.append({'registered_accounts':total,'seed':'synthetic existing-account model','measured_concurrency':4,'operations':100,'p50_ms':round(statistics.median(latencies),2),'p95_ms':round(sorted(latencies)[94],2),'password_login_p50_ms':round(statistics.median(auth),2),'elapsed_seconds':round(time.monotonic()-start,2),'python_cpu_seconds':round((used.ru_utime+used.ru_stime)-(usage.ru_utime+usage.ru_stime),2),'python_peak_rss_kib':used.ru_maxrss,'schema_storage_bytes':int(size)})
    finally:
        backend.close()
        with psycopg.connect(dsn,autocommit=True) as db:db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
    folder=Path('load_evidence');folder.mkdir(exist_ok=True)
    (folder/'RESULT.json').write_text(json.dumps({'scope':'GitHub runner service/persistence profile, no HTTP/TLS/VPS benchmark','vps_tested':False,'simultaneous_5000_users_tested':False,'profiles':results},indent=2)+'\n')
    print('Synthetic profiles completed: 100 / 1000 / 5000 registered accounts, concurrency 4; see load_evidence.')

if __name__=='__main__':main()
