"""Only generated inbox history is trimmed; user records and active notices survive."""
import datetime as dt
from unittest.mock import patch
from backend.tests import test_budget_inbox as budget_tests
from backend.tests.test_inbox import uid


class InboxRetentionTests(budget_tests.BudgetInboxTests):
    def renew_fixture_sessions(self):
        with self.backend.transaction() as db:
            for actor in (self.first, self.second, self.owner):
                self.tokens[actor['id']] = self.backend.new_session(db, actor['id'], False)['token']

    def test_generated_history_is_limited_to_90_days_and_1000_newest(self):
        from backend.inbox import Inbox
        from backend import inbox_retention
        inbox = Inbox(self.backend)
        with patch.object(inbox_retention, 'HISTORY_LIMIT', 3):
            for number in range(6):
                self.now += 1
                with self.backend.transaction() as db:
                    inbox.append_delivery(db, {'user_id': self.first['id']}, self.now, uid())
            value = self.customer()[1]
            self.assertEqual(len(value['notifications']), 3)
            self.assertEqual(value['history_limit'], 3)
            self.assertEqual(value['retention_days'], 90)
            self.assertEqual(value['announcement_retention_days_after_expiry'], 90)
            self.assertEqual(value['notifications'][-1]['created_at'], self.now - 2)
        self.now += 91 * 86400
        self.renew_fixture_sessions()
        self.assertEqual(self.customer()[1]['notifications'], [])
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM inbox_notifications WHERE user_id=?', (self.first['id'],)).fetchone()['n'], 0)

    def test_active_announcements_survive_history_cap_and_expired_payload_is_reclaimed_globally(self):
        from backend.inbox import Inbox
        from backend import inbox_retention
        item = self.publish(self.draft(audience='all', user_ids=[]))
        with patch.object(inbox_retention, 'HISTORY_LIMIT', 1):
            for i in range(3):
                with self.backend.transaction() as db:
                    Inbox(self.backend).append_delivery(db, {'user_id': self.first['id']}, self.now, uid())
            value = self.customer()[1]
            self.assertIn(item['id'], {x['id'] for x in value['notifications']})
        self.now = item['expires_at'] + 91 * 86400
        self.renew_fixture_sessions()
        self.customer()
        with self.backend.connect() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM announcements WHERE id=?', (item['id'],)).fetchone())
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM announcement_recipients').fetchone()['n'], 0)

    def test_annual_budget_threshold_does_not_replay_after_history_retention(self):
        self.now = int(dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc).timestamp())
        wid = self.workspace()
        self.budget(wid, period='year', start_on='2026-01-01')
        self.expense(wid, 1000, date='2026-01-02')
        self.settings({'budget_enabled': True})
        self.assertEqual(len(self.customer()[1]['notifications']), 3)
        self.now += 91 * 86400
        self.assertEqual(self.customer()[1]['notifications'], [])
        self.assertEqual(self.customer()[1]['budget_evaluation']['state'], 'evaluated')
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM budget_inbox_sources WHERE user_id=?', (self.first['id'],)).fetchone()['n'], 3)

    def test_pre_retention_annual_budget_history_backfills_dedup_before_erasure(self):
        self.now = int(dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc).timestamp())
        wid = self.workspace()
        self.budget(wid, period='year', start_on='2026-01-01')
        self.expense(wid, 1000, date='2026-01-02')
        self.settings({'budget_enabled': True})
        self.assertEqual(len(self.customer()[1]['notifications']), 3)
        with self.backend.transaction() as db:
            db.execute('DELETE FROM budget_inbox_sources WHERE user_id=?', (self.first['id'],))
        self.now += 91 * 86400
        self.assertEqual(self.customer()[1]['notifications'], [])

    def test_budget_source_cap_is_explicit_without_partial_notifications(self):
        wid = self.workspace()
        self.budget(wid)
        self.expense(wid, 1000)
        self.settings({'budget_enabled': True})
        with patch('backend.budget_inbox.MAX_SOURCES', 2):
            value = self.customer()[1]
        self.assertEqual(value['budget_evaluation']['state'], 'skipped_limit')
        self.assertEqual(value['notifications'], [])

    def test_retention_never_erases_another_accounts_generated_history(self):
        from backend.inbox import Inbox
        with self.backend.transaction() as db:
            Inbox(self.backend).append_delivery(db, {'user_id': self.second['id']}, self.now - 91 * 86400, uid())
        self.customer()
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM inbox_notifications WHERE user_id=?', (self.second['id'],)).fetchone()['n'], 1)
