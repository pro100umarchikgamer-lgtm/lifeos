#!/usr/bin/env bash
# Run as root on the existing VPS, from an archive of the pinned reviewed commit.
# No DNS, edge routes, secrets, registration policy or database volumes are changed.
set -euo pipefail
umask 077
revision=${1:?full reviewed commit SHA}
[[ $revision =~ ^[0-9a-f]{40}$ ]]
source_dir=$(cd "$(dirname "$0")/../.." && pwd)
test "$(id -u)" = 0
test -s /etc/uladim/backend-image.override.json
test -s /etc/uladim/production.env
test ! -e "/etc/uladim/checkpoints/$revision"
test ! -e "/opt/uladim/releases/$revision"

# The exact commit must have completed the existing mandatory workflows.
python3 - "$revision" <<'PY'
import json, sys
from urllib.request import Request, urlopen
revision = sys.argv[1]
url = 'https://api.github.com/repos/pro100umarchikgamer-lgtm/lifeos/actions/runs?head_sha=' + revision + '&per_page=100'
with urlopen(Request(url, headers={'Accept':'application/vnd.github+json','User-Agent':'ULADIM-release'}), timeout=20) as response:
    runs = json.load(response)['workflow_runs']
for path in ('.github/workflows/web-platform.yml', '.github/workflows/stage1.yml'):
    matches = [r for r in runs if r['head_sha'] == revision and r['path'].split('@')[0] == path]
    run = max(matches, key=lambda r:r['id']) if matches else None
    if not run or run['status'] != 'completed' or run['conclusion'] != 'success':
        raise SystemExit('Stopped: required CI has not passed: ' + path)
    print('CI_PASSED', run['html_url'])
PY

# Refuse a frontend release if it would also change the running backend/schema.
python3 - "$source_dir" <<'PY'
import hashlib, json, subprocess, sys
from pathlib import Path
root = Path(sys.argv[1])
code = """import hashlib,json;from pathlib import Path
root=Path('/app');print(json.dumps({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'backend').rglob('*') if p.is_file() and p.suffix in ('.py','.sql') and 'webassets' not in p.parts}))"""
live = json.loads(subprocess.check_output(['docker','exec','lifeos-api-1','python','-c',code]))
source = {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
          for p in (root/'backend').rglob('*') if p.is_file()
          and p.suffix in ('.py','.sql') and 'webassets' not in p.parts}
changed = [name for name in source.keys() | live.keys() if source.get(name) != live.get(name)]
# This release adds one image to the existing static asset allowlist. Require
# byte-for-byte equality after removing exactly that literal; no API change can
# pass this exception.
if 'backend/web.py' in changed:
    candidate = (root / 'backend/web.py').read_bytes()
    running = subprocess.check_output(['docker','exec','lifeos-api-1','cat','/app/backend/web.py'])
    addition = b"'app.css', 'auth-texture.webp', 'manifest.webmanifest'"
    original = b"'app.css', 'manifest.webmanifest'"
    if candidate.count(addition) == 1 and candidate.replace(addition, original) == running:
        changed.remove('backend/web.py')
        print('STATIC_ASSET_ALLOWLIST_ADDITION auth-texture.webp')
if changed:
    raise SystemExit('Stopped: running backend differs from candidate: ' + ', '.join(sorted(changed)))
print('BACKEND_AND_SCHEMA_UNCHANGED')
PY

# Require a fresh encrypted backup and verify its stored checksum before switching.
started=$(date +%s)
systemctl start uladim-database-backup.service
backup=$(cat /var/log/uladim/latest-backup-path)
[[ $backup == /var/backups/uladim/*.pgdump.aesgcm ]]
test -s "$backup"
test "$(stat -c %Y "$backup")" -ge "$((started - 60))"
sha256sum -c "$backup.sha256"

rollback() {
  if test -s "/etc/uladim/checkpoints/$revision/image.previous.json"; then
    bash "$source_dir/deploy/hostinger/rollback-backend-checkpoint.sh" "$revision"
  fi
}
if ! bash "$source_dir/deploy/hostinger/deploy-backend-checkpoint.sh" "$source_dir" "$revision"; then
  rollback
  exit 1
fi
if ! python3 "$source_dir/tool/verify_web_release.py"; then
  rollback
  echo 'Asset check failed; previous backend configuration restored.' >&2
  exit 1
fi
printf 'FOCUS_UI_PUBLISHED %s\n' "$revision"
printf 'Rollback: bash %q %q\n' "$source_dir/deploy/hostinger/rollback-backend-checkpoint.sh" "$revision"
