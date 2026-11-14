# Subscription foundation: free preview release

This release supports a **free app launch**, not paid subscriptions. No paid
service, merchant account, third-party AI API, checkout or purchase SDK is
installed or invoked. The app requests no payment details. Prices and official
store product identifiers have not been supplied and are deliberately absent.

## Catalog and availability

The bundled catalog is revision 2 with `schema_version=2`. A stored compatible
catalog supersedes it only at the same or a newer revision. An old schema is
projected into this release's safe shape at a revision greater than its saved
revision, even after repeated old owner edits; it cannot hide the release gates.
The owner can publish a newer compatible catalog through the existing audited
Control handler. Sales, offers and activation of Premium remain blocked in
server code as well as catalog validation.

| Tier | Current status | Current access |
| --- | --- | --- |
| Free | Available | Every existing personal, family, chart, personalization, import and planning feature |
| Plus | Preview | The same currently implemented import and planning tools, available free; no promise of an exclusive unimplemented tool |
| Premium | Unavailable | Future AI assistance; no AI request, API key, model, endpoint or entitlement is enabled |

The structure takes inspiration from the separation between core planning,
additional import/planning tools and future AI assistance in planning apps.
It does not copy another product's price, billing period or feature claims.
`statement_import` and `advanced_planning` now have explicit entitlement names;
both are part of Free and keep the existing tools accessible.

`DISABLED_TIERS` and `DISABLED_FEATURES` in `backend/entitlements.py` are release
gates. Premium grants, purchases and AI overrides fail closed. Legacy Premium
rows remain in history but cannot activate Premium or AI. Current Free features
cannot be removed by a catalog change or access override. Service/account
moderation retains its existing authority.

`GET /account/api/plans` returns the versioned catalog. Existing authenticated
`/account/api/entitlements` and `/v1/account/entitlements` responses additionally
include `catalog`, `phase`, `evaluated_at`, `unavailable_tiers`,
`disabled_features`, empty `purchase_actions` and explicit provider readiness.
The user identifier continues to come from the authenticated server principal;
there is no endpoint accepting a user-chosen tier or a `verified=true` receipt.

Native Access renders the three levels without purchase, restore or manage
payment buttons. It shows Premium unavailable even with legacy/spoofed Premium
data. After an offline failure or while refreshing, it does not claim that a
cached Plus entitlement is currently verified. The existing offline local tools
remain available. Copy is supplied in all 16 shipped locales.

## Provider boundary and lifecycle

`ProviderAdapter.verify` returns a controlled `provider_unconfigured` error;
it is not a production store integration. No network store verifier is claimed.
`provider_readiness()` states that verification, purchase and restore are
unconfigured for Google Play, RuStore and web. Supplying an environment secret
alone cannot enable checkout.

A future trusted adapter must fetch and validate provider-authoritative state,
verify package/application identity and the exact server-owned product mapping,
bind the purchase to the authenticated account using the provider's supported
account binding, and return `VerifiedPurchase`. The injected internal adapter
contract requires an exact product-to-tier allowlist. Never fill that map from
a client request. `VerifiedPurchase` is not accepted from an HTTP caller.

The existing reconciliation transaction records a provider event once, checks
replay digests, prevents re-binding a provider reference to another account,
and applies only a newer authoritative revision. Conflicting equal revisions
are rejected. A late activation cannot overwrite a newer refund. Purchase
references are hashed before storage. Active/trial/cancelled/grace access ends
at its authoritative period end; hold/paused/refunded/revoked/expired do not
confer access. Cancellation preserves an already-paid period; restore means
re-verifying the same provider record, not creating another grant. A service
hold resolves to Free without falsely reporting a purchase as its access basis.
These mechanisms are exercised with **synthetic trusted test adapters only**.

## Before any paid activation

This work makes the disabled state explicit; it does not bypass these external
requirements or characterize unpaid tests as successful sandbox purchases.

1. The operator supplies legal merchant identity, store developer access,
   approved markets, subscription terms and support/refund information.
2. The operator creates actual products/base plans/offers in the intended
   Google Play and/or RuStore console and approves prices and billing periods.
   Display localized prices from official store product data, not this JSON.
3. Implement the official store billing SDK for the actual distribution build
   and the matching server API verifier/notification verifier. Configure least
   privilege credentials through the secret environment, never chat or source.
4. Exercise store sandbox purchase, pending/payment failure, account binding,
   token replay, cancellation, grace/hold, renewal, expiry, restore, refund and
   revocation end to end. Fulfill provider acknowledgement requirements and
   server-notification delivery/retry rules. Preserve restore/refund processing
   when new sales are disabled. No real purchase is authorized by this task.
5. Review the catalog and activation code as a separate release. Premium still
   requires a working, reviewed AI feature and an explicit future decision;
   creating a store SKU or issuing a manual grant cannot activate it now.

Official implementation references to re-check during that activation:

- Google Play Billing integration and subscriptions:
  https://developer.android.com/google/play/billing/integrate
  https://developer.android.com/google/play/billing/lifecycle/subscriptions
- Google Play server subscription authority:
  https://developers.google.com/android-publisher/api-ref/rest/v3/purchases.subscriptionsv2/get
- Google Play real-time developer notifications:
  https://developer.android.com/google/play/billing/rtdn-reference
- RuStore developer documentation and official SDK documentation:
  https://www.rustore.ru/help/developers
  https://www.rustore.ru/help/sdk

No policy-specific payment exception, external checkout permission or merchant
eligibility has been assumed. The free release has no enabled digital purchase.
