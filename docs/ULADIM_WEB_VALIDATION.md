# ULADIM Web recovery validation — 2026-11-11

Branch: `work/uladim-web-platform`. Draft PR:
https://github.com/pro100umarchikgamer-lgtm/lifeos/pull/3
Original a9016f7 / a2d155e commits were transferred through the reviewed Git
bundle and published unchanged, without a force push. Work continues in a separate
Codespaces checkout `/workspaces/uladim-web-recovery`.

## Confirmed evidence
- Vitest: 11 tests pass (recurrence, inclusive end, timezone/day/DST policy,
  task filters, currency/account/transfer validation and exact minor units).
- Existing money checks pass. npm audit reports zero vulnerabilities.
- CI run 42906557524 ran **187 backend tests with PostgreSQL, no skips or failures**.
  Database is an isolated lifeos_test service with a non-admin application role.
  No production database or credentials are used.
- The same CI run passed DOM integration and browser product acceptance against
  actual WSGI + disposable PostgreSQL: task search/status, event create,
  long note edit/cancel-delete, finances, six screens plus transaction forms at
  375/768/1024/1440 in light/dark. Its overall result was red because a later
  existing PWA assertion found duplicated single-line note text. That UI defect
  was reproduced and removed, not hidden by weakening the assertion.
- Run 42906557524 artifact 13805586999 contains 61 files, including actual browser
  screenshots and backend logs. No visual baselines were automatically accepted.
- Codespaces browser run on adce324 passed the existing PWA suite (including
  retry/idempotence, all 16 locales rendering, contrast, logout/history scrubbing,
  safe cache and offline page), 12 finance scenarios (real parser/import,
  deduplication/lost responses, exact balances, charts and responsive screens),
  and the new Service Worker update lifecycle test.
- CodeQL has completed successfully on the web PR. Final commit checks must still
  be read from the current PR checks, not inferred from earlier runs.

## Actual defects corrected during recovery
1. PostgreSQL container healthcheck quoting was incompatible with the Actions
   service parser; corrected to double quotes.
2. Browser navigation selectors matched quick actions as well as the navigation
   bar; scoped to the actual nav, preserving exact assertions.
3. Single-line notes repeated their heading in preview; preview now shows only
   remaining content and full body is still preserved in the editor/server.
4. Phone navigation broke a label across lines; removed card borders and reserved
   one-line captions, clipping long/zoomed captions inside their own touch targets.
5. Desktop Today reserved unused grid rows; widgets now fill available rows.
6. System-theme changes left canvas pixels in old colors; a real canvas-pixel test
   reproduced it, and a repaint callback now preserves open dialog drafts.

## Current expanded gates
Latest browser suite additionally verifies financial form submission and exact
account balance, all four widths/both themes, 44px touch targets, label wrapping,
150% text scaling, short-height/landscape form scrolling and a Playwright trace.
Short-height viewport checks simulate keyboard occlusion; they do not certify an
actual iOS/Android hardware device or its virtual keyboard.
The PWA update test copies static assets into a temporary directory, installs a
new shell version, checks no takeover while an old client is open, closes the last
old client, and checks activation/cache cleanup without session/server data loss.
All successful artifacts are uploaded by web-platform.yml; failures retain traces
and screenshots. Use the latest run as final evidence.

## Preview and release boundaries
Private preview:
https://shiny-meme-966jrwrrx677hx49j-8765.app.github.dev/app
Requires access to the owner's Codespace; port 8765 is Private. It is an acceptance
fixture using the existing WSGI service with temporary synthetic SQLite records.
Account: web@example.test / synthetic-web-platform-password. Do not make the port
public or treat the fixture as the production backend. Data resets on restart and
the URL works only while the Codespace/process is running.

No production deployment, registration-policy change, OAuth/signing change, merge
or main modification was made. Real Google OAuth and Android device/production
round-trip remain coordinated release gates. Missing feature contracts remain in
ULADIM_WEB_CONTRACT_GAPS.md and were handed off through PR #2.

## Access diagnosis
The connected GitHub app resolves the correct owner but rejects ref creation with
403 Resource not accessible by integration. The local executor has no git/gh
credential. Codespaces' separately authorized credential successfully pushed the
same branch and created Draft PR #3. It cannot cancel Actions runs (Actions write
is denied). These are distinct credential permission sets, not proof of a missing
owner role or a branch-protection problem. No token was requested from the user.
CodeRabbit skips Draft PRs by default; manual review is requested only after the
head stabilizes. A request cancelled because the head changed is not a review.
