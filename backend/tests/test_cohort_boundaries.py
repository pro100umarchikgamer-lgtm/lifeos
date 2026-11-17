"""Coordinate real creation/publication order without sleeps or production hooks."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import threading
import time
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from backend.tests import test_newcomer_announcements as newcomer_fixtures


class CohortBoundaryTests(unittest.TestCase):
    setUp = newcomer_fixtures.NewcomerAnnouncementTests.setUp
    fixtures = newcomer_fixtures.NewcomerScenarios.fixtures
    user = newcomer_fixtures.NewcomerScenarios.user
    customer = newcomer_fixtures.NewcomerScenarios.customer
    staff_request = newcomer_fixtures.NewcomerScenarios.staff_request
    draft = newcomer_fixtures.NewcomerScenarios.draft
    publish = newcomer_fixtures.NewcomerScenarios.publish

    def registered_user(self, email):
        mail = {}
        self.backend.deliver = lambda address, code: mail.update({address: code})
        session = self.backend.register(email, 'cohort-valid-passphrase')
        actor = self.backend.authenticate(session['token'])
        self.backend.verify(actor, mail[email])
        actor = self.backend.authenticate(session['token'])
        self.tokens[actor['id']] = session['token']
        return actor

    def test_account_committed_while_publisher_waits_is_outside_future_cohort(self):
        draft = self.draft(audience='newcomers', user_ids=[])
        waiting, release = threading.Event(), threading.Event()
        transaction = self.backend.transaction

        @contextmanager
        def gated_transaction(*args, **kwargs):
            if threading.current_thread().name.startswith('cohort-publisher'):
                waiting.set()
                if not release.wait(10):
                    raise AssertionError('Publisher transaction was not released')
            with transaction(*args, **kwargs) as db:
                yield db

        with patch.object(self.backend, 'transaction', gated_transaction), ThreadPoolExecutor(max_workers=1, thread_name_prefix='cohort-publisher') as workers:
            future = workers.submit(self.publish, draft)
            try:
                self.assertTrue(waiting.wait(10))
                self.now += 1
                person = self.registered_user('committed-before-publication@example.test')
            finally:
                release.set()
            item = future.result(timeout=10)
        self.assertEqual(self.customer(person)[1]['notifications'], [])
        with self.backend.connect() as db:
            self.assertTrue(db.execute('SELECT 1 FROM announcement_cohort_exclusions WHERE announcement_id=? AND user_id=?',
                (item['id'], person['id'])).fetchone())

    def test_registration_waiting_in_kdf_until_after_publication_receives_welcome(self):
        import backend.service as service
        draft = self.draft(audience='newcomers', user_ids=[])
        waiting, release = threading.Event(), threading.Event()
        derive = service.hashlib.pbkdf2_hmac

        def gated_kdf(*args, **kwargs):
            if threading.current_thread().name.startswith('cohort-register'):
                waiting.set()
                if not release.wait(10):
                    raise AssertionError('Registration KDF was not released')
            return derive(*args, **kwargs)

        with patch.object(service.hashlib, 'pbkdf2_hmac', gated_kdf), ThreadPoolExecutor(max_workers=1, thread_name_prefix='cohort-register') as workers:
            future = workers.submit(self.registered_user, 'created-after-publication@example.test')
            try:
                self.assertTrue(waiting.wait(10))
                self.now += 1
                item = self.publish(draft)
            finally:
                release.set()
            person = future.result(timeout=10)
        self.assertEqual([message['id'] for message in self.customer(person)[1]['notifications']], [item['id']])

    def test_google_account_waiting_on_insertion_transaction_receives_welcome(self):
        from backend.config import Settings
        from backend.google_identity import GoogleIdentity
        from backend.tests.test_google_identity import CLIENT, SyntheticGoogle
        self.now = int(time.time())
        settings = Settings.load({'DATABASE_URL': 'postgresql://example/db', 'EMAIL_QUEUE_KEY': Fernet.generate_key().decode(),
            'RATE_LIMIT_KEY': 'x' * 48, 'SMTP_HOST': '127.0.0.1', 'SMTP_TLS': 'none', 'EMAIL_FROM': 'test@example.test',
            'GOOGLE_OAUTH_CLIENT_ID': CLIENT, 'GOOGLE_OAUTH_CLIENT_SECRET': 'synthetic-secret', 'REGISTRATION_MODE': 'open'})
        provider = SyntheticGoogle()
        google = GoogleIdentity(self.backend, settings, provider)
        request = google.start('android', 'cohort-device')
        token = provider.sign(request['nonce'])
        draft = self.draft(audience='newcomers', user_ids=[])
        waiting, release = threading.Event(), threading.Event()
        transaction = self.backend.transaction
        entered = 0

        @contextmanager
        def gated_transaction(*args, **kwargs):
            nonlocal entered
            if threading.current_thread().name.startswith('cohort-google'):
                entered += 1
                if entered == 2:
                    waiting.set()
                    if not release.wait(10):
                        raise AssertionError('Google insertion transaction was not released')
            with transaction(*args, **kwargs) as db:
                yield db

        with patch.object(self.backend, 'transaction', gated_transaction), ThreadPoolExecutor(max_workers=1, thread_name_prefix='cohort-google') as workers:
            future = workers.submit(google.finish, request['challenge'], 'android', 'cohort-device', id_token=token)
            try:
                self.assertTrue(waiting.wait(10))
                self.now += 1
                item = self.publish(draft)
            finally:
                release.set()
            session = future.result(timeout=10)
        person = self.backend.authenticate(session['token'])
        self.tokens[person['id']] = session['token']
        self.assertEqual([message['id'] for message in self.customer(person)[1]['notifications']], [item['id']])
