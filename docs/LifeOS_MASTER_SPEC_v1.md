# LifeOS — Master Product Specification

**Status:** Approved product direction; implementation not started  
**Revision:** 1.0 · 10 October 2026  
**Purpose:** Single source of truth for Codex planning and staged implementation  
**Working language:** English in specifications; Codex communicates progress and decisions in Russian.

## 1. Product vision and non-negotiable principles

LifeOS is a modular, offline-capable personal and family organizer combining everyday finances, tasks, reminders, notes, shared spaces, savings, habits, learning, projects, and lightweight wellness tracking. It must be powerful internally but immediately understandable to ordinary people.

- **Fast by default.** Adding an expense, income, task, or note must take seconds; do not require the user to configure a module first.
- **No artificial spending restrictions.** A budget is an accounting/planning tool, not a payment authorization system. Negative balances, overspending, missing accounts, and incomplete history are valid states.
- **Only essential fields are required.** All other metadata remains editable later.
- **Personal privacy by default.** Family membership never implies access to another adult's private records.
- **Personal and family use are first-class.** A person can use LifeOS alone or join multiple shared spaces without separate accounts.
- **Common underlying mechanisms.** Reuse tasks, calendar events, reminders, permissions, relationships, and transaction processing across modules instead of recreating them.
- **High customization, low visual noise.** Prominent primary actions; compact secondary controls; advanced settings visible on demand, but important permissions and limits remain easy to reach.
- **Works without AI.** AI is introduced after the core product; it is an optional interface to existing typed actions, not the foundation of application behavior.
- **Android-first**, designed for responsive phone/tablet UX and potential later expansion to other platforms.
- **No code in the planning conversation.** Codex Plan Mode receives this document, proposes the technical plan, and implements only after plan approval.

## 2. Release strategy (substantial v0.1)

### v0.1 — usable personal + family LifeOS
A cohesive everyday product, not a finance-only prototype:

- Offline-first personal experience; optional account registration for cloud synchronization and family sharing.
- Accounts, workspaces, equal co-parent capabilities, child profiles and configurable access; family budgets, chores, reminders and shared calendar.
- Manual finances: accounts, income, expenses, transfers, categories, budgets, debts, savings pots/goals, basic manual investment tracking, planned income/payments, and useful views.
- Extremely fast manual entry for finances, tasks and notes, with optional advanced fields.
- Simple calendar, tasks, recurring reminders, device alarms/notifications subject to OS permissions.
- Notes, habits, learning schedules, projects, basic wellness check-ins, home chores; shared underlying task/reminder components.
- Customizable dashboard, global search within accessible data, consistent navigation and UI.
- Optional **user-initiated, on-device import** of exported financial transaction files with preview and confirmation.
- Localization from day one: English, Russian, Kazakh, Uzbek and Ukrainian (Uzbek Latin plus ideally Cyrillic).
- Sync, conflict preservation, backup/recovery strategy, security and test coverage adequate for real family use.

Plan and deliver v0.1 as testable internal milestones; do not ask Codex to implement everything in one giant change.

### v0.2 — optional AI assistance
AI recognizes short natural-language requests and emits a small, validated, structured list of existing application actions. Complex planning/summaries are optional extensions. AI does not directly modify the database and is not required for ordinary workflows.

### v0.3 — external beta and hardening
Cross-device and family testing, import edge cases, recurring reminders, sync conflicts, localization QA, accessibility, data recovery, performance, and defect fixes.

### v1.0 — production release
Polish, reliability, onboarding, store preparation, support, diagnostics/privacy, and validated completion of all launch-critical scenarios.

**No banking automation in this roadmap.** Revisit any new integration only if a future product decision explicitly authorizes it.

## 3. Information architecture and interaction standard

Suggested bottom navigation: **Home / Plans / Finances / Modules / Profile**. Family/shared workspace is accessible by a simple workspace switcher, not an additional compulsory tab.

### Home
- A clear Today section, next actions/reminders, finances, goals and optional family summary.
- User can show/hide/reorder/resize widgets, choose a preferred home layout, and customize personal vs family dashboards independently.
- Presets may be offered (balanced, finances, study, family) but are never mandatory.
- Visible **Quick Add** entry point for Expense / Income / Task / Note; events and further actions available without deep navigation.

