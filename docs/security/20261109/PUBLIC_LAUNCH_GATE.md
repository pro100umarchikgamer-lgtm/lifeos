# Public registration preparation — 9 November 2026

The 10 November final directive requires owner manual acceptance and a fresh final confirmation before opening registration. Earlier conditional authorization must not trigger automatic opening.
No owner address or bootstrap capability belongs in this public repository.
Matching an email never assigns staff authority. Owner enrollment still requires
the private single-use operator grant, verified email, password reauthentication,
TOTP confirmation and recovery-code handoff. Control remains closed meanwhile.

## Checked authentication checkpoint

`282a63f55f87671239bc95de7c0492e55063b3c3` contains the password-first protocol:

- Correct password without customer MFA establishes the usual account session.
- Correct password with MFA returns only an opaque 300-second challenge. There
  is no cookie, CSRF token or staff session before the second factor.
- Challenge hashes are stored in additive migration 010, bound to account/staff
  scope, user agent and current password/factor/authority version. Five failed
  factors exhaust a challenge; completion is atomic and single-use.
- Password resets and session revocation invalidate pending challenges. Password
  recovery also deletes old signup codes; signup confirmation cannot sign an
  already verified account in through a stale code.
- Signup has generic duplicate-address responses without a second password KDF.
  The historical `/v1/auth/register` alias now uses that same verified-signup
  flow. Explicit resend invalidates the previous code, has its own cooldown and
  shares the HTTP auth rate limit. Confirmation and Control login are also in
  the strict HTTP auth category.
- Existing Android password-plus-factor login remains supported. The retained
  APK134001 source `6acbde34f499d7c740322687416abc3aa542f9ac` was checked: its
  controller uses `/v1/auth/signup`, `/signup/confirm` and `/login`, not the old
  registration/session alias. This is source-contract evidence, not a new
  physical-device or retained-binary acceptance run.

Before publishing that checkpoint, 163 tests passed on SQLite and disposable
PostgreSQL 17 with a non-superuser role. All nine synthetic registration/MFA
browser scenarios passed, plus the existing PWA and public/Control browser
suites. No production mail, personal signup or existing APK was used by these
tests. The first local run lacked psycopg and one old HTTP assertion assumed a
401 instead of a pending 200 challenge. Dependency-complete PostgreSQL runs
passed; the assertion now also checks no cookie, no authority and rejection of
the challenge as a staff cookie. The permission checks were retained.

The checkpoint used `[skip ci]` after these checks; the next reviewed product
commit must trigger the full workflow over the combined source. A skipped run
is never a passing CI result.

## Product phase and remaining localization

The product phase simplifies the product landing/pricing/install pages and makes
the account entry lead into the same PWA. The first-space guide and initial
record actions use all 16 locale packs. Acceptance now covers editing records and the presence of
the deletion control; an intermediate edit-handler change referenced an uninitialized
dialog and was corrected back to the original valid container scope before
publication. Transitions inside a dialog retain a close control and update its
accessible heading.

In open mode, the previous-applications page leads to ordinary registration.
Its email recovery sends a new management verification only for an existing
application, preserves its decision and cannot create an application/account
for an unknown address. Existing request rows and invitations remain intact.

PWA and authentication retain 16 locales. Public marketing/legal text and much
of the existing Control UI still require complete localization; do not report
the whole website as translated into 16 languages.

## Mandatory production gates still outstanding

1. Restore access through the existing encrypted SSH key without exposing its
   passphrase. Re-read installed image, configuration, data/owner counts and
   health; do not assume an earlier inventory is current.
2. Create and verify a fresh encrypted backup; prepare tested image, Caddy,
   environment and monitor rollback. Migration 010 is additive: a rollback must
   preserve the database and old backups, not drop the new table or restore an
   older database over current records.
3. Deploy verified source with registration closed first. Verify delivery of
   actual Resend messages to owner-authorized test aliases, resend, confirmation,
   reset, MFA, account isolation, record creation and deletion grace. No raw
   passwords, tokens or codes in screenshots, URLs, Git or logs.
4. Complete private owner activation with the owner performing personal
   password/TOTP/recovery steps. Do not expose Control before authority and MFA
   are confirmed. Keep real payments disabled.
5. Confirm operator identity/contact/region, launch countries, actual storage
   location, processors/transfer basis and retention (including backups).
   Existing draft privacy/terms pages do not establish legal readiness.
6. Only after the owner completes manual acceptance and explicitly confirms public launch, apply `REGISTRATION_MODE=open` and necessary API
   routing. The existing staged app/API Caddy configuration keeps Control at
   503 and blocks operational health/metrics routes. Validate actual candidate
   Caddy configuration and HTTPS before acceptance. Do not publish DB ports.

Actual iPhone/iPad Safari, installed PWA and physical Android synchronization,
fresh production email, owner MFA, off-server backup retrieval, provider
emergency access/MFA and complete infrastructure CVE assessment remain separate
unconfirmed checks. Browser viewports do not count as physical devices.

## Legal sources checked

The applicable regions and legal status cannot be inferred from the owner's
language or the VPS address. If collecting Russian citizens' personal data,
the localization issue in Article 18(5) must be resolved; the current setup has
not established that compliance. For an EEA-directed service, transparency
requires actual controller/contact details, processing purposes/legal basis,
recipients/transfers, retention and rights. No invented operator record or a
generic consent checkbox substitutes for those facts.

- Current 152-FZ text, Ministry of Labour publication:
  https://mintrud.gov.ru/docs/laws/130
- EDPB small-business transparency FAQ:
  https://www.edpb.europa.eu/sme/find-practical-info/faq_en?page=2
- EDPB international transfers guide:
  https://www.edpb.europa.eu/sme/be-compliant/international-data-transfers_en
