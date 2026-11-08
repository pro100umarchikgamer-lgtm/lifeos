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

## Gates before public launch

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
