"""Boundary checks for one exact pre-build proof, never a failed-run acceptance."""
import copy
import hashlib
import io
import json
import unittest
from unittest.mock import patch
import zipfile

from tool import validation_evidence as evidence

SOURCE = 'fe141a77b85fef84f16383a8d94578924510eecb'
LOCK = 'e28c2e59f6351a7d1656487e8d52c0c25c136d4c6154a369ce0aa0200d1bd19c'
PATHS = ('tool/check_shared_editor_browser.py', 'tool/check_release_upgrade.py',
         'tool/tests/test_release_upgrade.py', 'tool/ci_validation.py',
         'tool/validation_evidence.py', 'tool/tests/test_validation_evidence.py')


def sha(raw): return hashlib.sha256(raw).hexdigest()


def tree(files):
    return ['100644 blob ' + hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            + '\t' + path for path, raw in sorted(files.items())]


class PassedPrebuildEvidence(unittest.TestCase):
    def setUp(self):
        self.baseline = {'lib/ui/app.dart': b'unchanged runtime', '.github/workflows/stage1.yml': b'unchanged workflow'}
        self.baseline.update({path: b'old helper ' + path.encode() for path in PATHS[:4]})
        self.blobs = {path: b'approved automation ' + path.encode() for path in PATHS}
        helper = b"SELF_SHA256 = '" + b'0' * 64 + b"'\n# reviewed helper\n"
        self.helper_pin = sha(helper)
        self.blobs['tool/validation_evidence.py'] = helper.replace(b'0' * 64, self.helper_pin.encode())
        candidate = {**self.baseline, **self.blobs}
        self.baseline_lines, self.candidate_lines = tree(self.baseline), tree(candidate)
        self.inputs = sha('\n'.join(self.baseline_lines).encode())
        self.current = {'sha': 'b' * 40, 'flutter': '3.47.7', 'lock': LOCK,
                        'inputs': sha('\n'.join(self.candidate_lines).encode())}
        self.parents = [SOURCE]
        self.run = {'id': 43876258617, 'run_number': 352, 'run_attempt': 1,
                    'head_sha': SOURCE, 'head_branch': 'work/uladim-web-platform',
                    'status': 'completed', 'conclusion': 'failure', 'event': 'workflow_dispatch',
                    'path': '.github/workflows/stage1.yml',
                    'repository': {'id': 1413453356, 'full_name': 'pro100umarchikgamer-lgtm/lifeos'},
                    'head_repository': {'id': 1413453356, 'full_name': 'pro100umarchikgamer-lgtm/lifeos'}}
        steps = [{'number': n, 'name': 'passed step ' + str(n), 'status': 'completed', 'conclusion': 'success'}
                 for n in range(1, 29)]
        steps[-1]['name'] = 'Save evidence after all mandatory validation succeeds'
        self.layout = sha(json.dumps([(s['number'], s['name']) for s in steps], separators=(',', ':')).encode())
        self.jobs = [{'id': 133332792360, 'name': 'checks', 'run_id': 43876258617,
                      'run_attempt': 1, 'head_sha': SOURCE, 'status': 'completed', 'conclusion': 'failure',
                      'steps': steps + [{'number': 33, 'name': 'later upgrade', 'status': 'completed', 'conclusion': 'failure'}]}]
        for name in ('release_mode', 'production_backend / postgres'):
            self.jobs.append({'name': name, 'run_id': 43876258617, 'run_attempt': 1,
                              'head_sha': SOURCE, 'status': 'completed', 'conclusion': 'success'})
        proof = {'sha': SOURCE, 'inputs': self.inputs, 'lock': LOCK, 'flutter': '3.47.7'}
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, 'w') as archive:
            archive.writestr('validation-proof.json', json.dumps(proof))
        self.raw = raw.getvalue()
        self.artifact = {'id': 14231457826, 'name': 'lifeos-validation-proof', 'expired': False,
                         'size_in_bytes': len(self.raw), 'digest': 'sha256:' + sha(self.raw),
                         'workflow_run': {'id': 43876258617, 'head_sha': SOURCE,
                                          'head_branch': 'work/uladim-web-platform',
                                          'repository_id': 1413453356, 'head_repository_id': 1413453356}}
        pins = {path: sha(raw) for path, raw in self.blobs.items()}
        pins['tool/validation_evidence.py'] = self.helper_pin
        for name, value in {'BASE_INPUTS': self.inputs, 'BASE_ARTIFACT_SHA256': sha(self.raw),
                            'PREFIX_LAYOUT_SHA256': self.layout, 'SELF_SHA256': self.helper_pin,
                            'APPROVED_FILE_SHA256': pins}.items():
            patcher = patch.object(evidence, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def verify(self):
        return evidence.verify_prebuild_evidence(self.run, self.jobs, self.artifact, self.raw,
                                                self.baseline_lines, self.candidate_lines, self.blobs,
                                                self.current, self.parents)

    def test_later_failed_upgrade_does_not_discard_verified_prebuild_prefix(self):
        receipt = self.verify()
        self.assertIsNotNone(receipt, 'A verified pre-build prefix should be reusable despite the later upgrade failure')
        self.assertEqual(receipt['scope'], 'pre-build-only')
        self.assertFalse(receipt['prior_run_accepted_as_green'])
        self.assertTrue(receipt['fresh_signing_upgrade_publication_required'])

    def test_every_required_step_and_saved_proof_must_have_succeeded(self):
        original = copy.deepcopy(self.jobs)
        for change in ('failed', 'skipped', 'missing', 'duplicate', 'renamed'):
            with self.subTest(change=change):
                self.jobs = copy.deepcopy(original)
                steps = self.jobs[0]['steps']
                if change in ('failed', 'skipped'): steps[18]['conclusion'] = change
                elif change == 'missing': steps.pop(19)
                elif change == 'duplicate': steps.append(copy.deepcopy(steps[0]))
                else: steps[27]['name'] = 'different proof step'
                with self.assertRaises(evidence.EvidenceRejected): self.verify()

    def test_run_job_artifact_source_and_attempt_are_pinned(self):
        for target, key, value in [(self.run, 'head_sha', 'c' * 40), (self.run, 'run_attempt', 2),
                                   (self.run, 'conclusion', 'success'), (self.jobs[0], 'run_id', 99),
                                   (self.artifact, 'id', 99), (self.artifact, 'expired', True)]:
            with self.subTest(key=key):
                previous = target[key]; target[key] = value
                with self.assertRaises(evidence.EvidenceRejected): self.verify()
                target[key] = previous

    def test_corrupt_or_ambiguous_archive_never_becomes_validation(self):
        raw = self.raw
        self.raw = raw + b'changed'
        with self.assertRaises(evidence.EvidenceRejected): self.verify()
        self.raw = raw
        self.artifact['digest'] = 'sha256:' + '0' * 64
        with self.assertRaises(evidence.EvidenceRejected): self.verify()

    def test_sdk_lock_and_full_input_fingerprint_must_match(self):
        for key, value in [('flutter', '3.48.0'), ('lock', '0' * 64), ('inputs', '0' * 64)]:
            previous = self.current[key]; self.current[key] = value
            with self.subTest(key=key), self.assertRaises(evidence.EvidenceRejected): self.verify()
            self.current[key] = previous

    def test_runtime_workflow_dependency_or_unapproved_test_drift_requires_full(self):
        original = self.candidate_lines
        for path in ['lib/ui/app.dart', '.github/workflows/stage1.yml', 'pubspec.yaml', 'test/new_unapproved_test.dart']:
            changed = {**self.baseline, **self.blobs, path: b'drift'}
            self.candidate_lines = tree(changed)
            self.current['inputs'] = sha('\n'.join(self.candidate_lines).encode())
            with self.subTest(path=path), self.assertRaises(evidence.EvidenceRejected): self.verify()
        self.candidate_lines = original

    def test_approved_filename_with_different_bytes_or_mode_is_not_approved(self):
        path = 'tool/ci_validation.py'
        original = self.blobs[path]
        self.blobs[path] += b'\nnot reviewed'
        with self.assertRaises(evidence.EvidenceRejected): self.verify()
        self.blobs[path] = original
        self.candidate_lines = [line.replace('100644 ', '100755 ', 1) if line.endswith('\t' + path) else line
                                for line in self.candidate_lines]
        self.current['inputs'] = sha('\n'.join(self.candidate_lines).encode())
        with self.assertRaises(evidence.EvidenceRejected): self.verify()

    def test_helper_drift_or_second_descendant_is_outside_one_child_exception(self):
        path = 'tool/validation_evidence.py'
        self.blobs[path] += b'\nchanged gate'
        with self.assertRaises(evidence.EvidenceRejected): self.verify()
        self.blobs[path] = self.blobs[path].removesuffix(b'\nchanged gate')
        self.parents = ['b' * 40]
        with self.assertRaises(evidence.EvidenceRejected): self.verify()
        self.parents = [SOURCE, 'c' * 40]
        with self.assertRaises(evidence.EvidenceRejected): self.verify()

    def test_incomplete_metadata_is_rejected_as_unusable_evidence(self):
        original_run, original_jobs, original_artifact = map(copy.deepcopy, (self.run, self.jobs, self.artifact))
        for change in ('jobs_missing', 'steps_missing', 'repository_missing', 'artifact_origin_missing'):
            self.run, self.jobs, self.artifact = map(copy.deepcopy, (original_run, original_jobs, original_artifact))
            if change == 'jobs_missing': self.jobs = None
            elif change == 'steps_missing': self.jobs[0]['steps'] = None
            elif change == 'repository_missing': self.run['head_repository'] = None
            else: self.artifact['workflow_run'] = None
            with self.subTest(change=change), self.assertRaises(evidence.EvidenceRejected): self.verify()
