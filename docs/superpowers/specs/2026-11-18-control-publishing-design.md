# ULADIM Control: public pages and signed Android releases

The owner explicitly approved these features and requested implementation in
«Разработка Основная». This is that existing task and repository, based on
`604a5c2`. The previous attempted 367001 deployment is unrelated acceptance
evidence and must not be resumed by this work.

## Goal and boundaries

Add two usable Control sections: editing all twelve public HTML pages in all
sixteen existing locales, and accepting/publishing an already signed Android
APK. Preserve the existing design, forms, authentication, deletion procedures,
legal readiness indicators, download verification and protected Control host.
No paid service or separate CMS. No arbitrary user HTML, script, CSS, filesystem
path or executable command.

## Public pages

The catalog covers `/`, `/account`, `/plans`, `/privacy`, `/terms`, `/support`,
`/delete-account`, `/status`, `/download`, `/faq`, `/early-access`, `/docs`.
`/app`, API routes and binary downloads remain operational resources.

Use explicit editorial fields and typed ordered block regions on the existing
page components. Include existing editorial text, images and links; an appended
news panel alone does not satisfy the feature. Render source defaults exactly
when no override is published. Code-owned functional islands stay outside
removable editorial regions. Source content is immutable revision zero and the
fallback for a locale without an override. Resolve its existing translation keys
through the existing localization packs, without changing the Control locale
while the editor selects another content locale.

Each `(page, locale)` has immutable revisions and optimistic state version,
draft and published pointers. Save creates a draft; preview reads an authorized
saved revision; publish explicitly selects a draft; restore copies a previous
revision, including zero, into a new draft for explicit publication. Concurrent
stale changes return 409. Publication and audit occur in the same transaction.
Public readers see only the requested scope's published revision or source.

Support plain text, existing component/source blocks, validated links and raster
images. The implementation catalog pins allowed fields/regions and source block
identities. Images are decoded, bounded, normalized and re-encoded; no SVG/HTML
or remote fetch. Draft media is private; public media requires a current
publication reference. Keep widgets/forms and editable content separate.

## Android APK

Continue supporting the exact seven-field legacy manifest and its original
GitHub URL, and the existing `/download/android/<source40>/ULADIM.apk` route.
Do not invent a Git source or GitHub URL for an uploaded file. New manifests use
the exact discriminated seven-field alternative:

`origin, version_code, version_name, bytes, apk_url, apk_sha256, certificate_sha256`

`origin` is `control`; `apk_url` is exactly
`/download/android/sha256/<full-sha256>/ULADIM.apk`. All public consumers validate
the selected variant and verify the corresponding same-origin HEAD response.
The immutable prior routes and GitHub fallback remain usable.

Use a separate private persistent `NATIVE_PUBLISH_DIR` owned by the API UID.
Leave `NATIVE_DOWNLOAD_DIR` root-owned and read-only. Stream at most 64 KiB at a
time with a positive Content-Length capped at 512 MiB, after admission, HTTPS,
host, origin, Control session/MFA, account binding, capability and CSRF checks.
Do not read APKs into JSON or memory. Draft/create, upload, validate, publish and
cancel are distinct transitions with revision checks and safe error states.

Official `apksigner` verification and binary manifest inspection must establish
package `app.lifeos.lifeos`, retained direct-release signer
`5fa37e4abf1ec90d5787bd0d7dc4cf0b3f49022172f9d25e91f4d8a76702a96e`,
versionCode and actual server size/SHA-256. Only an isolated test verifier can
trust disposable fixture signers; runtime trust is fixed, with no HTTP/env debug
override. Bound verifier memory/time and concurrency on the 512 MiB API.

Durable immutable bytes precede the publication transaction. A singleton DB
pointer is the only live selection; its update, history and audit are atomic.
Revalidate file identity/digest before publish. Enforce increasing versionCode
against both current managed and actual legacy release. Error, interrupted
upload, cancellation, concurrent publication or audit failure leaves the old
manifest/download usable. Published bytes are never overwritten or deleted by
draft cancellation. Existing transfers retain their accepted descriptors.

`/download/release.json` must ultimately be routed to this backend resolver,
falling back to the exact validated legacy cache manifest before any managed
publication. Update source-side Caddy/runtime instructions; source edits alone
do not prove an installed cutover.

## Authority and user interaction

Use existing Control admission, session MFA, CSRF, deny restrictions and chained
audit. New capabilities are `pages.edit`, `pages.publish`, `android.read`,
`android.upload`, `android.publish`. Owners have all five. Introduce narrow
`content_editor`, `content_publisher`, `release_manager` roles, assignable under
the existing hierarchy/delegation rules. Existing support/moderation/billing and
admin roles acquire no implicit publication rights. Do not add a new five-minute
reauthentication policy: retain the existing mandatory Control MFA contract.

The panels use current Control navigation, buttons, spacing, status feedback and
accessible controls. Preview and unsaved/published state must be unmistakable.
APK selection alone never publishes. Show verified version, signer state and
server checksum, and a separate explicit publish action.

## Acceptance and delivery

Exercise service, real WSGI admission/MFA/CSRF routes, PostgreSQL concurrency,
ordinary Control browser flows and public rendered/download endpoints with
isolated data and signed test APKs. Include wrong package/signer/version,
tampering, denied rights, draft leakage, locale/page isolation, restore,
disconnect/cancel/publication races, manifest/HEAD/Range/full-byte agreement and
legacy regressions. Run relevant existing checks and normal project CI; no live
test content/APK publication. Report code/checks, panel instructions and actual
delivery state separately.
