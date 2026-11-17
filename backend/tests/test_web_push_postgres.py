"""Run the focused delivery scenarios against CI's real disposable PostgreSQL."""
import os
import unittest
import uuid
from urllib.parse import urlsplit
import psycopg
from psycopg import sql
from cryptography.fernet import Fernet
from backend.postgres import PostgresBackend
from backend.tests.test_web_push import PushScenarios

DSN=os.environ.get('LIFEOS_TEST_DATABASE_URL','')


@unittest.skipUnless(DSN,'Requires isolated lifeos_test PostgreSQL database')
class WebPushPostgresTests(PushScenarios,unittest.TestCase):
    def setUp(self):
        if urlsplit(DSN).path!='/lifeos_test': raise RuntimeError('Tests refuse a non-test database')
        self.schema='push_test_'+uuid.uuid4().hex
        with psycopg.connect(DSN,autocommit=True) as db:
            db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.addCleanup(self.drop_schema)
        self.backend=PostgresBackend(DSN,Fernet(Fernet.generate_key()),schema=self.schema,migrate=True)
        self.addCleanup(self.backend.close)
        self.fixtures()

    def drop_schema(self):
        with psycopg.connect(DSN,autocommit=True) as db:
            db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))

    def test_migration_applies_to_existing_data_and_is_idempotent(self):
        # Recreate the pre-013 schema in this disposable DB after users and
        # workspaces exist. No existing migration or core data is rewritten.
        with self.backend.transaction() as db:
            db.execute('DROP TABLE web_push_deliveries')
            db.execute('DROP TABLE web_push_subscriptions')
            db.execute('DROP TABLE web_push_keys')
            db.execute("DELETE FROM schema_migrations WHERE version='013_web_push.sql'")
        self.backend.migrate();self.backend.migrate()
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT email FROM users WHERE id=?',(self.user,)).fetchone()['email'],self.actor['email'])
            self.assertEqual(db.execute('SELECT name FROM workspaces WHERE id=?',(self.workspace,)).fetchone()['name'],'Personal')
            self.assertIsNotNone(db.execute("SELECT 1 FROM schema_migrations WHERE version='013_web_push.sql'").fetchone())
        self.assertTrue(self.subscribe()['enabled'])
