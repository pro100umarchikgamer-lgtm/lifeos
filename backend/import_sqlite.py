"""Operator-only migration of the development SERVER database; never reads Android SQLCipher."""
import argparse
import re
import sqlite3
from pathlib import Path
from .service import Failure

OPTIONAL_TABLES={'account_mfa','account_recovery','account_state','devices','session_devices','refresh_tokens','staff','control_sessions','staff_invitations','staff_recovery','control_audit','plan_catalog','entitlement_grants','entitlement_overrides','provider_purchases','provider_events','service_holds','support_tickets','support_messages','feature_flags','flag_proposals','web_sessions','email_changes','deletion_jobs','ownership_transfers'}
TABLES=re.findall(r'CREATE TABLE IF NOT EXISTS (\w+)\(',Path(__file__).with_name('schema.sql').read_text())

def import_server(backend,source,apply=False):
    path=Path(source).resolve()
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as old:
        old.row_factory=sqlite3.Row
        old.execute('BEGIN')
        names={row[0] for row in old.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if not set(TABLES)-OPTIONAL_TABLES<=names or not names<=set(TABLES):raise ValueError('Source must be a compatible LifeOS development server database')
        if old.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('Source foreign-key integrity check failed')
        counts={name:old.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] if name in names else 0 for name in TABLES}
        if not apply:return counts
        with backend.transaction() as db:
            for name in TABLES:
                if db.execute('SELECT 1 FROM '+name+' LIMIT 1').fetchone():raise Failure('import_target_not_empty',409)
            for name in TABLES:
                if name not in names:continue
                for row in old.execute('SELECT * FROM '+name):
                    fields=list(row.keys())
                    overriding=' OVERRIDING SYSTEM VALUE' if name in {'changes','control_audit'} else ''
                    db.execute('INSERT INTO '+name+'('+','.join(fields)+')'+overriding+' VALUES('+','.join('?' for _ in fields)+')',list(row))
            for sequence_table in ['changes','control_audit']:
                db.execute("SELECT setval(pg_get_serial_sequence('"+sequence_table+"','seq'),COALESCE(MAX(seq),1),COUNT(*)>0) FROM "+sequence_table)
        return counts

def main():
    from cryptography.fernet import Fernet
    from .config import Settings
    from .postgres import PostgresBackend
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args();settings=Settings.load()
    backend=PostgresBackend(settings.database_url,Fernet(settings.email_queue_key.encode()))
    try:
        counts=import_server(backend,args.source,args.apply)
        print(('Imported atomically: ' if args.apply else 'Read-only preview: ')+str(counts))
    finally:backend.close()

if __name__=='__main__':main()
