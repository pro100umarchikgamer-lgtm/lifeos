"""The same inbox authorization/history scenarios against a disposable PostgreSQL."""
import os
import unittest
import uuid
from urllib.parse import urlsplit
import psycopg
from psycopg import sql
from cryptography.fernet import Fernet
from backend.postgres import PostgresBackend
from backend.tests.test_inbox import InboxScenarios
from backend.tests.test_budget_inbox import BudgetInboxScenarios
from backend.tests import test_inbox_retention as retention_tests

DSN = os.environ.get('LIFEOS_TEST_DATABASE_URL', '')


@unittest.skipUnless(DSN, 'Requires isolated lifeos_test PostgreSQL database')
class InboxPostgresTests(InboxScenarios, unittest.TestCase):
    def setUp(self):
        if urlsplit(DSN).path != '/lifeos_test':
            raise RuntimeError('Tests refuse a non-test database')
        self.schema = 'inbox_test_' + uuid.uuid4().hex
        with psycopg.connect(DSN, autocommit=True) as db:
            db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.addCleanup(self.drop_schema)
        self.backend = PostgresBackend(DSN, Fernet(Fernet.generate_key()), schema=self.schema, migrate=True)
        self.addCleanup(self.backend.close)
        self.fixtures()

    def drop_schema(self):
        with psycopg.connect(DSN, autocommit=True) as db:
            db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))

    def test_additive_migration_is_repeatable_and_preserves_existing_data(self):
        with self.backend.transaction() as db:
            db.execute('DROP TABLE announcement_states')
            db.execute('DROP TABLE announcement_recipients')
            db.execute('DROP TABLE announcements')
            db.execute('DROP TABLE inbox_notifications')
            db.execute("DELETE FROM schema_migrations WHERE version='014_inbox.sql'")
        self.backend.migrate()
        self.backend.migrate()
        self.assertEqual(self.customer()[1]['notifications'], [])
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT email FROM users WHERE id=?', (self.first['id'],)).fetchone()['email'], self.first['email'])
            self.assertEqual(db.execute("SELECT COUNT(*) AS n FROM schema_migrations WHERE version='014_inbox.sql'").fetchone()['n'], 1)


class BudgetInboxPostgresTests(BudgetInboxScenarios, InboxPostgresTests):
    def test_budget_migration_is_additive_repeatable_and_preserves_history(self):
        item = self.publish(self.draft())
        with self.backend.transaction() as db:
            db.execute('DROP TABLE budget_inbox_notifications')
            db.execute('DROP TABLE inbox_settings')
            db.execute("DELETE FROM schema_migrations WHERE version='016_budget_inbox.sql'")
        self.backend.migrate()
        self.backend.migrate()
        self.assertEqual(self.customer()[1]['notifications'][0]['id'], item['id'])
        self.assertEqual(self.settings()[1]['budget_enabled'], False)


class InboxRetentionPostgresTests(retention_tests.InboxRetentionTests, InboxPostgresTests):
    setUp = InboxPostgresTests.setUp

    def test_retention_migration_is_repeatable_and_keeps_existing_history(self):
        item = self.publish(self.draft())
        with self.backend.transaction() as db:
            db.execute('DROP TABLE budget_inbox_sources')
            db.execute("DELETE FROM schema_migrations WHERE version='017_inbox_retention.sql'")
        self.backend.migrate()
        self.backend.migrate()
        self.assertEqual(self.customer()[1]['notifications'][0]['id'], item['id'])
