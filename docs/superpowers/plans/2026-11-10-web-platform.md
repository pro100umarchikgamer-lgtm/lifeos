# ULADIM Web Implementation Plan

**Goal:** Expand the existing second client using verified shared contracts.
**Architecture:** Vanilla JS/CSS, existing Python WSGI API; no new service.
**Spec:** docs/superpowers/specs/2026-11-10-web-platform-design.md

## Constraints
Separate branch from da2301c; PR base feature/uladim-hostinger-launch; no production,
main, Android, OAuth or database changes. Currency totals stay separate and exact.

## Review focus
Timezone day boundaries, month-end recurrence, lost mutation responses, switching
space while a dialog is open, offline deletion must not lose data.

1. Add failing domain tests for calendar recurrence/timezones, tasks and finance
validation; implement pure browser domain module; run unit checks.
2. Test calendar CRUD through existing record.put event contract, task filters,
note editing and deletion cancellation. Implement views and Today using same sync.
3. Redesign responsive shell and forms in existing CSS; test widths 375/768/1024/1440,
themes, text zoom and touch targets; inspect real screenshots.
4. Update safe PWA shell list/version, contextual offline/session messages, localization
coverage; run existing PWA/security/finance browser suites.
5. Add web-only PR CI (unit/browser/screenshots/dependency audit/CodeQL), document
contract gaps and results; commit, push and open draft PR without merge/deployment.

## Progress
- Repository audit complete; no deadlines/priorities on task contract, no server restore,
  habit/goal/debt/investment/category entities. Events do support recurrence/timezones.
- Ruling: user explicitly requested immediate execution; use existing stack and execute
  without a design approval round. No extra product decisions are needed to begin.
