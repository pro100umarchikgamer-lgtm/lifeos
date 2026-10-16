"""One server authority for access, independent of distribution and billing.

No production purchase adapter is configured by this release. Manual access is
not a transaction, a store trial or an authorization to charge a payment card.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import uuid

from .service import canonical, identifier, require, text, token_hash

TIERS = {'Free': 0, 'Plus': 1, 'Premium': 2}
SOURCES = {'google_play', 'rustore', 'web'}
STATES = {'active', 'trial', 'cancelled', 'grace', 'hold', 'paused', 'expired', 'refunded', 'revoked'}
ACTIVE = {'active', 'trial', 'cancelled', 'grace'}


def catalog(db):
    row = db.execute('SELECT body FROM plan_catalog ORDER BY version DESC LIMIT 1').fetchone()
    return json.loads(row['body']) if row else json.loads(Path(__file__).with_name('plans.json').read_text())


def validate_catalog(value, previous):
    require(isinstance(value, dict) and set(value) == set(previous))
    require(type(value['version']) is int and value['version'] == previous['version'] + 1, 'revision_conflict', 409)
    require(value['sales_enabled'] is False, 'payments_unconfigured', 409)
    require(value['approval'] in {'closed_test_catalog_for_owner_review', 'approved_closed_test'})
    require(value['features'] == previous['features'])
    require(isinstance(value['tiers'], dict) and set(value['tiers']) == set(TIERS))
    for tier, plan in value['tiers'].items():
        require(isinstance(plan, dict) and set(plan) == {'features', 'limits', 'price'})
        require(isinstance(plan['features'], list) and len(plan['features']) == len(set(plan['features'])) and set(plan['features']) <= set(value['features']))
        require('personal_core' in plan['features'] and plan['price'] is None)
        require(isinstance(plan['limits'], dict) and set(plan['limits']) == {'shared_records'})
        limit = plan['limits']['shared_records']
        require(limit is None or (type(limit) is int and 1 <= limit <= 1000000))
    # Existing offline/personal functionality is never monetized retroactively.
    require(set(previous['tiers']['Free']['features']) <= set(value['tiers']['Free']['features']), 'existing_features_preserved', 409)


def resolve(db, uid, now):
    identifier(uid)
    c = catalog(db)
    grants = db.execute('SELECT id,tier,source,starts_at,valid_until,revoked_at,reason FROM entitlement_grants WHERE user_id=? ORDER BY starts_at DESC,id', (uid,)).fetchall()
    purchases = db.execute('SELECT source,product_id,tier,state,valid_until,trial_until FROM provider_purchases WHERE user_id=? ORDER BY updated_at DESC', (uid,)).fetchall()
    active = [dict(row, basis='grant') for row in grants if row['starts_at'] <= now and not row['revoked_at'] and (row['valid_until'] is None or row['valid_until'] > now)]
    active += [dict(row, basis='purchase') for row in purchases if row['state'] in ACTIVE and row['valid_until'] > now]
    chosen = max(active, key=lambda row: (TIERS[row['tier']], row['valid_until'] is None, row['valid_until'] or 0), default=None)
    tier = chosen['tier'] if chosen else 'Free'
    holds = {row['service']: row['until_at'] for row in db.execute('SELECT service,until_at FROM service_holds WHERE user_id=? AND until_at>?', (uid, now)).fetchall()}
    if 'premium' in holds:
        tier = 'Free'
    plan = c['tiers'][tier]
    flags = {name: name in plan['features'] for name in c['features']}
    for row in db.execute('SELECT feature,enabled,valid_until FROM entitlement_overrides WHERE user_id=?', (uid,)).fetchall():
        if row['feature'] in flags and row['feature'] != 'personal_core' and (row['valid_until'] is None or row['valid_until'] > now):
            flags[row['feature']] = bool(row['enabled'])
    flags['personal_core'] = True
    return {'tier': tier, 'catalog_version': c['version'], 'features': flags, 'limits': plan['limits'],
            'valid_until': chosen['valid_until'] if chosen else None,
            'source': chosen['source'] if chosen else None,
            'billing_managed_by': chosen['source'] if chosen and chosen['basis'] == 'purchase' else None,
            'payment_required': False, 'payments_enabled': False, 'holds': holds,
            'grants': [dict(row) for row in grants], 'purchases': [dict(row) for row in purchases],
            'duplicate_purchase_warning': any(row['state'] in ACTIVE and row['valid_until'] > now for row in purchases)}


def grant(db, uid, tier, source, valid_until, reason, actor, now):
    identifier(uid)
    require(tier in {'Plus', 'Premium'} and source in {'manual', 'promo'})
    require(valid_until is None or (type(valid_until) is int and now < valid_until <= now + 10 * 366 * 86400))
    text(reason, 500)
    require(db.execute('SELECT 1 FROM users WHERE id=?', (uid,)).fetchone() is not None, 'not_found', 404)
    gid = str(uuid.uuid4())
    db.execute('INSERT INTO entitlement_grants VALUES(?,?,?,?,?,?,0,?,?)', (gid, uid, tier, source, now, valid_until, reason, actor))
    return {'grant_id': gid, 'tier': tier, 'source': source, 'valid_until': valid_until, 'payment_created': False}


@dataclass(frozen=True)
class VerifiedPurchase:
    source: str
    reference: str
    event_id: str
    user_id: str
    product_id: str
    tier: str
    state: str
    valid_until: int
    revision: int
    trial_until: int | None = None


class ProviderAdapter:
    """Implement provider-side verification, not a client 'verified' boolean.

    Network adapters must verify a provider response and authoritative account
    binding before returning VerifiedPurchase. No HTTP route accepts this object.
    """
    source = ''
    def verify(self, notification):
        raise NotImplementedError('Provider credentials and verification are not configured')


def reconcile(backend, adapter, notification):
    require(isinstance(adapter, ProviderAdapter), 'provider_unconfigured', 503)
    event = adapter.verify(notification)
    require(isinstance(event, VerifiedPurchase) and event.source == adapter.source and event.source in SOURCES, 'provider_verification_failed', 403)
    identifier(event.user_id)
    require(event.tier in {'Plus', 'Premium'} and event.state in STATES)
    require(type(event.valid_until) is int and type(event.revision) is int and event.revision >= 0)
    require(event.trial_until is None or (type(event.trial_until) is int and event.trial_until <= event.valid_until))
    for value in [event.reference, event.event_id, event.product_id]: text(value, 512)
    digest = token_hash(canonical(event.__dict__))
    reference = token_hash(event.source + ':' + event.reference)
    with backend.transaction() as db:
        old = db.execute('SELECT * FROM provider_events WHERE source=? AND event_id=?', (event.source, event.event_id)).fetchone()
        if old:
            require(old['digest'] == digest, 'provider_event_conflict', 409)
            return json.loads(old['result'])
        prior = db.execute('SELECT * FROM provider_purchases WHERE source=? AND reference_hash=?', (event.source, reference)).fetchone()
        require(prior is None or prior['user_id'] == event.user_id, 'purchase_already_bound', 409)
        require(db.execute('SELECT 1 FROM users WHERE id=?', (event.user_id,)).fetchone() is not None, 'not_found', 404)
        applied = prior is None or event.revision > prior['revision']
        if prior and event.revision == prior['revision']:
            require(all(prior[key] == getattr(event, key) for key in ['product_id', 'tier', 'state', 'valid_until', 'trial_until']), 'provider_revision_conflict', 409)
        if applied:
            db.execute('INSERT INTO provider_purchases VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source,reference_hash) DO UPDATE SET product_id=excluded.product_id,tier=excluded.tier,state=excluded.state,valid_until=excluded.valid_until,revision=excluded.revision,trial_until=excluded.trial_until,updated_at=excluded.updated_at',
                       (event.source, reference, event.user_id, event.product_id, event.tier, event.state, event.valid_until, event.revision, event.trial_until, int(backend.clock())))
        result = {'applied': applied, 'source': event.source, 'event_id': event.event_id}
        db.execute('INSERT INTO provider_events VALUES(?,?,?,?,?,?)', (event.source, event.event_id, digest, reference, int(backend.clock()), canonical(result)))
    return result
