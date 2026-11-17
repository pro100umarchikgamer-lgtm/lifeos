# Account privacy release contract — 2026-11-13

This change is limited to account authentication, deletion, restoration suppression,
notification delivery and security metadata. It does not enable payments, analytics,
new provider scopes, automatic family closure or production data deletion.

## Customer flows

Web retains `/account/api/deletion`, `cancel-deletion`, `transfer`, and
`accept-transfer`. Native retains `/v1/account/lifecycle/` followed by those names.

Deletion status adds `has_password`, `google_linked`, `mfa_required`,
`staff_offboarding_required`, `grace_seconds:86400`, and `cancel_available`.
Web additionally computes `google_reauth_available` from actual OAuth configuration.
Native can use the existing Google account status/config endpoints. Family blockers
include `workspace_revision`, `eligible_parent_id`, `eligible_parent_label`,
`pending_until`, and `close_family_available:true`.

A password user supplies `password`. A linked Google user can instead use:

1. Web `POST /account/api/google/reauth/start {}` with its existing account cookie,
   same-origin and CSRF. Redirect to the returned authorization URL. Existing
   callback and `google/complete` return `{reauth_token,expires_in:300}` without
   replacing the customer session. Native uses authenticated
   `POST /v1/auth/google/reauth/start {}`; existing native chooser consumes
   `{challenge,nonce,client_id}`, and existing `/v1/auth/google/finish` returns the
   proof rather than a new login.
2. Supply `reauth_token` in the lifecycle mutation. It is valid for five minutes,
   single use, and bound to the originating active session, linked Google subject,
   and current credential/MFA version. No email-based linking occurs. A failed
   Google verification consumes its nonce challenge. Tokens stay in client memory.
3. Both primary methods still require `code` when customer MFA is enabled. TOTP
   counters and recovery codes keep existing single-use rules. Proofs cannot sign
   in, change Google links, disable MFA or grant Control authority.

Deletion requires `confirmation:'DELETE'`. Cancellation is accepted strictly before
`due_at`; after that point a short serialized preflight moves the account into
`erasing`, blocks sign-in/mutations, and begins erasure. Independent acknowledgment
failures keep that state retryable and never report completion. A live family creator must transfer to
another active parent and await the recipient's separate authenticated acceptance,
or explicitly close the family. `POST close-family` takes `workspace_id`, `revision`,
`confirmation:'CLOSE FAMILY'`, and the same primary/MFA fields. It uses existing
`workspace.dissolve` semantics: every membership becomes inactive, the family closes,
and other members' accounts and record payloads are preserved. Closing is never an
implicit part of requesting account deletion. Each mutation needs a fresh proof.

Active staff cannot request deletion until secure operator offboarding. An owner
must arrange a verified emergency administrative successor through the separate
operator process; this release neither grants an owner role nor silently removes
staff authority. The deletion UI must explain that action rather than offering an
inoperative delete button.

## Actual erasure and shared financial history

At the due worker transaction, all records owned by the deleting user lose their
payloads, including private, shared and previously soft-deleted recovery contents.
Record UUID tombstones, revisions and sync changes remain. The account loses its
original email, rate-limit email hashes, creation time, verification flag, password,
Google subject, MFA/recovery factors, session/access/refresh tokens and device data.
Inbox, push subscriptions/deliveries, admissions, restore grants, operations,
provider links/events, entitlements/holds, support contributions, pending email
changes, invitations and early-access/setup capabilities are cleared. Linked child
profiles lose names and permissions. Current creator-owned workspace names are
scrubbed; transferred families retain their current owner's shared workspace name.
The user UUID and deletion/restore-suppression timestamp remain for references.

Other participants' own record UUIDs, amounts, currencies, dates and text remain.
Their nullable transaction account and request movement links are detached, with
new canonical revisions and sync changes. A transfer's non-null account reference
can retain an **immutable deleted** generic account shell: UUID and currency only
in the API, generic database name, zero opening balance. It cannot be edited,
restored, selected for new entries or counted as an active account. Its tombstone
has `data:{}`, `structural_reference:true`, `reference_currency:'USD'` (example),
`deleted:1`, and `editable:false`. Returned erased-owner tombstones additionally carry
`privacy_erased:true` so clients can distinguish irreversible account erasure from
ordinary soft deletion and discard corresponding queued payloads. Private revoked
grant IDs are not globally disclosed; an ordinary epoch change alone is not proof
that every absent queued item should be destroyed. Currency metadata is available only through the
normal account ACL or a readable surviving transfer reference. Both sync protocols
carry it; an access epoch reset removes old mirrored content.

**Shared aggregate balances can change because the erased owner's contributions
and opening balances are removed.** Keeping another participant's original amounts
does not promise identical derived account balances. No peer financial records are
cloned, reassigned or silently rewritten to invent balancing transactions.

Local Android/offline files and copies previously exported or received by another
participant are not remotely erased. Necessary account and user-entered data are
processed for the service. No new analytics SDK or telemetry is introduced.

## Independent restore suppression and encrypted archives

`ACCOUNT_ERASURE_LEDGER` identifies a persistent private regular file outside
database backup archives. A local file alone cannot survive rollback of the whole
host; production additionally requires `ACCOUNT_ERASURE_ACK_SOCKET` and independently
durable, encrypted off-host truth confirmed by its root-owned service. Each JSONL line contains exactly:

```json
{"user_id":"00000000-0000-4000-8000-000000000001","erased_at":1794571200}
```

