"""One reviewed tooling child may reuse run352's successful pre-build prefix."""
import hashlib
import io
import json
import re
import zipfile

BASE_RUN_ID = 43876258617
BASE_ARTIFACT_ID = 14231457826
BASE_SOURCE = 'fe141a77b85fef84f16383a8d94578924510eecb'
BASE_INPUTS = '1fdb9cdf427458bafcdc3cdbf55028d3bf2ef2e59fc2f001c03842a74bbc9d87'
BASE_LOCK = 'e28c2e59f6351a7d1656487e8d52c0c25c136d4c6154a369ce0aa0200d1bd19c'
BASE_ARTIFACT_SHA256 = '9b8c7b35ef4acb6a695bb435f914e38bf7c7b22831ae8d1ab37adf9fbe9a02af'
PREFIX_LAYOUT_SHA256 = '01f8c336dd5671e8f0e1da6de16c41b197958ebc240d68b05a3a38263fac2663'
SELF_SHA256 = 'a1de3dc74a38a5709aa69477bffb500ecff6d0a3f9d56f8eee08f8bb6fa34fcc'
APPROVED_FILE_SHA256 = {
    'tool/check_shared_editor_browser.py': '176ec10fdbcfc4660492f1e16a8e37e534a79d60676054fbb5a85649c467f040',
    'tool/check_release_upgrade.py': '47a0bf531d2d2d7b713ab2984480c6ed11956529428bbadd0a63fa75d4e28262',
    'tool/tests/test_release_upgrade.py': '6e72292f0dd1fb8e1203901114f9ea079b6599459e9d592d241273d3d8fa6241',
    'tool/ci_validation.py': 'bd8436e83e6715d020b73b2676655c51fd8342eddc658d9917414b5a4f7b4dfe',
    'tool/validation_evidence.py': SELF_SHA256,
    'tool/tests/test_validation_evidence.py': 'eab91a1c5e68ee0a5505465bf347779a171159ae4be756169839d376c8a1b95a',
}
REPO = 'pro100umarchikgamer-lgtm/lifeos'
REPO_ID = 1413453356
BRANCH = 'work/uladim-web-platform'


