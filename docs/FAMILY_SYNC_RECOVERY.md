# Historical family sync recovery checkpoint

This document preserves the earlier recovery evidence. For the current integrated implementation and publication route, see [FAMILY_SYNC_IMPLEMENTATION.md](FAMILY_SYNC_IMPLEMENTATION.md).

At this historical checkpoint this was an integrated **source candidate**, not a validated Android release.

## Recovery and history

The ZIP, patch and bundle matched the SHA-256 digests and sizes in the attached manifest.
The manifest does not contain a digest of itself. Its source commit was checked against the bundle.
The original WIP was restored at `51f6e4582f8e8626e240a8ed66cc734d87d05aeb`.
GitHub main was read at `b946469cce8df33e4f2a48bade2bc669cbc1c2e0`.
The saved WIP history and GitHub history had no common ancestor. Their matching application
snapshots were joined with a normal merge, preserving both histories. The only add/add conflict
was `.gitignore`; both the original exclusions and backend privacy exclusions were retained.

GitHub publication failed through both available methods: ordinary git lacked credentials;
the GitHub integration returned `403 Resource not accessible by integration` for tree creation.
No force push or remote update occurred. There is **no published checkpoint SHA** for this session.

## Implementation

- Optional account and family entry in Profile; the existing local application needs no server.
- Register, sign in, verify email, logout and change password. Password changes revoke all sessions.
- Endpoint validation: HTTPS; HTTP permitted only for explicit loopback/emulator development hosts.
- Bearer tokens live in secure storage. Request bodies and responses are bounded; redirects are disabled.
- Family selection, invitations and revocation, equal co-parent administration, consent to downgrade
  a co-parent, child profiles and editable permissions, membership removal, leave and dissolution.
- SQLCipher schema migration 11: scoped outbox, remote mirrors, cursors and metadata. Existing personal
  rows and immutable local identity are not converted, uploaded or replaced.
- Each outbox operation has a stable UUID, is durable before transmission and is acknowledged atomically.
  Batches contain up to 100 operations. Transport failures retain the queue and retry every 30 seconds
  while the controller is alive; the user can retry manually. This is not an Android background service.
- A record with a queued/unresolved mutation cannot receive another local edit until the previous one is
  acknowledged or resolved. Conflicts retain both versions; explicit resend uses a new UUID and server revision.
- Revoked mirrors are purged; unsent operations remain encrypted and visible for explicit recovery/discard.
  Server authorization governs all operations even if cached offline rights are stale.
- Family editors support notes, tasks, accounts, expenses/income, transfers, budgets, events, shopping lists
  and money requests. Private sharing is read-only in the current grant UI. Request fulfillment refers to
  one existing transfer, and the same transfer cannot fulfill two requests.
- Existing personal encrypted backups retain their personal scope. Cloud sessions/cache/outbox are excluded
  from portable personal backups; restoring a personal backup does not restore or transfer a cloud session.
- CI includes backend tests, the actual Dart HTTP protocol test and a new native SQLCipher queue integration
  test. The existing certificate pinning and final-only signed APK gate remain intact.

## Evidence and limitations

Executed here: backend unittest suite, project Python tests including migration 11, installed RU/EN language
pack validation, actual two-client Dart HTTP synchronization, standalone Dart analysis of API/contracts/engine,
and Dart parser/formatter checks for new UI/controller/storage/native-test sources.

**Not executed:** Flutter package resolution/analyze/widget tests, UI rendering, Android SQLCipher execution,
complete GitHub CI, native Kotlin compilation and final signed APK. The native queue test exists but has not run.
Automatic approval review rejected Flutter startup because it reported a cloud metadata endpoint access.
Standalone `dart pub get` could not resolve Flutter SDK dependencies. No workaround was used to restart Flutter.
The Android SDK and the protected signing keystore are not present in this session. No APK was built.

Existing launch scope remains incomplete: only RU and EN packs are installed; the 15-language release gate is
not satisfied. The family event form supports basic scheduling and preserves an existing recurrence, but the
complete recurring-calendar UX remains a follow-up. Shopping item completion and per-assignee task completion
with co-parent review are implemented in source; task completion/review was verified in backend tests.
The Flutter screens still require compilation, widget/visual QA and real Android validation before release.

The reference backend listens on loopback and writes verification codes into a private development mailbox.
It is not a production service. No VPS was bought/deployed. No live cloud synchronization is claimed.

## Safe continuation

1. Restore the updated bundle into an isolated clone and inspect `git log --graph --all` and the manifest.
2. Obtain repository write access and publish with an ordinary fast-forward push, after fetching current main.
   Merge any new remote work without discarding the preserved WIP. Never force push.
3. Resolve the Flutter startup approval/environment blocker. Run focused client checks before fixing any errors.
4. Finish any issues found by Flutter analysis and UI QA, and run the required native encrypted-storage tests.
5. Run one complete final CI and request one signed APK using the existing keystore secret and pinned certificate.
   Do not generate a replacement signing identity or intermediate APKs.
