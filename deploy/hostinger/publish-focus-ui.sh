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
# after reviewing the final fifteen-file change. No wildcard or version-only bypass.
# None permits an absent old file, not any previous content. These approvals
# authorize the additive category column, safe moderation-state presentation,
# and opt-in encrypted calendar Web Push with its routes, queue, worker tick,
# deletion/import compatibility and focused tests. Existing authentication and
# record permissions are unchanged; every other backend file must remain
# byte-for-byte identical to the running image.
REVIEWED_BACKEND_CHANGES = {
    'backend/account_lifecycle.py': ('1488ffd56c74fc9cab6af68e09bb9bc1e1d037764369cfb8928c3b8ca089f318', 'c673e844a424c6801ed0d87ea7fec29cf43404010e1ec40ec4cdf0e5e50775b0'),
    'backend/control.py': ('65eff55f14f3bd4bcfbe6e0110902f58cc24590d6c7011cbda7cb0da9a1bc939', 'd3d25e8bc5726a110c88e8612aca6994b1545c1037316bc45cd6d83d5d433bfc'),
    'backend/import_sqlite.py': ('a7543d156826fee05f9a21c6d15c58c0bb1a3d02f9b9b247a5f49af59c273a93', 'aadecaadabd8047d5f00e6d34cc92c47d12b982ba40f4417027c2c7020790d05'),
    'backend/mail.py': ('90f8dd3d15c78e9c2170b578b5237714d7670d92bd5dd4f154887d58d811263d', '12986e2d76296e5161d0f0fb68e217cb9314bceb1a1099c735a1d7da7dee246f'),
    'backend/migrations/012_transaction_categories.sql': (None, '8cb3c22388baa1039603e98148f67463110126817db1d1512d58c56d43be7119'),
    'backend/migrations/013_web_push.sql': (None, '96259d626cc4a1d013c4513acd14c678c39ed5e70216863df4126b121535431e'),
    'backend/schema.sql': ('0f066ca4569f9c616052efec30b1167bd2ac2796ad07e9fde3a0f4852a928bb8', 'ed5841dad2ff4faf1b7bc484559ea44d151be760c27219a9c2ce4141a8a98a7d'),
    'backend/service.py': ('67b2f9d04141677ebcdfb73e9efafaf1828ca84400eaaaa6af71bd3cc13bfac7', '00cbd0837313c19a804bef67f6f15f0be9565d9af31c527d0ebc5bfa284dfb86'),
    'backend/tests/test_control.py': ('d5d765d370ff6192bbbaa44ca9d3167e835882f3eb2ce051f9ed5d45044be9c2', '918a9011f9dfad53349c9c34bc7717d3935dd6d59139e1fa6d52fd52ceea04ad'),
    'backend/tests/test_postgres.py': ('4ab3b36d21d2115e07d6a6bb9022d141f4c2d8514a43a5404dd3cca57ab7024b', 'de2500b1e7370b01182ddc4cffb2825dd6ec415ec76da384f43d966ff25f8c54'),
    'backend/tests/test_transaction_categories.py': (None, '9201f02e8219899a05d68947391f36898ded67a269b33d0a70857459bcba58f9'),
    'backend/tests/test_web_push.py': (None, '029a42c1e8e305e461f0180c350a61baeff29c8c83694301821909df829c3e83'),
    'backend/tests/test_web_push_postgres.py': (None, 'dfcdb0ec69ae1993ab1945059ae4a312da884360569d884625ce1142197356cd'),
    'backend/web.py': ('50e458d6e7e3ae05cd509a2e1879a9be1d3025ae242c5458883fc4582f9a38e1', '526d60946ae8d9470761b8b88f2e970d7eb7a9d6b9a938567402d087526cc10a'),
    'backend/web_push.py': (None, '60fc17bbc6ae3aff5e3349ce2c2ba533282795eb71711c525ebfb70e56830a8f'),
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
