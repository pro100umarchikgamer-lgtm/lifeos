# Control browser admission

Control remains a separate origin and staff authority. The customer browser must
first receive admission; admission never replaces staff MFA or role permissions.

- Own customer `/account/api/session` reports `control_available` only for an
  actually verified, active staff account. A query/header/client role cannot set it.
- Authenticated, exact-origin and CSRF-protected `POST /account/api/control/access`
  issues `{ticket, control_url, expires_in:60}`. Ticket is43 random URL-safe chars;
  only its SHA-256 digest is stored, tied to the current concrete web session and
  User-Agent. Issuing a new ticket invalidates older tickets from that session.
- The browser submits an HTML form with only `ticket` to `control_url` (`/admit`).
  There is no credential in a URL, redirect query or browser history. The handler
  accepts only bounded form POST from the exact site origin, consumes once, sets
  `__Host-uladim_control_admission` (Secure, HttpOnly, SameSite=Strict, no Domain),
  and redirects303 to `/`. Customer cookies remain Host-only on the apex.
- Every Control root, asset or API request requires that admission plus its
  original parent web session/device still active, verified account, active staff,
  matching User-Agent and available account. Otherwise it returns404. Admission
  expires no later than eight hours or the parent session expiry.
- Staff login still requires password plus MFA. Staff/challenge identity must
  equal the admitted customer's identity. All privileged POSTs retain Control
  Origin/CSRF and server role checks. A staff cookie alone cannot expose Control.
- Customer logout/device revoke/password reset and staff deactivation remove
  admission authority immediately. Successful customer session replacement clears
  admission and pending handoffs for the previous browser cookie in the central
  `customer_session` hook (password, MFA completion and Google completion). Signup
  and signup verification do not mint a web cookie or change the current identity.

The first owner still requires the existing operator-issued capability and verified
customer account with TOTP confirmation (`/app?setup=owner`). No owner is created,
reset or granted automatically. Existing enrollment must be reused.

## Recovery

`users.recover` lets owner/admin/support request a recovery email for an existing
verified, available lower-rank recipient. It cannot act on self/equal/higher staff.
The recipient comes from the user record, never an arbitrary submitted email.
`POST /control/api/user/recovery` accepts only user_id and reason. It uses the
existing15-minute recovery-code flow, recipient60s rate limit plus10 requests per
staff/15min, and commits email queue plus audit together. No code, link or password
is returned to staff. No password is changed and customer MFA stays enabled.

Legacy staff recovery-code login revokes all customer devices and staff sessions.
Under browser admission that deliberately invalidates the parent browser session,
so lost-authenticator recovery should use protected operator `recover-staff`, then
fresh customer login, handoff and the rotated TOTP. Do not weaken revocation or
reset a live owner to make the UI reachable. This limitation is explicit pending a
separate, fully reviewed reciprocal-session recovery design.

## Deployment

Migration015 is additive. Apply with the existing checked migration runner before
switching API/mail to this code; no existing migration/checksum changes. The old
UI-only publish guard does not authorize these new backend files/migration.
`deploy/hostinger/Caddyfile.control-platform` is a reviewed candidate, not active
configuration. Preserve the existing pgdata volume, keys, registration policy and
backup/rollback. Read the operator-upgrade proposal in the delivery audit before
activating either Control or the native API hostname.