class EvidenceRejected(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise EvidenceRejected(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def inputs_fingerprint(lines):
    # Match the original proof's full fingerprint, including test and CI files.
    return sha('\n'.join(line for line in lines
                         if line.split('\t', 1)[1] != 'docs/ANDROID_TEST_SIGNING.md').encode())


def entries(lines):
    require(isinstance(lines, list) and all(isinstance(line, str) for line in lines), 'Missing Git tree')
    result = {}
    for line in lines:
        require('\t' in line, 'Malformed Git tree entry')
        fields, path = line.split('\t', 1)
        require(path not in result, 'Ambiguous Git tree path')
        result[path] = fields
    return result


def approved_blob(path, raw):
    if path == 'tool/validation_evidence.py':
        pattern = rb"(?m)^SELF_SHA256 = '([a-f0-9]{64})'$"
        matches = re.findall(pattern, raw)
        require(matches == [SELF_SHA256.encode()], 'Helper self pin differs')
        # Only this one literal is normalized; all other code and byte pins count.
        raw = re.sub(pattern, b"SELF_SHA256 = '" + b'0' * 64 + b"'", raw)
    return sha(raw) == APPROVED_FILE_SHA256[path]


def verify_prebuild_evidence(run, jobs, artifact, raw, baseline_lines, candidate_lines,
                            candidate_blobs, current, parents):
    require(all(isinstance(value, dict) for value in (run, artifact, current, candidate_blobs))
            and isinstance(jobs, list) and all(isinstance(job, dict) for job in jobs)
            and isinstance(raw, bytes), 'Incomplete evidence metadata')
    before, after = entries(baseline_lines), entries(candidate_lines)
    require(parents == [BASE_SOURCE] and re.fullmatch('[a-f0-9]{40}', current.get('sha', ''))
            and current['sha'] != BASE_SOURCE, 'Outside the one-child validation exception')
    require(inputs_fingerprint(baseline_lines) == BASE_INPUTS
            and current.get('inputs') == inputs_fingerprint(candidate_lines), 'Full source fingerprint differs')
    require(current.get('flutter') == '3.47.7' and current.get('lock') == BASE_LOCK,
            'Flutter or resolved lock changed')
    changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
    require(changed == set(APPROVED_FILE_SHA256) == set(candidate_blobs), 'Unapproved or missing input delta')
    for path in sorted(changed):
        require(after.get(path, '').startswith('100644 blob ') and approved_blob(path, candidate_blobs[path]),
                'Unapproved automation bytes or file mode: ' + path)
    expected_run = {'id': BASE_RUN_ID, 'run_number': 352, 'run_attempt': 1, 'head_sha': BASE_SOURCE,
                    'head_branch': BRANCH, 'event': 'workflow_dispatch', 'path': '.github/workflows/stage1.yml',
                    'status': 'completed', 'conclusion': 'failure'}
    require(all(run.get(key) == value for key, value in expected_run.items()), 'Prior run provenance differs')
    for name in ('repository', 'head_repository'):
        require(isinstance(run.get(name), dict) and run[name].get('id') == REPO_ID
                and run[name].get('full_name') == REPO, 'Prior repository differs')
    for name in ('release_mode', 'production_backend / postgres', 'checks'):
        matches = [job for job in jobs if job.get('name') == name]
        require(len(matches) == 1, 'Missing/duplicate prior job: ' + name)
        job = matches[0]
        expected_job = {'run_id': BASE_RUN_ID, 'run_attempt': 1, 'head_sha': BASE_SOURCE,
                        'status': 'completed', 'conclusion': 'failure' if name == 'checks' else 'success'}
        require(all(job.get(key) == value for key, value in expected_job.items()), 'Prior job provenance/status differs')
        if name == 'checks':
            require(job.get('id') == 133332792360, 'Prior checks job ID differs')
            steps = job.get('steps')
            require(isinstance(steps, list) and all(isinstance(step, dict)
                    and type(step.get('number')) is int and isinstance(step.get('name'), str)
                    for step in steps), 'Incomplete prior steps')
            prefix = sorted([step for step in steps if step['number'] <= 28],
                            key=lambda step: step['number'])
            require([step['number'] for step in prefix] == list(range(1, 29)), 'Pre-build steps missing or duplicated')
            layout = [(step['number'], step['name']) for step in prefix]
            require(sha(json.dumps(layout, separators=(',', ':')).encode()) == PREFIX_LAYOUT_SHA256,
                    'Required pre-build step names/order differ')
            require(all(step.get('status') == 'completed' and step.get('conclusion') == 'success'
                        for step in prefix), 'A required pre-build step did not succeed')
            require(prefix[-1]['name'] == 'Save evidence after all mandatory validation succeeds',
                    'Successful Save-evidence step missing')
    expected_artifact = {'id': BASE_ARTIFACT_ID, 'name': 'lifeos-validation-proof', 'expired': False,
                         'digest': 'sha256:' + BASE_ARTIFACT_SHA256, 'size_in_bytes': len(raw)}
    require(all(artifact.get(key) == value for key, value in expected_artifact.items())
            and len(raw) <= 16384 and sha(raw) == BASE_ARTIFACT_SHA256, 'Prior proof artifact bytes/digest differ')
    origin = {'id': BASE_RUN_ID, 'head_sha': BASE_SOURCE, 'head_branch': BRANCH,
              'repository_id': REPO_ID, 'head_repository_id': REPO_ID}
    require(isinstance(artifact.get('workflow_run'), dict)
            and all(artifact['workflow_run'].get(key) == value for key, value in origin.items()),
            'Prior proof artifact source differs')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            require(archive.namelist() == ['validation-proof.json']
                    and archive.getinfo('validation-proof.json').file_size <= 4096, 'Ambiguous proof ZIP')
            prior = json.loads(archive.read('validation-proof.json'))
    except (zipfile.BadZipFile, ValueError, UnicodeError, KeyError) as error:
        raise EvidenceRejected('Unreadable proof ZIP') from error
    require(prior == {'sha': BASE_SOURCE, 'inputs': BASE_INPUTS, 'lock': BASE_LOCK, 'flutter': '3.47.7'},
            'Original full-input/lock/Flutter proof differs')
    return {'scope': 'pre-build-only', 'prior_run_id': BASE_RUN_ID, 'prior_source': BASE_SOURCE,
            'prior_run_conclusion': 'failure', 'prior_run_accepted_as_green': False,
            'proof_artifact_id': BASE_ARTIFACT_ID, 'proof_artifact_sha256': BASE_ARTIFACT_SHA256,
            'successful_prebuild_steps': 28, 'approved_changed_paths': sorted(changed),
            'source': current['sha'], 'inputs': current['inputs'], 'lock': BASE_LOCK, 'flutter': '3.47.7',
            'fresh_signing_upgrade_publication_required': True}
