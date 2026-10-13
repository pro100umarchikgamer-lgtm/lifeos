# LifeOS production backend

This is deployment infrastructure, not a publicly deployed service. Existing SQLite development backend and Android SQLCipher data remain compatible. Do not point clients at a new empty database expecting their private local data to upload automatically.

## Initial host (2 vCPU, 4 GB RAM, 60 GB disk)

Install Docker Engine and Compose from their official sources. Only ports 80/443 need public access; PostgreSQL has no published port. Restrict SSH to the operator. Configure DNS for a domain you control; Caddy obtains and renews HTTPS certificates. No VPS purchase is required to develop or test this repository.

Copy `.env.example` to `.env`, mode 600. Supply independent random URL-safe app/admin database passwords, a Fernet key (`python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`) and a separate random rate-limit key of at least 32 characters. Keep the mail key across restarts and backups. Set the domain, ACME contact, verified sender and transactional provider's SMTP credentials. Use STARTTLS/587 or TLS/465 with certificate validation; external plaintext SMTP is refused. No cloud SDK or metadata credentials are consulted.

`docker compose up -d --build` initializes a non-superuser application role, applies checksummed migrations, starts API/mail workers and HTTPS proxy. Inspect `docker compose ps` and `docker compose logs --tail=100 migrate api mail proxy`. Do not publish `.env`, database dumps, queued mail payloads or SMTP logs. Changing initial DB passwords in `.env` does not rotate already-created PostgreSQL roles; coordinate credential rotation explicitly. Database volume and identity must survive container updates. Never run `down --volumes` against a real installation.

Resource limits leave headroom for the OS and PostgreSQL page cache. API has two workers, bounded thread/connection pools and request/body/time limits. Mutations take an advisory lock before a repeatable-read transaction, preserving committed sync cursor order across workers. This deliberately favors simple correctness for initial family workloads. PostgreSQL permission tests and simultaneous writers run in CI; scale only after measuring queue latency and database size.

## Email and health

Verification/recovery tokens and encrypted email jobs commit together. A separate SMTP worker leases jobs, retries transient failures and survives restart. Successful/expired jobs erase only their temporary encrypted secret payload; account, financial and sync history is never pruned. SMTP delivery is at least once: a disconnect after provider acceptance can cause a duplicate with the same Message-ID. Codes remain one-use and expiring.

`scripts/monitor.sh` checks service status, readiness, metrics and disk headroom. `/health/live` reports process health; `/health/ready` verifies DB connectivity. Public `/metrics` is blocked by Caddy. `docker compose --profile monitoring up -d prometheus` enables local-only Prometheus on 127.0.0.1:9090 with API/mail backlog alerts; use an SSH tunnel to view it. Configure your own alert receiver separately; no external telemetry destination is enabled. Inspect disk alerts and expand storage or move encrypted backups manually; scripts never delete old history or backups automatically.

## Backup and restore

Create an independent backup password file with at least 32 random bytes, mode 600, outside the repository. Store a second copy securely off-host. Run `scripts/backup.sh /absolute/path/backup.key`; it checks space, streams a consistent `pg_dump` archive through authenticated AES-256-GCM encryption, atomically publishes it and writes SHA-256 evidence. Protect and copy the encrypted backup off-host using an operator-selected destination. Retain `.env`/mail key separately in protected storage. No Google Drive integration is used.

Run `scripts/restore.sh /absolute/path/backup.aesgcm /absolute/path/backup.key lifeos_restored_20261013`. It refuses an existing target, validates the complete authentication tag before restoring, and restores in one transaction into a NEW database. Verify users, UUIDs, financial totals and sync cursors there. A failed restore leaves the current database untouched. Plan a maintenance window and switch DATABASE_URL only after verification; retain the previous database for rollback. Test this procedure periodically. Restoring an older server snapshot also requires explicit client resynchronization before accepting replay; never silently rewind cursors in an active installation.

## Mobile deployment

For an existing development SERVER SQLite database, stop its writers and make an independent backup first. `python -m backend.import_sqlite --source /protected/server.db` previews only table counts. With a NEW, migrated, empty PostgreSQL target, add `--apply` to import atomically; existing targets are refused. UUIDs, integer money, operation receipts, audit cursors and credentials are preserved, and the next sequence is advanced. Verify identity, history and replay before switching the same server origin. This tool does not open Android SQLCipher or upload personal local records. Existing unverified accounts can request another verification email after migration.

The server origin must be selected by the app distributor at build time, after deploying and validating this backend. Set the repository variable `LIFEOS_API_ORIGIN` for CI signing, or use Flutter's `--dart-define=LIFEOS_API_ORIGIN=https://your-domain` in an authorized build environment. There is no production origin configured by this infrastructure checkpoint. Signing identity, applicationId, local SQLCipher storage and private/shared record boundaries remain unchanged. Final Android release validation is a separate mandatory gate.
