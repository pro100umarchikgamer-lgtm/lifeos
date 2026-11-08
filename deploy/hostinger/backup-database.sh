#!/usr/bin/env bash
# Encrypted local backup; preserves every existing archive (no retention deletion).
set -euo pipefail
umask 077
exec 9>/run/lock/uladim-backup.lock
flock -n 9 || exit 0
root=/var/backups/uladim
mkdir -p "$root"
free=$(df -Pk "$root" | awk 'NR==2 {print $4}')
(( free > 2097152 )) || { echo 'BACKUP_FAILED insufficient disk space' >&2; exit 1; }
stamp=$(date -u +%Y%m%dT%H%M%SZ)
out="$root/uladim-$stamp-$$.pgdump.aesgcm"
test -s /etc/uladim/backup.key
docker exec lifeos-db-1 pg_dump -U postgres -d lifeos -Fc |
  docker run --rm -i --network none --user 0:0 --read-only --cap-drop ALL     --security-opt no-new-privileges -v /etc/uladim/backup.key:/run/backup.key:ro     --entrypoint python uladim-backend:c0a7f33     -m backend.backup encrypt --key-file /run/backup.key > "$out.partial"
test -s "$out.partial"
mv -n "$out.partial" "$out"
sha256sum "$out" > "$out.sha256"
printf '%s\n' "$out" > /var/log/uladim/latest-backup-path
echo "BACKUP_OK $out"
