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
backup_image=$(docker inspect lifeos-api-1 --format '{{.Image}}')
stamp=$(date -u +%Y%m%dT%H%M%SZ)
out="$root/uladim-$stamp-$$.pgdump.aesgcm"
test -s /etc/uladim/backup.key
docker exec lifeos-db-1 pg_dump -U postgres -d lifeos -Fc |
  docker run --pull never --rm -i --network none --user 0:0 --read-only --cap-drop ALL --cap-add DAC_OVERRIDE     --security-opt no-new-privileges -v /etc/uladim/backup.key:/run/backup.key:ro     --entrypoint python "$backup_image"     -m backend.backup encrypt --key-file /run/backup.key > "$out.partial"
test -s "$out.partial"
mv -n "$out.partial" "$out"
sha256sum "$out" > "$out.sha256"
printf '%s\n' "$out" > /var/log/uladim/latest-backup-path
echo "BACKUP_OK $out"
