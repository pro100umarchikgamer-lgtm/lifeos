# ULADIM online-first PWA checkpoint

The `/app` shell uses the existing `__Host-uladim_account` HttpOnly session,
CSRF and backend services. There is no second identity or database. Browser writes
use the same UUID/revision operations and incremental pull protocol as Android.

Implemented: tasks and completion, searchable notes, accounts, income/expenses,
transfers and budget definitions, per-currency totals, three chart modes and three
palettes, light/dark/system appearance; family creation, email-bound invitations,
child profiles and permissions, participant/invitation revocation; signup by
invitation, verification, recovery, customer MFA, devices, password/email changes,
reversible deletion requests, plan status and support threads. Payments remain
unavailable. First-owner activation requires a locally issued, 24-hour capability,
a verified customer account, password reauthentication and confirmed TOTP.

The 16 web catalogs are built from Android's authoritative language files, with
explicitly translated web-only messages. Unknown backend errors use a localized
generic message. Do not expose raw backend codes to users.

`localStorage` contains only language/theme/palette/chart preferences. Records,
sessions, CSRF, drafts and enrollment material are not persisted there. The service
worker has an exact static-asset allowlist and never caches account, sync or
Control responses. Offline navigation displays a localized connection page.
There is no offline mutation queue or claim of full offline synchronization.
A lost sync response preserves the same operation UUID for a safe retry; stale
revisions are reported, and overwriting is not automatic.

The financial overview uses integer minor units and keeps currencies separate.
Balances include visible account movements and transfers. Budget definitions are
editable; automatic rollover/recurrence accounting and richer analytics remain
Android functionality pending a separate web implementation. Charts summarize
visible records, not bank-provider balances. Private Android-only local records
are not uploaded merely by signing into the web client.

Build assets: `python tool/build_pwa_assets.py` (Pillow required). Run
`python -m unittest discover -s backend/tests -q`; PostgreSQL tests require a
non-admin role and an isolated database whose name is exactly `lifeos_test`.
`PYTHONPATH=. python tool/check_pwa_browser.py` exercises a disposable loopback
fixture. `ULADIM_BROWSER=webkit` selects WebKit after installing its official
Playwright browser and OS dependencies. Never use production credentials for it.

Deployment is intentionally separate from code publication. Back up first; archive
the exact reviewed source, use the checkpoint helper, run additive migrations
008/009, check mail delivery/readiness, and then validate/reload the existing
Caddy early-access configuration. Update the phase-specific edge monitor only
from its actual installed configuration. API/Control must stay closed until their
separate authentication, authorization and HTTPS checks pass. The backend rollback
helper restores the previous image configuration while preserving data and schemas.
Do not remove PostgreSQL volumes, encryption keys, old backups or signed APKs.

Outstanding production acceptance: unlock the existing Hostinger SSH key; deploy
and independently verify real HTTPS routes, PostgreSQL migrations, SMTP application
confirmation and invitation delivery; bind the owner's actual email, finish owner
MFA and only then expose Control; verify the full real invitation chain, recovery
and deletion executor, real Android/web two-client sync, physical iPhone/iPad
installation/Safari behavior, backup restore and rollback. No APK was rebuilt.

Transactional email templates remain Russian in this checkpoint; multilingual mail is not claimed. Physical-device, load, accessibility audit and restore acceptance remain separate release gates.

Owner enrollment UI is deliberately separate from normal settings: open `/app?setup=owner` after the operator issues the private capability and the owner verifies their account. Staff invitations use `/app?setup=staff`. These URL flags confer no rights; the server validates every step.
