# LifeOS — UI/UX Design Gate Before Stage 2

**Document type:** Product/design acceptance brief for Codex Plan Mode  
**Version:** 1.0 — 10 October 2026  
**Status:** Review and design only. **No code changes are authorized by this document.**  
**Reference:** `LifeOS_MASTER_SPEC_v1.md`, approved subsequent launch-localization (15 languages / 16 locales) and reliable-alarm addenda, current `pro100umarchikgamer-lgtm/lifeos` implementation, and the user's recorded walkthroughs **if accessible in your task**. If a source is inaccessible, say so instead of inventing observations. If a design detail contradicts a product requirement, surface the contradiction explicitly for review.

## 1. Correct the interpretation of LifeOS

LifeOS is **not** a text notebook, generic CRUD demo, to-do list with bottom navigation, or spreadsheet in mobile clothing. It is a cohesive personal and family life-management product: capable yet simple, calm, premium in execution, and immediately useful. The user has explicitly rejected the current Stage 1 visual quality. The approved design direction uses organized modular cards, clear information hierarchy, useful summaries, quick actions, flexible dashboard layouts, optional detail, and a restrained visual style. It does **not** imply flashy animations, cluttered widgets, artificially inflated feature counts, or meaningless decoration.

Do not confuse a technically passing build with a product-quality interface. A screen is accepted only when **what it shows, what the user can do, and how it looks** meet the agreed standard. Do not blindly agree with proposed changes; identify conflicts, poor trade-offs, privacy leaks, data fabrication, and unsupported behaviors.

## 2. Ground truth and non-goals

- Preserve the verified Flutter architecture, domain actions, migrations, offline SQLite/SQLCipher, idempotency, tests, localization-pack architecture and functional Stage 1 behavior. Do not rewrite those layers merely for visual polish.
- Android-first, designed for eventual iOS with a shared Flutter UI and shared business logic; platform-specific alarms/permissions remain native adapters.
- Current implemented data: locally recorded expenses, income, tasks, notes, settings, RU/EN pack content. Some future modules, account balances, due dates, families, budget categorization and notification schedules are **not yet implemented**. Distinguish current functionality from the full v0.1 vision.
- Future v0.1 scope remains substantial: personal and family spaces, equal co-parent rights, configurable child permissions and budgets, finances, savings, manual investments, calendar/reminders, notes, habits, learning, projects, lightweight wellness tracking, and household tools. These should inform navigation and extensibility, **not be faked on current screens**.
- **No document collection/storage/management**, including passports, IDs or medical files. A plain date reminder is permitted.
- **No banking automation:** no API links, SMS or bank notification access. User-initiated local parsing of exported transaction files is a separate, optional advanced v0.1 feature, without retaining source documents.
- No AI dependency in v0.1; AI is a later optional structured-action interface. Do not introduce AI during this design phase.
- Do not impose spending caps. Negative totals, uncategorized expenses, incomplete sources, multiple currencies and budget overrun are valid. Do not pretend a cumulative income/expense total equals the user's bank balance.
- Launch targets: 15 languages / 16 locales including Uzbek Latin/Cyrillic; one complete versioned language-pack file per locale. EN/RU may be the only packs implemented at the current stage. Avoid hard-coded new UI text.

## 3. Visual north star — concrete design system

Design a coherent, calm, contemporary mobile productivity/finance app; not default Material widgets without an art direction. Material 3 may supply accessibility and OS conventions, but customize typography, component hierarchy, shape, spacing, selected states, icons, surfaces and empty/loading/error states.

- **Hierarchy:** a small, clean app header; clear page heading; one primary focal summary; 1–3 meaningful secondary cards; carefully grouped items. The user must identify today's most important information in roughly five seconds.
- **Palette:** restrained neutral backgrounds/surfaces, excellent light/dark modes, one controlled green/teal accent if appropriate, clear semantic success/warning/error states. Do not fill every control with the same mint-green pill and do not use visually noisy gradients.
- **Typography:** intentional scale for page title, balance/important number, section heading, item title and supporting text; readable Cyrillic and longer European strings. Monetary amounts are tabular/aligned, formatted with locale and currency correctly.
- **Spacing:** consistent grid (e.g. 4/8/12/16/24/32 logical px), adequate breathing room but no acres of empty space; coherent card padding, corner radii and component sizes. On compact phones, prioritize meaningful content above the fold.
- **Affordances:** clear action names/icons, sufficiently large touch targets, predictable inline actions, unobtrusive confirmation, reversible edits where applicable. Don't hide important budget/permission controls behind deep menus.
- **Density:** avoid both clutter and emptiness. Cards should convey information, not merely decorate a list. Never simulate fake live data to fill blanks.
- **Motion:** subtle, purposeful transitions only; respect reduced-motion preferences. Loading must not block basic local actions.
- **Accessibility/responsiveness:** contrast, readable scaling, labels for screen readers, keyboard insets, RTL-ready layout architecture, 360–430dp phones and tablets, one-handed reachability, meaningful light/dark parity.

## 4. Navigation model — a coherent information architecture

