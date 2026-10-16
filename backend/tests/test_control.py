import copy
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet
from backend.control import Control, StaffPrincipal, ROLE_PERMISSIONS, totp
from backend.entitlements import ProviderAdapter, VerifiedPurchase, catalog, reconcile, resolve
from backend.service import Backend, Failure


class FixtureProvider(ProviderAdapter):
    source = 'google_play'
    def verify(self, event):
        return event


class ControlScenarios:
    def setup_control(self):
        self.control = Control(self.backend)
        self.enrollment = self.control.bootstrap(self.p1['email'])
        self.now = int(self.backend.clock())
        self.backend.clock = lambda: self.now
        session = self.control.login(self.p1['email'], 'a-valid-long-passphrase', totp(self.enrollment['totp_secret'], self.now // 30), 'test-agent')
        self.control_token = session['token']
        self.owner = self.control.authenticate(session['token'], 'test-agent')

    def test_totp_rfc6238_and_staff_session_fail_closed(self):
        # RFC 6238 SHA-1 vector at 59 seconds, reduced to six digits.
        self.assertEqual(totp('GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ', 1), '287082')
        with self.assertRaises(Failure): self.control.login(self.p1['email'], 'a-valid-long-passphrase', totp(self.enrollment['totp_secret'], self.now // 30), 'test-agent')
        with self.assertRaises(Failure): self.control.authenticate(self.control_token, 'different-agent')
        self.now += 901
        with self.assertRaises(Failure): self.control.authenticate(self.control_token, 'test-agent')

    def test_unique_owner_and_no_self_or_peer_escalation(self):
        with self.assertRaises(Failure): self.control.bootstrap(self.p2['email'])
        with self.assertRaises(Failure): self.control.update_staff(self.owner, self.owner.id, ['admin'], True, 1, 'not allowed')
        for role in ['support', 'auditor', 'moderator', 'billing_manager']:
            actor = StaffPrincipal('test', self.p2['id'], (role,))
            with self.assertRaises(Failure): self.control.update_staff(actor, self.owner.id, ['admin'], True, 1, 'not allowed')
        admin = StaffPrincipal('admin', self.p2['id'], ('admin',))
        with self.assertRaises(Failure): self.control.update_staff(admin, self.owner.id, ['admin'], True, 1, 'cannot demote owner')

    def test_grants_are_not_purchases_expire_and_keep_data(self):
        result = self.control.give_access(self.owner, self.p2['id'], 'Premium', 'manual', self.now + 100, 'Closed test access')
        self.assertFalse(result['payment_created'])
        with self.backend.connect() as db:
            active = resolve(db, self.p2['id'], self.now)
            self.assertEqual(active['tier'], 'Premium')
            self.assertEqual(active['purchases'], [])
            self.assertIsNone(active['billing_managed_by'])
            self.assertEqual(resolve(db, self.p2['id'], self.now + 101)['tier'], 'Free')
        self.control.revoke_access(self.owner, result['grant_id'], 'Access ended')
        with self.backend.connect() as db:
            self.assertEqual(resolve(db, self.p2['id'], self.now)['tier'], 'Free')
            self.assertIsNotNone(db.execute('SELECT id FROM users WHERE id=?', (self.p2['id'],)).fetchone())

    def test_role_permission_matrix_and_no_private_content(self):
        for role, permissions in ROLE_PERMISSIONS.items():
            actor = StaffPrincipal('test', self.p2['id'], (role,))
            for permission in {'users.read', 'plans.grant', 'users.moderate', 'staff.manage', 'plans.catalog', 'audit.read'}:
                if permission in permissions:
                    self.control.require(actor, permission)
                else:
                    with self.assertRaises(Failure): self.control.require(actor, permission)
        result = self.control.user(self.owner, self.p2['id'])
        self.assertEqual(set(result), {'user', 'devices', 'entitlements'})
        self.assertNotIn('password_hash', result['user'])
        self.assertNotIn('records', result)

    def test_bans_revoke_sessions_without_deleting_records(self):
        token = self.backend.login(self.p2['email'], 'a-valid-long-passphrase')['token']
        self.control.moderate(self.owner, self.p2['id'], 'account', self.now + 3600, 'Test abuse restriction')
        with self.assertRaises(Failure): self.backend.authenticate(token)
        self.control.moderate(self.owner, self.p2['id'], 'account', 0, 'Appeal accepted')
        result = self.backend.login(self.p2['email'], 'a-valid-long-passphrase')
        self.assertEqual(self.backend.authenticate(result['token'])['id'], self.p2['id'])
        with self.assertRaises(Failure): self.control.moderate(self.owner, self.p1['id'], 'account', self.now + 3600, 'Cannot ban owner')

    def test_append_only_audit_and_versioned_three_tier_catalog(self):
        with self.backend.connect() as db: before = catalog(db)
        after = copy.deepcopy(before)
        after['version'] += 1
        self.control.update_catalog(self.owner, after, 'Review closed test catalog')
        invalid = copy.deepcopy(after)
        invalid['version'] += 1
        invalid['tiers']['Family'] = invalid['tiers']['Premium']
        with self.assertRaises(Failure): self.control.update_catalog(self.owner, invalid, 'fourth tier forbidden')
        with self.backend.transaction() as db:
            with self.assertRaises(Exception): db.execute('DELETE FROM control_audit')
        events = self.control.audit_log(self.owner)['events']
        self.assertTrue(events)
        self.assertNotIn(self.control_token, json.dumps(events))
        self.assertNotIn(self.enrollment['totp_secret'], json.dumps(events))

    def test_provider_replay_binding_out_of_order_refund_and_cross_store(self):
        event = VerifiedPurchase('google_play', 'synthetic-reference', 'event-1', self.p2['id'], 'premium.month', 'Premium', 'active', self.now + 1000, 1)
        provider = FixtureProvider()
        self.assertEqual(reconcile(self.backend, provider, event), reconcile(self.backend, provider, event))
        bound = VerifiedPurchase(**(event.__dict__ | {'event_id': 'steal', 'user_id': self.p1['id']}))
        with self.assertRaises(Failure): reconcile(self.backend, provider, bound)
        with self.backend.connect() as db:
            result = resolve(db, self.p2['id'], self.now)
            self.assertEqual(result['tier'], 'Premium')
            self.assertEqual(result['billing_managed_by'], 'google_play')
            self.assertTrue(result['duplicate_purchase_warning'])
        refund = VerifiedPurchase(**(event.__dict__ | {'event_id': 'refund', 'revision': 3, 'state': 'refunded'}))
        reconcile(self.backend, provider, refund)
        stale = VerifiedPurchase(**(event.__dict__ | {'event_id': 'late-active', 'revision': 2}))
        self.assertFalse(reconcile(self.backend, provider, stale)['applied'])
        with self.backend.connect() as db: self.assertEqual(resolve(db, self.p2['id'], self.now)['tier'], 'Free')
        altered = VerifiedPurchase(**(event.__dict__ | {'state': 'trial'}))
        with self.assertRaises(Failure): reconcile(self.backend, provider, altered)


class ControlTests(ControlScenarios, unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.mail = {}
        self.backend = Backend(Path(folder.name) / 'control.db', deliver=lambda e, c: self.mail.update({e: c}))
        self.backend.cipher = Fernet(Fernet.generate_key())
        self.p1, self.p2 = self.user('owner@example.test'), self.user('user@example.test')
        self.setup_control()

    def user(self, email):
        result = self.backend.register(email, 'a-valid-long-passphrase')
        actor = self.backend.authenticate(result['token'])
        self.backend.verify(actor, self.mail[email])
        return self.backend.authenticate(result['token'])
