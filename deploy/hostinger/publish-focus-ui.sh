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

# Reject backend/schema changes except the exact reviewed feedback additions below.
python3 - "$source_dir" <<'PY'
import hashlib, json, re, subprocess, sys
from pathlib import Path

# Baseline: the published 5617fff release. Root fills each candidate digest only
# after reviewing the final seven-file change. No wildcard or version-only bypass.
# None permits an absent old file, not any previous content. These approvals
# authorize one additive category column and safe moderation-state presentation;
# authentication, existing record permissions and every other backend file must
# remain byte-for-byte identical to the running image.
REVIEWED_BACKEND_CHANGES = {
    'backend/control.py': ('65eff55f14f3bd4bcfbe6e0110902f58cc24590d6c7011cbda7cb0da9a1bc939', 'd3d25e8bc5726a110c88e8612aca6994b1545c1037316bc45cd6d83d5d433bfc'),
    'backend/service.py': ('67b2f9d04141677ebcdfb73e9efafaf1828ca84400eaaaa6af71bd3cc13bfac7', '00cbd0837313c19a804bef67f6f15f0be9565d9af31c527d0ebc5bfa284dfb86'),
    'backend/schema.sql': ('0f066ca4569f9c616052efec30b1167bd2ac2796ad07e9fde3a0f4852a928bb8', '2adae60e9307da8935d5c655bd3819991a2a4c3a9ea5a622f12909a03c234d7c'),
    'backend/migrations/012_transaction_categories.sql': (None, '8cb3c22388baa1039603e98148f67463110126817db1d1512d58c56d43be7119'),
    'backend/tests/test_control.py': ('d5d765d370ff6192bbbaa44ca9d3167e835882f3eb2ce051f9ed5d45044be9c2', '918a9011f9dfad53349c9c34bc7717d3935dd6d59139e1fa6d52fd52ceea04ad'),
    'backend/tests/test_postgres.py': ('4ab3b36d21d2115e07d6a6bb9022d141f4c2d8514a43a5404dd3cca57ab7024b', 'de2500b1e7370b01182ddc4cffb2825dd6ec415ec76da384f43d966ff25f8c54'),
    'backend/tests/test_transaction_categories.py': (None, '9201f02e8219899a05d68947391f36898ded67a269b33d0a70857459bcba58f9'),
}

def reviewed_backend_changes(live, source):
    for name, (before, after) in REVIEWED_BACKEND_CHANGES.items():
        if not re.fullmatch('[0-9a-f]{64}', str(after)):
            raise SystemExit('Stopped: backend review digest is not finalized: ' + name)
        if before is not None and not re.fullmatch('[0-9a-f]{64}', before):
            raise SystemExit('Stopped: invalid baseline backend digest: ' + name)
        if source.get(name) != after:
            raise SystemExit('Stopped: candidate differs from reviewed backend digest: ' + name)
    changed = {name for name in source.keys() | live.keys() if source.get(name) != live.get(name)}
    reviewed = []
    for name in sorted(changed):
        expected = REVIEWED_BACKEND_CHANGES.get(name)
        if expected and live.get(name) == expected[0] and source.get(name) == expected[1]:
            reviewed.append(name)
    return changed.difference(reviewed), reviewed

root = Path(sys.argv[1])
code = """import hashlib,json;from pathlib import Path
root=Path('/app');print(json.dumps({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'backend').rglob('*') if p.is_file() and p.suffix in ('.py','.sql') and 'webassets' not in p.parts}))"""
live = json.loads(subprocess.check_output(['docker','exec','lifeos-api-1','python','-c',code]))
source = {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
          for p in (root/'backend').rglob('*') if p.is_file()
          and p.suffix in ('.py','.sql') and 'webassets' not in p.parts}
changed, reviewed = reviewed_backend_changes(live, source)
if reviewed:
    print('REVIEWED_BACKEND_ADDITIONS ' + ', '.join(reviewed))
# This release adds one image to the existing static asset allowlist. Require
# byte-for-byte equality after removing exactly that literal; no API change can
# pass this exception.
if 'backend/web.py' in changed:
    candidate = (root / 'backend/web.py').read_bytes()
    running = subprocess.check_output(['docker','exec','lifeos-api-1','cat','/app/backend/web.py'])
    addition = b"'app.css', 'auth-texture.webp', 'manifest.webmanifest'"
    original = b"'app.css', 'manifest.webmanifest'"
    if candidate.count(addition) == 1 and candidate.replace(addition, original) == running:
        changed.discard('backend/web.py')
        print('STATIC_ASSET_ALLOWLIST_ADDITION auth-texture.webp')
if changed:
    raise SystemExit('Stopped: running backend differs from candidate: ' + ', '.join(sorted(changed)))
print('BACKEND_REVIEWED_DELTAS_ONLY' if reviewed else 'BACKEND_AND_SCHEMA_UNCHANGED')
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
