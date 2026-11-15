# Google Sign-In: release integration and owner setup

This is an extension of the existing ULADIM users, sessions, MFA and sync model.
It is not a second account system. Real Google and physical Android acceptance
remain a release gate; synthetic RSA/provider tests do not satisfy that gate.

## Runtime configuration

Set these only in the protected VPS environment, never in source, browser storage,
chat or screenshots:

- `GOOGLE_OAUTH_CLIENT_ID`: Web application OAuth client ID.
- `GOOGLE_OAUTH_CLIENT_SECRET`: that Web application's client secret.
- `GOOGLE_OAUTH_ANDROID_CLIENT_IDS`: up to eight exact, comma-separated Android
  OAuth client IDs from the same Google project. These public identifiers must
  come from the existing Android OAuth client records; do not invent values or
  substitute a package name, certificate fingerprint or Web client ID. Empty
  trusts no additional Android authorized presenters.

Without the configuration, login forms do not show an inoperative Google button.
No Google/Drive access or refresh tokens are requested or stored. Only `openid
email` is requested. No Apple button is added.

In the owner's existing Google Cloud project, configure an OAuth Web application
with the exact authorized redirect URI:

`https://getuladim.space/account/api/google/callback`

The web uses server authorization-code exchange, S256 PKCE, state, nonce and a
short-lived HttpOnly Secure SameSite=Lax binding cookie. The actual customer cookie
remains HttpOnly Secure SameSite=Strict. The callback immediately redirects to a
credential-free `/app?google=return`; the client removes that marker after loading.
Access logs must remain disabled or redact callback query strings at the edge.
Do not enable access logging of authorization codes or request bodies.

Register an Android OAuth client **in the same project**:

- Package: `app.lifeos.lifeos`.
- Verified existing certificate SHA-1:
  `ec8ed09554510989a4a0290d9a3a636fd65f178e`.
- Verified existing certificate SHA-256:
  `5fa37e4abf1ec90d5787bd0d7dc4cf0b3f49022172f9d25e91f4d8a76702a96e`.

These fingerprints were computed from the retained private keystore in Codespaces
on 2026-11-10 and the SHA-256 matched `docs/ANDROID_TEST_CERT.sha256`.
They are public certificate metadata, not private keys. Do not generate a new key.
The Android client receives the Web client ID and one-time nonce from the server;
it uses Credential Manager through the existing Flutter/native MethodChannel.
No WebView or Firebase user store is introduced.

Google supports hybrid tokens whose `aud` is the Web client ID and whose `azp`
is a different Android client ID in the same project. The backend accepts that
Android presenter only when it exactly matches `GOOGLE_OAUTH_ANDROID_CLIENT_IDS`.
Web callbacks still require the Web presenter. Both paths keep signature, Web
audience, issuer, nonce, expiry, one-use challenge, browser/device binding and MFA
checks. A client ID in this list never grants staff or owner authority.

An otherwise valid Android token from an unlisted presenter returns
`google_android_client_untrusted` (403), without token contents or client IDs.
The app can offer its existing alternate sign-in methods; retrying the same
unconfigured Android client is not a password correction. Public
`GET /v1/auth/google/config` exposes only the additional boolean
`google_android_clients_configured`; this reports a configured list, not proof of
a successful real device login.

The new environment variable must reach the actual API process. The current
Compose definition forwards it. Older immutable release overrides may not do so;
the next reviewed release must explicitly preserve and forward it. Do not edit or
rerun a previously pinned deployment helper to bypass that release check.

Add the approved QA Google accounts as test users if the consent configuration is
in testing. Complete the consent screen using real operator/contact details and
verified domains. Do not invent operator identity. For Play distribution, also
register the actual Play **app signing** certificate; the upload certificate alone
is insufficient. Do not authorize key replacement to make OAuth work.

## Account boundaries

ID tokens are RS256 verified against Google's fixed JWKS endpoint, with issuer,
audience/authorized party, exp, iat, verified email, nonce and subject checks.
The one-time challenge is consumed before verification; the token cannot be reused
with another nonce. Expiry is five minutes. PKCE metadata is encrypted with the
existing runtime cipher; Google tokens/codes are never persisted.

An existing Google subject returns its existing ULADIM UUID. An email collision
requires existing-method login followed by explicit linking with password and
customer MFA when enabled. It never silently merges accounts. A new subject obeys
the existing registration mode, exact allowlist and invitation gate. Google cannot
create staff, moderator or owner authority. A Google primary factor still requires
ULADIM customer MFA when enabled; Control keeps its separate password/MFA flow.

Google-only accounts have no known local password. Establish one with existing
email recovery before unlinking Google or using password-reauthenticated account
operations. Google is authoritative for Gmail/managed Workspace; other email
addresses receive ULADIM verification and cannot use protected data before it.
Unlink requires an established password and MFA if enabled, then revokes sessions.
Deletion also removes Google identity metadata and pending link requests.

## Required remaining acceptance

1. Configure real OAuth clients and protected VPS values. The deployment helper
   rebuilds dependencies when requirements differ and passes Google environment
   variables through the retained Compose configuration. Never use a code-only
   overlay without PyJWT. Migrate 011 only after a
   fresh verified backup and checks. Registration remains closed and payments off.
2. Real browser Google signup/login, cancellation, relogin, email-collision linking,
   unlink and ULADIM MFA. Check production callback log redaction.
3. Real signed Android Credential Manager login with the retained certificate,
   same-account sync, no-account/cancel/network scenarios and relogin.
4. Confirm protected Android API routing, account lifecycle, two-user isolation and
   owner activation separately. Do not open Control because OAuth succeeds.
5. Only then describe Google login as operational or the whole product as RC-ready.

Reference implementations/policies reviewed on 2026-11-10:
- https://developers.google.com/identity/openid-connect/openid-connect
- https://developers.google.com/identity/gsi/web/guides/verify-google-id-token
- https://developer.android.com/identity/sign-in/credential-manager-siwg-implementation
- https://developer.android.com/jetpack/androidx/releases/credentials

Stable Maven metadata was checked: Credential Manager 1.6.0, googleid 1.2.1.

## Android report on 2026-11-15

The supplied recording shows native Google verification failures early in the
session. Later speech about successful Google login occurs in the browser; it
does not establish native acceptance. The production public Google config was
200 with `google_enabled:true`, which proves the route is enabled, not that the
Android OAuth client, retained certificate or presenter list is correct.

A synthetic RS256 token with the supported hybrid `aud`/`azp` combination
reproduced the original backend's `google_invalid` rejection. The exact allowlist
fix is covered by positive and negative tests, including retained Web strictness,
nonce/audience rejection, replay/device binding and customer MFA. The owner's real
token claims and Google Console client records were not inspected, so this is a
confirmed compatibility defect and a possible cause of the recording, not proof
of its sole cause. Configuration of the real Android client IDs and a successful
signed physical Android login remain unobserved release gates. No app signing
key, customer role, MFA rule or production data was changed during diagnosis.
