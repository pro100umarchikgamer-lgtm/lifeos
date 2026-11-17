# ULADIM Focus completion

Goal: finish the existing browser interface and batch statement workflow without changing the backend or Android.
Spec: owner's uploaded ULADIM_CODEX_TASK.md. Baseline: f973ed6 on work/uladim-web-platform.

The existing Focus implementation already covers the public pages, Today, tasks, calendar, notes and finance. Preserve those changes. This fresh clone contains no uncommitted owner work. The reference archive, original CSV and a conversation-reading tool are unavailable; do not claim fidelity or validation against those missing materials.

- [x] Import: reproduce stale mapping and conflicting amount assignments; add explicit modes, sample values, whole-file rebuilding and ready-row selection. Use synthetic statements; verify saved exact amounts, reread and repeat import.
- [x] Settings: make devices an application section; preserve password confirmation and selected-device revocation. Check narrow navigation, stale async responses and current-session logout.
- [x] Shell: expose profile and theme controls; show actual refresh progress/failure and last successful server read instead of an unconditional synchronization claim. Keep financial totals and private records untouched.
- [x] Verify: targeted browser acceptance using disposable real backend records; phone, tablet, desktop, light/dark and short viewport. Check public pages and safe service-worker updates. Run npm tests and relevant existing checks once after integration.
- [ ] Release: commit and push to existing branch without force. Production requires authorized Hostinger access, encrypted backup and rollback. No SSH binding or Codespace is currently available; do not claim deployment. Save concrete continuation evidence if this remains blocked.

Review focus: mapping changes during async preview; duplicate/currency separation; revoking only selected devices; changing settings while a request is pending; failed refresh retaining an honest status.

Ruling: user explicitly opted out of intermediate design approval and delegated technical choices. Continue directly on existing implementation; no builder questionnaire or new prototype.

Evidence: Chromium 1168 persisted synthetic operations including 1000-row common correction; 12 npm tests; Focus controls/devices at five sizes and both themes; both real sign-in routes; delayed workspace response regression RED→GREEN; platform acceptance; PWA update lifecycle. Original CSV, reference archive, physical iPad, production writes and this candidate on production remain unverified.

Ruling: live app.js, design.css and sw.js match f973ed6, contradicting the old release checkpoint. Treat that as asset evidence, not proof of the running container SHA.

Final review: reviewer reproduced old-space records rendering after queued workspace switch. Fixed by immediate generation invalidation; regression now passes.
