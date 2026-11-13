# Access plans and moderation

This release uses the existing backend authority. It does not create a second
billing or moderation service, and it does not introduce a paywall.

## Current access

`backend/plans.json` is the default catalog. A newer version in `plan_catalog`
takes precedence. The three existing levels are Free, Plus and Premium.
`entitlements.resolve()` combines valid server grants and verified provider
records, applies safe feature overrides and service holds, and keeps personal
core functionality available. Every current feature is in every default tier;
`sales_enabled` remains false and prices remain null.

Public plans and the account access page now explain the intended focus of
each level and display **«Пока всё доступно бесплатно»**. The descriptions are
positioning for the future; they do not promise additional unimplemented
features or change current entitlements. Neither page contains a purchase
button, payment form, invented price or automatic subscription enrollment.

To activate paid offers later, the owner must separately approve the catalog,
prices and legal terms, configure a real provider adapter and credentials, and
verify authoritative provider events, account binding, cancellation and refund
handling. The existing adapter/reconciliation interface is a foundation, not
an active payment integration. Manual/promo access is not a purchase.

## Moderation and complaints

Staff operations remain on the separate configured Control origin, behind
the existing MFA, staff sessions, exact-origin/CSRF checks and six-role server
permission matrix. Ordinary account credentials cannot access Control.
Moderators can read account metadata and explicitly submitted support messages;
there is no private task, note or financial-record inspection or impersonation.

The existing complaint category is now selectable by a user. Support threads
open within the account page. The Control queue can filter type and state;
authorized staff can use the existing triage endpoint to set priority/state
with an audit reason. Existing ticket/message limits and credential redaction
remain in force.

Temporary account, family-write, premium and support-write restrictions reuse
the existing server handlers. The Control account card now reads the safe
`disabled_until` field from `account_state` and shows whole-account restrictions
alongside service holds. Previously that account restriction was enforced but
not returned by the detail endpoint, so its removal control was missing.
The change adds one metadata field through the existing permission-checked
query; it changes no restriction, session or data-deletion rules. Restrictions
can be lifted with a reason. Every operation remains audited and staff hierarchy
checks still prevent acting on oneself or equal/higher staff.

First-owner bootstrap and recovery remain operator-only and retain MFA.
Existing owner enrollment must be reused. Do not reset or rebootstrap a
production owner to make the UI accessible, and do not expose Control links to
ordinary customers as an authorization shortcut.

## Focused acceptance

- Plan pages describe Free/Plus/Premium, show current free availability, and
  offer no enabled purchase action. Existing resolver behavior is unchanged.
- A complaint persists with its category and replies render within settings.
- Staff filters and triage use the existing server endpoints. Unauthorized
  callers are rejected by the server.
- A whole-account restriction is visible, can be lifted with a reason, revokes
  existing sessions on application and preserves user records.
- Existing permission, private-data isolation and audit-redaction checks remain
  applicable; no broad backend rewrite or schema migration is required.
