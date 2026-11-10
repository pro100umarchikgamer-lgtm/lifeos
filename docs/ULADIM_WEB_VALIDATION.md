# ULADIM Web verification

Implemented on existing source; no production release claim.

- Vitest: 11 tests, including month-end recurrence, inclusive until dates,
  viewer timezones, all-day dates, DST overlaps/half-hour gaps, task filters,
  transfer/account currency validation and maximum money precision.
- Full backend discovery: 187 tests, 95 passed, 92 PostgreSQL tests skipped because
  no LIFEOS_TEST_DATABASE_URL was configured. No failures.
- `node tool/check_money.js`: passed, existing exact-money checks.
- `python -m unittest backend.tests.test_pwa backend.tests.test_control_web`:
  9 passed; includes common records, Android protocol compatibility, conflicts,
  session/CSRF/host/space boundaries, manifest/static allowlists.
- `python -m tool.check_web_dom`: passed using actual disposable WSGI application
  and SQLite data; task search/status, event creation, note edit/cancel-delete,
  finance display and operation creation, theme and Uzbek, shared server records.
  jsdom substitutes dialog/ResizeObserver/canvas APIs; it does NOT verify rendering,
  layout, focus trap, worker imports, service workers or hardware keyboard behavior.
- `npm audit --audit-level=high`: 0 vulnerabilities at verification time. All
  npm packages are development tools; runtime remains buildless JavaScript.
- Independent review found DST selection/gap and timezone-label issues. Added
  reproducing failing tests and fixed the implementation to match Android.

Not executed successfully: Playwright/browser screenshots, visual regression,
Lighthouse, CodeQL, CodeRabbit, real production OAuth and PostgreSQL/Android device
round-trip. Configuring tests is not passing them. No snapshots were overwritten.

Commands for an enabled environment:
```
npm ci --ignore-scripts
npm test
npm audit --audit-level=high
python -m pip install -r backend/requirements.txt -r tool/web-requirements.txt
python -m playwright install --with-deps chromium
python -m tool.check_web_dom
python -m tool.check_web_platform
python -m tool.check_pwa_browser
python -m tool.check_finance_browser
python -m tool.check_web_browser
```

`python -m tool.serve_web_fixture` serves a loopback-only synthetic preview on
port 8765 for Lighthouse/development. Synthetic account: web@example.test,
password synthetic-web-platform-password. It contains no user data and is not a
second product backend or a deployable staging service. Do not expose it publicly.
