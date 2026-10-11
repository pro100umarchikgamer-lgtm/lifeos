# LifeOS — Offline Core Expansion: Implementation Brief

**Prepared:** 2026-10-11  
**Repository:** `pro100umarchikgamer-lgtm/lifeos` · `main`  
**Last verified remote HEAD:** `23e537d7256b` (GitHub Actions #39 successful). Always recheck HEAD before editing.  
**Status:** Approved product direction; implementation NOT yet started for this expansion.  
**Execution language:** Code/comments as appropriate; progress and final reports **in Russian**.

## 1. Product objective

Deliver a substantial **offline-first expansion** of an already working LifeOS Personal Core, without rebuilding the app, adding cloud/server dependencies, or breaking existing installed users. The product is a simple, integrated personal/family life organizer, **not** a spreadsheet, a complicated Notion clone, or a set of disconnected demo screens.

An ordinary user must be able to use the app immediately, without registration, a tutorial, setting up accounts, or choosing a budget. Adding a basic expense, note or task remains fast. Advanced choices appear only when useful.

### Existing, to preserve

Flutter Material 3 UI, responsive Home/Plans/Finances/Modules and profile, four distinct Quick Add cards, four color palettes and dynamic wallpaper theme, date/calendar/reminders, notes/tasks CRUD with undo and revisions, SQLCipher encrypted local SQLite, UUIDs, typed ActionEngine with idempotent operation journal, backup/restore encryption and validation, Android native alarms, locale-pack infrastructure, test signing identity, GitHub Actions workflow, tests and existing user records.

**Current database is schema v3** (`assets/migrations/001.sql`–`003.sql`). Accounts table exists but is not yet a complete user-facing account ledger. Existing transactions have optional `account_id`. Do not assume all user transactions have accounts/categories. The old `docs/ROADMAP.md` has a now-superseded sequence; synchronize documentation with the approved offline-first order without deleting full v0.1 scope.

## 2. Market research translated into design decisions

This is a synthesis of documented *patterns*, not a license to copy other apps or to claim hands-on benchmarking that did not occur.

| Reference | Verified useful pattern | LifeOS application |
|---|---|---|
| Todoist Quick Add (September 2026) | Enter task first; reveal scheduling, reminder and advanced options contextually. | Fast task input with optional date/priority/links; no massive default form. |
| TickTick | Shared calendar/task scheduling and habits, multiple calendar views. | One existing calendar engine; habits/projects/study create linked events rather than a second scheduler. |
| Actual Budget | File import with column mapping, duplicate candidates, paired transfers, explicit rollover logic. | Local import preview/confirm, reversible batches, no silent duplicates; transfers never count as consumption. |
| YNAB | Visual savings goals, planned allocation, debt and useful reports. | Clear budget/goal views without forced zero-based budgeting or restrictions. |
| Wallet by BudgetBakers | Real bank CSV/XLS/XLSX/OFX format support and number/date quirks. | Format adapters with deterministic parsing, localized numbers and error reports. |
| Google Keep | Simple notes with reminders. | Full-screen note editor, checklists and links; keep single shared reminder engine. |
| Obsidian | Tags and links between knowledge items. | Typed record links and note tags, not a plugin system or document vault. |
| Notion | Flexible information organization, but complex forms and partial offline availability. | Adjustable dashboard widgets; strong offline behavior by default and no database jargon in UI. |
| Flutter official guidance | Profile-mode real-device measurements; lazy lists; localized rebuilds. | Performance gates based on evidence, not only debug APK impressions. |

Primary sources:
- https://www.todoist.com/help/todoist/features/use-task-quick-add-in-todoist-va4Lhpzz
- https://ticktick.com/features
- https://actualbudget.org/docs/transactions/transfers/
- https://actualbudget.org/docs/transactions/importing/
- https://www.ynab.com/features
- https://support.budgetbakers.com/hc/en-us/articles/7077275632274-Import-your-transactions-or-files
- https://support.google.com/keep/answer/3187168?co=GENIE.Platform%3DAndroid&hl=en
- https://obsidian.md/help/properties
- https://docs.flutter.dev/perf/ui-performance

## 3. Work packages — implement continuously, test and checkpoint each

Do not split this into independent new conversations or await user approval after each small module. Use a coherent architecture and incremental commits. Never make a giant untested final commit. Do not silently omit any package; if blocked, record the exact blocker and continue independent packages.

### A. Safe financial foundation

- Extend current accounts into user-visible **cash/card/wallet/deposit/custom bookkeeping accounts**, all optional. Allow initial balance, name, currency, archived state and correct transaction assignment. Never collect card numbers, banking credentials or bank-login details.
- User-defined transaction categories and subcategories, reassignable at any time; category metadata must not alter historical financial truth.
- Money stored in exact minor units (or precision-safe integer decimal representation where multi-currency conversions require it); **no floats for accounting**. Preserve existing currency digits and revisions. No implicit conversion or mixing currencies.
- Expense without an account is valid; it affects expense analytics but never decrements a guessed account. Opening balance may be positive or negative. Retroactive edits update derived balances.
- Atomic, paired **internal transfers** that move funds between two accounts without being income/expense. Cross-currency transfers require explicit entered received amount/rate, and preserve both currencies. Reversal/edit/delete affects both sides consistently and has a safe audit trail.
- **Split one expense** into category/project/participant allocations; category budgets report splits, but the financial transaction and total expense must be counted only once.
- Separate **real money movements**, **budgets/allocations**, and **future planned cashflow** at the domain/data-model level.
- Budgets by week/month/year/custom interval, optional rollover of positive, negative, both, or neither. Overspending and negative balances are valid; warnings never block entry.
- Planned income, bills and recurring financial reminders remain **plans** until manually confirmed as real transactions; confirmations cannot create duplicates. Distinguish recurring task from recurring financial transaction.
- Clear financial screens: ledger, account list, categories, budgets, planned cashflow and analytics; no unreadable walls of tiny numbers.

### B. Savings, obligations and manual investments

- Savings pots/goals: target, contribution/withdrawal, optional linked real account vs virtual earmark. No double-counting real money, no magical changes to account balances when earmarking only.
- Debts/loans/IOUs, installments, remaining principal, due dates; distinguish principal repayment from interest and fees. Debt and loan movements reconcile with user-selected account transactions only when explicitly linked.
- Manual investment records: assets, positions, buy/sell, fees, dividends, distributions, user-entered valuations. Show realized vs unrealized gain separately and identify estimates as estimates. No automated quotes or trading execution.
- Financial record links may reference projects, savings goals, family profile placeholders, etc., without silently sharing private data.

### C. Manual import of bank-exported transaction files

- Entry: **Finances → Import from file**, optional, no bank login. Use Android system file picker/Storage Access Framework for user-selected file from downloads or chosen cloud provider. No broad file or SMS permissions.
- Priority formats: CSV/TSV, XLS/XLSX, OFX/QIF; support sensible TXT/JSON/XML where well-defined. Text-based PDF **only if reliable safe parsing is feasible**; do not promise scanned PDFs/OCR or arbitrary bank formats.
- Never run scripts/macros/formula instructions; treat spreadsheet formulas as untrusted. Apply file-size/row-count/time/memory limits. Handle date formats, decimal comma/point, negative signs, encodings, multiple sheets and multicurrency uncertainty explicitly.
- **Three-step flow:** select → preview/map dates/amounts/currency/descriptions/account → confirm chosen records. Show import summary, skipped invalid rows, duplicate candidates and uncertainties. Do not silently discard an ambiguous duplicate.
- ImportBatch ID and per-row origin metadata (only minimal normalized dedupe keys), idempotent transactional confirmation and undo/reversal for a whole import batch without touching unrelated pre-existing transactions.
- Never store/upload the source file as a document. Drop ephemeral temporary source data after processing and confirmation/cancel; retain only user-approved normalized records and minimal import metadata. Server, cloud and background bank access forbidden.

### D. Connected personal modules

- **Projects:** goal, milestone, tasks/subtasks, due dates, statuses, simple progress, optional planned vs actual budget links. Keep tasks as one canonical entity, not duplicated copies.
- **Habits:** schedule, check-in, completion/streak, pause/resume, optional reminders via existing calendar engine. Streak calculation robust across timezone and daylight-saving changes. No punitive UX for missed days.
- **Learning:** subjects, study assignments, timetables, progress, links to tasks/projects/calendar; no complex grade book required unless explicitly specified in master spec.
- **Notes:** checklists, tags, quick search and safe links to other records; preserve existing body and reminders. No document-management module.
- **Home/household:** shopping lists and chore templates locally; can later be assigned to family participants when server-supported rights become available. Avoid pretend multi-user collaboration.
- **Minimal wellbeing:** optional general activity/sleep/habit logs, not medical records, diagnosis or healthcare documents.
- **Dashboard:** working hide/show/reorder controls, compact vs expanded modules (limited presets), persisted per local workspace. Keep four independent Quick Add cards, Today dashboard and approved reference composition. No empty 'Coming soon' screens for supposedly implemented modules.
- **Family foundation, local-only:** immutable local profile IDs for adults/child-managed profiles, workspace memberships and permission *data structures* ready for future authentication/sync. Do not turn identity names into IDs; do not misrepresent simulated collaboration as real family access. Preserve current local owner/workspace IDs. Future account linking needs a documented migration path.

### E. UX and Android polish integrated with changed screens

- Fix user-observed Permissions & Diagnostics screen: structured status cards and readable distinct buttons, system-appropriate allowed/blocked states, long OS limitations in collapsible help, no raw diagnostic text wall. Keep real permissions requirements.
- Fix clipped/floating captions, especially **"Повтор"** in task/event editors: never draw text through outline borders. Eliminate duplicated labels in nested ExpansionTile + selector fields; make repeat settings compact and understandable.
- Refine nested rounded bottom sheets/selectors, limited heights, sensible overlay dimming, safe areas, soft keyboard behavior and 200% text scale. Do not layer unnecessary stacked sheets.
- Premium calm typography, aligned finance figures and chart scales, subtle motion, tactile feedback, consistent input/selectors and light/dark/pistachio palettes. Respect reduced motion and minimum touch targets.
- One consistent `Modules` hub with useful available modules, discoverable search/filter, contextual quick add and readable empty states. Avoid hamburger/menu complexity.
- Performance: measure on physical Android in **profile mode** if available, target smooth screen transitions and efficient 1k–10k row rendering; use paged/lazy lists and limit app-wide refreshes. A green visual golden screenshot test does not prove match to approved design or real-device 60fps.

## 4. Implementation constraints

- Extend **typed ActionEngine**; UI must never mutate SQLite directly. Every mutation has a UUID operation ID, stable record ID, version/revision checks, owner/workspace scope and transactionally consistent writes. No duplicate operations after retries.
- Versioned migrations strictly forward from v1, v2 and v3 and from current app-installed database. Tests must cover migration and rollback-on-failure. **Do not delete/recreate existing DB or overwrite local key.**
- Maintain compatibility with existing encrypted backup/restore. New tables must have deterministic validated export/restore with foreign-key integrity and no lost data.
- Future server synchronization will be batched AFTER local Save, not per keystroke. Only prepare stable IDs, metadata and operation journal; **do not** implement or depend on server/network here.
- Android test APK update must retain exact existing `applicationId`, permanent test signing certificate and incremented `versionCode`; never expose keystore. No force-push or loss of Git history.
- New text via locale keys; update RU and EN language packs fully; preserve one versioned language pack per locale and all 15-language/16-locale release requirements. Do not claim remaining language packs are complete when not reviewed.
- No forced onboarding, no server, no AI, no SMS/Open Banking, no fake account integrations, **no documents module**.
- Keep scope narrow inside each package, but the complete approved Offline Core scope broad; eliminate redundant services/models.

## 5. Mandatory acceptance scenarios

1. Install updated APK **over** old signed LifeOS; original accounts/records/notes/calendar/reminders and encrypted backups survive. Fresh install works too.
2. Add expense without account; budgets/analytics update but account totals do not change. Add retroactive source account and verify balances accurately.
3. Transfer between accounts (same currency and different currency with explicit values), edit/undo/delete; no income/expense double-counting.
4. Split one expense into two categories and one project; actual expense appears exactly once while allocations sum to it.
5. Carry positive and negative budget remainders forward according to explicit selected policy; overspending remains valid.
6. Add savings contribution as virtual earmark vs linked real transfer; avoid increasing/decreasing available money twice.
7. Create bill reminder; verify it does NOT appear as paid income/expense until user confirms; confirmation idempotent.
8. Buy/sell investment manually, fees/dividends/valuation, verify realized/unrealized separation.
9. Import CSV/XLSX/OFX realistic fixture, select columns, flag possible duplicate, import confirmed subset, repeat import with no duplicate, undo batch without deleting user-entered transactions; source file not retained.
10. Create project with nested tasks, habit with repeat and check-in, learning assignment, checklist note and shopping list; existing unified calendar/reminders display relevant activities, no duplicate schedule engine.
11. Modify names of local profiles with same display name; stable IDs and links remain correct. No unauthorized leakage of personal records into family-ready placeholders.
12. Reload/restart, change theme/language, create encrypted backup, restore on separate test database/device; every new module survives and passes FK/integrity checks. Wrong-password/corrupt restore leaves original intact.
13. Validate permissions screen, "Повтор" field, selector layout and bottom sheet keyboard on 320/390/430 dp and 200% text scale in light/dark; no overlap. Review real screenshots rather than only goldens.
14. Unit/domain/migration/UI/integration tests pass; real Android alarms not silently altered; profile-mode performance measured on physical device where possible.

## 6. Development and delivery protocol

1. **Immediate execution:** inspect repository and current branch; preserve all correct work. No planning-only run. Implement package A first, then B, C, D, E in one coordinated assignment, or split package D internally if context limits require it.
2. After each coherent package: run focused tests, **commit and push if permitted**, report in Russian which files changed, what passed, what remains. No waiting for new approval.
3. If GitHub write returns 403, try at most once in this environment then **create a clean patch + repository snapshot/commit bundle** based on exact current main HEAD; preserve all work for safe application by Work or Codespaces. Never force-push. No repeated SSH/proxy/SDK installations beyond 3 attempts per blocker.
4. If Flutter SDK is unavailable, run available Python/schema checks; document unverified Dart/Kotlin rather than claiming validation. GitHub Actions in the connected repository performs full Flutter and Android native checks once changes are published.
5. Avoid one huge, fragile untested diff; keep independently reviewable, atomic checkpoints. No additional debug APK per package. **ONE final signed APK** after the full CI validation has succeeded (or clear blocker report if not possible).
6. The final report in Russian must provide tested features, untested features, migration integrity, new module paths, commit(s), CI status, screenshots, APK artifact link, exact test result counts and remaining limitations.

**Stop conditions:** never remove SQLCipher, authorization-ready owner boundaries, checks or signatures merely to force CI green. Do not publish a version claiming feature-complete when one mandatory package is absent; mark explicitly incomplete and preserve it for the next continuation.

## 7. Future follow-up after Offline Core acceptance (NOT part of this assignment)

Optional account sign-in and immutable server user IDs; central backend and PostgreSQL; batched background synchronization with per-workspace access control, eventual consistency, conflict resolution; real family invitations and separate child/adult permissions; independent encrypted off-VPS backups (including user-owned Google Drive where appropriate); load tests. VPS selection and deployment belong here, not to the current offline milestone.

Current product-wide release still requires 15 languages / 16 locales, including Uzbek Latin and Cyrillic; final localization, iOS validation and public launch compliance are **not** silently declared complete by this offline expansion.
