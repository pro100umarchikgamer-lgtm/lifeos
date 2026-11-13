# Native notification inbox implementation plan

Goal: give ULADIM a persistent, readable native inbox and safe startup announcements.

Architecture: a focused NotificationCenter owns encrypted local reminder history and account-scoped message cache/queued state. The existing FamilyApi remains the authenticated transport. The shell offers a labeled bell and a compact banner; pushed details/fullscreen announcement routes show long text without interrupting editors.

Constraints: preserve SQLCipher, secure account sessions, logout isolation, offline personal data, all 16 locales, large text, and existing reminder scheduling. No paid dependencies, backend changes, or web assets. User explicitly requested autonomous execution without questions or approval gates.

- [x] Add meaningful controller tests for offline reminder history, deduplication, deferred read state, account changes during requests, and once-only presentation.
- [x] Implement models/controller, SQLCipher metadata adapter, and account lifecycle wiring. Run targeted tests.
- [x] Capture actual fired reminders through the encrypted Android runtime and bridge without changing alarm behavior.
- [x] Add the inbox, long-text detail page, bell, banner, and safe startup presentation. Add small-screen/large-text tests and actual UI screenshots.
- [x] Add public privacy/terms links using the existing service origin and native browser intent.
- [x] Add all locale strings; run Flutter analyzer, focused regressions and locale checks; inspect the final diff and commit.

Review focus: logout during network requests; failed persistence before acknowledgements; offline queued state; long text at 320 px/large font; announcements arriving while an editor is active.

Verification: 46 focused/controller/widget/locale/regression tests pass; Flutter analyzer reports no issues. The selected currency row header-bleed pixel regression and full-month calendar tests failed before the fixes and pass afterward. Launcher platform preparation was exercised twice in a temporary project: all ten density images, both adaptive resources, exact canonical brand source, manifest bindings, and idempotence passed. New APK/device validation remains with the root integration build.

Ruling: use existing SQLCipher sync_metadata for history rather than a new schema migration — account caches remain excluded from personal backups and the established encryption boundary is preserved. Personal reminder history is device-local and survives sign-out.
