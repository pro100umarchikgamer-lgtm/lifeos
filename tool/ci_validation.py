"""Reuse successful branch validation only for identical application/dependency inputs."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile
from urllib.parse import urlencode
from release_policy import permits_signed_build
import validation_evidence as passed

REPO = os.environ['GITHUB_REPOSITORY']
API = f'repos/{REPO}/actions'
# Validation and signing gate changes must invalidate prior proof as well.
EXCLUDED = {'docs/ANDROID_TEST_SIGNING.md'}

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


def passed_prebuild_prefix(proof):
    """Only the reviewed direct child may reuse the successful prefix of #352."""
    passed.require(os.environ.get('GITHUB_REPOSITORY') == passed.REPO
                   and os.environ.get('GITHUB_REF') == 'refs/heads/' + passed.BRANCH
                   and os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'
                   and os.environ.get('GITHUB_SHA') == proof['sha']
                   and os.environ.get('GITHUB_WORKFLOW_SHA') == proof['sha'], 'Untrusted current validation context')
    parents = command('git', 'rev-list', '--parents', '-n', '1', 'HEAD').split()[1:]
    passed.require(parents == [passed.BASE_SOURCE], 'Not the reviewed direct child')
    baseline = command('git', 'ls-tree', '-r', passed.BASE_SOURCE).splitlines()
    candidate = command('git', 'ls-tree', '-r', 'HEAD').splitlines()
    before, after = passed.entries(baseline), passed.entries(candidate)
    changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
    passed.require(changed == set(passed.APPROVED_FILE_SHA256), 'Outside approved automation delta')
    blobs = {name: subprocess.check_output(['git', 'cat-file', 'blob', 'HEAD:' + name]) for name in changed}
    run = api(f'{API}/runs/{passed.BASE_RUN_ID}/attempts/1')
    listing = api(f'{API}/runs/{passed.BASE_RUN_ID}/attempts/1/jobs?per_page=100')
    passed.require(isinstance(listing, dict) and isinstance(listing.get('jobs'), list)
                   and listing.get('total_count') == len(listing['jobs']) < 100, 'Incomplete prior job evidence')
    artifact = api(f'{API}/artifacts/{passed.BASE_ARTIFACT_ID}')
    passed.require(isinstance(artifact, dict) and artifact.get('id') == passed.BASE_ARTIFACT_ID and artifact.get('size_in_bytes') == 319
                   and artifact.get('digest') == 'sha256:' + passed.BASE_ARTIFACT_SHA256,
                   'Unexpected prior proof artifact')
    raw = subprocess.check_output(['gh', 'api', '--allow-escape-sequences',
                                   f'{API}/artifacts/{passed.BASE_ARTIFACT_ID}/zip'], timeout=60)
    return passed.verify_prebuild_evidence(run, listing['jobs'], artifact, raw,
                                           baseline, candidate, blobs, proof, parents)

sdk = json.loads(command('flutter', '--version', '--machine'))['frameworkVersion']
lock = hashlib.sha256(Path('pubspec.lock').read_bytes()).hexdigest()
proof = {'inputs': inputs('HEAD'), 'lock': lock, 'flutter': sdk, 'sha': command('git', 'rev-parse', 'HEAD').strip()}
Path('validation-proof.json').write_text(json.dumps(proof, sort_keys=True) + '\n')
reuse = False
apk_exists = False
trusted = permits_signed_build(os.environ['GITHUB_REF'], os.environ['GITHUB_EVENT_NAME'])
branch = os.environ['GITHUB_REF'].removeprefix('refs/heads/')
if trusted:
    # Changed automation is checked fresh even when the unchanged app checks can
    # reuse proof. Test failure aborts this decision before any skip/build output.
    subprocess.run([sys.executable, '-m', 'unittest', 'tool.tests.test_validation_evidence',
                    'tool.tests.test_release_upgrade', '-v', '-b'], check=True)
    if os.environ.get('FORCE_FULL_VALIDATION') != 'true':
        try:
            receipt = passed_prebuild_prefix(proof)
            receipt['fresh_changed_tool_tests_passed'] = True
            Path('validation-step-reuse.json').write_text(json.dumps(receipt, sort_keys=True) + '\n')
            reuse = True
            print('Reusing only the verified pre-build prefix of run #352; its later upgrade remains failed.')
        except (passed.EvidenceRejected, subprocess.SubprocessError, KeyError, ValueError, OSError) as error:
            print(f'Passed-step evidence not reusable ({type(error).__name__}); checking complete validation evidence.')
run_query = urlencode({'branch': branch, 'status': 'success', 'per_page': 100})
try:
    runs = api(f'{API}/workflows/stage1.yml/runs?{run_query}')['workflow_runs'] if trusted else []
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
