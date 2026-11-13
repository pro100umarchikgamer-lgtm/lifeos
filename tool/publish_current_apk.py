"""Publish this trusted signed-build run automatically after its checks succeed.

The run is still in progress because this is its final job. Unlike retained
publication, its gate is the API-confirmed success of every prerequisite job
and actual signing/upgrade steps. Artifact IDs and digests come only from this
run's GitHub API response; no caller-supplied publication manifest is accepted.
"""
import io
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

from tool.native_release_mode import BRANCH, REPOSITORY
from tool import publish_retained_apk as retained

REPOSITORY_ID = 1413453356
CERTIFICATE = '5fa37e4abf1ec90d5787bd0d7dc4cf0b3f49022172f9d25e91f4d8a76702a96e'
MINIMUM_VERSION = 312001
REQUIRED_JOBS = ('release_mode', 'production_backend / postgres', 'checks')
SIGNED_STEPS = (
    'Verify prior validation evidence and prevent duplicate APKs',
    'Build and verify one APK with the persistent test identity',
    'Upgrade signed 134001 through 303001 and verify OS notifications',
    'Save Android upgrade evidence',
    'Upload signed APK and public certificate evidence',
)
require = retained.require


def positive_integer(value, label):
    require(isinstance(value, str) and re.fullmatch(r'[1-9][0-9]*', value), 'Invalid ' + label)
    return int(value)


def verify_context(env, event, command=None):
    expected = {
        'GITHUB_REPOSITORY': REPOSITORY, 'GITHUB_REF': 'refs/heads/' + BRANCH,
        'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_JOB': 'publish_signed',
        'GITHUB_WORKFLOW_REF': REPOSITORY + '/.github/workflows/stage1.yml@refs/heads/' + BRANCH,
    }
    require(all(env.get(key) == value for key, value in expected.items()), 'Untrusted automatic publication context')
    source = env.get('GITHUB_SHA', '')
    require(re.fullmatch(r'[0-9a-f]{40}', source) and env.get('GITHUB_WORKFLOW_SHA') == source,
            'Workflow/source must be the same full commit SHA')
    inputs = event.get('inputs', {})
    require(inputs.get('build_apk') is True or inputs.get('build_apk') == 'true', 'Signed build was not explicitly requested')
    require(not any(inputs.get(key) is True or inputs.get(key) == 'true'
                    for key in ('focused', 'upgrade_probe', 'reuse_signed_apk')), 'Probe/focused/reused APK publication rejected')
    pin = {'id': positive_integer(env.get('GITHUB_RUN_ID'), 'run ID'),
           'number': positive_integer(env.get('GITHUB_RUN_NUMBER'), 'run number'),
           'attempt': positive_integer(env.get('GITHUB_RUN_ATTEMPT'), 'run attempt'), 'source': source}
    version = pin['number'] * 1000 + pin['attempt']
    require(pin['attempt'] < 1000 and MINIMUM_VERSION < version <= 2100000000, 'APK version must increase beyond the published baseline')
    command = command or (lambda *args: subprocess.check_output(['git', *args]))
    require(command('rev-parse', 'HEAD').decode().strip() == source, 'Pinned source checkout mismatch')
    return pin


def verify_current_run(run, pin):
    require(run['id'] == pin['id'] and run['run_number'] == pin['number'] and run['run_attempt'] == pin['attempt'],
            'Current run identity/attempt mismatch')
    require(run['status'] == 'in_progress' and run['conclusion'] is None, 'Current publication run must still be in progress')
    require(run['event'] == 'workflow_dispatch' and run['path'] == '.github/workflows/stage1.yml',
            'Current run event/workflow mismatch')
    require(run['head_sha'] == pin['source'] and run['head_branch'] == BRANCH, 'Current run source/branch mismatch')
    for key in ('repository', 'head_repository'):
        require(run[key]['full_name'] == REPOSITORY and run[key]['id'] == REPOSITORY_ID,
                'Current run repository mismatch')


def verify_jobs(jobs, pin):
    names = [job['name'] for job in jobs]
    require(len(names) == len(set(names)), 'Duplicate current-run jobs')
    require(set(REQUIRED_JOBS) | {'publish_signed'} <= set(names), 'Required current-run job missing')
    for job in jobs:
        require(job['run_id'] == pin['id'] and job['run_attempt'] == pin['attempt'] and job['head_sha'] == pin['source'],
                'Job run/attempt/source mismatch')
        if job['name'] == 'publish_signed':
            require(job['status'] == 'in_progress' and job['conclusion'] is None, 'Expected active publication job')
        else:
            allowed = ('success',) if job['name'] in REQUIRED_JOBS else ('success', 'skipped')
            require(job['status'] == 'completed' and job['conclusion'] in allowed,
                    'Current-run prerequisite did not pass: ' + job['name'])
    checks = next(job for job in jobs if job['name'] == 'checks')
    for name in SIGNED_STEPS:
        steps = [step for step in checks['steps'] if step['name'] == name]
        require(len(steps) == 1 and steps[0]['status'] == 'completed' and steps[0]['conclusion'] == 'success',
                'Actual signed build/upgrade step did not pass: ' + name)


def paginated(api, endpoint, key):
    result = []
    for page in range(1, 101):
        response = api.request(endpoint + f'?per_page=100&page={page}')
        values = response[key]
        result.extend(values)
        if len(values) < 100:
            require(response['total_count'] == len(result), 'Incomplete current-run API listing')
            return result
    raise ValueError('Current-run API pagination limit exceeded')


