#!/bin/bash
# Restore an earlier backend configuration; additive schemas and data remain intact.
set -euo pipefail
revision=${1:?full checkpoint revision}
[[ $revision =~ ^[0-9a-f]{40}$ ]]
checkpoint=/etc/uladim/checkpoints/$revision
test -s "$checkpoint/image.previous.json"
test "$(docker inspect lifeos-db-1 --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}')" = lifeos_pgdata
cd /opt/uladim/releases/c0a7f33
compose=(docker compose --env-file /etc/uladim/production.env -f compose.yaml -f "$checkpoint/image.previous.json")
"${compose[@]}" config --quiet
"${compose[@]}" up -d --no-build --pull never api mail
cp -p "$checkpoint/image.previous.json" /etc/uladim/backend-image.override.json
# Caddy was not changed by the backend helper. No volumes or migrations are removed.
echo BACKEND_ROLLBACK_STARTED
