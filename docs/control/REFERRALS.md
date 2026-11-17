# Referral foundation

This release records a verified customer's explicit, one-time attribution. It does
not change signup, OAuth, entitlements, sales, rewards or payouts. A query parameter
only prefills a client form; attribution requires the current verified customer's
same-origin CSRF-protected POST. Never carry an in-flight claim across accounts.

## Customer API

`GET /account/api/referrals?offset=0` returns only:

```json
{
  "confirmed_count": 1,
  "invite": {"code": "43-character-opaque-code", "url": "https://getuladim.space/app?ref=..."},
  "people": [{"display_name": "Умар U."}],
  "next_offset": null
}
```

`invite` is null until `POST /account/api/referrals/code {}` creates it. Repeating
that POST returns the same code. Codes are random, public sharing identifiers,
not authentication credentials. The list has at most50 nonclickable short labels;
pagination uses a number, not an encoded user identifier. `offset` is0..100000.
No invited customer's ID, email, activity, purchase, profile URL or detailed status
is returned. Customer queries cannot select another account.

`POST /account/api/referrals/claim {"code":"..."}` returns
`{"status":"confirmed"}`. Same-code replay is idempotent. Self-attribution and
invalid/inactive/unverified referrers are rejected. Another referrer is409
`referral_already_attributed`. This is a confirmed relationship, not evidence of
a new signup, a visit, a payment or causation.

`GET /account/api/referrals/alias` returns the caller's own `display_name`.
`POST /account/api/referrals/alias` accepts exactly:

```json
{"first_name":"Умар","surname_initial":"U"}
```

The interface must clearly label this optional consent: **«Имя для пригласившего»**.
Only a short first name and optional one-letter initial are stored as `Умар U.`;
full surname is neither accepted nor stored. No name is derived from email or
Google profile data. Empty strings clear the alias. The fallback is «Участник».
Names must render as plain, nonclickable text, never links/HTML.

## Control API

`GET /control/api/referrals` requires `referrals.read`, granted only to the existing
owner/admin roles. Existing browser admission, MFA, staff session and authorization
continue to apply. Support, moderator, billing manager, auditor and customers are
denied. There is no new staff role grant or public referral lookup.

Optional filters: `referrer=UUID`, `activity=active|inactive`, `converted=yes|no`,
`before=confirmed_at:invitee_UUID`. Each query key accepts exactly one value.
The response has `counts:{confirmed,active,inactive,purchase_converted}`, up to50
`edges:[{referrer_id,invitee_id,confirmed_at,activity,purchase_converted}]`, and
`next_before`. Counts use the referrer filter; activity/converted/cursor filter the
page so the totals remain comparable. Graph IDs may link only to the existing
permission-protected Control user view.

Activity means an existing nonrevoked device last_seen within30 days. Moderation
labels are not substituted for that observed time. No IP, browsing event, page view
or new tracking is collected.
Record changes have no timestamps and are not misrepresented as recent activity.

Purchase conversion conservatively requires Google Play/RuStore authoritative
purchase state (`active`/`cancelled` with remaining validity and no current trial),
a matching applied provider event, and an update after referral confirmation.
Manual/promo access, web/invoice records, trial/grace/hold/paused/expired/refunded/
revoked state and provider rows without authoritative events do not count. This is
not a revenue/paid-amount report. Current production billing adapters are not
configured; `purchase_conversion_available`, `sales_enabled`, `rewards_enabled`
and `payouts_enabled` remain false. No purchase or entitlement is created here.

## Erasure and persistence

Migration020 and the SQLite schema create `referral_codes`, `referral_aliases` and
`referral_attributions`. Attribution is serialized in the existing backend
transaction and has one primary-key slot per invitee, plus a self-reference check.

Canonical account erasure deletes the subject's code, alias and incoming
attribution; outgoing links lose the deleted referrer UUID and relationship
timestamp. Only the remaining invitee's consumed slot stays, preventing
later re-attribution without retaining the deleted referrer's identifier. It is
not listed or counted in any graph. Erasing that invitee removes the slot too.
Referral codes/aliases are not copied into the immutable Control audit chain.

Tests use only disposable SQLite/guarded lifeos_test PostgreSQL and synthetic
users/provider receipts. They cover actual Web authentication/CSRF, role scope,
cross-user payload/query rejection, alias privacy, idempotence, re-attribution,
erasure, bounded pagination and store/manual/invoice/trial distinctions.
