"""PostgreSQL persistence using the existing authorization and sync service.

The initial deployment serializes mutations with one PostgreSQL advisory lock.
This preserves committed cursor order across workers (sequence values alone do not).
Read operations use a repeatable-read snapshot; no user history is pruned.
"""
import contextlib
import hashlib
import time
from pathlib import Path

from psycopg_pool import ConnectionPool
from .service import Backend

LOCK = 748934510

class Row(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)

def row_factory(cursor):
    names = [column.name for column in cursor.description] if cursor.description else []
    return lambda values: Row(zip(names, values))

class Connection:
    def __init__(self, pool):
        self.pool = pool
        self.raw = pool.getconn(timeout=10)
        self.closed = False
    def execute(self, sql, params=()):
        return self.raw.execute(sql.replace('?', '%s'), params)
    def __enter__(self):
        self.execute('BEGIN ISOLATION LEVEL REPEATABLE READ')
        return self
    def __exit__(self, kind, value, trace):
        try:
            self.rollback() if kind else self.commit()
        finally:
            self.close()
    def commit(self): self.execute('COMMIT')
    def rollback(self): self.execute('ROLLBACK')
    def close(self):
        if not self.closed:
            self.closed = True
            self.pool.putconn(self.raw)

class PostgresBackend(Backend):
    def __init__(self, dsn, mail_cipher, clock=time.time, migrate=False, pool_size=4, schema=None):
        import re
        if schema is not None and not re.fullmatch(r'[a-z][a-z0-9_]{1,62}',schema):raise ValueError('Invalid schema')
        options = '-c statement_timeout=15000 -c idle_in_transaction_session_timeout=30000'
        if schema:options+=' -c search_path='+schema
        self.clock = clock
        self.cipher = mail_cipher
        self.deliver = self._deliver
        self.pool = ConnectionPool(dsn, min_size=1, max_size=pool_size, max_waiting=32,
            timeout=10, kwargs={'autocommit':True, 'row_factory':row_factory,
            'connect_timeout':5, 'options':options}, open=True)
        self.pool.wait(timeout=15)
        if migrate: self.migrate()
    def connect(self): return Connection(self.pool)
    @contextlib.contextmanager
    def transaction(self):
        db = self.connect()
        locked = False
        try:
            # Session lock before BEGIN prevents a stale snapshot while waiting.
            db.execute('SELECT pg_advisory_lock(?)', (LOCK,))
            locked = True
            db.execute('BEGIN ISOLATION LEVEL REPEATABLE READ')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            try:
                if locked: db.execute('SELECT pg_advisory_unlock(?)', (LOCK,))
            finally: db.close()
    def _audit(self, db, wid, actor, op, kind, rid=None):
        return db.execute('INSERT INTO changes(workspace_id,record_id,actor_id,operation_id,kind) VALUES(?,?,?,?,?) RETURNING seq',
            (wid,rid,actor['id'],op,kind)).fetchone()['seq']
    def _deliver(self, db, email, code, purpose):
        import uuid
        from .service import canonical
        now = int(self.clock())
        payload = self.cipher.encrypt(canonical({'email':email,'code':code,'purpose':purpose}).encode())
        db.execute('INSERT INTO email_jobs(id,payload,expires_at,next_attempt) VALUES(?,?,?,?)',
            (str(uuid.uuid4()), payload, now+(900 if purpose=='recovery' else 3600), now))
    def migrate(self):
        with self.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY,digest TEXT NOT NULL,applied_at BIGINT NOT NULL)')
            for file in sorted(Path(__file__).with_name('migrations').glob('*.sql')):
                digest = hashlib.sha256(file.read_bytes()).hexdigest()
                prior = db.execute('SELECT digest FROM schema_migrations WHERE version=?',(file.name,)).fetchone()
                if prior:
                    if prior['digest'] != digest: raise RuntimeError('Applied migration checksum changed: '+file.name)
                    continue
                db.raw.execute(file.read_text())
                db.execute('INSERT INTO schema_migrations VALUES(?,?,?)',(file.name,digest,int(self.clock())))
    def close(self): self.pool.close()
