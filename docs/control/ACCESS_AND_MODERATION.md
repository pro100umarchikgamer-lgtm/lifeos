# Access plans and moderation

This release uses the existing backend authority. It does not create a second
billing or moderation service, and it does not introduce a paywall.

## Current access

`backend/plans.json` is the bundled version-2 free-preview catalog. A saved
catalog in the current schema takes precedence only at the same or a newer
revision. Legacy schema revisions are safely projected forward. Free preserves
all current personal, family, import and planning tools. Plus is a preview of
the import/planning tier and has the same actual access during this phase.
Premium is reserved for future AI and is technically unavailable. Sales remain
disabled, offers are empty and prices are unset.

The central resolver ignores legacy Premium grants and purchases when deciding
access and always reports AI disabled. Premium grants, reconciliation, catalog
activation and AI overrides are blocked on the server. Current Free features
cannot be removed through a catalog change or generic feature override. Existing
account/service moderation stays separate. No account or user record is deleted
by a change in entitlement.

Public plans and native Access explain current free availability and future AI
without purchase actions or invented prices. The native client also refuses to
show Premium as active, and does not claim cached access is verified after an
offline error. See [SUBSCRIPTION_FOUNDATION.md](SUBSCRIPTION_FOUNDATION.md) for
the catalog/API contract, tested lifecycle and the exact external activation
requirements. Provider adapters, merchant configuration and successful store
sandbox evidence are not part of this free release. Manual/promo access is not
a purchase.

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
  offer no purchase action. Premium/AI remains disabled on both server and client.
- A complaint persists with its category and replies render within settings.
- Staff filters and triage use the existing server endpoints. Unauthorized
  callers are rejected by the server.
- A whole-account restriction is visible, can be lifted with a reason, revokes
  existing sessions on application and preserves user records.
- Existing permission, private-data isolation and audit-redaction checks remain
  applicable; no broad backend rewrite or schema migration is required.
