# Public help and legal content, 13 November 2026

Implementation is reviewable locally. This is not approval to mark legal or store release gates passed.

## Single source of factual statements

`backend/webassets/web.js` exposes `PUBLIC_RELEASE_FACTS` as the source reviewed with the public documents. An optional `config.public_legal` object may inject the same public keys; no new API, auth, payment or database routes are required by this frontend change. Current API config does not expose those keys. Never put secrets in this object.

`published` remains false. The final-document banner can only clear when `published` is true and all required nonempty facts below are supplied, with a valid public support email. Filling the operator name alone does not silently finalize the document. Confirmed source facts now name Usmonov U, Uzbekistan, and the target mailbox support@getuladim.space. The mailbox stays pending until `supportEmailReady=true`. Publication also requires `processingVerified`, `privacyLifecycleReady`, `retentionVerified`, and `agePolicyEnforced` to be true; these flags require actual evidence, not only completed text. The operator-selected 7-day archive lifetime is recorded as a plan, not exposed as an active retention guarantee. See [current Uzbek-law and implementation review](UZBEK_PRIVACY_FACTS_20261113.md).

| Key | Required evidence |
| --- | --- |
| `operatorName` | Actual legal operator name or company |
| `operatorCountry` | Confirmed operator country and applicable jurisdiction |
| `operatorPostalAddress` | Actual postal address for legally required data-subject disclosures; currently unknown |
| `supportEmail` | Public mailbox available without an account, including blocked users |
| `processingRegion` | Actual production hosting/processing region, providers and any cross-border transfer terms |
| `minimumAgePolicy` | Approved minimum age and family/minor/representative rules |
| `legalBasis` | Processing grounds matching actual operator and jurisdiction |
| `deletionPolicy` | Verified deletion behavior for all personal, shared and counterparty data; deidentified structural exceptions only if necessary for another user's own financial records |
| `backupRetention` | Implemented bounded retention, deletion exclusions on restore and treatment of previous backups |
| `correspondenceRetention` | Actual separate external support-email retention/deletion procedure |
| `securityRetention` | Actual necessary security-log fields and expiry, with no advertising use |

`deletionGraceHours` defaults to the verified current 24 hours. Update only with corresponding service behavior. Google scope wording reflects `openid email`; Google contacts, Drive and calendars are not requested by sign-in. No advertising analytics/trackers is distinct from necessary account, records and security processing.

Android artifact metadata in `android` is the immutable audited fallback build 312001. Only `/download` optionally requests same-origin `GET /download/release.json` (omit credentials, no-store, redirect error, 2500 ms deadline). The approved edge coordinator publishes this JSON only after checking a real signed APK; no backend API or secret is added. The consumer validates the exact seven-key contract: full lowercase `source`, Android `version_code` 312001–2100000000, actual `bytes` 1–2147483647, `version_name` as a short printable string or explicit null/empty when unavailable, exact source-bound GitHub `apk_url`, lowercase SHA-256 `apk_sha256`, and the retained `certificate_sha256`. A missing cosmetic name displays “Android · сборка N” with the new verified bytes. It never reuses the old version or size. Only a complete valid tuple replaces the whole release card, including its digest, in one DOM replacement; stale navigation responses and invalid/unavailable metadata keep the entire verified fallback. The real next APK digest is never hardcoded into source, so publication does not require rebuilding that APK. Do not use a moving “latest” URL. Android API cloud readiness is a separate deployment check.

Targeted check: `PYTHONPATH=. python tool/check_download_release_browser.py`. Its local synthetic cases cover full atomic updates, unavailable version names, safe text rendering, invalid fields, 503/offline/redirect/malformed JSON, timeout, navigation races and config outage. Evidence defaults to `web_evidence/download-release`; override with `ULADIM_DOWNLOAD_EVIDENCE`.

## Public UI and coverage

The FAQ contains 21 grouped searchable answers. Stable topic links used by contextual help are `/faq#today`, `#tasks`, `#calendar`, `#notes`, `#finances`, `#account`, `#security`, `#notifications`, `#recovery`, `#family`, `#import`, `#support`, `#privacy`, `#deletion`, `#plans`, `#installation` and `#delete-staff-account`. A topic fragment opens its answer.

Privacy and terms have readable sections, a contents index, version/date, plain-language highlights and a print action. Support, deletion and downloads have separate actionable pages. Informational pages stay available during account-config failures. Plans reflect current free access, a Plus preview and unavailable future AI, without prices or paid calls to action.

Native HelpCenterScreen is available through Settings → Data and privacy without requiring a cloud account. It provides searchable Russian/English answers, with English fallback for other app languages, and public legal/support links. Operator/legal details remain on the public site to avoid stale packaged legal facts.

## Targeted verification

Run from the checkout:

```sh
node --check backend/webassets/web.js
PYTHONPATH=. python tool/check_public_help_browser.py
source /workspace/work/toolchains/flutter-env.sh
export DASH__SUPPRESS_ANALYTICS=true
flutter analyze lib/ui/help_center.dart lib/ui/settings.dart test/help_center_test.dart --no-pub
flutter test test/help_center_test.dart --no-pub
```

The browser check uses only the existing disposable synthetic WSGI fixture and local Chromium. It verifies seven public routes at widths 320, 390, 768 and 1440; internal navigation; search match/empty/clear; keyboard expansion; the 17 context anchors; and all six informational pages with account config returning 503. Actual light desktop/phone and dark/reduced-motion screenshots plus JSON results are written to `/workspace/work/delivery/legal-faq-2026-11-13`. Native widget checks cover logged-out search/deep links and narrow-screen 150% text. No old complete backend suite or real user data is used.