### Forms and settings
- Default expense: amount, optional short purpose/category, date defaults to today. Source account, budget, participants, project and memo are optional. Save should not fail because a source is missing.
- Default income: amount, optional label/source; planned and received income remain separate.
- Default task: title; due date, reminder, assignment and recurrence optional.
- Default note: text; tags and links optional.
- Every module uses large primary actions, inline Edit/Change buttons for limits and permissions, small contextual icons or ellipsis for rare actions, and an optional expanded section.
- Crucial controls (e.g., child permissions, budget limit) should normally be accessible within **two taps** from their associated screen, not buried in nested global settings.
- Support edit, undo where feasible, accessible touch targets, light/dark themes, and predictable navigation.

## 4. Core shared data and permission model

Design a modular typed domain model rather than one generic unstructured table. Core concepts include: User, Workspace, Membership, Role/Permission, DashboardConfiguration, Account, Transaction, Budget, Allocation, SavingsGoal, Debt/Obligation, InvestmentHolding, Task, CalendarEvent, Reminder, RecurrenceRule, Note, Habit, LearningItem, Project, WellnessEntry, Link/Relation and ImportBatch.

- Every record has a well-defined owner, workspace visibility, timestamps, and stable identifier.
- Changes requiring sync are idempotent; retries must not duplicate financial transactions or notifications.
- Linked objects reuse one task/reminder mechanism. Links do not duplicate expenses or assets.
- Per-user visibility and object-level grants are enforced in the application/backend, not only hidden in the UI.
- Personal data and family-shared data remain distinct even when linked.
- Support offline edits followed by sync. Merge independent additions; surface real concurrent conflicts, never silently overwrite a conflicting budget or permission value.
- Maintain a meaningful audit/history trail for shared financial and permission changes; provide restore/undo for accidental edits.

Codex should recommend a practical Android/client/local storage/backend stack during planning rather than assume an expensive server from the outset.

## 5. Family spaces, roles, children and collaboration

- One account may belong to multiple personal/shared spaces. A child may initially exist as a parent-managed profile without a login and later link an account to that profile.
- **Two parents are equal** in everyday family management: assign tasks, manage child budgets, record transfers, review shared activities, and adjust child permissions.
- The original workspace creator has the exclusive ability to dissolve the family space; this ownership must not make one parent superior in everyday child management.
- One parent cannot silently or unilaterally remove the other parent's equivalent parental authority. Sensitive role changes need a transparent confirmation/dispute/recovery route.
- Adults' personal accounts, diaries/notes and finances remain private unless the owner grants specific access. Grants are scoped, visible, and revocable.
- Child permissions are configurable individually: view own budget, add/edit own entries, report spending, request funds, interact with shared budgets, create/complete tasks, etc. Presets are only convenient starting points.
- Permission controls govern **who may access/modify records**, not whether real-world spending can happen. Do not reject a child's recorded expense for exceeding a budget.
- Both parents can independently contribute to a child's money record and assign tasks. Parallel legitimate additions are both kept.
- A child may have a personal budget and participate in one or more shared budgets (e.g., two siblings share one allowance). Track attributed spending without double counting.
- Money requests to multiple parents close once fulfilled; do not issue duplicate fulfillment from repeated actions.
- Task assignment modes: single person; each participant separately; jointly performed; first/any participant completes. Optional parent review, rescheduling, recurring chores, and optional rewards.
- Shared events/reminders can be created by authorized members; each recipient controls their device's notification behavior. Do not assume a remote adult can force an alarm on someone else's phone.
- If a family space is dissolved or a member leaves, private content remains theirs; only allowed shared content may be exported or retained according to access rules.

## 6. Financial engine (manual-first, not restrictive)

Keep **three distinct concepts**: (a) recorded real accounts and transactions, (b) spending budgets/allocations, (c) scheduled/planned cash flow. Do not present an expected payment as already received.

### Entry and account behavior
- Manual income/expense/transfer first. Cash, cards, wallets, deposits and user-defined accounts supported; custom categories and different currencies supported.
- Expense source account is **optional**. An unassigned expense affects expenditure analytics and applicable budgets but does not secretly decrease a guessed account balance. A later edit can assign it.
- Support arbitrary starting balances, retroactive entries/edits and recalculation. Negative account balances and budget remainders are acceptable accounting states.
- Internal transfers among one's accounts are not income/consumption; same for tracked intra-family transfers when showing consolidated family totals.
- Split one purchase across several budget allocations/participants/projects without counting it twice as actual spending.
- Correct mistakes via edits; keep meaningful edit history for shared records.

