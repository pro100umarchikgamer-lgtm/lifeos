# Verified applications before public registration

This release adds a PostgreSQL application queue and same-origin public form.
It does not change REGISTRATION_MODE, activate Control, create customer accounts
from applications, start payments, or modify Android application data.

- `/early-access` collects email and explicit versioned consent.
- A 15-minute, hashed, one-use email capability confirms the address.
- An in-memory management capability permits status and cancellation for 24h.
  Reloading requires another verification email; no credentials go into localStorage.
- Persistent IP/email quotas, a honeypot, identical duplicate responses, strict
  Origin checks and existing JSON/body limits protect the public endpoint.
- `applications.manage` is restricted to owner/admin. Decisions are revision
  checked and audited without message bodies or invitation capabilities.
- Approval queues an encrypted transactional invitation valid for 7 days;
  account signup still requires the matching email and invitation, followed by
  the existing independent account email verification.
- Cancellation invalidates an outstanding invitation. It does not delete an
  existing account, Android database, financial record or backup.

Deployment: back up first; build a new immutable image from the verified backend
base; run append-only migration 008 with the existing production secrets; roll
API/mail only. Validate Caddyfile.early-access before reload. Keep API and Control
503 until their separate acceptance. Update the edge monitor to the new public
site contract. Rollback uses the prior image and Caddy file; migration 008 is
additive and must remain in place, with queued applications preserved.

Outstanding: owner MFA/enrollment; real invitation lifecycle with owner-controlled
credentials; multilingual web copy/email; authenticated PWA and browser/device
sync acceptance; legal operator details/backup retention disclosure. This is a
first implementation checkpoint, not a claim that the complete web platform or
all sixteen web locales are released.
