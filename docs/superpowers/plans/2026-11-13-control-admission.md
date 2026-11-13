# Same-browser Control admission

Approved contract: owner/customer browser identity must remain active before any Control root, asset or API is exposed. Unadmitted requests receive404. Existing staff MFA, CSRF, roles and private-content boundaries remain.

Approach: separate Host-only admission cookie from an authenticated apex one-use60s POST handoff. Domain-wide customer cookies and URL credentials were rejected because they broaden exposure. No role grants or live changes.

1. Write failing WSGI tests for anonymous404, ordinary metadata/no handoff, staff metadata/CSRF handoff, form redemption Origin/single-use/expiry/UA, no privilege before MFA, identity match and parent logout/revocation. Use real temporary SQLite and synthetic users.
2. Add backend/control_admission.py; additive migration015 + SQLite schema; Web own-session metadata and CSRF issue route; narrow production form redemption and early origin gate, exact Control form-action CSP.
3. Update existing Control HTTP fixture admissions without bypassing production code. Run admission and related Control/security tests; no full historic suite (parent explicitly bounds verification).
4. Add staff-triggered recovery email only if existing verified-user recovery fits safely; audit/rate limits; no secret output, staff-set password or MFA reset.
5. Write guarded operator edge-upgrade proposal (no execution): exact verified baseline hash, candidate backend-digest review, additive migrations, fresh backup, Caddy validate/reload, live negative checks and saved rollback. Root handles integration/review.

Evidence baseline: audit report at /workspace/work/delivery/audit-2026-11-13/admin-security.md;24 existing local security tests passed. Native configured API supplied at build by LIFEOS_API_ORIGIN; accepted artifact checker expects https://api.getuladim.space.