Working navigation target: **Home / Plans / Finances / Modules / Profile**, with a workspace switcher for Personal/Family as that feature is implemented. A persistent or equally discoverable **Quick Add** must let a user choose Expense, Income, Task, Note in one or two interactions. Do not show a “Modules” tab that is literally a renamed Notes screen. If only Notes is implemented, show Notes clearly as an available module in a genuine module hub or another truthful, simple arrangement; hide unimplemented destinations instead of presenting empty/dead buttons.

A user should never need to understand the backend entities, language-pack system or seven-stage roadmap to use the interface. Avoid mandatory onboarding for basic local use. Important actions on associated screens should normally be reachable within two taps; optional advanced actions can expand in place.

## 5. Screen-level blueprint and behavior

### A. HOME / TODAY — product identity, highest priority

Replace today's raw “Today + four green buttons + most recent 12 records” layout with an actual **daily dashboard**.

Top-to-bottom recommended structure:
1. Compact LifeOS header with an understandable current workspace label and a small entry to personalize the home screen (only functional when that capability exists). Date/day heading and a short, accurate contextual subtitle; not a generic 'offline-ready' banner as the main content.
2. One obvious Quick Add action or compact primary action row allowing Expense/Income/Task/Note. Avoid four equally loud green rounded pills consuming the visual hierarchy.
3. Meaningful **finance summary tiles** reflecting real recorded income and expenses for the selected period, grouped by currency. Label as recorded activity, NOT available cash balance. A small chart can be based on actual daily transaction totals if robustly supported; category charts only after categories exist.
4. **Task preview** showing incomplete tasks, number completed, and time labels only if the underlying data model actually supports them. Task completion must be immediate and reversible.
5. **Recent notes preview** with a readable snippet and tap-to-open. Don't merge note text, expense records and tasks into an undifferentiated feed.
6. Other dashboard widgets (family, goals, habits, upcoming calendar items) join as their real modules become available; no fictional cards implying functioning systems.
7. Use editable dashboard composition as the approved longer-term v0.1 requirement: show/hide/reorder/resize or choose a sensible layout; preserve local customization. Design the extension points now, then implement at the relevant milestone.

Required states: brand-new user (deliberate useful empty states), few items, many items, very long text, negative results, mixed currencies, offline, loading/recovery. The blank state should communicate what to do without looking unfinished.

### B. FINANCES — simple recordkeeping that looks like a financial tool

- Clear 'Now' summary with period selector (e.g., This month) and two distinct KPI cards: Recorded income, Recorded expenses; possibly net difference if supported and honestly labeled.
- Group and format by currency rather than silently combining RUB, EUR, KZT, etc. Label the choice of active currency.
- Visually distinguish positive/negative amounts without relying solely on color.
- Show legible transaction rows with purpose, local date, amount and type; allow viewing/editing when the corresponding action exists. Group by time where helpful; provide trustworthy empty states.
- Use lightweight graphs of actual data only when these can be drawn without fabricating categories/balances.
- Dedicated one- or two-step 'Add expense' and 'Add income'. Only amount required; other fields optional. Preserve keyboard focus, clear save feedback, and user-entered content after failures.
- Future prepared views: planned income, budgets, savings, debts, investment positions and family finances. Do not display current accounts or balances until built.

### C. PLANS — understandable tasks/calendar, not an empty checklist

- Show task overview with clear unfinished/completed grouping, simple status/actions and a prominent add button.
- Design future support for dates, time, recurrence, personal/family assignment and reminder modes. Do not display fake time labels before implemented.
- A familiar calendar is enough; do not create an overengineered scheduling system. When native notifications arrive at the relevant stage, design Standard / Important / Alarm modes with clear permission diagnostics.
- Tap items to view details; avoid silent failure and dead-end interactions. Plan editing and deleting capabilities even if a change requires a later functional milestone.

### D. NOTES — first-class notes, not a single dialog

- Show card/list previews with sensible truncation and recency; readable focused detail view.
- Plan an edit flow, deletion/undo, search, basic checklists/tags when supported, and related task links later.
- Notes should not be misleadingly synonymous with Modules. Preserve the offline-first write path and existing notes.

### E. MODULES — honest expandable hub

- Genuine organized navigation to currently available personal modules, with reserved clean architecture for Habits, Learning, Projects, Wellness and Home/Shopping as they ship.
- No false selectable 'working' modules, no cluttered icon grid of unavailable features, no complete module implementations merely for a mock screen.

### F. PROFILE / SETTINGS — tidy, understandable controls

- Group locale/language, currency, theme and local privacy clearly; visible current value and quick change control. Avoid merely piling three raw dropdowns with excessive whitespace.
- Reserve a comprehensible path to family workspace management and privacy controls for the later milestone.
- Explain permissions only where relevant; diagnose notification permissions when implemented.

### G. FAMILY (approved forward design, not current implementation)

