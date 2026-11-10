# Android RC and store preparation — 2026-11-10

The product remains the existing native Flutter app, `app.lifeos.lifeos`.
Do not replace it with a WebView/PWA wrapper. Do not regenerate the retained key.
Verified certificate SHA256:
`5fa37e4abf1ec90d5787bd0d7dc4cf0b3f49022172f9d25e91f4d8a76702a96e`.
The historic installed version is 134001. New release code must exceed the
highest actually distributed version, with 134001 as the known minimum floor.

## Build path

The existing manually requested `build_apk` CI input now builds both the native
release APK and AAB, with one certificate and version, after mandatory validation.
No store publication occurs. No secret values are printed. The keystore secret
is retained under its existing name; missing/mismatched key aborts the build.

Preparation pins target API 36, retains minimum API 23, and includes native
Credential Manager 1.6.0 / googleid 1.2.1. Google ID/secret stay on the server.
The build verifies the APK certificate/applicationId/version and checks the
AAB JAR signature, pinned signer, manifest applicationId/version/target API,
non-debuggable state and `allowBackup=false`. Official bundletool 1.18.3 is pinned
by the SHA256 published with its official GitHub release.

The release build upgrade probe now downloads and hash-checks retained 134001
and upgrades to the candidate without uninstall/clear-data. The historical
112001 probe is retained as a separate option. The updated 134001 path still needs
to pass against an actual newly signed candidate.
Physical-device upgrade and offline data preservation remain owner checks.

## Current status

No new release APK/AAB has yet passed the full RC gate at this checkpoint.
A build script is not an artifact, and compilation is not physical acceptance.
Real Google login, protected production API routing, owner activation and legal
operator details remain release blockers. See GOOGLE_SIGN_IN_RELEASE.md.

## Verified store requirements

Official policies reviewed 2026-11-10:

- Google Play new apps/updates require Android 16/API36 since 2026-08-31;
  extension deadline was 2026-11-01.
  https://support.google.com/googleplay/android-developer/answer/11926878
- Play versionCode must increase and remain <=2100000000.
  https://support.google.com/googleplay/android-developer/answer/9859152
- Play App Signing upload certificate and delivered app-signing certificate are
  different concepts. Register the delivered certificate for Google Sign-In;
  decide cross-store signature continuity before enrollment. Do not select a
  replacement key without owner approval.
  https://developer.android.com/studio/publish/app-signing
  https://support.google.com/googleplay/android-developer/answer/9842756
- RuStore accepts APK and AAB. Updates retain package/signature and increase
  version. AAB requires separate app-signing setup. For preserving the currently
  installed certificate, a signed APK is the least ambiguous initial artifact.
  https://www.rustore.ru/help/developers/publishing-and-verifying-apps/app-publication
  https://www.rustore.ru/help/developers/publishing-and-verifying-apps/app-publication/new-version-app/upload-aab

These checks do not constitute store approval or a completed Data Safety form.

## Publication content draft (requires owner/legal review)

Short description: Tasks, notes, personal finances and family planning in one app.

Description: ULADIM helps organize daily tasks, notes, calendar and habits,
manage financial accounts, income, expenses, budgets and goals, and work with
family spaces. Android keeps local data in an encrypted database and supports
local work without a connection. Cloud account/synchronization require an
available server and appropriate access. Statement import uses a preview before
saving; unsupported PDF/legacy XLS formats must not be advertised. Available
features and limits depend on the actual plan. Real payments remain disabled.

Change draft: Password-first sign-in with a separate MFA step; Google account
integration; protected account linking; updated finance/import and tablet web UX.
Do not publish this text until real Google and candidate acceptance pass.

Data Safety preparation: inventory email/account IDs, cloud-synced user content,
financial records selected for sync, device/session security metadata and user-
submitted support messages. State actual retention, deletion and processor
locations, distinguish local-only content from uploaded content, and disclose
Google/Resend/hosting roles accurately. The app does not request bank passwords,
SMS codes or direct bank tokens. Do not declare no data collected while cloud
accounts/sync exist. Do not claim end-to-end encryption of shared spaces.

Privacy URL: https://getuladim.space/privacy
Account deletion URL: https://getuladim.space/delete-account
These pages still require real operator identity, storage/retention/transfer
information and region-specific legal review before public launch.

Store screenshots must come from the accepted native APK, not PWA screenshots.
Do not upload fabricated reviews, ratings, charts or unimplemented OAuth buttons.
