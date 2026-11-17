-- Payload erasure retains the canonical UUID tombstone and independent suppression.
CREATE TABLE IF NOT EXISTS record_erasure_ledger (
 record_id TEXT PRIMARY KEY, erased_at BIGINT NOT NULL CHECK(erased_at>0)
);
CREATE TABLE IF NOT EXISTS record_erasure_intents (
 record_id TEXT PRIMARY KEY REFERENCES records(id),
 user_id TEXT NOT NULL REFERENCES users(id), operation_id TEXT NOT NULL,
 record_revision BIGINT NOT NULL CHECK(record_revision>0), consent_hash TEXT NOT NULL,
 erased_at BIGINT NOT NULL CHECK(erased_at>0), operation_digest TEXT NOT NULL,
 UNIQUE(user_id,operation_id)
);
