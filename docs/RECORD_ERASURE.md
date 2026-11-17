# Permanent removal of a trash record

This operation erases a deleted record's retained server payload. It preserves an
empty UUID tombstone for synchronization and an independent record-only journal
so restoring an older server backup cannot bring the content back. It does not
delete an active record, a different owner's record, or another record's links.
There is no client-side hiding presented as permanent erasure.

Source support is not production readiness. The feature remains unavailable
until the separate root durability service and independent encrypted remote
record object are provisioned and verified. The existing account erasure journal,
its exact `{user_id,erased_at}` format and its socket protocol are unchanged.

## Customer API

The authenticated customer trash response includes
`permanent_delete_available`. This checks the record durability channel once for
the complete list; no per-row readiness requests are needed. Availability does
not authorize any record operation. The route retains ordinary same-origin,
session, CSRF, rate and current-account checks.

`GET /account/api/recovery/purge-preview?record=<UUID>` returns an exact private
owner preview with `consent_hash`, `permanent_delete_available` and
`pending_operation_id`. A pending operation can be retried after a lost response
or reload with that same operation UUID. When independent synchronization already
completed the erasure, the response instead contains `erased:true` and
`record_id`, without a private record body. During an outage a private pending
preview can remain available while the destructive feature is unavailable.

`POST /account/api/recovery/purge` accepts exactly:

```json
{
  "operation_id": "canonical-operation-UUID",
  "record_id": "canonical-record-UUID",
  "revision": 2,
  "consent_hash": "exact-64-character-preview-hash"
}
```

The server rechecks the current verified owner, active workspace membership,
edit authority, deleted state, revision and preview hash. It blocks any retained
transaction account reference, transfer account reference or request movement
reference, including references in soft-deleted payloads. It never detaches or
rewrites a surviving participant's record to make a purge succeed.

The first transaction commits an immutable pending intent and revokes old
recovery grants. That UUID is reserved across canonical record and family
operations. Restore, put and new recovery grants cannot race the intent. A failed
root/offsite acknowledgment leaves the payload intact and the intent pending;
the API does not report success. One bounded worker retry also closes a crash
between committed consent and the first root IPC.

Only after independent confirmation does one transaction erase typed payloads,
task progress/reminders, grants, recovery requests and scoped copied notification
payloads. It clears the audience, increments record revision/sequence, and emits
`access.changed` so offline former grantees reset their private cache. The empty
UUID header and minimal idempotent receipt remain. The successful response is:

```json
{"id":"operation-UUID","status":"accepted","record_id":"record-UUID","revision":3,"erased":true}
```

The same body/UUID returns the same receipt. A different operation reusing a
pending or completed UUID is rejected. Errors distinguish unavailable durability,
pending consent, retained references, changed preview and an already erased UUID.
Staff do not gain payload access or a new purge endpoint.

## Startup and backup restore

Migration `023_record_erasure.sql` adds a minimal suppression table and pending
consent table. The journal itself contains only canonical `record_id` and positive
`erased_at` values; no names, titles, account IDs, email, credentials or content
hashes are sent to independent storage.

The next reviewed deployment supplies, to API and worker:

```text
RECORD_ERASURE_LEDGER=/run/uladim-record-erasure.jsonl
RECORD_ERASURE_ACK_SOCKET=/run/uladim-record-privacy/sync.sock
RECORD_ERASURE_REQUIRED=true
```

The separate journal is mounted read-only. The root Unix socket is also mounted
into both processes. The journal and socket must never alias the account erasure
paths. Before provisioning, both paths remain empty and the feature is disabled.
Once provisioned, the `required` setting stays true independently of database
backups; an older snapshot must not silently disable suppression.

API and worker startup synchronize the existing account journal first, then the
record journal, before serving or delivering jobs. The operator import CLI does
the same after an applied import. A missing/unavailable required channel, wrong
protocol, nonroot peer, wrong prefix digest or rewound suppression stops startup.
Confirmed record UUIDs absent from an old snapshot are still reserved, preventing
later recreation with revision zero. A restored old active row for an already
confirmed erased UUID is tombstoned and its payload is erased before exposure.

Replay considers the complete confirmed record set. A restored reference from
another confirmed erased record may be removed with that record's own payload;
a surviving reference outside the set stops replay/startup instead of changing
another person's financial data. Pending consent is never treated as success.

The published seven-day encrypted backup retention is unchanged. Existing backup
files are not rewritten by this operation; an authorized restore applies the
independent suppression before exposing data. Copies or exports retained by a
user on their own device are not claimed to be remotely wiped. No month-long
account retention or deletion policy is introduced by the trash control.

## Durability protocol

The product client accepts only a root peer (`SO_PEERCRED.uid == 0`) and exact
`uladim-record-erasure-v1` messages. Synchronization returns a bounded journal
prefix length and SHA-256. A record acknowledgment additionally binds the exact
UUID and a timestamp at least as large as the committed intent. The client reads
only that prefix from the private regular journal and requires its SHA-256 and
strict record-only schema to match. Local append/fsync without authenticated
offsite readback is insufficient.

The root service is a separate private delivery artifact. Its new remote object,
journal, socket, config and head/initialization pins are all separate from account
erasure. It reuses the reviewed encrypted channel and retained key; it does not
create another repository, request a new credential or reset existing truth.
Provisioning and an actual service/restore acceptance test remain deployment
gates. The operational adapter is not part of the public application or store kit.

Focused verification:

```sh
python3 -m unittest backend.tests.test_record_erasure backend.tests.test_record_recovery -v
```

The record suite also runs in an isolated PostgreSQL `lifeos_test` schema when
`LIFEOS_TEST_DATABASE_URL` points to that explicitly guarded local test database.
