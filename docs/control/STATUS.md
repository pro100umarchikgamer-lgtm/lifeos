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
- Account deletion worker, email-change and public verification-first signup; current public site directs closed testers to Android account flows. Public registration remains closed.
- Customer MFA/recovery management, completed staff recovery workflow and complete polished staff action UI.
- Android plan/device/support UI and translated new strings; existing 16 packs are preserved and release validator passes.
- Browser visual/E2E review, PostgreSQL acceptance for new Control migration, final CI and new signed APK.
- Production deployment/TLS/SMTP/two-client live sync: provider console is not authenticated and no trusted SSH fingerprint/key is available. No live-service claim.

## Operator bootstrap
After verified deployment/migrations, create and verify the intended owner account through the normal configured closed-test account flow. Run locally on the server:

```sh
umask 077
python -m backend.operator bootstrap-owner --email OWNER_EMAIL --output /secure-owner-path/enrollment.json
```

The output path must not already exist and must be accessible only to the operator. It contains the TOTP enrollment secret and single-use recovery material, never stdout. Transfer it to the owner's authenticator through a secure owner-controlled channel; retain emergency material offline. Do not commit or send it in chat. First-owner bootstrap is one-time and is not an HTTP endpoint. Recovery codes are reserved for a separately tested operator recovery workflow; no bypass of MFA is exposed.

## Deployment gates
Existing VPS/domain remain the target. Verify the provider-console ED25519 fingerprint against SSH before accepting a host key. Preserve emergency owner access before credential rotation/firewall changes. Do not disable trust checks. No purchase is required.

Keep `REGISTRATION_MODE=closed` and an explicit tester allowlist. Configure verified transactional SMTP and test delivery before enabling enrollment. Add/verify apex and Control DNS only when authorized provider access exists; never report DNS or HTTPS based solely on source configuration. Real billing stays disabled until signed provider adapters, credentials, legal texts and store readiness have passed acceptance.
