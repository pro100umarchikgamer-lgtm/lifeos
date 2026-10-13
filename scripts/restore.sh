#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
backup_file=$(realpath "${1:?Usage: restore.sh BACKUP KEY_FILE NEW_DATABASE}")
key_file=$(realpath "${2:?Backup key file required}")
target=${3:?A NEW database name is required}
[[ "$target" =~ ^[a-z][a-z0-9_]{1,48}$ ]] || { echo 'Invalid target database name'; exit 1; }
# Existing databases are never overwritten, including the live production database.
exists=$(docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d postgres -Atc "$1"' sh "SELECT count(*) FROM pg_database WHERE datname='$target'")
[[ "$exists" == 0 ]] || { echo 'Target already exists; restore refused'; exit 1; }
plain=$(mktemp)
trap 'rm -f "$plain"' EXIT
# Validate the complete GCM tag before any pg_restore command is executed.
docker compose run --rm -T --no-deps --user "$(id -u):$(id -g)" -v "$backup_file:/run/backup.aesgcm:ro" -v "$key_file:/run/backup.key:ro" --entrypoint python api -m backend.backup decrypt --key-file /run/backup.key --input /run/backup.aesgcm > "$plain"
docker compose exec -T db sh -c 'createdb -U "$POSTGRES_USER" -O "$APP_DB_USER" "$1"' sh "$target"
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" --role "$APP_DB_USER" -d "$1" --single-transaction --exit-on-error --no-owner --no-privileges' sh "$target" < "$plain"
echo "Restored into NEW database $target. Live database was not switched."