- A Personal/Family switcher and family overview of shared budgets, reminders, household tasks and child budgets.
- **Equal everyday authority for both parents**; creator alone controls dissolution. Rights and child limits easy to find and change, with clear scope.
- Personal accounts/notes of each adult stay private unless specifically shared. No duplicated family transactions, no spending blocks for children; shared children may have one individual budget and two other children a joint budget.
- Include forward UI blueprints for this module, but do not present or implement false functioning screens during Stage 1 visual correction.

## 6. Quick Add — optimize for real human usage

Design one universal, recognizably LifeOS entry surface rather than four disconnected raw forms. The primary UI shows only necessary fields, with a clearly labeled expandable detail area.

- Expense: amount mandatory; note/purpose/category optional; default date today; source optional; negative budget result should never block saving.
- Income: amount mandatory; optional label and source; never imply a planned amount was received.
- Task: title mandatory; advanced date/reminder/assignment/recurrence when those functions exist.
- Note: text mandatory; optional checklist/tags/links later.
- Keyboard-safe layout, initial focus, appropriate numeric/alpha keyboard, Save/Cancel, protection from duplicate taps, predictable error message, post-save feedback and, where feasible, Undo.
- Evaluate time-to-complete: save a normal expense and a note without unnecessary navigation or configuration.

## 7. Visual design decisions and examples to present for approval

Create **one recommended, internally consistent design direction**, not a catalogue of 10 vague alternatives. Show the proposed visual tokens (palette, typography, spacing, corners, icons), a compact navigation map and screen-by-screen description with content and actions.

Supply an explicit visual representation for these **minimum six screens/states** before code changes: (1) Home populated; (2) Home empty; (3) Finances populated; (4) Task list; (5) Notes with an item open; (6) Quick Add expense with keyboard. Also specify dark theme and a compact-phone vs tablet adaptation. Include a family-home forward blueprint distinctly marked as future, not implemented.

If your environment can produce reviewable static mockups/screenshots *without changing production code*, provide them. Otherwise supply annotated low-fidelity wireframes/layout specifications and **say clearly that images were not produced**. Do not substitute verbal promises for actual visuals. After implementation is separately approved, CI should capture reproducible screenshots or golden snapshots of key real Flutter screens so design can be reviewed **before** waiting for the next APK; do not claim visual QA without reviewing those images.

## 8. Approval gates and acceptance criteria

**Gate A — DESIGN APPROVAL, current task:** No production code changes. Deliver a concise proposal with layout wireframes/static mockups where supported, design tokens, screen behavior map, explicitly currently possible vs future-only features, a small set of trade-offs requiring approval, and a prioritized implementation outline. Wait for explicit approval.

**Gate B — UI IMPLEMENTATION, separately authorized:** Refactor only presentation and required minimal user interactions using existing domain logic; preserve local data and migration safety. Keep current tests passing. Prioritize Home, Finance, Quick Add, Plans, Notes, Modules, Profile; share reusable components. Add UI/widget/golden tests and meaningful empty/dark/compact states. Do not fake data or work on Stage 2 sync/family backends.

**Gate C — VISUAL REVIEW BEFORE APK:** Provide real screenshots (light/dark, populated/empty, finance, quick entry, narrow phone; tablet where possible) plus a short explanation of what is tested vs simulated. Run `flutter analyze` and relevant widget tests. User evaluates appearance and usability **before** spending a full cycle building and installing an APK.

**Gate D — DEVICE SMOKE TEST:** Only after Gate C approval, build one debug APK through existing GitHub Actions; test basic record creation, viewing, edit paths where implemented, persistence across restart, navigation, light/dark, keyboard overlap and screen-size behavior on Android. Mark omissions and platform blockers honestly.

Definition of success: the app no longer resembles a flat sequential notebook; core activity can be understood at a glance; a user can find and record a transaction/task/note in seconds; numerical summaries are accurate, correctly labeled and grouped; primary flows are working, not visual facades; styles hold across light/dark/large text; no broken navigation or placeholder buttons; the foundation remains ready for real family features in subsequent stages.

## 9. Execution economy and critical judgment

- Do not implement all of v0.1 in this design iteration; do not rebuild the domain architecture to solve visual problems.
- Avoid speculative features, dozens of design concepts, unnecessary packages, design dependencies or excessive investigations. Prefer well-executed small shared components.
- Maximum three sensible attempts per truly blocked installation or command, with bounded timeouts; report the blocker and continue independent work. Do not skip correctness/privacy checks and falsely claim completion.
- If a user suggestion conflicts with device platforms, security, truthful financial accounting, current implemented capabilities or the agreed vision, explain the conflict and propose the smallest sound alternative. **Do not rubber-stamp requests.**
- Communicate plans and milestone reports **entirely in Russian**. Keep reports short and factual: done, evidence, unresolved, next step.

## 10. Exact current instruction for Codex

Operate in **Plan Mode**. Inspect this document, the approved master specification, the latest repository and available design references. **Do not edit production code, install Flutter, build an APK, commit or push.** First present the redesigned LifeOS user experience and the screens/states of Section 7 for user approval; distinguish existing functionality from future modules and identify only consequential open decisions. Wait for approval before any implementation.
