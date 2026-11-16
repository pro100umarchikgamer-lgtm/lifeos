"""Selected future-cohort scenarios against the existing disposable Postgres fixture."""
import unittest
import uuid

try:
    from backend.tests import test_inbox_postgres as postgres_fixtures
    DSN = postgres_fixtures.DSN
except ModuleNotFoundError as error:
    if error.name not in ('psycopg', 'psycopg_pool'):
        raise
    DSN, postgres_fixtures = '', None
from backend.tests.test_newcomer_announcements import NewcomerScenarios


@unittest.skipUnless(DSN, 'Requires isolated lifeos_test PostgreSQL database')
class NewcomerPostgresTests(NewcomerScenarios, unittest.TestCase):
    if postgres_fixtures:
        setUp = postgres_fixtures.InboxPostgresTests.setUp
        drop_schema = postgres_fixtures.InboxPostgresTests.drop_schema

    def test_additive_targeting_migration_repeats_without_changing_existing_snapshots(self):
        item = self.publish(self.draft(audience='all', user_ids=[]))
        manual = self.publish(self.draft())
        self.assertEqual(self.customer(suffix='/presented', body={'id': item['id']})[0], 200)
        wid, rid = str(uuid.uuid4()), str(uuid.uuid4())
        self.backend.family(self.first, {'id': str(uuid.uuid4()), 'workspace_id': wid,
            'action': 'workspace.create', 'kind': 'personal', 'name': 'Existing private workspace'})
        written = self.backend.batch(self.first, wid, [{'id': str(uuid.uuid4()), 'action': 'record.put',
            'record_id': rid, 'revision': 0, 'kind': 'account', 'visibility': 'private', 'audience': [],
            'data': {'name': 'Existing private account', 'currency': 'RUB', 'opening_minor': 1234567890123}}])
        self.assertEqual(written['results'][0]['status'], 'accepted')
        with self.backend.transaction() as db:
            before_users = [row['id'] for row in db.execute('SELECT id FROM users ORDER BY id').fetchall()]
            before_recipients = [dict(row) for row in db.execute('SELECT * FROM announcement_recipients ORDER BY announcement_id,user_id').fetchall()]
            before_record = dict(db.execute('SELECT * FROM records WHERE id=?', (rid,)).fetchone())
            for table in ('newcomer_welcome_claims', 'announcement_cohort_exclusions', 'announcement_targeting'):
                db.execute('DROP TABLE ' + table)
            db.execute('DROP INDEX users_created_history')
            db.execute("DELETE FROM schema_migrations WHERE version='025_announcement_targeting.sql'")
        self.backend.migrate()
        self.backend.migrate()
        messages = {row['id']: row for row in self.customer()[1]['notifications']}
        self.assertEqual(set(messages), {item['id'], manual['id']})
        self.assertEqual(messages[item['id']]['presented_at'], self.now)
        with self.backend.connect() as db:
            self.assertEqual([row['id'] for row in db.execute('SELECT id FROM users ORDER BY id').fetchall()], before_users)
            self.assertEqual([dict(row) for row in db.execute('SELECT * FROM announcement_recipients ORDER BY announcement_id,user_id').fetchall()], before_recipients)
            self.assertEqual(dict(db.execute('SELECT * FROM records WHERE id=?', (rid,)).fetchone()), before_record)
            self.assertEqual(db.execute('SELECT opening_minor FROM accounts WHERE id=?', (rid,)).fetchone()['opening_minor'], 1234567890123)
            self.assertEqual(db.execute("SELECT COUNT(*) AS n FROM schema_migrations WHERE version='025_announcement_targeting.sql'").fetchone()['n'], 1)
            self.assertEqual(db.execute('SELECT roles FROM staff WHERE id=?', (self.sid,)).fetchone()['roles'], '["owner"]')
