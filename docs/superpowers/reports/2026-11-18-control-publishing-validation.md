# Control publishing validation

Implemented against base `604a5c2` in the existing ULADIM project and task.
The two sections use the current Control host, staff session MFA, admission,
CSRF, effective permission restrictions and chained audit. Panel operation and
runtime cutover are documented in [Control publishing](../../CONTROL_PUBLISHING.md).

## Local evidence

- Full backend discovery: 652 tests, zero failures or errors, one explicit
  nonapplicable PostgreSQL physical-SQLite-backup scenario skipped. SQLite
  executes that physical backup scenario; PostgreSQL has its SQL rollback case.
- Final focused page/WSGI/old-import run: 30 passing checks on SQLite and actual
  restricted PostgreSQL, including immutable public revision-zero fallback.
  Restoring and publishing a positive historical revision also passed both DBs.
- Signed APK/service/legacy transport: 46 checks, zero skips, using official
  apksigner and aapt. Includes bad package, signer, signature, version, truncated
  upload, cancellation after a worker exit, concurrent publication, atomic
  audit rollback, historical HEAD/Range and complete byte/manifest agreement.
- JavaScript: 38 Vitest and 35 Node checks passed. Complete key coverage for 168
  new strings in each of 16 locales; 2688 translated values.
- Real isolated Chromium/WSGI Control admission and MFA: 10 publishing journeys
  passed. Includes draft image privacy, exact page/language publication, restore,
  stale edit reconciliation, delayed save/media responses, frozen public source
  despite changed live translations, preserved account/early-access input,
  signed APK validation/publication and German panel labels.
- Existing public help, legacy/managed download, and Control workbench browser
  checks passed. Release/delivery guards and evidence boundaries also passed.
- Both independent backend and full integration reviews closed their findings.

Test APKs and accounts were isolated. The production verifier has fixed package
and signing-certificate trust; no runtime environment or HTTP switch enables
the fixture signer. No live test content, test APK or old 367001 publication
was submitted.

## Delivery boundary

Source validation does not establish installation. The normal GitHub workflows
include the new tests and actual Caddy validation. The local inherited Python
environment differs from some production pins, and no local Caddy runtime
image was available; the hosted Docker build and dependency-pin check cover
those runtime boundaries.

Production cutover requires migrations 026/027, official verification tools,
the retained read-only accepted APK cache, a separate private persistent API
volume and the reviewed edge manifest/upload route changes. Existing pinned
installers serve the historical static manifest and must not install this
resolver without that separately reviewed cutover. All existing source-based
APK URLs and the exact original seven-field GitHub manifest remain supported.