### Budgets
- Personal, family, child-specific and multi-child/shared budgets.
- Periods: week, month, year or user-defined. Per-budget options to carry positive remainder, negative remainder, both or neither into the next period.
- Remaining budget may be negative. Notify gently if opted in; never block a recorded purchase.
- A budget allocation does not claim that cash physically moved.

### Income, payments, savings and obligations
- Multiple income streams: salary, advance, freelance, business, stipend, benefits, gifts, interest/dividends and custom categories.
- Salary and advance may be installments of one monthly salary; avoid double-counting expected total.
- Recurring incoming payments and bills generate **plans/reminders**, not automatic actual transactions. User confirms receipt/payment.
- Savings pots can be virtual earmarks or linked to an actual account; avoid counting linked money twice. Support personal and shared goals, target amount/date, contributions and withdrawals.
- Debts, loans, installments and money owed/owing; separate principal movements from relevant interest/fees. Family reimbursements should not double-record the originating purchase.
- Manual investment portfolios, buys/sells, holdings, fees, dividends and user-entered valuations. Distinguish market value, realized gains, unrealized gains and cash distributions. No automatic quotes required for v0.1.

### Presentation
- Views for Now / Plans / Family (when available), with understandable cards and charts; user-customizable widgets.
- Different currencies must not be silently summed without an explicit conversion method/rate.
- Show accounting uncertainty plainly when some sources, opening balances or past entries are missing, without treating incomplete records as an app error.

## 7. Optional import of bank-exported files (NOT banking automation)

This is an **advanced manual feature**: the user explicitly selects a local exported file. There is no bank connection, bank account credential, SMS access, notification listener, automatic download or background bank monitoring.

- Target feasible formats: XLS/XLSX, CSV/TSV, TXT; structured JSON/XML/OFX/QIF where supported; text-based PDF extraction when reliably feasible. Non-text scans/OCR are not necessary for the first release.
- Parse source files on device; never automatically upload or retain the statement document. Only user-confirmed normalized transaction records may enter LifeOS and sync subject to normal account settings.
- Detect encodings, separators, dates, number formats, multiple sheets, currency and signed amounts as practical.
- Show a preview and probable categories. For unknown structures, let the user map columns to date, amount, type, description and account.
- Identify duplicates based on available evidence and mark uncertain matches for review rather than silently dropping legitimate operations.
- Import only after explicit confirmation; group records into a reversible import batch.
- Never execute spreadsheet macros, formulas or embedded code; treat input as untrusted.
- Adding new format/bank parsers must not alter the accounting engine.

## 8. Plans, notes and everyday modules

### Calendar / tasks / reminders
Keep this familiar and straightforward, like standard phone apps: one shared calendar engine for personal and family events, tasks, recurring rules, alarm-style reminders and scheduling.
- Date/time/time-zone handling; recurring reminders; snooze, dismiss and mark done; ordinary vs important reminders.
- Android notification/alarm delivery must respect OS permission and scheduling limits. Avoid guarantees the platform cannot enforce.
- Finances, family chores, learning schedules, savings contributions, wellness routines and projects can create calendar entries using the same engine.
- Scheduling overlap indication is useful, but do not build a complicated autonomous scheduler for v0.1.

### Notes, habits, learning, projects, wellness, home
- **Notes:** plain text, checklists, tags/search and links to relevant records. No document management workflow.
- **Habits:** schedules, check-ins, streaks/progress and optional reminders.
- **Learning:** subjects, study tasks, deadlines, timetable and progress; reuse tasks/calendar.
- **Projects:** personal/shared projects, subtasks, milestones, basic budget/goal links and participants.
- **Wellness:** voluntary minimal wellness/activity/sleep habit tracking; **no medical records or healthcare document storage**.
- **Home:** shared chores, shopping lists and household reminders, reusing family tasks/budgets.

## 9. Languages and regional preferences

**Release languages:** English (`en`), Russian (`ru`), Kazakh (`kk`), Uzbek Latin (`uz-Latn`), Ukrainian (`uk`). Design for Uzbek Cyrillic (`uz-Cyrl`) as an additional ready-to-ship variant if feasible.

