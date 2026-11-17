# ULADIM Web integration handoff — 2026-11-10

Base: da2301cfd13db87de293b0fdc12ee1d8f6b13a70, feature/uladim-hostinger-launch.
Work: work/uladim-web-platform. No production deployment, merge or OAuth changes.

## Verified existing boundary
Browser calls `/account/api/*` with same-origin HttpOnly session cookies and
`X-CSRF-Token` for writes. `/account/api/session`, `/spaces`, `/roster?workspace=…`,
`/sync?workspace=…&cursor=…&epoch=…`, and POST `/sync` are reused as implemented.
Writes preserve operation UUID on uncertain responses and use record revisions.
No second authentication system, database or API implementation was added.
Python changes extend the static asset allowlist, expose the current device in the account response, and update account lifecycle behavior.

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
| Categories/counterparties | Optional built-in transaction `category`; no custom category/counterparty IDs | Custom shared entities still require stable IDs; don't encode metadata in `label` |
| Note organization | `body` only | Folder/tag/title schema and Android compatibility |
| Today widget preferences | Browser preferences only; no server layout schema | If cross-device widget configuration is wanted, add profile preferences contract |
| Notification reminders | Event schedule contains no reminder field | Shared reminder semantics and delivery ownership |

Deletion currently offers a 4-second cancel window BEFORE sending record.delete.
It does not advertise server restoration. Pending deletes are cancelled when identity
is cleared. Delete operations do not enter an offline mutation queue.

Notes keep an unsent draft in the current browser tab, scoped to the signed-in
account, workspace and note. A lost response preserves the exact operation
for a user-initiated retry. A definite rejection restores editing. Explicit
logout removes this account's local note drafts. A confirmed write with a failed
refresh retries the refresh. Other record types do not have persistent drafts.

## Localization
Existing 16 catalogs are reused unchanged. New copy: Russian, English,
uz-Latn, uz-Cyrl; other languages visibly say partial translation and fall back to
English for new labels. Public/legal pages remain Russian. No claim of complete
16-language support or professional Uzbek linguistic certification is made.

## Infrastructure and current release gates
- Original Git history is now published unchanged on work/uladim-web-platform;
  Draft PR #3 targets feature/uladim-hostinger-launch. No force push or merge.
- The connected GitHub integration still rejects Contents writes; the separately
  authorized Codespaces credential successfully pushes and creates PRs. Owner
  identity and integration permissions are different. Codespaces Actions write
  is also denied, so automatic core runs from this branch could not be cancelled.
- Existing stage1.yml triggers on every push/PR. This web branch did not alter its
  signing/release policies. Coordinate paths filtering with the Android owner;
  do not treat its independent results as the dedicated web workflow result.
- CI 42906557524 passed all 187 backend tests with isolated PostgreSQL, without
  skips, plus actual browser product checks and 56 screen/form captures. A later
  PWA test exposed duplicated note text; that UI defect was fixed. Latest CI
  results and artifacts, not this earlier run, determine final acceptance.
- Codespaces PWA, financial browser checks and shell-update lifecycle passed.
  CodeQL passed. Lighthouse and expanded browser/keyboard-height tests must be
  verified on the final head. Physical iOS/Android keyboard acceptance remains
  distinct from viewport-height simulation.
- A private Codespaces preview now exists; see ULADIM_WEB_VALIDATION.md. It uses
  the existing WSGI application with disposable synthetic records, not production
  accounts. No alternative product backend was added.
- CodeRabbit skips Draft PRs by default. A manual review cancelled because the
  head changed is not a completed review. Request it again on the stable head.
- Real Google OAuth and production/Android device synchronization remain release
  gates coordinated with the Android/backend owner. No production credentials,
  registration opening or deployment are part of this branch.
- Legal notices remain preliminary pending operator identity, retention and
  jurisdiction review; no legal approval for a public launch is claimed.

## Safe next integration steps
Apply this branch to a checkout with write access; inspect for concurrent changes.
Open a draft PR to feature/uladim-hostinger-launch, review CodeRabbit critically,
run web CI and review screenshots at 375/768/1024/1440 in both themes. Approve
visual baselines manually. Resolve backend gaps in separate coordinated PRs.
Only then use an explicitly configured staging origin with the same real backend
and test synchronization with Android. Do not merge or deploy based only on these
local checks. Rollback is reverting the web PR; no database migration is included.
