"""Mail locale changes presentation only; synthetic messages are never sent."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from threading import Barrier
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from backend import mail
from backend.notification_copy import packs


class MailLocaleTests(unittest.TestCase):
    settings = SimpleNamespace(email_from='ULADIM <noreply@example.test>')

    def translated_catalog(self):
        catalog = deepcopy(packs())
        catalog['en']['strings'].update({
            'mail_subject_verify': 'ULADIM: verify your email',
            'mail_subject_recovery': 'ULADIM: account recovery',
            'mail_subject_email_change': 'ULADIM: verify your new email address',
            'mail_subject_early_verify': 'ULADIM: confirm your application',
            'mail_subject_early_invite': 'ULADIM: invitation to the closed test',
            'mail_subject_early_rejected': 'ULADIM: application decision',
            'mail_body_verify': 'Verify your email in ULADIM:\n{code}',
            'mail_body_recovery': 'Recover your account in ULADIM:\n{code}',
            'mail_body_email_change': 'Verify your email in ULADIM:\n{code}',
            'mail_body_early_verify': 'Confirm at https://getuladim.space/early-access (15 minutes):\n{code}\nNo account is created.',
            'mail_body_early_invite': 'Create an account at https://getuladim.space/account (7 days):\n{code}',
            'mail_body_early_rejected': 'No account created. Status: https://getuladim.space/early-access',
            'mail_code_single_use': 'This code can be used once.',
            'mail_unrequested': 'If you did not request this action, ignore this email.',
        })
        return catalog

    def test_selected_locale_formats_all_six_purposes_without_changing_code_or_headers(self):
        subjects = {
            'verification': 'ULADIM: verify your email',
            'recovery': 'ULADIM: account recovery',
            'email_change': 'ULADIM: verify your new email address',
            'early_verify': 'ULADIM: confirm your application',
            'early_invite': 'ULADIM: invitation to the closed test',
            'early_rejected': 'ULADIM: application decision',
        }
        with patch.object(mail, 'packs', return_value=self.translated_catalog(), create=True):
            for purpose, subject in subjects.items():
                with self.subTest(purpose=purpose):
                    result = mail.message(self.settings, 'synthetic-job', {
                        'email': 'recipient@example.test', 'code': 'SYNTHETIC-8431',
                        'purpose': purpose, 'locale': 'en',
                    })
                    self.assertEqual(str(result['Subject']), subject)
                    self.assertEqual(result['To'], 'recipient@example.test')
                    self.assertEqual(result['From'], self.settings.email_from)
                    self.assertEqual(result['Message-ID'], '<synthetic-job@lifeos-mail>')
                    self.assertEqual(result.get_content_type(), 'text/plain')
                    body = result.get_content()
                    self.assertNotRegex(body, '[А-Яа-яЁё]')
                    self.assertEqual(body.count('SYNTHETIC-8431'), purpose != 'early_rejected')
                    if purpose == 'early_verify':
                        self.assertIn('https://getuladim.space/early-access', body)
                        self.assertIn('15 minutes', body)
                    if purpose == 'early_invite':
                        self.assertIn('https://getuladim.space/account', body)
                        self.assertIn('7 days', body)

    def test_legacy_and_invalid_locales_keep_existing_russian_recovery(self):
        for locale in [None, '../en', ['en'], 'en\r\nSubject: injected']:
            payload = {'email': 'recipient@example.test', 'code': 'SYNTHETIC', 'purpose': 'recovery'}
            if locale is not None:
                payload['locale'] = locale
            result = mail.message(self.settings, 'legacy-job', payload)
            self.assertEqual(str(result['Subject']), 'ULADIM: восстановление аккаунта')
            self.assertEqual(result.get_content(), 'Введите этот код в ULADIM для восстановления аккаунта:\nSYNTHETIC\n\nКод одноразовый. Если вы не запрашивали это действие, проигнорируйте письмо.\n')

    def test_incomplete_or_corrupt_translations_cannot_drop_code_or_change_fixed_url(self):
        catalog = self.translated_catalog()
        for replacement in ['https://getuladim.space/account without a code',
                            'https://evil.example/ {code}',
                            'https://getuladim.space/account {code} {unexpected}',
                            'https://getuladim.space/account {{code}}']:
            catalog['en']['strings']['mail_body_early_invite'] = replacement
            with patch.object(mail, 'packs', return_value=catalog, create=True):
                result = mail.message(self.settings, 'fallback-job', {
                    'email': 'recipient@example.test', 'code': 'EXACT-CODE',
                    'purpose': 'early_invite', 'locale': 'en',
                })
            self.assertIn('EXACT-CODE', result.get_content())
            self.assertIn('https://getuladim.space/account', result.get_content())
            self.assertNotIn('evil.example', result.get_content())
            self.assertNotIn('{EXACT-CODE}', result.get_content())

    def test_request_locale_honors_weights_and_resets_after_exceptions(self):
        from backend.request_locale import current_locale, negotiate_locale, request_locale
        for header, expected in [
            ('fr-CA, en;q=0.5', 'fr'), ('de;q=0, en;q=0.8', 'en'),
            ('uz-Cyrl-UZ, ru;q=0.8', 'uz-Cyrl'), ('UZ-latn', 'uz-Latn'),
            ('unknown, pt-PT;q=0.4', 'pt'), ('en;q=1.5', 'ru'),
            ('en\r\nX-Test: yes', 'ru'), ('x' * 513, 'ru'),
        ]:
            self.assertEqual(negotiate_locale(header), expected, header)
        self.assertEqual(current_locale(), 'ru')
        with request_locale('fr'):
            self.assertEqual(current_locale(), 'fr')
            with self.assertRaises(RuntimeError):
                with request_locale('en'):
                    raise RuntimeError('synthetic')
            self.assertEqual(current_locale(), 'fr')
        self.assertEqual(current_locale(), 'ru')

    def test_simultaneous_requests_and_reused_thread_do_not_share_locale(self):
        from backend.request_locale import current_locale, request_locale
        barrier = Barrier(2)
        def worker(locale):
            with request_locale(locale):
                barrier.wait(timeout=5)
                selected = current_locale()
            return selected, current_locale()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, locale) for locale in ['fr', 'en']]
            self.assertEqual([f.result() for f in futures], [('fr', 'ru'), ('en', 'ru')])

    def test_queue_keeps_locale_only_inside_existing_encrypted_payload(self):
        from backend.postgres import PostgresBackend
        from backend.request_locale import request_locale
        cipher = Fernet(Fernet.generate_key())
        backend = SimpleNamespace(cipher=cipher, clock=lambda: 1700000000)
        class Queue:
            def execute(self, statement, values):
                self.statement, self.values = statement, values
        queue = Queue()
        with patch('backend.account_erasure.mail_subject', return_value=None):
            with request_locale('fr'):
                PostgresBackend._deliver(backend, queue, 'recipient@example.test', 'SYNTHETIC-CODE', 'recovery')
        encrypted = queue.values[1]
        self.assertNotIn(b'SYNTHETIC-CODE', encrypted)
        self.assertNotIn(b'recipient@example.test', encrypted)
        self.assertEqual(json.loads(cipher.decrypt(encrypted)), {
            'email': 'recipient@example.test', 'code': 'SYNTHETIC-CODE',
            'purpose': 'recovery', 'locale': 'fr',
        })
        self.assertEqual(queue.values[2:4], (1700000900, 1700000000))


if __name__ == '__main__':
    unittest.main()
