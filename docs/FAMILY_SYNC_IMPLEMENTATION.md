# Family Sync + UX 2.0 — integrated candidate

The original WIP `15a03cd5ed9e94292ca4c20f6229a4bd342c4f0a` is published on
`feature/family-sync`, preserving its history and the original main baseline
`b946469cce8df33e4f2a48bade2bc669cbc1c2e0`. Publication uses an authenticated
Codespaces normal Git workflow. Main has not been overwritten or force-pushed.
`FAMILY_SYNC_RECOVERY.md` records the earlier recovery session and its historical blockers.

## Integrated behavior

- Optional accounts: registration with password confirmation, login, verification, logout,
  password change and single-use email recovery. Password changes/reset revoke sessions.
- Personal/family workspace switcher and dashboard, scoped search and creation actions.
  Personal records are never automatically uploaded or mixed into shared financial totals.
- Equal parent administration, invitations and revocation, child profiles and permission
  controls; downgrade of a co-parent requires consent. Server permissions remain authoritative.
- Private family records can be explicitly granted for viewing or editing and revoked.
- SQLCipher migration 11 persists account/server/workspace scoped outbox, mirrors and cursors.
  Acknowledgement and conflict resolution are transactional. Lost replies reuse operation UUIDs.
  Revocation purges remote mirrors but retains unsent work for explicit recovery or discard.
- Batched push/pull, bounded payloads, retries while the app/controller is running, offline
  cached rosters and explicit conflict decisions. No closed-app background service is claimed.
- Typed family notes, tasks, child completion/review, accounts, spending/income, transfers,
  budgets with rollover, events with date/time/repeat controls, shopping and money requests.
- Today empty state simplified; Modules grid/list preference persists; finance uses contextual
  navigation; import starts with file selection, conservative detection, preview and confirmation.
  Ambiguous dates/encodings require explicit adjustment. Raw statements remain local.
- Family money uses normal decimal amounts while storing exact minor units. Forms scroll,
  date/time selectors replace technical timestamps, and Activity/Sleep spacing is improved.

## Validation gates

Focused Actions checks run Flutter analysis, relevant Dart/widget tests, backend tests, the
actual two-client Dart HTTP scenario and rendered light/dark/narrow/large-text screenshots.
The final workflow retains full Dart/widget tests, complete screenshot verification, Kotlin
compilation, Android SQLCipher migration/backup integration and a two-client SQLCipher + HTTP
scenario with restart, conflict, privacy and revocation checks.

The signed release-test APK is gated after all mandatory checks. The existing keystore secret,
certificate pin (`docs/ANDROID_TEST_CERT.sha256`) and `app.lifeos.lifeos` applicationId remain.
CI derives a monotonically increasing versionCode from the workflow run number.

A source candidate is not a completed release until the final complete CI and APK verification
actually pass. Generated screenshots must be inspected before requesting that build.

## Backend deployment boundary

`backend/http_server.py` is a loopback development adapter. Its mailbox is deliberately local;
production needs a real email adapter, TLS, operational backup/recovery and configured hosting.
No VPS or production service has been deployed. Sync requires an explicitly configured backend.
`tool/serve_family_test_backend.py` uses a disposable database and synthetic `.test` identities
for CI only. No credentials, personal records or statements belong in artifacts.

Installed language packs remain Russian and English; the broader launch-language gate and
legacy BIFF `.xls` import remain outside this family/UX release-test checkpoint.
