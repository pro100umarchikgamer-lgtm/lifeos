-- Optional account metadata; never inferred from private workspace records.
CREATE TABLE IF NOT EXISTS account_identity (
 user_id TEXT PRIMARY KEY REFERENCES users(id), display_name TEXT NOT NULL,
 search_name TEXT NOT NULL, updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS staff_permission_restrictions (
 staff_id TEXT NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
 permission TEXT NOT NULL, PRIMARY KEY(staff_id,permission)
);
CREATE TABLE IF NOT EXISTS staff_invitation_restrictions (
 invitation_hash TEXT NOT NULL REFERENCES staff_invitations(hash) ON DELETE CASCADE,
 permission TEXT NOT NULL, PRIMARY KEY(invitation_hash,permission)
);
CREATE TABLE IF NOT EXISTS support_recovery_cases (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
 ticket_id TEXT REFERENCES support_tickets(id),
 kind TEXT NOT NULL CHECK(kind IN ('access','records')),
 state TEXT NOT NULL CHECK(state IN ('waiting_owner','confirmed','closed','cancelled')),
 revision BIGINT NOT NULL DEFAULT 1, created_at BIGINT NOT NULL,
 expires_at BIGINT NOT NULL, confirmed_at BIGINT NOT NULL DEFAULT 0,
 updated_at BIGINT NOT NULL, created_by TEXT NOT NULL REFERENCES staff(id)
);
CREATE INDEX IF NOT EXISTS recovery_case_target ON support_recovery_cases(user_id,created_at,id);
CREATE INDEX IF NOT EXISTS recovery_case_queue ON support_recovery_cases(created_at,id);
