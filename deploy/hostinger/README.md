# Hostinger private deployment checkpoint — 2026-11-08

Application source: c0a7f33c2b18c44c4ba9acbf688f9ba1507a0970.
Server: srv2139270, 187.126.10.198, Ubuntu 24.04.5 LTS.

## Verified

- Strict SSH host-key verification and the existing encrypted owner key remain enabled.
- Ubuntu packages updated; Docker 29.9.3 / Compose v5.7.0 were already installed.
- UFW denies incoming connections except OpenSSH (IPv4 and IPv6).
- Separate SSH upload user uladim-deploy: existing owner public key, restricted forwarding,
  no sudo or docker group. System runtime identity uladim has a nologin shell.
- Immutable application archive installed in /opt/uladim/releases/c0a7f33.
- PostgreSQL 17 uses the db service, internal database network and pgdata volume from
  the existing compose.yaml; it has no published port. A root-private derived
  /etc/uladim/compose.database.yaml selects only that service while SMTP is unavailable.
- Existing backend image uladim-backend:c0a7f33 built on the VPS.
- Seven checksummed SQL migrations applied; production users table remains empty.
- 104 backend tests passed on the VPS in 54.808 seconds, including PostgreSQL,
  family isolation/conflicts/recovery, account lifecycle, MFA, Control and entitlements.
  Tests used a separate lifeos_test database and a non-superuser application role.
  First attempt safely refused a differently named test database; the guard was preserved.
- AES-GCM encrypted production database backup was decrypted and restored into the
  separate lifeos_restore_20261108t012557z database: all 7 migrations, 0 users.
- Both supplied systemd oneshot services passed on the VPS. Daily backup and
  five-minute local health timers are enabled. No archive retention/deletion is configured.

## Installed operational files

Scripts: /usr/local/libexec/uladim/. Units: /etc/systemd/system/.
Secrets: /etc/uladim/database.env and /etc/uladim/backup.key, root-only mode 0600.
Do not commit, print or copy these keys into reports. Preserve them when activating
full Compose; never generate replacement database/encryption keys for existing volumes.
Archives: /var/backups/uladim/. Receipt/logs: /var/log/uladim/.
The image tag in backup-database.sh is deliberately pinned to the accepted source;
review and test it when advancing the deployed release.

Inspect with systemctl list-timers 'uladim-database-*', journalctl -u
uladim-database-backup.service and journalctl -u uladim-database-monitor.service.
Local monitoring currently writes to journald only: external notifications are not set up.
Backup encryption key escrow and a durable off-server backup destination remain required.

## Historical gates at the private database checkpoint

- DNS: getuladim.space and control.getuladim.space have no resolved A address;
  api.getuladim.space still resolves to old 144.31.148.122. Set the intended A records
  to 187.126.10.198 after authenticated access to the existing Spaceship zone.
- Spaceship password login returned Invalid username or password; site requires username,
  not email. No DNS changes were made.
- Real SMTP host, sender identity and credentials are absent. Do not use fake SMTP
  values to make strict production configuration pass. Email delivery is not verified.
- Verify provider emergency access and owner credential rotation before hardening SSH.
  Hostinger hPanel sign-in is restricted in this cloud browser; console not verified.
- API, mail worker and Caddy/Control are NOT started; 80/443 remain closed. HTTPS,
  actual delivery and Android two-device synchronization are NOT accepted.
- Registration stays closed. Do not expose administrative bootstrap or credentials.

After those gates, use the repository's existing full Compose deployment, readiness,
mail, Control MFA and two-client acceptance procedures. Reuse the existing lifeos project,
volume and secrets. Do not run down --volumes, reinitialize PostgreSQL, or rebuild APK
before server acceptance. Main and Android application/signing identity are unchanged.

## Preserved unrelated Codespace work

The old dirty workspace was not used as deployment source. Its 437 tracked-modified
and untracked non-ignored files were archived with manifest and checksum under
/home/codespace/.local/state/uladim-hostinger/20261108T011600Z/.
Do not discard that archive or publish its mixed changes automatically.


## Current DNS / HTTPS checkpoint — 2026-11-08

All three A records now resolve to 187.126.10.198. Existing Spaceship nameservers,
DNSSEC and unrelated records were preserved. The API A record was updated; apex
and control records were added. The saved records were checked after page reload.

The existing public website assets are served by the repository's Caddy proxy at
https://getuladim.space/. Certificates were verified with normal CA/hostname checks
for the site, API and Control domains (TLS 1.3). HTTP redirects to HTTPS.
This is a pre-launch website, not an operational cloud service.

Caddyfile.bootstrap deliberately returns HTTP 503 for all API/Control access and
for site accounts/subscriptions. Metrics and health paths return 404 on every
hostname. No backend application or mail worker has been started. No registration,
account, payment, administrative bootstrap or data synchronization is exposed.
An initial route-order defect on /metrics was found by check-edge.py and corrected
with mutually exclusive handle blocks. Existing goldens/tests were not weakened.

check-edge.py passed 30 real DNS/TLS/HTTP checks from Codespace and the VPS,
including POST requests to registration, staff login and sync routes. Original
web.js/web.css bytes match their source SHA-256 digests. Browser rendering of the
live homepage was reviewed. Acceptance evidence is in acceptance-20261108.json.

The uladim-edge-monitor timer now repeats those pre-launch checks every five
minutes as the unprivileged uladim service user. It writes to journald; external
alerts are still absent. Disable/replace this phase-specific monitor when the
accepted full backend intentionally replaces the 503 responses.

Operational scripts and their parent directory are root-owned; the deployment
user cannot replace them. Runtime source is root:uladim, without group/other write
permission. Parent source directories allow read/traversal only to the service
group. Secrets in /etc/uladim remain root-only. When transferring future archives,
use tar --no-same-owner --no-same-permissions, followed by explicit root ownership
and install modes; do not preserve Codespace numeric UIDs onto system files.

prepare-edge.py requires PyYAML and derives only the proxy service, Caddy volumes
and edge network from the existing Compose. Run it with --source set to the actual
immutable server source path and --output /etc/uladim/compose.edge.yaml. Install
Caddyfile.bootstrap at /etc/uladim/Caddyfile.bootstrap and render the existing
backend/webassets/index.html with __SURFACE__ replaced by public into
/etc/uladim/public-index.html. The existing site assets are mounted read-only.
The db service, PostgreSQL volume, migrations and encryption keys are untouched.

### Remaining launch inputs

No Spacemail service is present in the authenticated account. No SMTP environment
settings are available. Supply an existing provider's verified sender and SMTP
configuration through protected Codespaces secrets: SMTP_HOST, SMTP_PORT,
SMTP_TLS (starttls or ssl), SMTP_USERNAME, SMTP_PASSWORD and EMAIL_FROM. The full
Compose also requires the real administrative contact ACME_EMAIL. Do not paste
credentials into chat, commit them, or use dummy SMTP values. No new service was
purchased. Exact closed-test email allowlisting can be configured separately;
REGISTRATION_MODE must stay closed pending explicit launch acceptance.

Provider emergency console access and owner credential rotation remain unverified.
Hostinger browser sign-in restrictions were not bypassed. Full production API/mail,
Control MFA bootstrap, real email verification/recovery, Android two-client sync
and final server acceptance remain pending those inputs. APK was not rebuilt.
