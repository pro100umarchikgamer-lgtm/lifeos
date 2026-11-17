"""Saved expense categories extend legacy transactions without changing money rules."""
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path

from backend.service import Backend


def uid():
    return str(uuid.uuid4())


class TransactionCategoryScenarios:
    """Also runs unchanged against the disposable PostgreSQL fixture."""
    def category_operation(self, category='food'):
        return {'id': uid(), 'action': 'record.put', 'record_id': uid(),
                'revision': 0, 'kind': 'transaction', 'visibility': 'private',
                'audience': [], 'data': {'kind': 'expense', 'amount_minor': 1250,
                'currency': 'RUB', 'date': '2026-11-13', 'label': 'Lunch',
                'account_id': None, 'category': category}}

    def category_write(self, operation, actor=None):
        return self.backend.batch(actor or self.p1, self.wid, [operation])['results'][0]

    def category_record(self, rid):
        return next(row for row in self.backend.pull(self.p1, self.wid, 0)['records']
                    if row['id'] == rid)

    def test_category_roundtrip_and_legacy_edit_preserve_money_and_selection(self):
        operation = self.category_operation()
        self.assertEqual(self.category_write(operation)['status'], 'accepted')
        saved = self.category_record(operation['record_id'])
        self.assertEqual(saved['data'], operation['data'])
        legacy_data = {key: value for key, value in operation['data'].items() if key != 'category'}
        legacy_data['label'] = 'Edited by previous client'
        legacy = {**operation, 'id': uid(), 'revision': 1, 'data': legacy_data}
        self.assertEqual(self.category_write(legacy)['status'], 'accepted')
        saved = self.category_record(operation['record_id'])
        self.assertEqual(saved['data']['category'], 'food')
        self.assertEqual(saved['data']['amount_minor'], 1250)
        self.assertEqual(saved['data']['currency'], 'RUB')
        self.assertEqual(saved['data']['label'], legacy_data['label'])

    def test_category_clear_and_legacy_create_omit_null_from_response(self):
        operation = self.category_operation('transport')
        self.assertEqual(self.category_write(operation)['status'], 'accepted')
        clear = {**operation, 'id': uid(), 'revision': 1,
                 'data': {**operation['data'], 'category': None}}
        self.assertEqual(self.category_write(clear)['status'], 'accepted')
        self.assertNotIn('category', self.category_record(operation['record_id'])['data'])
        legacy = self.category_operation()
        legacy['data'].pop('category')
        self.assertEqual(self.category_write(legacy)['status'], 'accepted')
        self.assertEqual(self.category_record(legacy['record_id'])['data'], legacy['data'])

    def test_category_validation_rejects_unknown_and_structured_values(self):
        for value in ['not-a-category', '', 'FOOD', 12, True, [], {}]:
            with self.subTest(value=value):
                result = self.category_write(self.category_operation(value))
                self.assertEqual(result['status'], 'rejected')
                self.assertEqual(result['error'], 'invalid_category')
        self.assertEqual(self.backend.pull(self.p1, self.wid, 0)['records'], [])

    def test_category_uses_existing_revision_and_idempotency_contract(self):
        operation = self.category_operation()
        first = self.category_write(operation)
        self.assertEqual(first['status'], 'accepted')
        self.assertEqual(self.category_write(operation), first)
        altered_retry = {**operation, 'data': {**operation['data'], 'category': 'shopping'}}
        self.assertEqual(self.category_write(altered_retry)['error'], 'operation_conflict')
        stale = {**altered_retry, 'id': uid()}
        conflict = self.category_write(stale)
        self.assertEqual(conflict['status'], 'conflict')
        self.assertEqual(conflict['server']['data']['category'], 'food')
        self.assertEqual(self.category_record(operation['record_id'])['revision'], 1)

    def test_category_does_not_expose_private_finance_or_bypass_ownership(self):
        operation = self.category_operation()
        self.assertEqual(self.category_write(operation)['status'], 'accepted')
        self.assertEqual(self.backend.pull(self.p2, self.wid, 0)['records'], [])
        foreign = {**operation, 'id': uid(), 'revision': 1,
                   'data': {**operation['data'], 'category': 'health'}}
        self.assertEqual(self.category_write(foreign, self.p2)['error'], 'record_forbidden')
        self.assertEqual(self.category_record(operation['record_id'])['data']['category'], 'food')


class TransactionCategoryTests(TransactionCategoryScenarios, unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.mail = {}
        self.backend = Backend(Path(self.temp.name) / 'server.db',
                               deliver=lambda email, code: self.mail.update({email: code}))
        def user(email):
            value = self.backend.register(email, 'category-fixture-password')
            actor = self.backend.authenticate(value['token'])
            self.backend.verify(actor, self.mail[email])
            return self.backend.authenticate(value['token'])
        self.p1 = user('category-owner@example.test')
        self.p2 = user('category-other@example.test')
        self.wid = uid()
        self.backend.family(self.p1, {'id': uid(), 'workspace_id': self.wid,
            'action': 'workspace.create', 'kind': 'family', 'name': 'Categories'})
        invitation = self.backend.family(self.p1, {'id': uid(), 'workspace_id': self.wid,
            'action': 'invite.create', 'email': self.p2['email'], 'role': 'parent', 'profile_id': None})
        self.backend.accept(self.p2, {'id': uid(), 'invitation': invitation['invitation']})

    def test_category_sqlite_upgrade_preserves_existing_rows_and_is_repeatable(self):
        operation = self.category_operation()
        operation['data'].pop('category')
        self.assertEqual(self.category_write(operation)['status'], 'accepted')
        path = Path(self.temp.name) / 'server.db'
        with sqlite3.connect(path) as db:
            # Reproduce an existing database with the exact pre-extension table.
            columns = [row[1] for row in db.execute('PRAGMA table_info(transactions)')]
            if 'category' in columns:
                db.execute('ALTER TABLE transactions DROP COLUMN category')
        for _ in range(2):
            reopened = Backend(path)
            with reopened.connect() as db:
                row = db.execute('SELECT category,amount_minor,label FROM transactions WHERE id=?',
                                 (operation['record_id'],)).fetchone()
                self.assertIsNone(row['category'])
                self.assertEqual(row['amount_minor'], 1250)
                self.assertEqual(row['label'], 'Lunch')
                self.assertEqual(sum(c['name'] == 'category' for c in db.execute('PRAGMA table_info(transactions)')), 1)


if __name__ == '__main__':
    unittest.main()
