#!/bin/bash
set -euo pipefail
umask 077
cd /opt/uladim/releases/c0a7f33
before=$(docker inspect lifeos-db-1 --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}')
test "$before" = lifeos_pgdata
docker compose --env-file /etc/uladim/production.env -f compose.yaml -f /etc/uladim/backend-image.override.json config --quiet
docker compose --env-file /etc/uladim/production.env -f compose.yaml -f /etc/uladim/backend-image.override.json up -d --no-build --pull never api mail
after=$(docker inspect lifeos-db-1 --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}')
test "$before" = "$after"
echo PG_VOLUME_PRESERVED
