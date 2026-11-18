# Control Publishing Implementation Plan

> **For agentic workers:** Use focused implementation and independent review.
> The owner requested both planning and implementation; proceed without another
> approval round. Keep progress in `delivery/control-publishing-20261118`.

**Goal:** Deliver the Public Pages and Android APK sections in existing Control.

**Architecture:** Independent revision services share existing Control authority,
database transactions and audit. Public page fields/regions reuse existing
components; immutable APK objects precede an atomic database live pointer.

**Tech Stack:** Existing Python WSGI, SQLite/PostgreSQL, vanilla JS/CSS,
cryptography, official Android verifier tools and a bounded raster decoder.

**Spec:** `docs/superpowers/specs/2026-11-18-control-publishing-design.md`

## Global Constraints

- Preserve the twelve public page routes and sixteen canonical locale tags.
- No editable HTML/scripts/styles or operational form/download destinations.
- Preserve legacy seven-field GitHub manifests and source40 APK routes.
- Runtime package/signature trust is fixed as specified; tests use isolated trust.
- Current public selection changes only on explicit successful transaction.
- Preserve Control admission, mandatory session MFA, CSRF, denials and audit.
- No production fixture publication or retry of the old 367001 transaction.

## Review Focus

- Delayed page/language responses must not replace another locale or form input.
- Valid drafts, history and unpublished images must not leak to public readers.
- An APK accepted before a newer publication must not downgrade the pointer.
- Crashes between file writes and DB changes must leave the current file intact.
- Source Caddy interception and read-only runtime mounts require explicit cutover.

## Task 1: Page revision service and source contract

**Files:** `backend/public_pages.py`, migration
`backend/migrations/026_public_pages.sql`,
`backend/tests/test_public_pages.py`, shared catalog
`backend/webassets/public-pages-source.json` (frontend owner).

**Interfaces:** `PublicPages(backend)` exposes
`handle(actor, action, method, body, query)`,
`public_document(page, locale)`, `public_media(media_id)` and
`preview_media(actor, media_id)`. Control actions use `pages`, `pages/page`,
`pages/history`, `pages/revision`, `pages/preview`, `pages/save`, `pages/publish`,
`pages/restore`, `pages/media`. Pin the typed content/catalog wire shape with the
frontend implementer and record it in the ledger before implementation.

- [ ] Write failing scoped draft/publish/restore/baseline/validation/media tests.
- [ ] Implement immutable source/revisions, CAS state and same-tx audit.
- [ ] Validate raster decoding, text/URL bounds and current-public media references.
- [ ] Run focused tests and independent scope/security review.

## Task 2: Signed APK service and immutable byte serving

**Files:** `backend/android_releases.py`, `backend/apk_verifier.py`,
`backend/native_download.py`, `backend/migrations/027_android_releases.sql`,
`backend/tests/test_android_releases.py`, `backend/tests/test_apk_verifier.py`,
small signed fixtures/generator, `docs/NATIVE_APK_DOWNLOAD.md` additions.

**Interfaces:** `AndroidReleases(backend, settings, legacy_download)` exposes
`handle(actor, action, method, body, query)`, `upload(actor, environ)`,
`public_manifest()` and `download_response(environ)`. Actions under
`android-releases` follow the Android design table. Binary upload is exactly
`POST /control/api/android-releases/upload`; JSON body limits stay unchanged.
`NativeDownload.manifest()` resolves only a verified actual mounted legacy tuple.

- [ ] Write real signed-fixture verifier, old/new manifest and transition tests.
- [ ] Implement streaming, bounded verification, state/CAS and atomic publication.
- [ ] Preserve legacy reader and HEAD/Range/descriptors for new immutable files.
- [ ] Test wrong signer/package/version, tamper, interrupted uploads and races.
- [ ] Run focused tests and independent security/concurrency review.

## Task 3: Control/public frontend and source baseline

**Files:** new `backend/webassets/control-publishing.js`, publishing CSS,
`backend/webassets/public-pages.js`, source catalog; hook existing `web.js` and
`index.html` without changing existing functional handlers.

- [ ] Map all existing editorial fields/regions, including account story and
      early-access variants; source defaults preserve the unedited rendering.
- [ ] Add scoped page/language draft editor, ordered typed blocks, media,
      shared-renderer preview, publish and restore-to-draft history.
- [ ] Add APK file/drop selection, streaming progress, verified status, explicit
      publish/cancel/history and honest manifest-variant download validation.
- [ ] Preserve forms, FAQ indexing/anchors, locale epochs and legal readiness.
- [ ] Add browser scenarios using ordinary Control/public entry points.

## Task 4: Server, schema, permissions and runtime integration

**Files:** `backend/web.py`, `production.py`, `config.py`, `control.py`,
`staff_permissions.py`, `schema.sql`, `backend/Dockerfile`,
`deploy/hostinger/Caddyfile.control-platform`, deployment docs/tests.

- [ ] Add only the specified capabilities/narrow roles and existing audit use.
- [ ] Mount public APIs and authenticated service routes behind current authority.
- [ ] Authenticate the exact binary route before the first body read; stream
      directly to service; preserve normal JSON bounds and host/HTTPS handling.
- [ ] Mirror migrations in SQLite schema, configure private persistent storage,
      fixed verifier tools and narrow edge upload/manifest routing.
- [ ] Run WSGI denial/no-read, manifest/download and PostgreSQL concurrency tests.

## Task 5: Integrated acceptance and delivery

- [ ] Exercise draft-hidden, exact page/language publish and historical restore
      through the real panel and public pages.
- [ ] Exercise genuine signed test APK validation/publication and compare
      manifest, headers, ranges and complete downloaded bytes.
- [ ] Verify rejected APKs and missing permissions have no public side effects.
- [ ] Run selected existing Control/help/auth/native regressions and normal CI.
- [ ] Review the complete diff; commit/push the feature branch and create the
      normal reviewable change if the existing authorized channel permits it.
- [ ] Report source readiness, exact panel steps and actual site-delivery stage
      separately. Do not infer deployment from source/CI or the unrelated 367001 run.
