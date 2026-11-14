# ULADIM Focus continuation

Historical checkpoint (superseded by the asset verification below): production was `a05ac09def36bb9b4aaf71eb4da626352c54d2d6` at <https://getuladim.space/app/>. This release includes the public homepage, sign-up, sign-in, password recovery, Today and Tasks. Hostinger reported successful activation. A fresh browser confirmed the matching JavaScript, CSS, and migration to the `uladim-interface-v30-focus-tasks` service worker cache. The preceding `54edbc6` configuration and image were retained for rollback.

Continue on `work/uladim-web-platform`, PR [#3](https://github.com/pro100umarchikgamer-lgtm/lifeos/pull/3). `0e9e2fa` includes Calendar, Notes, the Finance overview and the Firefox date-picker fix. [Web CI and CodeQL passed](https://github.com/pro100umarchikgamer-lgtm/lifeos/actions/runs/43156769791). Later commits cover accounts, transaction forms, budgets, analytics, statement review, profile, security, devices, family, personal import, public information pages, and the appearance, access and support panels. See `git log --oneline a05ac09..HEAD` for the separate checkpoints.

Targeted browser checks covered the calendar modes and native date input, note draft recovery, exact account and operation amounts, budget limits, chart themes, bank import in Chromium, Firefox and WebKit, selected-device revocation, family creation, personal import across sessions, and public information pages at mobile sizes. The 167 bank operations and six personal records were written to disposable test databases.

The temporary Hostinger SSH key expired after the Tasks release. Use the existing authorized Codespace and [Hostinger release process](README.md) once an authorized session is available. Check the exact candidate and required CI before activation, verify a fresh encrypted backup and rollback, then verify the public asset hashes and service worker. Existing registration, payments, administrative access, and Android settings are outside this UI release.


## 2026-11-12 current-session checkpoint

Fresh HTTPS downloads of `/app/assets/app.js`, `/assets/design.css` and `/app/sw.js` match source commit `f973ed6b2dbc74f697bb1a1c4baa7b6bbdcf4879` byte for byte. The earlier production paragraph was stale. The running container revision has not been inspected directly in this environment.

The next candidate adds whole-file statement mapping correction and ready-only selection; explicit amount modes and sample-backed choices; truthful partial-import results; devices as a settings page; theme/profile shortcuts and refresh status; two-column wide-screen sign-in; and a regression guard against delayed old-workspace responses. Service worker is `uladim-interface-v46-focus-import`.

Local checks: 12 npm tests, parser/money checks, 1168 synthetic persisted transactions (including 1000 common-date corrections, exact reread and repeat-import suppression), responsive Focus controls/device revocation/current-session logout, both real sign-in routes, existing product acceptance, and safe PWA update lifecycle. Tests use disposable SQLite and emulated Chromium; physical devices, original bank CSV and this candidate on production have not been tested.

The original reference ZIP and videos were not attached here. Only `ULADIM_CODEX_TASK.md` was available. No conversation-reading tool was available. Do not describe this session as a frame-by-frame comparison.

Deployment remains manual: this environment has no SSH binding and the connected GitHub account lists zero Codespaces. The owner requested terminal commands. From an archive of the reviewed exact commit, run `bash deploy/hostinger/publish-focus-ui.sh FULL_SHA` as root on the existing VPS. The wrapper requires passed Web/general CI, identical running backend Python/SQL sources, and a fresh encrypted backup. It uses the existing deployment helper, verifies six public asset hashes, and restores the prior backend configuration if activation or asset verification fails. It does not alter Caddy/DNS/security settings. Root execution has not been performed here; only shell syntax and the asset verifier against a disposable local server were checked.
