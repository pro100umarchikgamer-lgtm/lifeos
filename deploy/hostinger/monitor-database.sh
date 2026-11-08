#!/usr/bin/env bash
# Local readiness checks only; no external alert delivery is configured.
set -euo pipefail
state=$(docker inspect --format '{{.State.Health.Status}}' lifeos-db-1)
test "$state" = healthy
free=$(df -Pk /var/backups/uladim | awk 'NR==2 {print $4}')
(( free > 2097152 ))
latest=$(cat /var/log/uladim/latest-backup-path)
test -s "$latest"
sha256sum --status -c "$latest.sha256"
age=$(( $(date +%s) - $(stat -c %Y "$latest") ))
(( age >= 0 && age < 129600 ))
echo "DATABASE_MONITOR_OK backup_age_seconds=$age"