- All user-facing text uses stable localization keys; no untranslated hard-coded interface strings.
- Define **one versioned language-pack file per locale** holding full translated strings, plurals, error messages, notifications, help text and relevant localized templates. New complete locales ship with an app update by adding one pack, without modifying business logic.
- Validate pack schema, missing keys, placeholders, plural forms and version compatibility during build/CI; use a defined fallback language for unknown keys.
- Design responsive UI for long translations and future right-to-left support.
- Language, region, currency, time zone, week start and date formatting are independently configurable. A family can contain members using different interface languages.
- A complete language pack does not automatically create store-listing translations or eliminate the need for linguistic review.

## 10. Safety, privacy and explicitly excluded functionality

**Do not implement or propose:**
1. A documents module; collection, uploading, scanning, management or storage of passports, identity cards, driving licenses, medical records or personal document archives — now or as a future LifeOS module. Users may create ordinary date-only reminders (e.g., a renewal date) without storing document files.
2. Bank APIs, Open Banking connectors, banking automation, SMS parsing, Android notification reading, payment initiation or automatic bank transaction monitoring in any currently planned release.
3. Forced AI onboarding, mandatory AI for core actions, hidden access to other adults' private information, hard stops when spending exceeds a budget.
4. Large per-country infrastructure, elaborate compliance automation or expensive servers before actual need is established.

Security should be proportional but real: secure authentication where required, encrypted local sensitive data when feasible, protected transport, server-side authorization for shared data, safe exports/deletions, backup and recovery, and a practical release-time review of applicable law and store requirements. Do not pretend that choosing a language or country setting alone settles legal residency issues.

**Special case:** the user-selected exported bank statement is a temporary local input to parsing, never a stored document or cloud upload. It is explicitly allowed under section 7.

## 11. Later AI interface (v0.2, not v0.1)

- AI receives minimum necessary input and a small catalog of allowed typed operations (e.g., `expense.create`, `income.create`, `task.create`, `reminder.create`).
- Example: “Spent 3,000 rubles on groceries today and remind me on 25 October at 18:00 to pay for internet” should produce **one structured response with two proposed actions**.
- Deterministic application code validates amounts, dates, rights, default fields and duplicates, then asks confirmation where appropriate and executes through the same normal engine used by UI controls.
- AI must never search source code, invent DB fields, directly edit storage, or receive unrestricted access to personal/family data.
- Prefer no-model logic for clear input, a low-cost model for short intent extraction, and stronger inference only for genuinely complex requests. Keep providers replaceable, keys server-side and token usage measured.
- Compare GPT, Claude and Gemini on quality across target languages and actual cost before choosing a provider. No need for a large multi-provider ensemble.

## 12. Implementation planning and quality gates

Codex should first propose a concise architecture, module boundaries, prioritized v0.1 internal milestones, dependencies, acceptance tests and realistic deployment assumptions. Do not start coding in Plan Mode until the plan is reviewed.

Mandatory scenario tests for v0.1:

1. New user creates a local note, task and expense without registration or lengthy setup.
2. Expense lacking a source account saves correctly; no unrelated account balance changes.
3. Budget overspending and negative carry-forward are accepted and displayed correctly.
4. A family of two equal parents and three children uses one individual child budget and one budget shared by two children.
5. Both parents add money/tasks independently; records are kept once each, with no unwanted double-counting.
6. A parent cannot read the other adult's private finances without explicit permission.
7. A child records spending beyond a budget and is not blocked by accounting logic.
8. Shared edits across offline devices preserve independent changes and surface direct conflicts.
9. Reminders recur, trigger according to granted OS permissions, and expose clear fallback behavior where exact alarms are unavailable.
10. A planned advance/salary remains a forecast until marked received; salary parts do not duplicate total income.
11. An on-device XLSX/CSV import previews records, spots possible duplicates, requests confirmation and supports undo; raw source is not uploaded/stored.
12. UI remains coherent when reordered/resized, in all release languages, on typical Android phone/tablet screens.
13. All launch-critical functions remain usable while the AI module is absent.

### Codex delivery discipline
- Treat this document as the product baseline. Flag unresolved implementation choices instead of silently inventing functionality.
- Prefer straightforward, maintainable components over premature microservices or complex abstractions.
- Report milestones in **Russian**: delivered modules, tests run/passed, blockers, and next step; no inflated claims.
- Keep additional ideas in a separate short backlog; do not expand scope without approval.
