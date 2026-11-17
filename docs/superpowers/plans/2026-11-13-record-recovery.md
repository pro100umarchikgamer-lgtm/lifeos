# User-consented admin-assisted record restore

Approved by parent: normal record-delete tombstones only; no account-erasure undo,
backup extraction, staff payload/title/amount viewing or silent staff mutation.

1. Test own-only deleted-record preview/consent; foreignID404; metadata-only staff
   request queue+permission/hierarchy, revision/hash consistency and one-use grant.
2. Add recovery module + additive018 tables. Customer requests and approvals keep
   only opaque record IDs/hash/revision; explicit user commit through normal batch.
3. Add record.restore canonical operation guarded by grant; owner/currentworkspace,
   normal editable/current child rights, `_validate_data` references and participants;
   audit/seq/revision/idempotent receipt exactly once. No raw tombstone-only flip.
4. Test stalehash/revision, erased payload/account, dissolvedspace, deletedlinked
   account, revocation/role changes; normal Web/native pull sees restored row once.
5. Expose customer trash/recovery and staff queue routes; coordinate frontend; run
   targeted SQLite and disposable PostgreSQL checks. Parent integrates shared files.
