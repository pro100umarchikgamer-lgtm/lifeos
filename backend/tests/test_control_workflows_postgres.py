"""Control workbench state boundaries in disposable PostgreSQL schemas."""
import unittest

try:
    from backend.tests.test_inbox_postgres import DSN
except ModuleNotFoundError as error:
    if error.name not in ('psycopg', 'psycopg_pool'):
        raise
    DSN = ''

from backend.tests import test_control_workflows as workflows


@unittest.skipUnless(DSN, 'Requires isolated lifeos_test PostgreSQL database')
class ControlWorkflowPostgresTests(workflows.ControlWorkflowTests):
    def setUp(self):
        from backend.tests.test_postgres import PostgresControlWebTests
        self.f = PostgresControlWebTests(methodName='test_staff_cookie_is_not_a_customer_bearer_and_mfa_required')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_additive_workflow_migration_repeats_and_preserves_existing_authority(self):
        from backend.account_identity import AccountIdentity
        f = self.f
        with f.backend.transaction() as db:
            before = [row['id'] for row in db.execute('SELECT id FROM users ORDER BY id').fetchall()]
            for table in ('support_recovery_cases', 'staff_invitation_restrictions', 'staff_permission_restrictions', 'account_identity'):
                db.execute('DROP TABLE ' + table)
            db.execute("DELETE FROM schema_migrations WHERE version='024_control_workflows.sql'")
        f.backend.migrate()
        AccountIdentity(f.backend).identity(f.user2, {'display_name': 'Voluntary identity'})
        f.backend.migrate()
        self.assertEqual(AccountIdentity(f.backend).identity(f.user2)['display_name'], 'Voluntary identity')
        self.assertEqual(f.control.authenticate(f.staff_login['token'], 'fixture').roles, ('owner',))
        with f.backend.connect() as db:
            self.assertEqual([row['id'] for row in db.execute('SELECT id FROM users ORDER BY id').fetchall()], before)
            self.assertEqual(db.execute("SELECT COUNT(*) AS n FROM schema_migrations WHERE version='024_control_workflows.sql'").fetchone()['n'], 1)


if __name__ == '__main__':
    unittest.main()
