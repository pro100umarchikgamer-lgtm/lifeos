# Reference video pass — implementation and evidence

Base: published 14f5d05. The owner requests faithful reference design, preservation of the working backend, proportionate frontend checks, and an APK update after the web design is finished. This latest APK instruction supersedes the older attached brief's exclusion of Android.

Available evidence: all six available videos have been decoded and their complete audio transcribed locally in Russian. The four compressed main-recording parts were checked in chronological order 389 → 503 → 480 → 414 (08:38.91 total); the separate B12 example is 01:25.91 and the later critique is 02:20.42. Statements were matched to source frames. Raw recordings, ASR output and personal reference material remain outside this public repository. The large originals exceed the connector limit, but their newly supplied compressed parts provided the full main recording. No paid transcription service was used.

Implemented:
- Fixed header, persistent workspace picker, grouped Planning/Finance/Workspace navigation and real synchronization status. Phone navigation and workspace selection remain available.
- B12-shaped summary tiles and independent dashboard columns using actual tasks, account balances, current-month financial series, recent transactions and calendar events; no demo records or invented notifications.
- Neutral light/charcoal dark surfaces, compact typography and surfaces, violet default palette. Existing saved palette selections remain functional.
- Redesigned Calendar month/day agenda and Notes library; original recurrence/timezone, save and draft behavior retained.
- Actual workspace cards and roster, profile identity/verified status, existing settings shortcuts and logout.
- Emergent-inspired public homepage and split sign-in: dark generated texture beside the existing compact form, responsive single-column forms, registration and recovery controls retained. Public FAQ and installation pages use clearer spacing and describe the actual Web/PWA and Android paths.
- New transaction amount is blank and decimal-friendly; last successful account is scoped to the current user/workspace tab, validated before reuse. Saving 2500 stores exactly 250000 minor units. Existing transaction editing is unchanged.

The apparent missing expense in the recent video is visible in its ledger with an extra trailing zero in the entered amount. No backend save failure was established; the obstructive zero was corrected in the editor.

Verification: both real customer sign-in routes pass using the actual compiled CSS bundle, including registration/recovery controls, all twelve viewport/theme captures, image HTTP 200 and WebP content type, no JavaScript/CSP errors or horizontal overflow. Public home, FAQ and platform-page captures were also inspected. Focused transaction-entry browser check (five scenarios), delayed workspace-switch guard, six shell captures, twelve Notes/Calendar captures, family/profile controls and screenshots, 320 px independent review. No full backend regression run was launched locally for this presentation pass. Existing required GitHub workflows remain enforced for publication. Independent review found no material blocker in the covered screens.

Browser acceptance follows the new Calendar/Notes labels, direct phone navigation, desktop sidebar, actual profile controls and scoped finance import actions. Existing persistence, retry/idempotency, account privacy, registration/MFA, responsive geometry and contrast assertions remain enforced. A muted-text contrast issue was corrected in the light palette; canvas, white and soft surfaces now exceed 4.5:1. Actual browser checks pass for product CRUD, PWA lifecycle/privacy/locales, both auth paths and first records, device management, workspace recovery, chart themes, personal import and a 1,168-operation bank-import fixture.

Operational scope: the only backend Python change adds the exact `auth-texture.webp` filename to the existing explicit static-asset allowlist. The publisher permits only this byte-exact change while rejecting every other backend/schema difference. The backup helper includes the already verified VPS permission repair for reading encrypted-backup input files. Authentication, API behavior, migrations and record logic are unchanged.

Pending: publish this final web candidate and verify its live asset hashes, then update/build the native APK with the existing signing identity. Source and local screenshots are not publication evidence. The installed temporary VPS operations bridge pins the previous release; its reviewed upgrade must install the exact web and native candidates while preserving authentication and the absolute expiry.
