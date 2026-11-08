"""Run bounded adversarial scenarios against disposable SQLite/PostgreSQL only."""
import argparse
import json
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='web_evidence/security-audit-20261109.json')
    parser.add_argument('--all',action='store_true',help='Run the full backend suite and collect audit evidence once')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root/'backend/tests'))
    sys.path.insert(0,str(root))
    import test_security_audit as audit
    dsn=os.environ.get('LIFEOS_TEST_DATABASE_URL')
    if dsn:
        if urlsplit(dsn).path!='/lifeos_test':raise RuntimeError('Refusing a non-test PostgreSQL database')
        import psycopg
        with psycopg.connect(dsn) as db:
            assert db.execute('SELECT rolsuper FROM pg_roles WHERE rolname=current_user').fetchone()==(False,), 'Test role must not be superuser'
    if args.all:
        suite=unittest.defaultTestLoader.discover(str(root/'backend/tests'))
    else:
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(audit.SecurityAuditTests)
        if dsn:
            from test_postgres import PostgresSecurityAuditTests
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(PostgresSecurityAuditTests))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'passed':result.wasSuccessful(),'tests':result.testsRun,'postgres':bool(dsn),'scope':'Disposable two-account HTTP fixtures, no production data or SMTP','cases':audit.EVIDENCE},ensure_ascii=False,indent=2)+'\n')
    print('SECURITY_AUDIT',len(audit.EVIDENCE),'assertions',result.wasSuccessful())
    return int(not result.wasSuccessful())


if __name__=='__main__':raise SystemExit(main())
