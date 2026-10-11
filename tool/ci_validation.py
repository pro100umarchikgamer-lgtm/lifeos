"""Reuse successful main validation only for identical application/dependency inputs."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

REPO = os.environ['GITHUB_REPOSITORY']
API = f'repos/{REPO}/actions'
EXCLUDED = {'.github/workflows/stage1.yml', 'tool/ci_validation.py',
            'tool/ci_signing.sh', 'docs/ANDROID_TEST_CERT.sha256', 'docs/ANDROID_TEST_SIGNING.md'}

def command(*args):
    return subprocess.check_output(args).decode()

def api(path):
    return json.loads(command('gh', 'api', path))

def inputs(ref):
    entries = command('git', 'ls-tree', '-r', ref).splitlines()
    return hashlib.sha256('\n'.join(e for e in entries if e.split('\t', 1)[1] not in EXCLUDED).encode()).hexdigest()

def output(name, value):
    with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
        stream.write(f'{name}={value}\n')

sdk = json.loads(command('flutter', '--version', '--machine'))['frameworkVersion']
lock = hashlib.sha256(Path('pubspec.lock').read_bytes()).hexdigest()
proof = {'inputs': inputs('HEAD'), 'lock': lock, 'flutter': sdk, 'sha': command('git', 'rev-parse', 'HEAD').strip()}
Path('validation-proof.json').write_text(json.dumps(proof, sort_keys=True) + '\n')
reuse = False
apk_exists = False
trusted = os.environ['GITHUB_REF'] == 'refs/heads/main' and os.environ['GITHUB_EVENT_NAME'] != 'pull_request'
try:
    runs = api(f'{API}/workflows/stage1.yml/runs?branch=main&status=success&per_page=100')['workflow_runs'] if trusted else []
    for run in runs:
        if run['event'] not in ('push', 'workflow_dispatch'):
            continue
        if reuse and run['head_sha'] != proof['sha']:
            continue
        artifacts = api(f"{API}/runs/{run['id']}/artifacts")['artifacts']
        apk_exists |= any(a['name'] == f"lifeos-release-test-apk-{proof['sha']}" and not a['expired'] for a in artifacts)
        for artifact in ([] if reuse else artifacts):
            if artifact['name'] != 'lifeos-validation-proof' or artifact['expired']:
                continue
            raw = subprocess.check_output(['gh', 'api', '--allow-escape-sequences', f"{API}/artifacts/{artifact['id']}/zip"])
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                prior = json.loads(archive.read('validation-proof.json'))
            if prior['sha'] != run['head_sha']:
                continue
            if all(prior.get(key) == proof[key] for key in ('inputs', 'lock', 'flutter')):
                reuse = True
                print(f"Reusing full validation run #{run['run_number']} ({prior['sha']})")
                break
    # One-time bootstrap: #27 predates validation-proof artifacts. Compare its
    # actual resolved dependency versions, not just pubspec constraints.
    if trusted and not reuse:
        baseline = api(f'{API}/runs/38132716495')
        if baseline['conclusion'] == 'success' and baseline['head_sha'] == 'ce2f52b7e7ffd8fc3d1bcdb3610b88b962241067' and sdk == '3.47.7' and inputs(baseline['head_sha']) == proof['inputs']:
            logs = command('gh', 'api', '--allow-escape-sequences', f'{API}/jobs/114450184799/logs')
            old = dict(re.findall(r'^\S+Z \+ ([a-z_0-9]+) (\S+)', logs, re.MULTILINE))
            dependencies = json.loads(command('flutter', 'pub', 'deps', '--json'))['packages']
            current = {p['name']: p['version'] for p in dependencies if p['name'] != 'lifeos'}
            if len(old) == 78 and old == current:
                reuse = True
                print('Reusing complete validation #27: identical source tree, Flutter SDK and all 78 resolved dependencies.')
except (subprocess.CalledProcessError, KeyError, ValueError, OSError, zipfile.BadZipFile) as error:
    print(f'Validation evidence unavailable ({type(error).__name__}); full validation required.')
full = not reuse or os.environ.get('FORCE_FULL_VALIDATION') == 'true'
output('full', str(full).lower())
output('build', str(trusted and os.environ.get('BUILD_APK') == 'true' and not apk_exists).lower())
output('sha', proof['sha'])
if apk_exists:
    print('An APK artifact already exists for this commit; duplicate APK build suppressed.')
print(f'Full validation required: {full}')
