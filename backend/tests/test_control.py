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
    product_tiers = {'synthetic.plus': 'Plus'}
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

    def test_operator_recovery_requires_password_and_one_use_code(self):
        with self.assertRaises(Failure): self.control.recover_staff(self.p1['email'], 'wrong', self.enrollment['recovery_codes'][0])
        recovered = self.control.recover_staff(self.p1['email'], 'a-valid-long-passphrase', self.enrollment['recovery_codes'][0])
        with self.assertRaises(Failure): self.control.authenticate(self.control_token, 'test-agent')
        with self.assertRaises(Failure): self.control.recover_staff(self.p1['email'], 'a-valid-long-passphrase', self.enrollment['recovery_codes'][0])
        self.assertNotEqual(recovered['totp_secret'], self.enrollment['totp_secret'])

    def test_unique_owner_and_no_self_or_peer_escalation(self):
        with self.assertRaises(Failure): self.control.bootstrap(self.p2['email'])
        with self.assertRaises(Failure): self.control.update_staff(self.owner, self.owner.id, ['admin'], True, 1, 'not allowed')
        for role in ['support', 'auditor', 'moderator', 'billing_manager']:
            actor = StaffPrincipal('test', self.p2['id'], (role,))
            with self.assertRaises(Failure): self.control.update_staff(actor, self.owner.id, ['admin'], True, 1, 'not allowed')
        admin = StaffPrincipal('admin', self.p2['id'], ('admin',))
        with self.assertRaises(Failure): self.control.update_staff(admin, self.owner.id, ['admin'], True, 1, 'cannot demote owner')

    def test_grants_are_not_purchases_expire_and_keep_data(self):
        result = self.control.give_access(self.owner, self.p2['id'], 'Plus', 'manual', self.now + 100, 'Closed test access')
        self.assertFalse(result['payment_created'])
        with self.backend.connect() as db:
            active = resolve(db, self.p2['id'], self.now)
            self.assertEqual(active['tier'], 'Plus')
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
        self.assertEqual(self.control.user(self.owner, self.p2['id'])['user']['disabled_until'], 0)
        token = self.backend.login(self.p2['email'], 'a-valid-long-passphrase')['token']
        self.control.moderate(self.owner, self.p2['id'], 'account', self.now + 3600, 'Test abuse restriction')
        moderator = StaffPrincipal('moderator', self.p1['id'], ('moderator',))
        self.assertEqual(self.control.user(moderator, self.p2['id'])['user']['disabled_until'], self.now + 3600)
        auditor = StaffPrincipal('auditor', self.p1['id'], ('auditor',))
        with self.assertRaises(Failure): self.control.user(auditor, self.p2['id'])
        with self.assertRaises(Failure): self.backend.authenticate(token)
        self.control.moderate(self.owner, self.p2['id'], 'account', 0, 'Appeal accepted')
        self.assertEqual(self.control.user(self.owner, self.p2['id'])['user']['disabled_until'], 0)
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
        event = VerifiedPurchase('google_play', 'synthetic-reference', 'event-1', self.p2['id'], 'synthetic.plus', 'Plus', 'active', self.now + 1000, 1)
        provider = FixtureProvider()
        self.assertEqual(reconcile(self.backend, provider, event), reconcile(self.backend, provider, event))
        bound = VerifiedPurchase(**(event.__dict__ | {'event_id': 'steal', 'user_id': self.p1['id']}))
        with self.assertRaises(Failure): reconcile(self.backend, provider, bound)
        with self.backend.connect() as db:
            result = resolve(db, self.p2['id'], self.now)
            self.assertEqual(result['tier'], 'Plus')
            self.assertEqual(result['billing_managed_by'], 'google_play')
            self.assertTrue(result['duplicate_purchase_warning'])
        refund = VerifiedPurchase(**(event.__dict__ | {'event_id': 'refund', 'revision': 3, 'state': 'refunded'}))
        reconcile(self.backend, provider, refund)
        stale = VerifiedPurchase(**(event.__dict__ | {'event_id': 'late-active', 'revision': 2}))
        self.assertFalse(reconcile(self.backend, provider, stale)['applied'])
        with self.backend.connect() as db: self.assertEqual(resolve(db, self.p2['id'], self.now)['tier'], 'Free')
        altered = VerifiedPurchase(**(event.__dict__ | {'state': 'trial'}))
        with self.assertRaises(Failure): reconcile(self.backend, provider, altered)

    def test_ai_is_unavailable_for_grants_overrides_and_legacy_rows(self):
        with self.assertRaises(Failure) as blocked:
            self.control.give_access(self.owner, self.p2['id'], 'Premium', 'manual', None, 'Future AI cannot be enabled')
        self.assertEqual(blocked.exception.code, 'tier_unavailable')
        with self.assertRaises(Failure):
            self.control.override(self.owner, self.p2['id'], 'ai_assistant', True, None, 'Future AI cannot be enabled')
        with self.backend.transaction() as db:
            # Old deployments allowed Premium grants. Retain history, never
            # reinterpret those rows as proof of implemented AI functionality.
            db.execute('INSERT INTO entitlement_grants VALUES(?,?,?,?,?,?,0,?,?)',
                       ('legacy-premium', self.p2['id'], 'Premium', 'manual', self.now - 1, None, 'Legacy test', self.owner.id))
            db.execute('INSERT INTO entitlement_overrides VALUES(?,?,?,?,?,?)',
                       (self.p2['id'], 'ai_assistant', 1, None, 'Legacy test', self.owner.id))
            result = resolve(db, self.p2['id'], self.now)
        self.assertEqual(result['tier'], 'Free')
        self.assertFalse(result['features']['ai_assistant'])
        self.assertEqual(result['unavailable_tiers'], ['Premium'])
        self.assertEqual(result['purchase_actions'], [])
        self.assertTrue(all(result['features'][key] for key in ('statement_import', 'advanced_planning', 'family_sync')))
        self.assertFalse(result['payments_enabled'])

    def test_catalog_cannot_enable_sales_ai_or_remove_current_free_import(self):
        with self.backend.connect() as db: current = catalog(db)
        for mutation in ('sales', 'ai', 'premium', 'import', 'offers', 'limit'):
            updated = copy.deepcopy(current)
            updated['version'] += 1
            if mutation == 'sales': updated['sales_enabled'] = True
            if mutation == 'ai': updated['disabled_features'] = []
            if mutation == 'premium': updated['tiers']['Premium']['availability'] = 'available'
            if mutation == 'import': updated['tiers']['Free']['features'].remove('statement_import')
            if mutation == 'offers': updated['offers'] = [{'product_id': 'invented'}]
            if mutation == 'limit': updated['tiers']['Free']['limits']['shared_records'] = 1
            with self.assertRaises(Failure, msg=mutation):
                self.control.update_catalog(self.owner, updated, 'Forbidden activation fixture')
        with self.backend.transaction() as db:
            db.execute('INSERT INTO plan_catalog VALUES(?,?,?,?)', (1, json.dumps({'version': 1}), self.now, self.owner.id))
            self.assertEqual(catalog(db)['version'], current['version'])
            db.execute('INSERT INTO plan_catalog VALUES(?,?,?,?)', (99, json.dumps({'version': 99}), self.now, self.owner.id))
            upgraded = catalog(db)
        self.assertEqual(upgraded['schema_version'], 2)
        self.assertEqual(upgraded['version'], 100)
        self.assertEqual(upgraded['tiers']['Premium']['availability'], 'unavailable')
        upgraded['version'] += 1
        self.control.update_catalog(self.owner, upgraded, 'Publish compatible upgrade after legacy revisions')

    def test_provider_requires_configuration_and_server_product_mapping(self):
        with self.assertRaises(Failure) as unconfigured:
            reconcile(self.backend, ProviderAdapter(), {'verified': True, 'tier': 'Premium', 'user_id': self.p2['id']})
        self.assertEqual(unconfigured.exception.code, 'provider_unconfigured')
        event = VerifiedPurchase('google_play', 'synthetic-reference', 'unknown-product', self.p2['id'], 'unconfigured.product', 'Plus', 'active', self.now + 1000, 1)
        with self.assertRaises(Failure): reconcile(self.backend, FixtureProvider(), event)
        ai = VerifiedPurchase(**(event.__dict__ | {'tier': 'Premium'}))
        with self.assertRaises(Failure) as unavailable: reconcile(self.backend, FixtureProvider(), ai)
        self.assertEqual(unavailable.exception.code, 'tier_unavailable')
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM provider_events').fetchone()['n'], 0)

    def test_purchase_lifecycle_expiry_cancellation_restore_and_hold(self):
        event = VerifiedPurchase('google_play', 'synthetic-life', 'active-1', self.p2['id'], 'synthetic.plus', 'Plus', 'active', self.now + 100, 1)
        for revision, state, expected in ((1, 'active', 'Plus'), (2, 'cancelled', 'Plus'), (3, 'hold', 'Free'), (4, 'active', 'Plus'), (5, 'paused', 'Free'), (6, 'grace', 'Plus'), (7, 'revoked', 'Free')):
            value = VerifiedPurchase(**(event.__dict__ | {'event_id': f'lifecycle-{revision}', 'revision': revision, 'state': state}))
            reconcile(self.backend, FixtureProvider(), value)
            with self.backend.connect() as db:
                self.assertEqual(resolve(db, self.p2['id'], self.now)['tier'], expected, state)
                self.assertEqual(resolve(db, self.p2['id'], self.now + 100)['tier'], 'Free')
        self.control.give_access(self.owner, self.p2['id'], 'Plus', 'manual', self.now + 1000, 'Hold fixture')
        self.control.moderate(self.owner, self.p2['id'], 'premium', self.now + 500, 'Temporary access hold')
        with self.backend.connect() as db:
            held = resolve(db, self.p2['id'], self.now)
        self.assertEqual(held['tier'], 'Free')
        self.assertIsNone(held['source'])
        self.assertIsNone(held['valid_until'])


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
