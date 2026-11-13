"""Automatic publication must prove the current trusted run, never caller pins."""
import io
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch
import zipfile

from tool import publish_current_apk as current
from tool import publish_retained_apk as retained
from tool.tests import test_retained_native_release as retained_tests


SOURCE = 'a' * 40
ENV = {
    'GITHUB_REPOSITORY': 'pro100umarchikgamer-lgtm/lifeos',
    'GITHUB_REF': 'refs/heads/work/uladim-web-platform',
    'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_JOB': 'publish_signed',
    'GITHUB_WORKFLOW_REF': 'pro100umarchikgamer-lgtm/lifeos/.github/workflows/stage1.yml@refs/heads/work/uladim-web-platform',
    'GITHUB_WORKFLOW_SHA': SOURCE, 'GITHUB_SHA': SOURCE,
    'GITHUB_RUN_ID': '1001', 'GITHUB_RUN_NUMBER': '400', 'GITHUB_RUN_ATTEMPT': '1',
}
EVENT = {'inputs': {'build_apk': 'true', 'focused': 'false', 'upgrade_probe': 'false',
                    'reuse_signed_apk': 'false', 'force_full_validation': 'true'}}


def pin():
    return current.verify_context(ENV, EVENT, lambda *args: (SOURCE + '\n').encode())


def run_fixture():
    repo = {'id': 1413453356, 'full_name': ENV['GITHUB_REPOSITORY']}
    return {'id': 1001, 'run_number': 400, 'run_attempt': 1, 'status': 'in_progress',
            'conclusion': None, 'event': 'workflow_dispatch', 'path': '.github/workflows/stage1.yml',
            'head_sha': SOURCE, 'head_branch': 'work/uladim-web-platform',
            'repository': repo.copy(), 'head_repository': repo.copy()}


def job_fixture(name, index, status='completed', conclusion='success'):
    return {'id': 2000 + index, 'run_id': 1001, 'run_attempt': 1, 'head_sha': SOURCE,
            'name': name, 'status': status, 'conclusion': conclusion,
            'steps': [{'name': step, 'status': 'completed', 'conclusion': 'success'}
                      for step in current.SIGNED_STEPS] if name == 'checks' else []}


def jobs_fixture():
    return [job_fixture(name, i) for i, name in enumerate(current.REQUIRED_JOBS)] + [
        job_fixture('publish_retained', 4, conclusion='skipped'),
        job_fixture('focused', 5, conclusion='skipped'),
        job_fixture('upgrade_probe', 6, conclusion='skipped'),
        job_fixture('publish_signed', 7, status='in_progress', conclusion=None)]


def apk_archive():
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as archive:
        archive.writestr(retained.APK_PATH, b'actual signed APK bytes')
    return data.getvalue()


def artifact_fixture(name, index, raw):
    return {'id': 3000 + index, 'name': name, 'expired': False,
            'digest': 'sha256:' + retained.sha256(raw),
            'workflow_run': {'id': 1001, 'head_sha': SOURCE, 'head_branch': 'work/uladim-web-platform',
                             'repository_id': 1413453356, 'head_repository_id': 1413453356}}


def artifacts_fixture():
    return [artifact_fixture('lifeos-release-test-apk-' + SOURCE, 0, apk_archive()),
            artifact_fixture('uladim-upgrade-evidence-400', 1, b'upgrade ZIP')]


def accepted_upgrade_archive(changes=None, omitted=None):
    fields = {'installedVersionCode': 400001, 'acceptedBaselineVersionCode': 312001,
              'acceptedBaselineApkSha256': current.ACCEPTED_APK_SHA256,
              'directUpgradeFromVersionCode': 312001, 'upgradeVersionChain': [134001,303001,312001,400001],
              'acceptedBaselineTaskAndFinancialDataRetained': True,
              'acceptedBaselineCreatedTaskRetainedAfterRestart': True}
    fields.update(changes or {})
    data=io.BytesIO()
    with retained_tests.EvidenceTests().upgrade_archive(fields) as original, zipfile.ZipFile(data,'w') as archive:
        for name in original.namelist():archive.writestr(name,original.read(name))
        additional={'accepted-312001-package.txt':b'Package [app.lifeos.lifeos] versionCode=312001',
                    'direct-312001-to-candidate-install.txt':b'Performing Streamed Install\nSuccess\n'}
        for stage in ('accepted-312001-control-task','accepted-312001-finances',
                      'accepted-312001-created-task','upgraded-312001-created-task'):
            additional[stage+'.png']=b'\x89PNG\r\n\x1a\n'
            additional[stage+'.xml']=b'<hierarchy><node text="synthetic retained record"/></hierarchy>'
        for name,value in additional.items():
            if name!=omitted:archive.writestr(name,value)
    return data.getvalue()