No original email or identifying email hash is written. The operator explicitly
creates the file once, mode 0600 and writable by service UID 10001. Runtime never
recreates a missing file, follows a symlink, accepts broad permissions, truncates
or overwrites it. Append uses an exclusive filesystem lock, one append write and
`fsync`, followed by matching independent durability acknowledgment, before the
erasure transaction commits. The acknowledgment roundtrip holds only the subject
lock; it does not hold the global ordered-sync mutation lock. Reads use a shared lock and merge
duplicate UUIDs by greatest timestamp. Failure prevents completion rather than
silently losing suppression. A precommit ledger entry is conservatively reapplied
if the database transaction later fails. Repeated acknowledgment failures reuse the
existing UUID intent timestamp without appending duplicate journal lines.

Both API and mail worker first ask the configured Unix service to synchronize
off-host truth into the local ledger, then load and apply that ledger before
serving or processing work. The protocol sends only `{action:"synchronize"}` at
startup and `{action:"acknowledge",user_id,erased_at}` before destruction. Completion
requires `{acknowledged:true,user_id,erased_at}` with matching UUID and a timestamp
at least as recent. Startup synchronization additionally returns the exact integer
`ledger_bytes` prefix durably confirmed while the root service holds the file lock;
the app validates its range/newline boundary and applies only that prefix. Later
concurrent appends cannot be mistaken for acknowledged erasures. Missing or malformed
confirmed-prefix metadata fails startup closed. A configured missing/unresponsive socket fails closed. No remote
credential is delivered to the app. The separately reviewed production adapter must
mandate both ledger and ACK configuration; optional local test mode is not a
disaster-independent production guarantee. A missing/malformed configured ledger fails startup closed.
Restoration is an offline operator procedure: preserve the independent ledger,
restore to a disconnected database, migrate through 019, apply the ledger, verify
erasure, then start any API or worker. The runtime check remains an additional gate.

```sh
python -m backend.account_erasure export-ledger --ledger /run/uladim-privacy/erasure-ledger.jsonl
python -m backend.account_erasure apply-ledger --ledger /run/uladim-privacy/erasure-ledger.jsonl
python -m backend.account_erasure legacy-audit-inventory
```

Export is a monotonic merge into an **existing** independent file. These commands
use configured `DATABASE_URL`; apply is destructive and belongs only in the reviewed
operator restoration procedure. No production deletion or archive removal was run
while implementing/testing this change. Old encrypted archives are not instantly
erased. Root selected a seven-day archive bound for the separate operator policy; that
policy and operational verification must actually be applied before public copy
claims the bound. No archive retention period is enforced by this backend code.

A final per-account delivery lock and fresh authorization check serialize SMTP and
push sends with account erasure. A previously leased job cannot start a new send
after committed erasure. PostgreSQL provider delivery does not hold the global sync
mutation lock; a busy subject leaves its deletion job pending for a later tick.
A push/mail message already accepted by an external provider cannot be recalled.
Separately received support email and the provider's independent technical/mailbox
copies need their own verified retention/deletion process; clearing app support
threads does not itself delete an external support mailbox.

## Security audit minimization and legacy boundary

New immutable Control events contain structured action reason codes, pseudonymous
UUIDs/timestamps and minimized diffs. Detailed staff rationale is separately
redacted for emails, phone numbers, JWTs and opaque/labeled secrets, encrypted in
`control_audit_notes`, and erased with a related subject/actor or after 90 days.
Flag-change previews retain their rationale only as encrypted proposal content for
a ten-minute approval window; committing consumes the proposal immediately, and
used/expired proposals are physically removed by the same worker sweep. Erasing a
former staff account also removes its proposals.
The worker physically expires notes and auth/OAuth metadata at most every 15 minutes
while healthy. Minimized immutable security events have no automatic expiry in this
release. Support and financial bodies are not put in those events.

Existing append-only audit rows are not rewritten or silently deleted. Migration
019 adds a metadata `format_version` default of1; only new minimized events are
version2, so a historical freeform reason starting with `event.` cannot evade the
legacy inventory gate. The aggregate
inventory command reports `security_events`, `legacy_freeform_events`,
`legacy_deleted_accounts`, and `legacy_deleted_owned_payloads` only. Nonzero legacy
freeform or payload counts require a separately reviewed remediation before claiming
that historical erasures or historical freeform security data satisfy this policy.
Migration 019 does not silently erase old families. A possible future legacy
compaction must verify the existing chain, preserve its terminal digest as an
explicit anchor, retain only reviewed minimal event metadata, and deliberately
destroy raw freeform content with a documented loss of full historical replay.
That operation is not authorized or implemented by this migration.

## Evidence

`backend/tests/test_account_privacy.py` runs against disposable SQLite and the
explicitly guarded `lifeos_test` PostgreSQL database. It exercises nonce/signature
validation through the existing synthetic RSA provider, actual WSGI web roundtrip,
passwordless start/cancel/complete, MFA and session/version/subject binding,
sole-parent/child explicit closure, all-owned data erasure with cross-currency peer
transfers, immutable structural tombstones and cursors, restore suppression,
capability/provider cleanup, encrypted-note erasure/expiry, and leased notification
races. Other targeted lifecycle/recovery/Google/push/Control checks cover existing
behavior. No real Google account, SMTP recipient, payment, production row or backup
archive is used by these fixtures.

Source review: native Google Credential Manager supplies only nonce-bound identity
credentials; web requests only `openid email`. Tokens and authorization codes are
not persisted by `google_identity.py`. The backend logs exception classes only;
Gunicorn access logs go to `/dev/null`, the checked Caddy configuration has no access
logging block, and PostgreSQL uses `log_statement=none`. Google and push/SMTP
providers still process requests under their own service operation; this is not a
claim that an external provider collects no technical data.
