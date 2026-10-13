#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
key_file=$(realpath "${1:?Usage: backup.sh KEY_FILE [BACKUP_DIRECTORY]}")
backup_directory=${2:-backups}
mkdir -p "$backup_directory"
# Conservative free-space guard: one database-size worth of space, plus 512 MiB.
database_bytes=$(docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT pg_database_size(current_database())"')
free_bytes=$(df -PB1 "$backup_directory" | awk 'NR==2{print $4}')
(( free_bytes > database_bytes + 536870912 )) || { echo 'Insufficient backup disk space'; exit 1; }
output="$backup_directory/lifeos-$(date -u +%Y%m%dT%H%M%SZ).pgdump.aesgcm"
[[ ! -e "$output" && ! -e "$output.partial" ]]
trap 'if [[ -f "$output.partial" ]]; then mv "$output.partial" "$output.failed"; fi' EXIT
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' |
  docker compose run --rm -T --no-deps --user "$(id -u):$(id -g)" -v "$key_file:/run/backup.key:ro" --entrypoint python api -m backend.backup encrypt --key-file /run/backup.key > "$output.partial"
mv "$output.partial" "$output"
sha256sum "$output" > "$output.sha256"
echo "Backup saved: $output"
