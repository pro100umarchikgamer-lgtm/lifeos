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

Follow-up: add account-only budget inbox preferences, disabled by default, with 50/80/100 and every 5/10/15 percent presets. Persist settings and queued changes in the same encrypted account cache; explain refresh-only synchronized-budget scope and the absence of system alerts. Honor server account-history retention metadata while retaining private reminders, and drop terminal not_found/notification_inactive queued message-state operations. Verification: 50 focused/controller/widget/locale/regression tests pass, including offline budget persistence and large-text threshold selection.

Independent review fixes: delayed GET/ACK/settings commits now rebase inside the same mutation queue as disk-backed local actions. Read-all captures the invoking account generation before waiting, so a queued Alice action cannot target Bob. Tests reproduced the slow-disk read/presented overwrite and account-switch cases before these fixes, then passed. Exact not_found/404 and notification_inactive/409 state mutations drain once; rate_limited/429 and offline changes stay queued. Public legal and safe relative /app links use the canonical public SITE_ORIGIN, with optional LIFEOS_SITE_ORIGIN configuration. Final verification: 65 focused protocol/controller/widget/account/locale tests pass; Flutter analyzer reports no issues.