class AcceptedUpgradeTests(unittest.TestCase):
    def test_direct_accepted_apk_and_data_retention_are_required(self):
        current.verify_accepted_upgrade(accepted_upgrade_archive(),{'version_code':400001})
        for key,value in [('acceptedBaselineVersionCode',303001),('acceptedBaselineApkSha256','0'*64),
                          ('directUpgradeFromVersionCode',303001),('upgradeVersionChain',[134001,303001,400001]),
                          ('acceptedBaselineTaskAndFinancialDataRetained',False),
                          ('acceptedBaselineCreatedTaskRetainedAfterRestart',False)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                current.verify_accepted_upgrade(accepted_upgrade_archive({key:value}),{'version_code':400001})

    def test_json_claims_without_installed_package_or_real_ui_files_are_rejected(self):
        for missing in ('accepted-312001-package.txt','direct-312001-to-candidate-install.txt',
                        'accepted-312001-created-task.xml','upgraded-312001-created-task.png'):
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                current.verify_accepted_upgrade(accepted_upgrade_archive(omitted=missing),{'version_code':400001})


class ContextTests(unittest.TestCase):
    def test_only_exact_native_github_context_and_checked_out_source_are_accepted(self):
        self.assertEqual(pin(), {'id': 1001, 'number': 400, 'attempt': 1, 'source': SOURCE})
        for key, value in [('GITHUB_REPOSITORY', 'fork/lifeos'), ('GITHUB_REF', 'refs/heads/other'),
                           ('GITHUB_EVENT_NAME', 'pull_request'), ('GITHUB_EVENT_NAME', 'push'),
                           ('GITHUB_EVENT_NAME', 'pull_request_target'), ('GITHUB_JOB', 'checks'),
                           ('GITHUB_SHA', 'a' * 12), ('GITHUB_WORKFLOW_SHA', 'b' * 40),
                           ('GITHUB_WORKFLOW_REF', 'other/workflow.yml@refs/heads/main'),
                           ('GITHUB_RUN_ATTEMPT', '0'), ('GITHUB_RUN_ATTEMPT', '1000'),
                           ('GITHUB_RUN_NUMBER', '312'), ('GITHUB_RUN_ID', '0')]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                current.verify_context({**ENV, key: value}, EVENT, lambda *args: (SOURCE + '\n').encode())
        with self.assertRaisesRegex(ValueError, 'checkout'):
            current.verify_context(ENV, EVENT, lambda *args: ('b' * 40).encode())

    def test_dispatch_inputs_cannot_select_probe_focused_reused_or_unsigned_release(self):
        for changes in ({'build_apk': 'false'}, {'build_apk': 'True'}, {'build_apk': None},
                        {'focused': 'true'}, {'upgrade_probe': 'true'}, {'reuse_signed_apk': 'true'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                current.verify_context(ENV, {'inputs': {**EVENT['inputs'], **changes}},
                                       lambda *args: SOURCE.encode())


class GateTests(unittest.TestCase):
    def test_running_run_requires_exact_repository_source_identity_event_and_attempt(self):
        current.verify_current_run(run_fixture(), pin())
        for key, value in [('id', 2), ('run_number', 401), ('run_attempt', 2), ('status', 'completed'),
                           ('conclusion', 'failure'), ('event', 'pull_request'), ('head_sha', 'b' * 40),
                           ('head_branch', 'main'), ('path', '.github/workflows/other.yml'),
                           ('head_repository', {'id': 1413453356, 'full_name': 'fork/lifeos'}),
                           ('repository', {'id': 2, 'full_name': ENV['GITHUB_REPOSITORY']})]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                current.verify_current_run({**run_fixture(), key: value}, pin())

    def test_all_prerequisite_jobs_and_actual_signed_upgrade_steps_must_succeed(self):
        current.verify_jobs(jobs_fixture(), pin())
        for name in current.REQUIRED_JOBS:
            for field, value in [('status', 'in_progress'), ('conclusion', 'failure'),
                                 ('conclusion', 'skipped'), ('run_attempt', 2), ('head_sha', 'b' * 40)]:
                jobs = jobs_fixture()
                next(job for job in jobs if job['name'] == name)[field] = value
                with self.subTest(name=name, field=field), self.assertRaises(ValueError):
                    current.verify_jobs(jobs, pin())
        for step in current.SIGNED_STEPS:
            jobs = jobs_fixture()
            checks = next(job for job in jobs if job['name'] == 'checks')
            next(item for item in checks['steps'] if item['name'] == step)['conclusion'] = 'skipped'
            with self.subTest(step=step), self.assertRaises(ValueError):
                current.verify_jobs(jobs, pin())

    def test_missing_duplicate_failed_or_concurrent_extra_jobs_are_rejected(self):
        for jobs in (jobs_fixture()[1:], jobs_fixture() + [job_fixture('checks', 90)],
                     jobs_fixture() + [job_fixture('new-gate', 91, conclusion='failure')],
                     jobs_fixture() + [job_fixture('new-gate', 92, status='in_progress', conclusion=None)]):
            with self.subTest(jobs=jobs), self.assertRaises(ValueError):
                current.verify_jobs(jobs, pin())

    def test_artifacts_are_selected_only_from_current_run_and_digest_pins_generated(self):
        declaration = current.derive_declaration(artifacts_fixture(), pin(), apk_archive())
        self.assertEqual(declaration['version_code'], 400001)
        self.assertEqual(declaration['source'], SOURCE)
        self.assertEqual(declaration['apk_artifact']['id'], 3000)
        self.assertEqual(declaration['upgrade_artifact']['id'], 3001)
        self.assertEqual(declaration['apk_sha256'], retained.sha256(b'actual signed APK bytes'))
        self.assertEqual(declaration['certificate_sha256'],
                         '5fa37e4abf1ec90d5787bd0d7dc4cf0b3f49022172f9d25e91f4d8a76702a96e')
        for artifacts in (artifacts_fixture()[:1], artifacts_fixture() + [artifacts_fixture()[0]]):
            with self.assertRaises(ValueError):
                current.derive_declaration(artifacts, pin(), apk_archive())

    def test_expired_wrong_digest_or_foreign_artifact_is_rejected_before_reading_zip(self):
        for key, value in [('expired', True), ('id', 0), ('digest', None),
                           ('digest', 'sha256:' + '0' * 64)]:
            artifacts = artifacts_fixture()
            artifacts[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                current.derive_declaration(artifacts, pin(), apk_archive())
        for key, value in [('id', 2), ('head_sha', 'b' * 40), ('head_branch', 'main'),
                           ('head_repository_id', 2), ('repository_id', 2)]:
            artifacts = artifacts_fixture()
            artifacts[0]['workflow_run'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                current.derive_declaration(artifacts, pin(), apk_archive())

    def test_branch_movement_blocks_each_release_mutation_including_final_publication(self):
        class API:
            def __init__(self):
                self.source = SOURCE
                self.mutations = []

            def request(self, path, method='GET', payload=None):
                if path == 'actions/runs/1001':
                    return run_fixture()
                if path.startswith('actions/runs/1001/attempts/1/jobs?'):
                    jobs = jobs_fixture()
                    return {'jobs': jobs, 'total_count': len(jobs)}
                if path.startswith('git/ref/heads/'):
                    return {'ref': ENV['GITHUB_REF'], 'object': {'type': 'commit', 'sha': self.source}}
                self.mutations.append((path, method, payload))
                return {}

            def upload(self, *args):
                self.mutations.append(args)

        api = API()
        guarded = current.SourcePinnedAPI(api, pin())
        guarded.request('releases', 'POST', {'draft': True})
        guarded.upload(1, 'ULADIM.apk', b'bytes')
        api.source = 'b' * 40
        with self.assertRaisesRegex(ValueError, 'branch'):
            guarded.request('releases/1', 'PATCH', {'draft': False})
        with self.assertRaisesRegex(ValueError, 'branch'):
            guarded.upload(1, 'other', b'bytes')
        self.assertEqual(len(api.mutations), 2)


class WorkflowTests(unittest.TestCase):
    def test_publication_is_final_scoped_dispatch_job_without_default_branch_dependency(self):
        root = Path(__file__).resolve().parents[2]
        workflow = (root / '.github/workflows/stage1.yml').read_text()
        job = re.split(r'\n(?=  [a-z_]+:\n)', workflow.split('  publish_signed:\n')[1])[0]
        self.assertIn('needs: [release_mode, production_backend, checks]', job)
        self.assertIn('permissions:\n      contents: write\n      actions: read', job)
        for guard in ("github.event_name == 'workflow_dispatch'", 'inputs.build_apk == true',
                      "github.repository == 'pro100umarchikgamer-lgtm/lifeos'",
                      "github.ref == 'refs/heads/work/uladim-web-platform'",
                      "needs.release_mode.outputs.mode == 'validate'", "needs.checks.result == 'success'",
                      "needs.production_backend.result == 'success'"):
            self.assertIn(guard, job)
        self.assertIn('ref: ${{ github.sha }}', job)
        self.assertIn('persist-credentials: false', job)
        self.assertIn('run: python3 -m tool.publish_current_apk', job)


class CurrentRunAPI:
    """Real publication transaction with synthetic API/Android signing boundaries."""
    def __init__(self):
        self.certificate = 'Number of signers: 1\nSigner #1 certificate SHA-256 digest: ' + current.CERTIFICATE + '\n'
        self.manifest = "package: name='app.lifeos.lifeos' versionCode='400001'\napplication-label:'ULADIM'\n"
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr(retained.APK_PATH, b'actual signed APK bytes')
            archive.writestr('apk-identity.txt',
                             'commit=' + SOURCE + '\napplicationId=app.lifeos.lifeos\nversionCode=400001\n'
                             'certificateSHA256=' + current.CERTIFICATE + '\ndisplayName=ULADIM\n'
                             'apiOrigin=https://api.getuladim.space\n')
            archive.writestr('apk-certificate.txt', self.certificate)
            archive.writestr('apk-manifest.txt', self.manifest)
        upgrade_raw = accepted_upgrade_archive()
        self.downloads = {3000: data.getvalue(), 3001: upgrade_raw}
        self.artifacts = [artifact_fixture('lifeos-release-test-apk-' + SOURCE, 0, self.downloads[3000]),
                          artifact_fixture('uladim-upgrade-evidence-400', 1, self.downloads[3001])]
        self.run, self.jobs = run_fixture(), jobs_fixture()
        self.release, self.tag, self.source = None, None, SOURCE
        self.calls, self.uploaded = [], {}
        self.move_after_upload = False

    def request(self, path, method='GET', payload=None):
        self.calls.append((path, method))
        if path == '':
            return {'id': 1413453356, 'full_name': ENV['GITHUB_REPOSITORY'], 'private': False}
        if path == 'actions/runs/1001':
            return self.run
        if path.startswith('actions/runs/1001/attempts/1/jobs?'):
            return {'jobs': self.jobs, 'total_count': len(self.jobs)}
        if path.startswith('actions/runs/1001/artifacts?'):
            return {'artifacts': self.artifacts, 'total_count': len(self.artifacts)}
        if path.startswith('git/ref/heads/'):
            return {'ref': ENV['GITHUB_REF'], 'object': {'type': 'commit', 'sha': self.source}}
        if path.startswith('git/matching-refs/tags/'):
            return [] if self.tag is None else [{'ref': 'refs/tags/' + self.release['tag_name'],
                                                'object': {'type': 'commit', 'sha': self.tag}}]
        if path.startswith('releases?'):
            return [] if self.release is None else [self.release]
        if path == 'releases' and method == 'POST':
            self.release = {**payload, 'id': 77, 'html_url': 'https://example.invalid/release', 'assets': []}
            return self.release
        if path == 'releases/77':
            if method == 'PATCH':
                self.release['draft'] = payload['draft']
                self.tag = self.release['target_commitish']
            return self.release
        raise AssertionError('Unexpected endpoint: ' + path)

    def download(self, artifact_id):
        self.calls.append(('download/' + str(artifact_id), 'GET'))
        return self.downloads[artifact_id]

    def upload(self, release_id, name, data):
        self.calls.append(('upload/' + name, 'POST'))
        self.uploaded[name] = data
        asset = {'name': name, 'state': 'uploaded', 'size': len(data),
                 'digest': 'sha256:' + retained.sha256(data),
                 'browser_download_url': 'https://example.invalid/' + name}
        self.release['assets'].append(asset)
        if self.move_after_upload:
            self.source = 'b' * 40
        return asset


class PublicationIntegrationTests(unittest.TestCase):
    def publish(self, api, binary_certificate=None):
        def inspect(args, **kwargs):
            return ((binary_certificate or api.certificate) if args[0] == 'apksigner' else api.manifest).encode()
        with patch.object(retained, 'android_tool', side_effect=lambda name: name), \
                patch.object(retained.subprocess, 'check_output', side_effect=inspect):
            return current.publish_current(api, pin())

    def test_verified_current_run_publishes_exact_bytes_and_records_automatic_gate(self):
        api = CurrentRunAPI()
        declaration, receipt = self.publish(api)
        self.assertFalse(api.release['draft'])
        self.assertEqual(receipt['source'], SOURCE)
        self.assertEqual(receipt['sha256'], retained.sha256(api.uploaded['ULADIM.apk']))
        self.assertEqual(declaration['version_code'], 400001)
        evidence = json.loads(api.uploaded['release-evidence.json'])
        self.assertEqual(evidence['publication_gate']['mode'], 'automatic-current-run')
        self.assertEqual(evidence['publication_gate']['run_attempt'], 1)
        self.assertEqual({job['name'] for job in evidence['publication_gate']['required_jobs']}, set(current.REQUIRED_JOBS))
        self.assertIn((retained.sha256(api.uploaded['release-evidence.json']) + '  release-evidence.json\n').encode(),
                      api.uploaded['SHA256SUMS'])
        # The completed, identical release remains idempotent on job retry.
        api.calls.clear()
        self.publish(api)
        self.assertTrue(all(method == 'GET' for _, method in api.calls))

    def test_binary_signature_mismatch_or_download_tampering_never_creates_release(self):
        api = CurrentRunAPI()
        with self.assertRaisesRegex(ValueError, 'certificate'):
            self.publish(api, binary_certificate=api.certificate.replace(current.CERTIFICATE, '0' * 64))
        self.assertIsNone(api.release)
        api = CurrentRunAPI()
        api.downloads[3001] = b'tampered upgrade ZIP'
        with self.assertRaisesRegex(ValueError, 'ZIP digest'):
            self.publish(api)
        self.assertIsNone(api.release)

    def test_source_moving_during_upload_leaves_only_unpublished_draft(self):
        api = CurrentRunAPI()
        api.move_after_upload = True
        with self.assertRaisesRegex(ValueError, 'branch'):
            self.publish(api)
        self.assertTrue(api.release['draft'])
        self.assertFalse(any(method == 'PATCH' for _, method in api.calls))

    def test_cancellation_during_download_or_upload_never_publishes(self):
        for boundary in ('download', 'first_upload', 'last_upload'):
            with self.subTest(boundary=boundary):
                class CancelledAPI(CurrentRunAPI):
                    def download(self, artifact_id):
                        raw = super().download(artifact_id)
                        if boundary == 'download':
                            self.run.update(status='completed', conclusion='cancelled')
                        return raw

                    def upload(self, *args):
                        asset = super().upload(*args)
                        if (boundary == 'first_upload' and len(self.uploaded) == 1
                                or boundary == 'last_upload' and len(self.uploaded) == 6):
                            self.run.update(status='completed', conclusion='cancelled')
                        return asset

                api = CancelledAPI()
                with self.assertRaisesRegex(ValueError, 'in progress'):
                    self.publish(api)
                if boundary == 'download':
                    self.assertIsNone(api.release)
                else:
                    self.assertTrue(api.release['draft'])
                    self.assertEqual(len(api.uploaded), 1 if boundary == 'first_upload' else 6)
                self.assertFalse(any(method == 'PATCH' for _, method in api.calls))

    def test_attempt_change_during_download_or_upload_never_publishes(self):
        for boundary in ('download', 'first_upload', 'last_upload'):
            with self.subTest(boundary=boundary):
                class ReattemptedAPI(CurrentRunAPI):
                    def download(self, artifact_id):
                        raw = super().download(artifact_id)
                        if boundary == 'download':
                            self.run['run_attempt'] = 2
                        return raw

                    def upload(self, *args):
                        asset = super().upload(*args)
                        if (boundary == 'first_upload' and len(self.uploaded) == 1
                                or boundary == 'last_upload' and len(self.uploaded) == 6):
                            self.run['run_attempt'] = 2
                        return asset

                api = ReattemptedAPI()
                with self.assertRaisesRegex(ValueError, 'identity/attempt'):
                    self.publish(api)
                if boundary == 'download':
                    self.assertIsNone(api.release)
                else:
                    self.assertTrue(api.release['draft'])
                    self.assertEqual(len(api.uploaded), 1 if boundary == 'first_upload' else 6)
                self.assertFalse(any(method == 'PATCH' for _, method in api.calls))


if __name__ == '__main__':
    unittest.main()
