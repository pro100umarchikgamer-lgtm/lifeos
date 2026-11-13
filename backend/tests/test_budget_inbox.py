"""Threshold alerts use the canonical finance semantics without provider sends."""
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.service import Backend, Failure
from backend.tests.test_inbox import InboxScenarios, uid


class BudgetInboxScenarios(InboxScenarios):
    def settings(self, body=None, actor=None):
        return self.customer(actor=actor, suffix='/settings', body=body)

    def workspace(self, actor=None):
        actor = actor or self.first
        wid = uid()
        with self.backend.transaction() as db:
            db.execute("INSERT INTO workspaces(id,name,creator_id,kind) VALUES(?,?,?,'personal')", (wid, 'Private', actor['id']))
            db.execute("INSERT INTO memberships(workspace_id,user_id,role) VALUES(?,?,'owner')", (wid, actor['id']))
        return wid

    def budget(self, workspace, **values):
        data = {'name': 'Secret budget name', 'currency': 'USD', 'limit_minor': 1000,
            'period': 'month', 'start_on': '2026-11-01', 'end_on': None,
            'rollover': 'none', 'participants': '[]', **values}
        rid = uid()
        with self.backend.transaction() as db:
            db.execute("INSERT INTO records VALUES(?,?,?,'budget','private','[]',1,0,1)", (rid, workspace, self.first['id']))
            db.execute('INSERT INTO budgets VALUES(?,?,?,?,?,?,?,?,?)', (rid, *data.values()))
        return rid

    def expense(self, workspace, amount, **values):
        rid = uid()
        data = {'kind': 'expense', 'amount_minor': amount, 'currency': 'USD',
            'date': '2026-11-13', 'label': 'Secret transaction label', 'account_id': None, 'category': None, **values}
        with self.backend.transaction() as db:
            db.execute("INSERT INTO records VALUES(?,?,?,'transaction','private','[]',1,0,1)", (rid, workspace, self.first['id']))
            db.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?)', (rid, *data.values()))
        return rid

    def test_budget_settings_default_off_bounds_and_account_isolation(self):
        status, settings = self.settings()
        self.assertEqual(status, 200, settings)
        self.assertEqual(settings, {'budget_enabled': False, 'budget_thresholds': [50, 80, 100], 'timezone': 'UTC'})
        for body in ({'budget_enabled': 'yes'}, {'budget_thresholds': []}, {'budget_thresholds': [0]},
                     {'budget_thresholds': [101]}, {'budget_thresholds': [True]},
                     {'budget_thresholds': [80, 50]}, {'budget_thresholds': [50, 50]},
                     {'budget_thresholds': list(range(1, 22))}, {'timezone': 'not/a-zone'}):
            self.assertEqual(self.settings(body)[0], 400, body)
        self.assertEqual(self.settings({'budget_enabled': True, 'budget_thresholds': [50], 'timezone': 'Asia/Tashkent'})[0], 200)
        self.assertFalse(self.settings(actor=self.second)[1]['budget_enabled'])

    def test_budget_alerts_refresh_only_exact_scope_currency_threshold_and_dedup(self):
        wid = self.workspace()
        self.budget(wid)
        self.expense(wid, 799)
        self.expense(wid, 999999, currency='RUB')
        other_wid = self.workspace()
        self.expense(other_wid, 999999)
        self.assertEqual(self.customer()[1]['notifications'], [])
        self.assertEqual(self.customer()[1]['budget_evaluation']['state'], 'disabled')
        self.assertEqual(self.settings({'budget_enabled': True})[0], 200)
        first = self.customer()[1]
        self.assertEqual(first['budget_evaluation']['state'], 'evaluated')
        self.assertEqual(len(first['notifications']), 1)
        self.assertEqual(first['notifications'][0]['kind'], 'budget')
        self.assertIn('50%', first['notifications'][0]['body'])
        self.expense(wid, 1)
        self.assertEqual(len(self.customer()[1]['notifications']), 2)
        self.assertEqual(len(self.customer()[1]['notifications']), 2)
        self.assertEqual(self.customer(self.second)[1]['notifications'], [])
        serialized = str(self.customer()[1])
        self.assertNotIn('Secret budget name', serialized)
        self.assertNotIn('Secret transaction label', serialized)
        self.assertNotIn(wid, serialized)
        self.settings({'budget_enabled': False})
        self.settings({'budget_enabled': True})
        self.assertEqual(len(self.customer()[1]['notifications']), 2)

    def test_budget_evaluation_limits_are_explicit_and_write_no_partial_results(self):
        wid = self.workspace()
        self.budget(wid)
        self.budget(wid)
        self.expense(wid, 1000)
        self.settings({'budget_enabled': True})
        with patch('backend.budget_inbox.MAX_BUDGETS', 1):
            value = self.customer()[1]
        self.assertEqual(value['budget_evaluation']['state'], 'skipped_limit')
        self.assertEqual(value['notifications'], [])
        self.expense(wid, 1)
        with patch('backend.budget_inbox.MAX_EXPENSES', 1):
            value = self.customer()[1]
        self.assertEqual(value['budget_evaluation']['state'], 'skipped_limit')
        self.assertEqual(value['notifications'], [])

    def test_budget_revoked_workspace_does_not_generate_new_private_progress(self):
        wid = self.workspace()
        self.budget(wid)
        self.expense(wid, 1000)
        self.settings({'budget_enabled': True})
        with self.backend.transaction() as db:
            db.execute('UPDATE memberships SET active=0 WHERE workspace_id=?', (wid,))
        self.assertEqual(self.customer()[1]['notifications'], [])

    def test_budget_only_counts_readable_expenses_and_assigned_participants(self):
        wid = self.workspace()
        self.budget(wid, participants='["child"]')
        visible = self.expense(wid, 500)
        private_other = self.expense(wid, 999999)
        sibling = self.expense(wid, 999999)
        with self.backend.transaction() as db:
            db.execute('UPDATE records SET audience=? WHERE id=?', ('["child"]', visible))
            db.execute('UPDATE records SET owner_id=?,audience=? WHERE id=?', (self.second['id'], '["child"]', private_other))
            db.execute('UPDATE records SET audience=? WHERE id=?', ('["sibling"]', sibling))
        self.settings({'budget_enabled': True})
        items = self.customer()[1]['notifications']
        self.assertEqual(len(items), 1)
        self.assertIn('50%', items[0]['body'])

    def test_hidden_rows_in_same_workspace_never_change_evaluation_limit_state(self):
        wid = self.workspace()
        self.budget(wid)
        hidden_budget = self.budget(wid)
        self.expense(wid, 500)
        hidden_expense = self.expense(wid, 999999)
        with self.backend.transaction() as db:
            for rid in (hidden_budget, hidden_expense):
                db.execute('UPDATE records SET owner_id=? WHERE id=?', (self.second['id'], rid))
        self.settings({'budget_enabled': True})
        with patch('backend.budget_inbox.MAX_BUDGETS', 1), patch('backend.budget_inbox.MAX_EXPENSES', 1):
            value = self.customer()[1]
        self.assertEqual(value['budget_evaluation']['state'], 'evaluated')
        self.assertEqual(len(value['notifications']), 1)

    def test_budget_settings_use_existing_origin_csrf_and_deletion_erases_them(self):
        from backend.account_lifecycle import AccountLifecycle
        self.web_sessions()
        self.assertEqual(self.web_request(False, 'inbox/settings', {'budget_enabled': True}, HTTP_X_CSRF_TOKEN='')[0], 403)
        self.assertEqual(self.web_request(False, 'inbox/settings', {'budget_enabled': True}, HTTP_ORIGIN='https://evil.test')[0], 403)
        self.assertEqual(self.web_request(False, 'inbox/settings', {'budget_enabled': True})[0], 200)
        wid = self.workspace()
        self.budget(wid)
        self.expense(wid, 1000)
        self.assertEqual(len(self.customer()[1]['notifications']), 3)
        with self.backend.transaction() as db:
            db.execute("INSERT INTO deletion_jobs VALUES(?,?,?,?,'pending',NULL)", (uid(), self.first['id'], self.now, self.now))
        self.assertTrue(AccountLifecycle(self.backend).process_one_deletion())
        with self.backend.connect() as db:
            for table in ('budget_inbox_notifications', 'inbox_settings'):
                self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM ' + table + ' WHERE user_id=?', (self.first['id'],)).fetchone()['n'], 0)


