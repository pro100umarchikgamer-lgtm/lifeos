"""Future account welcomes use exact publication boundaries and durable claims."""
import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet

from backend.service import Backend
from backend.tests.test_inbox import InboxScenarios


class NewcomerScenarios:
    fixtures = InboxScenarios.fixtures
    user = InboxScenarios.user
    customer = InboxScenarios.customer
    staff_request = InboxScenarios.staff_request
    draft = InboxScenarios.draft
    publish = InboxScenarios.publish

    def future_user(self, **kwargs):
        actor = self.user(**kwargs)
        with self.backend.transaction() as db:
            self.tokens[actor['id']] = self.backend.new_session(db, actor['id'], False)['token']
        return actor

    def test_same_second_accounts_before_publication_are_excluded_but_later_accounts_receive(self):
        earlier = self.user()
        with self.backend.transaction() as db:
            db.execute('UPDATE users SET created_at=? WHERE id=?', (self.now - 1, earlier['id']))
        unverified = self.user(verified=0)
        draft = self.draft(audience='newcomers', user_ids=[])
        before_publish = self.future_user()
        item = self.publish(draft)
        self.assertEqual(item['audience'], 'newcomers')
        self.assertEqual(item['recipient_count'], 0)
        with self.backend.connect() as db:
            self.assertIsNone(db.execute('SELECT user_id FROM announcement_cohort_exclusions '
                                         'WHERE announcement_id=? AND user_id=?', (item['id'], earlier['id'])).fetchone())
        after_publish = self.future_user()
        self.assertEqual(self.customer(before_publish)[1]['notifications'], [])
        self.assertEqual(self.customer()[1]['notifications'], [])
        with self.backend.transaction() as db:
            db.execute('UPDATE users SET verified=1 WHERE id=?', (unverified['id'],))
            self.tokens[unverified['id']] = self.backend.new_session(db, unverified['id'], False)['token']
        self.assertEqual(self.customer(unverified)[1]['notifications'], [])
        received = self.customer(after_publish)[1]['notifications']
        self.assertEqual([message['id'] for message in received], [item['id']])
        self.assertEqual(self.customer(after_publish)[1]['notifications'], received)

    def test_scheduled_evergreen_welcome_is_claimed_once_and_stays_presented_across_clients(self):
        item = self.publish(self.draft(audience='newcomers', user_ids=[], no_expiry=True,
                                      starts_at=self.now + 30, expires_at=None))
        self.publish(self.draft(audience='newcomers', user_ids=[], no_expiry=True,
                               starts_at=self.now + 60, expires_at=None))
        self.assertTrue(item['no_expiry'])
        person = self.future_user()
        self.assertEqual(self.customer(person)[1]['notifications'], [])
        self.now += 30
        self.assertEqual(self.customer(person)[1]['notifications'][0]['id'], item['id'])
        self.assertEqual(self.customer(person, '/presented', {'id': item['id']})[0], 200)
        presented = self.customer(person)[1]['notifications'][0]['presented_at']
        with self.backend.transaction() as db:
            # A second device has a different bearer session, the same account state.
            self.tokens[person['id']] = self.backend.new_session(db, person['id'], False)['token']
        self.assertEqual(self.customer(person)[1]['notifications'][0]['presented_at'], presented)
        self.now += 200 * 86400
        with self.backend.transaction() as db:
            self.tokens[person['id']] = self.backend.new_session(db, person['id'], False)['token']
        messages = self.customer(person)[1]['notifications']
        self.assertEqual([message['id'] for message in messages], [item['id']])
        self.assertTrue(messages[0]['active'])
        self.assertEqual(messages[0]['presented_at'], presented)

    def test_cancelled_or_expired_campaign_does_not_consume_the_account_welcome(self):
        item = self.publish(self.draft(audience='newcomers', user_ids=[]))
        person = self.future_user()
        status, _ = self.staff_request('/cancel', {'id': item['id'], 'revision': item['revision'],
                                                 'reason': 'Withdraw welcome before first open'})
        self.assertEqual(status, 200)
        self.assertEqual(self.customer(person)[1]['notifications'], [])
        self.now += 1
        active = self.publish(self.draft(audience='newcomers', user_ids=[]))
        # This account existed before the replacement campaign and is outside its cohort.
        self.assertEqual(self.customer(person)[1]['notifications'], [])
        later = self.future_user()
        self.assertEqual(self.customer(later)[1]['notifications'][0]['id'], active['id'])
        with self.backend.connect() as db:
            self.assertIsNone(db.execute('SELECT user_id FROM newcomer_welcome_claims WHERE user_id=?',
                                         (person['id'],)).fetchone())

    def test_evergreen_is_explicit_and_cannot_change_snapshot_audiences(self):
        for audience, ids in (('all', []), ('users', [self.first['id']])):
            status, _ = self.staff_request('/preview', {'title': 'No unbounded snapshot', 'body': 'Body',
                'audience': audience, 'user_ids': ids, 'no_expiry': True})
            self.assertEqual(status, 400)
        for invalid in ([], 'true', 1):
            status, _ = self.staff_request('/preview', {'title': 'Invalid flag', 'body': 'Body',
                'audience': 'newcomers', 'user_ids': [], 'no_expiry': invalid})
            self.assertEqual(status, 400)
        status, preview = self.staff_request('/preview', {'title': 'Future welcome', 'body': 'Body',
            'audience': 'newcomers', 'user_ids': [], 'no_expiry': True})
        self.assertEqual(status, 200, preview)
        self.assertEqual(preview['recipient_count'], 0)
        self.assertEqual(preview['user_ids'], [])

    def test_cancelled_evergreen_welcome_can_be_reclaimed_after_history_retention(self):
        from backend.inbox_retention import sweep_announcements
        item = self.publish(self.draft(audience='newcomers', user_ids=[], no_expiry=True))
        person = self.future_user()
        self.assertEqual(self.customer(person)[1]['notifications'][0]['id'], item['id'])
        status, _ = self.staff_request('/cancel', {'id': item['id'], 'revision': item['revision'],
                                                 'reason': 'Retire evergreen welcome'})
        self.assertEqual(status, 200)
        self.now += 91 * 86400
        with self.backend.transaction() as db:
            sweep_announcements(db, self.now)
        with self.backend.connect() as db:
            self.assertIsNone(db.execute('SELECT id FROM announcements WHERE id=?', (item['id'],)).fetchone())
            claim = db.execute('SELECT announcement_id FROM newcomer_welcome_claims WHERE user_id=?',
                               (person['id'],)).fetchone()
        self.assertIsNotNone(claim)
        self.assertIsNone(claim['announcement_id'])

    def test_expired_welcome_reclamation_keeps_the_once_per_account_claim(self):
        finite = self.publish(self.draft(audience='newcomers', user_ids=[], expires_at=self.now + 30))
        self.publish(self.draft(audience='newcomers', user_ids=[], no_expiry=True,
                               starts_at=self.now + 60, expires_at=None))
        person = self.future_user()
        self.assertEqual(self.customer(person)[1]['notifications'][0]['id'], finite['id'])
        self.now += 100 * 86400
        with self.backend.transaction() as db:
            self.tokens[person['id']] = self.backend.new_session(db, person['id'], False)['token']
        self.assertEqual(self.customer(person)[1]['notifications'], [])
        with self.backend.connect() as db:
            self.assertIsNone(db.execute('SELECT id FROM announcements WHERE id=?', (finite['id'],)).fetchone())
            claim = db.execute('SELECT announcement_id FROM newcomer_welcome_claims WHERE user_id=?',
                               (person['id'],)).fetchone()
        self.assertIsNotNone(claim)
        self.assertIsNone(claim['announcement_id'])

    def test_concurrent_first_opens_attach_one_welcome_and_erasure_clears_new_metadata(self):
        from concurrent.futures import ThreadPoolExecutor
        from backend.account_erasure import erase_in
        item = self.publish(self.draft(audience='newcomers', user_ids=[]))
        person = self.future_user()
        with ThreadPoolExecutor(max_workers=2) as workers:
            values = list(workers.map(lambda unused: self.customer(person), range(2)))
        for status, result in values:
            self.assertEqual(status, 200, result)
            self.assertEqual([message['id'] for message in result['notifications']], [item['id']])
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM newcomer_welcome_claims WHERE user_id=?',
                                        (person['id'],)).fetchone()['n'], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM announcement_recipients WHERE user_id=?',
                                        (person['id'],)).fetchone()['n'], 1)
        # A later campaign creates an exact-tie exclusion for this same account.
        self.publish(self.draft(audience='newcomers', user_ids=[]))
        with self.backend.transaction() as db:
            erase_in(self.backend, db, person['id'], self.now)
        for table in ('announcement_cohort_exclusions', 'newcomer_welcome_claims', 'announcement_recipients'):
            with self.backend.connect() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM ' + table + ' WHERE user_id=?',
                                            (person['id'],)).fetchone()['n'], 0)
        self.assertEqual(self.customer(person)[0], 401)


class NewcomerAnnouncementTests(NewcomerScenarios, unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.backend = Backend(Path(temp.name) / 'newcomers.db', deliver=lambda email, code: None)
        self.backend.cipher = Fernet(Fernet.generate_key())
        self.fixtures()


if __name__ == '__main__':
    unittest.main()
