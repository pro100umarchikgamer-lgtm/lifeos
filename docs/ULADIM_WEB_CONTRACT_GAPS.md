# ULADIM Web integration handoff — 2026-11-10

Base: da2301cfd13db87de293b0fdc12ee1d8f6b13a70, feature/uladim-hostinger-launch.
Work: work/uladim-web-platform. No production deployment, merge or OAuth changes.

## Verified existing boundary
Browser calls `/account/api/*` with same-origin HttpOnly session cookies and
`X-CSRF-Token` for writes. `/account/api/session`, `/spaces`, `/roster?workspace=…`,
`/sync?workspace=…&cursor=…&epoch=…`, and POST `/sync` are reused as implemented.
Writes preserve operation UUID on uncertain responses and use record revisions.
No second authentication system, database or API implementation was added.
The only Python production edit extends the static asset allowlist with domain.js.

Event `record.put` data is exactly:
```json
{"title":"Event","schedule":{"localStart":"2026-11-12T14:30:00","timezone":"Asia/Tashkent","allDay":false,"repeat":"weekly","interval":1,"until":null}}
```
The enclosing operation is the existing `id/action/record_id/revision/kind/visibility/audience/data` envelope,
posted as `{workspace_id,operations:[operation]}`. Event type, recurrence enum,
interval 1–365 and timezone policy match service.py and calendar_engine.dart.
All-day events retain civil dates; timed events show viewer-local time and its timezone.
DST overlap chooses earlier instant; gaps move forward by the actual gap.

## Contract coordination

Canonical existing contract: [PR #2](https://github.com/pro100umarchikgamer-lgtm/lifeos/pull/2),
head 565927498a7d3fff97536a4652f492c4e1701ce0, document
`docs/WEB_CLIENT_API_CONTRACT.md`. Compared with this branch: all nine current
record field sets and browser transport are unchanged. PR #2 documents existing
operations; it does not implement the missing features below. The web PR is #3.

No new record kind or field is implemented or approved here. Each future change
needs a versioned contract, migration, old Android compatibility and conflict,
permissions and arithmetic tests in a separate backend-owned PR. A protocol bump
must distinguish capability support; the web must not probe unknown writes.

## Missing contracts — backend/Android owner must coordinate
These are verified gaps in service.py TABLES/FIELDS and `_record`, not guesses
about fields the browser should silently submit. No proposed field below is active.

| Feature | Current contract | Required decision |
| --- | --- | --- |
| Task dates, overdue, priorities, lists, recurrence | `title,completed,assignment,assignees,review` only | Versioned shared task metadata and migration, scheduling/timezone semantics, compatibility with old Android clients |
| Server restore/trash | `record.delete` exists; no restore action; record.put rejects deleted rows | Restore action with revision/permissions, reference restoration and expiry rules |
| Habits | No habit record kind in shared service | Shared schedule, completion history, per-profile permissions and conflict model |
| Goals/savings/debts/investments | No corresponding record kinds | Shared schemas, money units/currencies, account references and balance effects |
| Categories/counterparties | Transaction `label`, but no category/counterparty IDs | Stable shared entities and schema versions; don't encode metadata in label |
| Note organization | `body` only | Folder/tag/title schema and Android compatibility |
| Today widget preferences | Browser preferences only; no server layout schema | If cross-device widget configuration is wanted, add profile preferences contract |
| Notification reminders | Event schedule contains no reminder field | Shared reminder semantics and delivery ownership |

Deletion currently offers a 4-second cancel window BEFORE sending record.delete.
It does not advertise server restoration. Pending deletes are cancelled when identity
is cleared. Network failure does not enter an offline mutation queue.

## Localization
Existing 16 catalogs are reused unchanged. New copy: Russian, English,
uz-Latn, uz-Cyrl; other languages visibly say partial translation and fall back to
English for new labels. Public/legal pages remain Russian. No claim of complete
16-language support or professional Uzbek linguistic certification is made.

## Infrastructure/coordination blockers
- GitHub connected app rejected branch creation with HTTP 403 Resource not accessible
  by integration. CLI git push has no credentials. Local commit is not a remote commit.
- No PR exists; CodeRabbit has not run. Need repository Contents write and Pull requests
  write through an authorized GitHub connection. Do not send credentials in chat.
- Local Chromium cannot create its singleton socket (Operation not permitted).
  Shared browser cannot reach executor localhost. Playwright download returned an
  invalid archive. No screenshots or visual-regression baselines were accepted.
- `stage1.yml` currently triggers on every push/PR, including web-only changes. It
  belongs to the parallel release work. Coordinate a paths gate before publishing if
  Android builds must not run; this branch intentionally did not edit that workflow.
- Web CI includes a dedicated JS CodeQL job; actual repository availability and SARIF
  permission need confirmation by a real run. Lighthouse thresholds are configured,
  not measured. Existing Python/Flutter checks were not replaced.
- No staging origin or test-account access to production was supplied or created.
  Production Google OAuth, PostgreSQL round trips and Android device sync remain
  release gates. Disposable SQLite/WSGI tests prove the application boundary only.
- Legal notices now describe the actual processing and remaining operator/retention
  questions. They remain preliminary, not legal approval for a public launch.

## Safe next integration steps
Apply this branch to a checkout with write access; inspect for concurrent changes.
Open a draft PR to feature/uladim-hostinger-launch, review CodeRabbit critically,
run web CI and review screenshots at 375/768/1024/1440 in both themes. Approve
visual baselines manually. Resolve backend gaps in separate coordinated PRs.
Only then use an explicitly configured staging origin with the same real backend
and test synchronization with Android. Do not merge or deploy based only on these
local checks. Rollback is reverting the web PR; no database migration is included.
