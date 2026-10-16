# ULADIM Control release checkpoint

Development branch: `feature/uladim-control-release`. Continues `c108a7a`; main is unchanged.

Implemented source:
- Versioned PostgreSQL migrations 004–006; old migration checksums unchanged.
- Device-bound rotating 15-minute access / absolute 30-day refresh sessions. Reuse revokes that device family. Password reset revokes account and staff sessions. SecureStorage stores an atomic credential bundle on Android.
- Separate Control origin, cookie/session store, mandatory TOTP, replay prevention, 15-minute staff idle timeout, eight-hour absolute timeout, HTTP-only Secure SameSite cookies, exact Origin and CSRF validation. User bearer credentials cannot authenticate Control.
- Explicit six-role server permission matrix; no owner assignment through HTTP, self/equal/higher staff modification rejected. MFA enrollment requires a verified matching invite recipient. No impersonation or private-content endpoint.
- Append-only audit triggers and chained hashes; moderation of accounts and selected services preserves records. Staff role changes revoke staff sessions.
- Free/Plus/Premium versioned catalog and central entitlement resolver, manual/promo grants and safe overrides. Existing features remain Free during this closed test. Prices are unset and sales are disabled. Provider reconciliation is an internal verified-adapter interface, not an HTTP `verified=true` shortcut. Real store adapters/credentials are absent.
- Account-isolated support tickets with explicit messages, limited creation/thread size, credential-pattern redaction, staff permissions and audit of actions rather than message bodies.
- Two-phase, revision-checked preview/commit of three UI feature flags; no security flags.
- Same-origin public site/customer/Control shells and operations API in the existing WSGI service. Caddy forwards the three configured hostnames. No second backend or unrelated hosting project.

Not yet accepted as complete:
- Implemented verification-first signup, reauthenticated one-use email change and a 24-hour cancellable account deletion queue. The worker rechecks family ownership, preserves shared history/UUID tombstones, erases private payloads and stops for review if they have external shared references. Ownership transfer requires the receiving active co-parent’s consent. Backups require a separate operator retention review; immediate erasure from all copies is not promised. PostgreSQL acceptance is pending.
- Optional customer MFA is now implemented with encrypted TOTP enrollment, one-use recovery codes, replay/attempt protection, device revocation and no email-recovery bypass. Native and web account flows expose setup/disable. Final isolated UI acceptance remains pending. Staff operator recovery requires the account password plus an offline one-use recovery code and rotates MFA/recovery material and sessions; it is not available over HTTP.
- Android account subpages now cover access, device revocation, support, email change and deletion requests; sixteen new keys have translations in all 16 versioned packs. Isolated Flutter analysis/layout acceptance is pending.
- PostgreSQL acceptance for Control/session/lifecycle migrations passed in CI126. CI127 also passed real two-client sync, Docker/Compose, Caddy validation, backup/restore; browser acceptance caught a real long-heading overflow on the privacy page. CSS was corrected without weakening the width assertion. New MFA migration, browser acceptance, Android account screenshots, final CI and signed APK are still awaiting acceptance.
- Production deployment/TLS/SMTP/two-client live sync: provider console is not authenticated and no trusted SSH fingerprint/key is available. No live-service claim.

## Operator bootstrap
After verified deployment/migrations, create and verify the intended owner account through the normal configured closed-test account flow. Run locally on the server:

```sh
umask 077
python -m backend.operator bootstrap-owner --email OWNER_EMAIL --output /secure-owner-path/enrollment.json
```

The output path must not already exist and must be accessible only to the operator. It contains the TOTP enrollment secret and single-use recovery material, never stdout. Transfer it to the owner's authenticator through a secure owner-controlled channel; retain emergency material offline. Do not commit or send it in chat. First-owner bootstrap is one-time and is not an HTTP endpoint. Operator recovery uses `python -m backend.operator recover-staff --email OWNER_EMAIL --output NEW_PRIVATE_FILE`. Password and offline recovery code are read with hidden terminal prompts. Existing output files are never overwritten; all previous staff sessions and recovery codes are invalidated. No HTTP MFA bypass exists.

## Deployment gates
Existing VPS/domain remain the target. Verify the provider-console ED25519 fingerprint against SSH before accepting a host key. Preserve emergency owner access before credential rotation/firewall changes. Do not disable trust checks. No purchase is required.

Keep `REGISTRATION_MODE=closed` and an explicit tester allowlist. Configure verified transactional SMTP and test delivery before enabling enrollment. Add/verify apex and Control DNS only when authorized provider access exists; never report DNS or HTTPS based solely on source configuration. Real billing stays disabled until signed provider adapters, credentials, legal texts and store readiness have passed acceptance.

## New verification scope

Browser CI uses a disposable loopback-only fixture (HTTP localhost, no certificate bypass, synthetic accounts only). Production HTTPS remains required. It captures actual public, customer/support, staff login/dashboard/search renders in both themes and fails on JavaScript errors or horizontal overflow. Android account visuals cover all 16 locales at 320dp and en/ru screens at 320/390/430dp with 1.4x text. Existing visual assertions are retained.

The release upgrade baseline is now the exact retained signed APK112001 (SHA256 pinned), not 85001. It creates synthetic task/finance records, installs the one candidate using `adb install -r`, requires unchanged package UID, task survival after restart and retained financial amounts. No uninstall/data clear is used.

A separate bounded PostgreSQL service-persistence profile models 100/1000/5000 existing synthetic registered accounts with concurrency four, plus real password-verification samples. It records latency, Python CPU/RSS and schema storage. This is a CI runner profile; it does not measure VPS HTTP/TLS performance or 5000 simultaneous users. Production capacity remains unverified while VPS access is blocked.

Control UI now includes account search, reasoned service holds/manual grants, staff invitations/role edits and two-phase UI flag preview/commit. Store purchases remain disabled; production provider adapters, approved prices and legal/operator disclosures are not available. Feature flags expose deterministic server rollout; `chart_styles` is reserved and does not claim an implemented chart-style selector.

## Reviewed-render corrections

CI128 browser acceptance passed and its actual screenshots were reviewed. The Control dashboard was then compacted: duplicate raw metric values were removed, CPU rounded, disk shown in GiB, and wrapped button tabs replaced by an accessible section selector. The browser workflow assertion was updated to operate that actual selector. The account hub now uses one grouped navigation surface; the 320dp large-text test scrolls to privacy and verifies the 48dp target instead of assuming lazy list children are always built. New final captures must still be reviewed.

Account deletion now removes the requesting account’s support threads/ephemeral invitations and inactive staff recovery material; shared references stop cleanup for operator review. A failed cleanup rolls back before marking the request for attention and does not stop mail delivery. Regression tests assert both cases. Incoming family ownership transfers and eligible co-parent actions are exposed on Android/web privacy screens; acceptance remains explicitly reauthenticated.