class BudgetInboxTests(BudgetInboxScenarios, unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.backend = Backend(Path(folder.name) / 'budgets.db')
        from cryptography.fernet import Fernet
        self.backend.cipher = Fernet(Fernet.generate_key())
        self.fixtures()


class CanonicalBudgetTests(unittest.TestCase):
    def metrics(self, policy='none', period='month', start='2026-10-01', at='2026-11-02', expenses=None, **extra):
        from backend.budget_inbox import budget_metrics
        budget = {'start_on': start, 'period': period, 'rollover': policy, 'currency': 'USD',
            'limit_minor': 1000, 'participants': [], 'end_on': None, **extra}
        return budget_metrics(budget, dt.date.fromisoformat(at), expenses or [])

    def test_all_rollover_policies_match_existing_dart_fixtures(self):
        for policy in ('none', 'positive', 'negative', 'both'):
            with self.subTest(policy=policy):
                old = [{'currency': 'USD', 'amount_minor': 1500, 'date': '2026-10-11', 'audience': []}]
                result = self.metrics(policy=policy, expenses=old)
                self.assertEqual(result['available'], 500 if policy in ('negative', 'both') else 1000)
                old[0]['amount_minor'] = 500
                self.assertEqual(self.metrics(policy=policy, expenses=old)['available'],
                    1500 if policy in ('positive', 'both') else 1000)

    def test_period_boundaries_leap_year_custom_span_and_participants(self):
        expenses = [{'currency': 'USD', 'amount_minor': 400, 'date': '2026-11-01', 'audience': ['child']},
            {'currency': 'USD', 'amount_minor': 9999, 'date': '2026-11-01', 'audience': ['sibling']},
            {'currency': 'RUB', 'amount_minor': 9999, 'date': '2026-11-01', 'audience': ['child']}]
        result = self.metrics(expenses=expenses, participants=['child'])
        self.assertEqual((result['start'], result['end'], result['spent']), ('2026-11-01', '2026-11-30', 400))
        self.assertEqual(self.metrics(period='week', start='2026-11-01', at='2026-11-08')['start'], '2026-11-08')
        self.assertEqual(self.metrics(period='month', start='2024-02-15', at='2024-02-29')['end'], '2024-02-29')
        self.assertEqual(self.metrics(period='year', start='2026-02-01', at='2027-01-01')['start'], '2027-01-01')
        self.assertEqual(self.metrics(period='custom', start='2026-11-01', end_on='2026-11-03', at='2026-11-04')['start'], '2026-11-04')

    def test_long_empty_rollover_and_large_minor_amounts_remain_exact(self):
        result = self.metrics(policy='both', period='custom', start='1900-01-01', end_on='1900-01-01', at='2200-01-01')
        self.assertEqual(result['available'], ((dt.date(2200, 1, 1) - dt.date(1900, 1, 1)).days + 1) * 1000)
        large = 999999999999999
        result = self.metrics(start='2026-11-01', expenses=[{'currency': 'USD', 'amount_minor': large, 'date': '2026-11-01', 'audience': []}], limit_minor=large)
        self.assertEqual(result['spent'], large)
        self.assertEqual(result['available'], large)


if __name__ == '__main__':
    unittest.main()