def artifact_declaration(artifacts, pin):
    declaration = {
        'source': pin['source'], 'repository_id': REPOSITORY_ID,
        'version_code': pin['number'] * 1000 + pin['attempt'],
        'application_id': 'app.lifeos.lifeos', 'display_name': 'ULADIM',
        'api_origin': 'https://api.getuladim.space', 'certificate_sha256': CERTIFICATE,
        'signed_run': {'id': pin['id'], 'number': pin['number'], 'workflow': 'stage1.yml', 'event': 'workflow_dispatch'},
        'required_runs': [],
    }
    names = {'apk_artifact': 'lifeos-release-test-apk-' + pin['source'],
             'upgrade_artifact': 'uladim-upgrade-evidence-' + str(pin['number'])}
    for key, name in names.items():
        matches = [artifact for artifact in artifacts if artifact['name'] == name]
        require(len(matches) == 1, 'Missing/duplicate current-run artifact: ' + name)
        artifact = matches[0]
        digest = artifact.get('digest')
        require(isinstance(digest, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', digest), 'Missing valid current-run artifact digest')
        require(type(artifact['id']) is int and artifact['id'] > 0, 'Invalid current-run artifact ID')
        declaration[key] = {'id': artifact['id'], 'name': name, 'sha256': digest.removeprefix('sha256:')}
        retained.verify_artifact(artifact, declaration[key], declaration)
    return declaration


def derive_declaration(artifacts, pin, apk_zip):
    declaration = artifact_declaration(artifacts, pin)
    require(retained.sha256(apk_zip) == declaration['apk_artifact']['sha256'], 'Downloaded current-run APK ZIP digest mismatch')
    with zipfile.ZipFile(io.BytesIO(apk_zip)) as archive:
        declaration['apk_sha256'] = retained.sha256(retained.read_member(archive, retained.APK_PATH))
    return declaration


def verify_branch(api, pin):
    branch = api.request('git/ref/heads/' + BRANCH)
    require(branch['ref'] == 'refs/heads/' + BRANCH and branch['object']['type'] == 'commit'
            and branch['object']['sha'] == pin['source'], 'Trusted source branch moved; publication stopped')


class SourcePinnedAPI:
    """Recheck the current-run gate before every write and final draft publish."""
    def __init__(self, api, pin):
        self.api, self.pin = api, pin

    def request(self, path, method='GET', payload=None):
        if method != 'GET':
            verify_gate(self.api, self.pin)
        return self.api.request(path, method, payload)

    def upload(self, *args):
        verify_gate(self.api, self.pin)
        return self.api.upload(*args)


def verify_gate(api, pin):
    verify_current_run(api.request(f"actions/runs/{pin['id']}"), pin)
    verify_branch(api, pin)
    jobs = paginated(api, f"actions/runs/{pin['id']}/attempts/{pin['attempt']}/jobs", 'jobs')
    verify_jobs(jobs, pin)
    return jobs


def publish_current(api, pin):
    repository = api.request('')
    require(repository['private'] is False and repository['id'] == REPOSITORY_ID
            and repository['full_name'] == REPOSITORY, 'Expected existing public release repository')
    verify_gate(api, pin)
    artifacts = paginated(api, f"actions/runs/{pin['id']}/artifacts", 'artifacts')
    declaration = artifact_declaration(artifacts, pin)
    apk_zip = api.download(declaration['apk_artifact']['id'])
    upgrade_zip = api.download(declaration['upgrade_artifact']['id'])
    declaration = derive_declaration(artifacts, pin, apk_zip)
    # Reuse the retained publisher's independent apksigner/aapt, exact metadata,
    # upgrade/data-retention/OS notification proof and ZIP digest checks.
    assets = retained.prepare_assets(declaration, apk_zip, upgrade_zip)
    jobs = verify_gate(api, pin)
    proof = json.loads(assets['release-evidence.json'])
    proof['publication_gate'] = {
        'mode': 'automatic-current-run', 'run_attempt': pin['attempt'],
        'branch_head_verified': pin['source'],
        'required_jobs': [{key: job[key] for key in ('id', 'name', 'conclusion')}
                          for job in jobs if job['name'] in REQUIRED_JOBS],
        'required_signed_steps': list(SIGNED_STEPS),
    }
    assets['release-evidence.json'] = (json.dumps(proof, indent=2) + '\n').encode()
    assets['SHA256SUMS'] = ''.join(retained.sha256(assets[name]) + '  ' + name + '\n'
                                for name in sorted(assets) if name != 'SHA256SUMS').encode()
    receipt = retained.publish(SourcePinnedAPI(api, pin), declaration, assets)
    return declaration, receipt


def main():
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    pin = verify_context(os.environ, event)
    declaration, receipt = publish_current(retained.GitHub(), pin)
    Path('native-release-declaration.json').write_text(json.dumps(declaration, indent=2) + '\n')
    Path('native-release-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write(f"Automatically published APK{declaration['version_code']} from `{pin['source']}`.\n\n"
                         f"[Release]({receipt['release_url']}) · [APK]({receipt['apk_url']})\n\n"
                         f"SHA256: `{receipt['sha256']}`\n")


if __name__ == '__main__':
    main()
