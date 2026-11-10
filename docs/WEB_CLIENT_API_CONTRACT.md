# ULADIM shared backend contract

Source baseline: `da2301cfd13db87de293b0fdc12ee1d8f6b13a70`.
This describes implemented handlers, not a claim that every route is publicly enabled.
Production registration, Control and payments must remain closed. Do not build a
second backend, user directory or identity mapping. Preserve server user UUIDs.

## Browser transport and identity

Use the existing same-origin `/account/api/` gateway on `getuladim.space`.
The gateway converts the browser's opaque session into the same internal actor used
by Android. Do not copy Android bearer-token handling into browser localStorage.

Requests are GET or POST; POST uses `Content-Type: application/json`, a JSON object
(including `{}` for no parameters), and the exact site `Origin`. Authenticated POST
also requires `X-CSRF-Token`, returned by GET `/account/api/session`. Keep it in
memory. Send cookies with same-origin credentials. Customer cookie
`__Host-uladim_account` is Secure, HttpOnly and host scoped; Control uses a separate
cookie. GET session returns `{user_id,email,verified,csrf}`. Do not infer any staff
authority from this response, email address, DOM or client settings.

Account/API responses use `Cache-Control: no-store`. Never cache authenticated
responses in Service Worker, CacheStorage, history or open browser storage.

## Browser endpoints

Every suffix below is relative to `/account/api/`.

| Method | Suffix | Request / result |
|---|---|---|
| GET | `config` | `{registration_open,payments_enabled,google_enabled}` |
| POST | `signup` | `{email,password,invitation?}`; closed-mode gate is server enforced |
| POST | `confirm-signup` | `{email,code}` → `{verified:true,sign_in_required:true}` |
| POST | `resend-signup` | `{email}`; preserve non-enumerating acknowledgement |
| POST | `login` | `{email,password}` → authenticated session + CSRF, or MFA challenge |
| POST | `login/mfa` | `{challenge,code}` → authenticated session + CSRF |
| POST | `recovery` | `{email}`; generic acknowledgement |
| POST | `reset` | `{email,code,password}`; one-use recovery |
| GET | `session` | Current user and CSRF; 401 when session is unavailable |
| POST | `logout` | `{}`; revoke originating device and clear cookie |
| POST | `logout-all` | `{password}`; revoke all sessions |
| GET | `devices` | Device list from shared session service |
| POST | `devices/revoke` | `{device_id,password}` |
| POST | `password` | `{old_password,new_password}` |
| POST | `email` | `{email,password}` |
| POST | `confirm-email` | `{code,password}` |
| GET | `mfa` | Current user MFA status, after authentication |
| POST | `mfa/begin` | `{password}`; sensitive enrollment response stays in memory |
| POST | `mfa/enable` | `{password,enrollment,code}`; show recovery codes once |
| POST | `mfa/disable` | `{password,code}` |
| GET / POST | `deletion` | Status / `{password,confirmation}` |
| POST | `cancel-deletion` | `{password}` |
| GET | `plans` | Public server catalog; payments remain disabled |
| GET | `entitlements` | Effective server permissions and tier |
| GET | `spaces` | `{spaces:[...]}`; verified email required |
| GET | `roster?workspace=UUID` | Workspace, profiles and server-authorized roster |
| GET | `sync?workspace=UUID&cursor=N&epoch=VALUE` | Incremental protocol 2 page |
| POST | `sync` | `{workspace_id,operations:[...]}` → `{results:[...]}` |
| POST | `family` | UUID family operation; see family service, not arbitrary role assignment |
| POST | `invitations/accept` | Existing invitation acceptance operation |
| POST | `transfer` | `{workspace_id,user_id,password}`; ownership transfer proposal |
| POST | `accept-transfer` | `{transfer_id,password}` |
| GET / POST | `support` | List / `{category,subject,message}` |
| GET | `thread?id=UUID` | Authorized support thread |
| POST | `support/reply` | `{ticket_id,message,state}` |

For exact ancillary response fields use `backend/account_lifecycle.py`,
`customer_mfa.py`, `account_sessions.py`, `support.py` and their scenario tests.
Do not invent response shapes for unimplemented UI features.

## Google identity and MFA

POST `google/start` with `{invitation?}` returns `authorization_url`; navigate to it.
GET `/account/api/google/callback` is a server callback, never a client-side token
exchange. Backend consumes state, validates binding, uses PKCE, exchanges code and
verifies Google ID token. Callback redirects to `/app?google=return`; remove this
marker from history and POST `google/complete` with `{}`. Result can be a domain
error, an MFA challenge or an established customer session. A callback handoff is
short lived and single use; never log its cookies, codes or tokens.

GET `google` returns `{google_linked,has_password,google_enabled,google_web_enabled}`.
POST `google/link` requires `{password,code?}`, CSRF and an active originating
session; it returns an authorization URL. POST `google/unlink` requires the same
reauthentication and signs the account out. Matching email alone never links a
legacy account. Prompt existing users to authenticate with their original method
and explicitly link Google. Do not display Apple sign-in.

