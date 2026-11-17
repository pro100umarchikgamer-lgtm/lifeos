# November 15 feedback and referrals implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans. Preserve completed steps; the owner has explicitly delegated implementation choices and asked to work without intermediate approvals.

**Goal:** Address the three new recorded reviews, make owner activation usable, then add private referral reporting and produce a verifiable release.

**Architecture:** Keep existing application, authentication authority, native signer and working data flows. Put adjunct task scheduling/referrals in small modules; frontend calls existing authenticated/CSRF-guarded routes. Local verification and published production remain distinct.

**Tech Stack:** Existing Python/SQLite/PostgreSQL, vanilla JavaScript/CSS, Flutter/Kotlin. No additional paid providers.

**Spec:** Owner messages and the three videos listed in `/workspace/work/video-review/nov15/downloads.json` and `third-download.json`; full transcripts beside those files. Working checklist: `/workspace/work/delivery/feedback-2026-11-15/WORKING_STATE.json`.

## Global constraints

- Admin access and all three videos precede referral completion.
- Preserve MFA, verified-account binding, server roles, CSRF, private record boundaries and exact update signer.
- User sees referral count and nonclickable short aliases such as «Умар U.» only; detailed activity/purchase/graph data is admin-only.
- Do not derive aliases from private email/Google data. New aliases are voluntary and cleared on account erasure.
- Current functions remain free, AI tier and payments/rewards/payouts disabled.
- Do not silently change account deletion retention to match a casual statement about trash. Privacy text must match actual storage.
- Targeted meaningful regressions only; no repetitive full-suite runs or repeated rebuilds.
- Store accounts are reportedly ready; the owner currently withholds store access. Do not request it before reviewable files are ready.

## Review focus

- Google roundtrip must preserve only UI setup intent; it cannot grant owner rights.
- A confirmed MFA enrollment must not hide already-issued recovery codes if the session refresh fails.
- Native Google errors must be distinguished from successful browser login and diagnosed in the actual Credential Manager path.
- Date controls must fit their tracks, including intrinsic/content-box stress, long account labels and large text.
- Referral APIs must never return invitee email, identifiers, activity or purchases to the inviter; aliases remain plain text.

## Task 1: Owner access

- [x] Reproduce setup query loss and stale client role flag; distinguish wrong-domain DNS from protected 404.
- [x] Modify `backend/webassets/app/app.js` only: preserve owner/staff enum through Google, refresh session after confirmation, distinguish activation from login.
- [x] Verify real disposable enrollment → admission → password/MFA Control flow; retain recovery codes on refresh error. Evidence in `delivery/owner-access-nov15/`.
- [ ] Carry changes into the new release and verify the published files; owner personally completes production MFA.

## Task 2: New-password policy

- [x] Server registration/reset/change share 8–256 Unicode-character policy, mixed letters/digits or nontrivial trimmed16-character phrase; reject common/repeated/sequential passwords.
- [x] Verify existing-password login is unchanged with legacy hashes.
- [x] Add visible accessible Web/Android guidance and client validation to new-password fields only.
- [x] Verify actual synthetic Web signup forms and focused Native controllers with the restored SDK; new policy leaves existing sign-in credentials unchanged.

## Task 3: Recorded layout and wording

- [x] Scope date-input geometry fix to `.finance-filter-panel` in `reference.css`; red/green intrinsic stress saved separately from ordinary Chromium and absent WebKit.
- [x] Add decorative palette intensity while preserving text/button contrast; save only UI preferences.
- [x] Simplify mobile Today, refine the rounded workspace focus cue while retaining keyboard focus, and persist personal account/budget ordering. Local real HTTP/browser checks passed.
- [x] Simplify Trash and implement owner-consented deletion with independent acknowledgment, retry handling and backup suppression. Local source tests passed; real root ACK provisioning remains a separate release gate.
- [ ] Describe calendar/note import by supported formats without pretending that unsupported synchronization works.

## Task 4: Scheduling and downloads

- [x] `backend/task_reminders.py`, migration021 and `web_push.py`: date/reminder adjunct metadata with current task visibility/edit checks; cancel completion/deletion/revocation before sending.
- [x] Frontend task editor persists schedule through authenticated route, supports date without notification and explains notification opt-in.
- [x] Diagnose native Google separately; preserve existing local personal task/calendar/alarm functionality and OS restrictions.
- [ ] Provide same-origin APK delivery retaining verified signed bytes.

## Task 5: Referrals, last

- [x] `backend/referrals.py`, migration020, schema/routes and erasure hooks; one immutable verified attribution, no self-referral or duplicates.
- [x] Customer contract: own invitation, confirmed count, bounded short-alias list; no detailed graph or financial/activity fields.
- [x] Admin contract: owner/admin permissioned bounded graph, activity from existing operational timestamps, conversions only from authoritative paid provider records.
- [x] Add matching Profile and Control sections with empty/error/loading states and negative authorization/privacy checks.

## Task 6: Release

- [x] Integrate assets, rebuild stylesheet once, review diff and run scoped affected checks.
- [ ] Build a new version with the existing signer, verify an update with saved data, prepare store APK/AAB/screens/text and source-bound manifests.
- [ ] Publish only through authorized available access; verify actual external responses before claiming deployment.
- [ ] Update the report and explicitly retain any unresolved legal/support/OS/store requirements.

## Task 7: Full localization

- [x] Complete all 16 offered languages: 895 native strings per language, 1490 explicit Web/public/Control source IDs, complete help and system notification templates.
- [x] Translate 14 transactional email templates per language; keep locale only inside existing encrypted mail jobs and scope request state per client/request.
- [x] Preserve saved customer text, aliases, announcements, exact technical values and template parameters.
- [x] Verify all 16 public/legal languages in actual synthetic browser views, selected-language Native help, language switching, request isolation and fallback-excluding catalog coverage.
- [ ] Include the frozen source in the new signed APK/AAB and verify the published release separately from local checks.
