# User-consented record recovery

This is recovery of a normal record-delete tombstone whose payload remains in the
current database. It never extracts backups, undoes account erasure, reinstates a
workspace membership or lets staff read private tasks, notes or financial details.
All nine current record kinds use the same canonical sync operation path.

## Owner flow

Authenticated verified customer session metadata includes
`record_recovery_available:true` when this implementation is present. Unverified
accounts report false. Old servers omit it and clients hide the entry.

`GET /account/api/trash?workspace=UUID` returns at most50 owner-only tombstones with
the retained normal record shape, consent_hash, restorable and restore_error.
`before=seq:UUID` pages results. Optional `record=UUID` previews exactly one owned
record in the selected active authorized workspace; foreign/unknown IDs return404.
Only the actual record owner receives content. Archived/missing references and lost
permissions make a retained record non-restorable; they do not grant new rights.
There is no promise that erased payloads or all history remain recoverable forever.

1. Owner previews and selects a retained record, then POSTs `recovery/request` with
   record_id, revision and consent_hash. The server binds consent to exact owner,
   workspace, kind, visibility, audience, revision, payload and task-progress state.
   Ten new requests per account/day; duplicate live consent returns the old request.
   Requests expire after seven days.
2. Owner reads `GET recovery/requests` (100/page with before cursor). Staff approval
   changes only request metadata; the record stays deleted.
3. Owner reviews the exact record again. POST `recovery/prepare` with request_id
   returns request_id, grant and expires_at. Grant is43 random characters, only its
   digest is stored, lifetime at most10 minutes, and a newer prepare replaces it.
4. Owner POSTs `recovery/commit` with request_id, grant and operation_id UUID.
   The operation goes through normal batch/revision/idempotency/change-log handling.
   A lost response is retried with the same grant and UUID. A new UUID cannot reuse
   a consumed grant. Pull protocol1 and2 receive one restored normal record revision.
5. Before completion, owner can POST `recovery/cancel` with request_id and request
   revision. It revokes consent and any prepared grant. Completed requests cannot be
   replayed into a newer restore of subsequently deleted records.

Every prepare/commit rechecks account availability, actual ownership, active
workspace membership, exact revision/content hash, current edit/create permissions
for children, current profiles/participants and existing type/reference validation.
Family writes retain existing holds/feature checks. A fulfilled money request can
only reconnect its unchanged existing transfer and receiving account, with matching
amount/currency/audience and no competing active fulfilled binding. It creates no
financial movement. Deleted linked accounts/transfers must be restored first.

## Staff boundary

New permission `records.recover` belongs to owner/admin/support. Moderator, auditor
and billing_manager cannot read the recovery queue or approve requests.

`GET /control/api/record-recovery` returns at most100 request metadata rows with a
stable created_at:id cursor. Fields: id,user_id,workspace_id,record_id,kind,
record_revision,consent_hash,state,revision,created_at,expires_at,approved_at,
completed_at,decision_reason. No title, body, amount, payload, task progress,
grant, grant hash or user session is exposed.

`POST /control/api/record-recovery/approve` accepts request_id, request revision,
consent_hash and reason. It validates current record metadata/account/membership
without loading the payload and returns metadata only. Stale or repeated approval
conflicts. Approval never changes a user record or supplies a user grant.

Self and peer approvals are deliberately allowed for this capability: the user
already owns the record and must request, review and commit it in their own customer
context. This avoids an impossible recovery loop for the highest-rank owner. Staff
cannot invent a request on another user's behalf or commit using a staff cookie.
Password recovery, moderation and staff-role hierarchy rules remain unchanged.

Requests, approvals, consent cancellation and user commit are audited with opaque
IDs, kind/revision and safe reasons; never private payloads or grant secrets.
Explicit account erasure deletes recovery requests, grants and private payloads.
Existing append-only audit retains safe administrative event metadata as before.

## Storage and release

Migration018 creates only metadata/hash/expiry fields. Original migrations remain
unchanged. Existing server SQLite imports may omit the new optional tables; imports
that contain them preserve them. This feature does not change Android signing,
restore a production backup or mutate a live account during verification.