Primary password must succeed before showing MFA. Challenge result is
`{mfa_required:true,challenge,expires_in:300}`. Keep challenge only in memory;
second step sends challenge and code, never repeats/persists the password.

## Shared synchronization and record fields

Android uses HTTPS `/v1/` with Bearer access tokens and rotating refresh tokens,
stored in platform secure storage. Its equivalents are `/v1/spaces`, `/v1/roster`,
POST `/v1/sync/push` and GET `/v1/sync/pull?...&protocol=2`. Browser gateway and
Android both call the same `Backend.batch` / `pull_incremental` implementations.

`operations` contains 1–100 objects; each mutation is independently atomic.
Each operation has a stable UUID `id`, UUID `record_id`, `action` and integer
`revision` (0 to create). `record.put` additionally requires `kind`, `visibility`
(`private` or `shared`), `audience` (profile UUIDs) and the complete exact `data`
field set below. Do not send partial PATCH data or add client-only fields.

| kind | Exact data keys |
|---|---|
| task | title, completed, assignment, assignees, review |
| note | body |
| account | name, currency, opening_minor |
| transaction | kind, amount_minor, currency, date, label, account_id |
| transfer | from_id, to_id, sent_minor, received_minor, date |
| budget | name, currency, limit_minor, period, start_on, end_on, rollover, participants |
| event | title, schedule |
| shopping | name, items |
| request | profile_id, amount_minor, currency, label, state, movement_id |

Other mutation actions: `record.delete`, `record.grant`, `request.fulfill`,
`task.complete`, `task.review`. Obtain their action-specific fields from
`backend/service.py:_record_operation`; there is no server `record.undo` action.
Task completion/review is profile-aware and requires `profile_id` plus boolean
`completed`. Task data `completed` and `review` are integer 0/1; assignment is
`single`, `each`, `joint` or `any`. Event schedule has exactly
`localStart,timezone,allDay,repeat,interval,until`: localStart has no UTC offset,
timezone is an IANA zone or `device`; interval is 1–365; repeat is none/daily/weekly/
monthly/yearly. Civil dates use `YYYY-MM-DD`; never UTC-shift a civil date.

Each result has its operation `id` and status `accepted`, `conflict` or `rejected`.
Conflict includes `record_id` and authorized `server` state (possibly null);
rejection includes a domain `error`. HTTP 200 does not mean every mutation
succeeded. Acknowledge each result individually. Preserve operation UUID across
timeouts and lost responses. Do not silently overwrite conflicts or mint new IDs
when retrying. A user's explicit conflict resolution is a new revision-aware
operation. Keep unsent input visible after a network failure.

Pull returns `{protocol:2,epoch,reset,records,cursor,more,membership}`. Records carry
server revisions, tombstones and `editable`. On `reset:true` replace the scoped
remote mirror before applying the page; do not erase unsent operations. Persist
page and cursor atomically, continue while `more:true`. Never mix server/user/
workspace scopes. Revoked workspace access must purge its visible remote mirror.

## Money, access and limits

Money is integer minor units, not floating-point major amounts. Absolute maximum
is 999999999999999. Transactions have positive `amount_minor` and kind income or
expense; signed opening balances are allowed; budget limits can be zero.
Currency is an uppercase three-letter code; validate supported currency and its
scale on the client. Never sum currencies without an explicit rate/conversion.
Transfers have two account IDs and two amounts; same-currency amounts must match.
Account/reference visibility and currency are checked on the server. Keep bank
files local; imports use normal revision-aware, idempotent operations. Android's
personal local records are not automatically uploaded to a shared workspace.

Server checks membership, profile permissions, record visibility, editable grants,
family service entitlement and action-specific roles on every operation. Roles
include owner/parent/adult/child. Child permissions are view_budget,
record_spending, edit_own, request_money, view_shared, create_tasks, complete_tasks.
Use server entitlements for Free/Plus/Premium; hiding buttons is not authorization.
Control is a separate host/session/authority and is not a user-client API.

Production WSGI accepts JSON objects up to 2 MiB, rejects duplicate keys and
unsupported methods, and emits `{error:domain_code}` on errors. Typical statuses:
400 invalid input, 401 unauthorized/invalid credentials, 403 forbidden/closed
registration/unverified email, 409 conflict or account-method constraint,
413 body limit, 415 content type, 429 rate limit (`Retry-After: 60`), 503 unavailable.
Baseline HTTP limiter: 30 auth requests/minute and 240 general API requests/minute
per keyed client category; account-specific protections also apply. Localize domain
codes using the existing locale packs; do not show raw provider messages.

Implementation sources: `backend/web.py`, `production.py`, `http_server.py`,
`service.py`, `google_identity.py`, `lib/sync/api.dart`, `lib/sync/engine.dart`.
Tests: `backend/tests/test_google_identity.py`, `backend/tests/test_postgres.py`,
`test/session_rotation_test.dart`, `tool/check_sync_protocol.py` and the browser
workflow checks. Synthetic-provider success is not real Google acceptance.
