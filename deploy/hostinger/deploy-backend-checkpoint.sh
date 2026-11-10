#!/bin/bash
# Run on the existing VPS against a git-archived, verified source directory.
set -euo pipefail
source_dir=${1:?source directory}
revision=${2:?full source commit}
[[ $revision =~ ^[0-9a-f]{40}$ ]]
release=/opt/uladim/releases/$revision
checkpoint=/etc/uladim/checkpoints/$revision
test ! -e "$checkpoint"
install -d -m 700 "$checkpoint"
cp -p /etc/uladim/backend-image.override.json "$checkpoint/image.previous.json"
cp -p /etc/uladim/Caddyfile.bootstrap "$checkpoint/Caddyfile.previous"
test "$(docker inspect lifeos-db-1 --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}')" = lifeos_pgdata
systemctl start uladim-database-backup.service
install -d -m 750 -o root -g uladim "$release"
cp -a "$source_dir/backend" "$release/"
# Private archive extraction can leave directories at 0700. The unprivileged
# edge monitor must be able to read the public reference assets for this release.
chgrp uladim "$release/backend"
chmod 750 "$release/backend"
find "$release/backend/webassets" -type d -exec chgrp uladim {} + -exec chmod 750 {} +
find "$release/backend/webassets" -type f -exec chgrp uladim {} + -exec chmod 640 {} +
runuser -u uladim -- test -r "$release/backend/webassets/web.js"
base_image=$(docker inspect lifeos-api-1 --format '{{.Image}}')
base_tag="uladim-overlay-base:$revision"
docker image tag "$base_image" "$base_tag"
test "$(docker image inspect "$base_tag" --format '{{.Id}}')" = "$base_image"
# An overlay cannot silently inherit stale dependencies (e.g. missing PyJWT).
# This is the effective requirements file installed by the original Dockerfile.
docker exec lifeos-api-1 cat /app/requirements.txt > "$checkpoint/requirements.previous.txt"
if cmp -s "$release/backend/requirements.txt" "$checkpoint/requirements.previous.txt"; then
    printf 'FROM %s\nCOPY --chown=10001:10001 backend ./backend\nLABEL org.opencontainers.image.revision="%s"\n' "$base_tag" "$revision" > "$release/Dockerfile.overlay"
    docker build --network=none --pull=false -f "$release/Dockerfile.overlay" -t "uladim-backend:$revision" "$release"
else
    # Build the reviewed pinned requirements with normal TLS verification before
    # stopping/replacing any running container. No production secrets in context.
    docker build --pull=false --label "org.opencontainers.image.revision=$revision" -f "$release/backend/Dockerfile" -t "uladim-backend:$revision" "$release"
fi
# Reject missing/incorrect requirements before a migration or container switch.
docker run --rm --network=none --entrypoint python "uladim-backend:$revision" -m backend.check_dependencies </dev/null
python3 - "$revision" "$checkpoint" <<'PY'
import json, sys
from pathlib import Path
revision, checkpoint = sys.argv[1:]
value = json.loads(Path(checkpoint, 'image.previous.json').read_text())
for name in ('api', 'mail', 'migrate'):
    value['services'][name]['image'] = 'uladim-backend:' + revision
    value['services'][name].setdefault('environment', {}).update({
        'GOOGLE_OAUTH_CLIENT_ID': '${GOOGLE_OAUTH_CLIENT_ID:-}',
        'GOOGLE_OAUTH_CLIENT_SECRET': '${GOOGLE_OAUTH_CLIENT_SECRET:-}',
    })
path = Path('/etc/uladim/backend-' + revision + '.override.json')
path.write_text(json.dumps(value)); path.chmod(0o600)
PY
cd /opt/uladim/releases/c0a7f33
compose=(docker compose --env-file /etc/uladim/production.env -f compose.yaml -f "/etc/uladim/backend-$revision.override.json")
"${compose[@]}" config --quiet
"${compose[@]}" run --rm --no-deps -T migrate </dev/null
"${compose[@]}" up -d --no-build --pull never api mail
for attempt in {1..20}; do
    if test "$(docker inspect lifeos-api-1 --format '{{.State.Health.Status}}')" = healthy && test "$(docker inspect lifeos-mail-1 --format '{{.State.Health.Status}}')" = healthy; then break; fi
    sleep 2
done
test "$(docker inspect lifeos-api-1 --format '{{.State.Health.Status}}')" = healthy
test "$(docker inspect lifeos-mail-1 --format '{{.State.Health.Status}}')" = healthy
cp -p "/etc/uladim/backend-$revision.override.json" /etc/uladim/backend-image.override.json
test "$(docker inspect lifeos-db-1 --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}')" = lifeos_pgdata
echo "BACKEND_CHECKPOINT_READY $revision; edge is unchanged"
