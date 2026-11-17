# Notification center and feedback implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans for the assigned scope.

**Goal:** Deliver the owner's new usability fixes, persistent notification center and an executed release-readiness audit.

**Architecture:** Extend the existing WSGI service, Web shell and Flutter/SQLCipher app. Separate additive inbox persistence from stable record/authentication logic. Independent audits inspect the published baseline.

**Tech Stack:** Python, SQLite/PostgreSQL, JavaScript/CSS, Flutter, existing Android bridge and CI.

**Spec:** docs/superpowers/specs/2026-11-13-notifications-feedback-design.md

## Global constraints

No paid services. Preserve existing data and backend behavior. Use synthetic test users. Never publish private recordings or credentials. Preserve Android package and signing identity. Do not silently bypass deployment guards or renew the expiring operations channel.

## Review focus

Cross-account notification isolation; duplicate reminder delivery; stale or expired announcements; active editor preservation; filled mobile layouts and long amounts.

## Tasks

- [ ] Review all five new recordings: local full audio transcripts, screen chronology, frame coverage and acceptance list. Owner: new_media_review.
- [ ] Add bounded, authorized inbox/announcement persistence, migration and customer/staff endpoints; test isolation, deduplication, expiry and state updates. Owner: notification_center_service.
- [ ] Add Web bell, notification page and Control composer with preview/audience confirmation; capture real responsive renders. Owner: web_inbox_control_ux.
- [ ] Add native bell, inbox, safe startup display and private offline reminder history; targeted controller/widget checks, legal links and branded launcher. Owner: native_inbox_ux.
- [ ] Fix demonstrated task/calendar/notes/finance interactions in existing Web components; meaningful browser checks against actual fixture. Owner: root.
- [ ] Execute admin/security and store/commercial audits with dated evidence, P0/P1/P2 backlog and separate launch decisions. Owners: admin_security_audit and stores_commercial_audit.
- [ ] Review changes independently, integrate commits, regenerate existing assets, run required checks once, then publish exact reviewed source and signed APK with rollback/evidence. Explicitly identify any operator action that existing access cannot perform. Owner: root.

## Progress

2026-11-13 13:41 UTC: started. Baseline application 84b0bdf; integration ee256a7; published APK 312001. Control is intentionally closed by edge HTTP 503. Five new videos identified by Drive metadata. Service, Web, native and audit scopes delegated independently.
