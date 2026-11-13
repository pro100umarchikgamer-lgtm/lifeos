"""Release boundary and publication transaction tests; no application tests."""
import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

from tool import native_release_mode as mode
from tool import publish_retained_apk as publisher

ROOT = Path(__file__).resolve().parents[2]
DECLARATION = json.loads((ROOT / mode.DECLARATION).read_text())


class ModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Release test')
        self.git('config', 'user.email', 'release@example.invalid')
        self.write('lib/app.dart', 'retained product')
        for path in mode.RELEASE_FILES:
            self.write(path, 'retained infrastructure')
        self.commit()
        self.declaration = {'source': self.git('rev-parse', 'HEAD').decode().strip()}
        self.env = {'GITHUB_REPOSITORY': mode.REPOSITORY, 'GITHUB_REF': 'refs/heads/' + mode.BRANCH,
                    'GITHUB_EVENT_NAME': 'workflow_dispatch', 'BUILD_APK': 'true'}

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.DEVNULL)

    def write(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value)

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture')

    def selected(self):
        return mode.choose_mode(self.declaration, self.env, self.git)

    def infra_change(self):
        self.write('tool/publish_retained_apk.py', 'updated infrastructure')
        self.commit()

    def test_nonempty_exact_infrastructure_diff_selects_publication(self):
        self.infra_change()
        self.assertEqual(self.selected(), 'publish-retained')

    def test_empty_source_equal_diff_keeps_normal_build(self):
        self.assertEqual(self.selected(), 'validate')

    def test_product_and_infrastructure_diff_keeps_normal_validation(self):
        self.infra_change()
        self.write('lib/app.dart', 'changed product')
        self.commit()
        self.assertEqual(self.selected(), 'validate')

    def test_product_rename_into_allowed_file_cannot_hide_deletion(self):
        self.git('mv', '-f', 'lib/app.dart', 'tool/publish_retained_apk.py')
        self.commit()
        self.assertEqual(self.selected(), 'validate')

    def test_newline_and_unicode_paths_cannot_cross_boundary(self):
        for name in ('tool/publish_retained_apk.py\nlib/app.dart', 'tool/релиз.py'):
            with self.subTest(name=name):
                self.write(name, 'product outside allowlist')
                self.commit()
                self.assertEqual(self.selected(), 'validate')

    def test_infrastructure_deletion_and_symlink_keep_normal_validation(self):
        self.infra_change()
        target = self.root / 'tool/native_release_mode.py'
        target.unlink()
        self.commit()
        self.assertEqual(self.selected(), 'validate')
        target.symlink_to('publish_retained_apk.py')
        self.commit()
        self.assertEqual(self.selected(), 'validate')

    def test_ancestry_mismatch_keeps_normal_validation(self):
        self.infra_change()
        self.declaration['source'] = '0' * 40
        self.assertEqual(self.selected(), 'validate')

    def test_literal_boolean_and_trusted_manual_context_required(self):
        self.infra_change()
        for key, value in [('BUILD_APK', 'false'), ('BUILD_APK', 'True'), ('BUILD_APK', ''),
                           ('GITHUB_EVENT_NAME', 'pull_request'), ('GITHUB_EVENT_NAME', 'push'),
                           ('GITHUB_EVENT_NAME', 'pull_request_target'), ('GITHUB_REPOSITORY', 'fork/lifeos'),
                           ('GITHUB_REF', 'refs/heads/other'), ('UPGRADE_PROBE', 'true'),
                           ('FOCUSED', 'true'), ('REUSE_SIGNED_APK', 'true'), ('FORCE_FULL_VALIDATION', 'true')]:
            with self.subTest(key=key, value=value):
                env = {**self.env, key: value}
                self.assertEqual(mode.choose_mode(self.declaration, env, self.git), 'validate')

    def test_missing_source_or_git_failure_never_selects_publication(self):
        with self.assertRaises(KeyError):
            mode.choose_mode({}, self.env, self.git)
        with self.assertRaises(OSError):
            mode.choose_mode(self.declaration, self.env, lambda *args: (_ for _ in ()).throw(OSError('git unavailable')))


def run_fixture(pin):
    repo = {'id': DECLARATION['repository_id'], 'full_name': mode.REPOSITORY}
    return {'id': pin['id'], 'run_number': pin['number'], 'status': 'completed', 'conclusion': 'success',
            'event': pin['event'], 'path': '.github/workflows/' + pin['workflow'],
            'head_sha': DECLARATION['source'], 'head_branch': mode.BRANCH,
            'repository': repo.copy(), 'head_repository': repo.copy()}


def artifact_fixture(pin):
    return {'id': pin['id'], 'name': pin['name'], 'expired': False, 'digest': 'sha256:' + pin['sha256'],
            'workflow_run': {'id': DECLARATION['signed_run']['id'], 'head_sha': DECLARATION['source'],
                             'head_branch': mode.BRANCH, 'repository_id': DECLARATION['repository_id'],
                             'head_repository_id': DECLARATION['repository_id']}}


class EvidenceTests(unittest.TestCase):
    def test_upload_redirects_never_forward_authorization(self):
        self.assertIsNone(publisher.NoUploadRedirect().redirect_request(
            None, None, 302, 'redirect', {}, 'https://untrusted.invalid'))

    def test_source_run_success_event_workflow_and_repository_pins(self):
        pin = DECLARATION['signed_run']
        publisher.verify_run(run_fixture(pin), pin, DECLARATION)
        for field, value in [('id', 1), ('run_number', 1), ('status', 'in_progress'), ('conclusion', 'failure'),
                             ('event', 'pull_request'), ('path', '.github/workflows/other.yml'),
                             ('head_sha', 'a' * 40), ('head_branch', 'other'),
                             ('head_repository', {'id': 1, 'full_name': 'fork/lifeos'})]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                publisher.verify_run({**run_fixture(pin), field: value}, pin, DECLARATION)

    def test_artifact_identity_digest_expiry_source_and_repository_pins(self):
        pin = DECLARATION['apk_artifact']
        publisher.verify_artifact(artifact_fixture(pin), pin, DECLARATION)
        for key, value in [('id', 1), ('name', 'other'), ('expired', True), ('digest', 'sha256:' + '0' * 64)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                publisher.verify_artifact({**artifact_fixture(pin), key: value}, pin, DECLARATION)
        for key, value in [('id', 1), ('head_sha', '0' * 40), ('head_repository_id', 1), ('head_branch', 'other')]:
            artifact = artifact_fixture(pin)
            artifact['workflow_run'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                publisher.verify_artifact(artifact, pin, DECLARATION)

    def test_binary_manifest_and_signer_identity_must_match(self):
        publisher.verify_manifest("package: name='app.lifeos.lifeos' versionCode='312001'\napplication-label:'ULADIM'", DECLARATION)
        for report in ("package: name='other' versionCode='312001'\napplication-label:'ULADIM'",
                       "package: name='app.lifeos.lifeos' versionCode='303001'\napplication-label:'ULADIM'"):
            with self.assertRaises(ValueError):
                publisher.verify_manifest(report, DECLARATION)
        cert = 'Number of signers: 1\nSigner #1 certificate SHA-256 digest: ' + DECLARATION['certificate_sha256'] + '\n'
        publisher.verify_certificate(cert, DECLARATION['certificate_sha256'])
        for report in (cert.replace('signers: 1', 'signers: 2'), cert.replace(DECLARATION['certificate_sha256'], '0' * 64)):
            with self.assertRaises(ValueError):
                publisher.verify_certificate(report, DECLARATION['certificate_sha256'])

    def test_downloaded_zip_bytes_are_verified_before_reading(self):
        with self.assertRaisesRegex(ValueError, 'ZIP digest'):
            publisher.prepare_assets(DECLARATION, b'wrong APK archive', b'wrong upgrade archive')

    def upgrade_archive(self, changes=None, report=None):
        evidence = {
            'previousVersionCode': 134001, 'intermediateVersionCode': 303001, 'installedVersionCode': 312001,
            'samePackageUid': True, 'syntheticTaskSurvivesUpdateAndRestart': True, 'uninstallOrDataClearUsed': False,
            'intermediateTaskAndFinancialDataRetained': True, 'baselineDeviceTimezone': 'Europe/Moscow',
            'candidateDeviceTimezone': 'Etc/UTC',
            'financialAmountsRetained': {'incomeMinor': 10000, 'expenseMinor': 1250, 'differenceMinor': 8750, 'currency': 'USD'},
            'nativeNavigationScreenshots': ['Today', 'Tasks', 'Calendar', 'Notes', 'Finances', 'Profile'],
            'notificationDelivery': {'runtimePermissionGranted': True, 'freshBridgeResult': 'posted',
                                     'activeOsNotification': True, 'channel': 'lifeos.important',
                                     'importance': 'high', 'physicalSoundOrBannerVerified': False},
        }
        evidence.update(changes or {})
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, 'w') as archive:
            archive.writestr('upgrade-result.json', json.dumps(evidence))
            for page in ('today', 'tasks', 'calendar', 'notes', 'finances', 'profile'):
                for theme in ('light', 'dark'):
                    archive.writestr(page + '-' + theme + '.png', b'\x89PNG\r\n\x1a\n')
            archive.writestr('notification-dumpsys.txt', report if report is not None else
                             '  Notification List:\n    NotificationRecord(0x1: pkg=app.lifeos.lifeos user=UserHandle{0} id=1 tag=test importance=4 key=test: Notification(channel=lifeos.important shortcut=null))\n')
        return zipfile.ZipFile(io.BytesIO(raw.getvalue()))

    def test_upgrade_chain_retention_no_clear_money_and_notification_proof(self):
        with self.upgrade_archive() as archive:
            publisher.verify_upgrade(archive, DECLARATION)
        for key, value in [('samePackageUid', False), ('uninstallOrDataClearUsed', True),
                           ('intermediateVersionCode', 134001), ('intermediateTaskAndFinancialDataRetained', False),
                           ('installedVersionCode', 303001), ('financialAmountsRetained', {}),
                           ('notificationDelivery', {})]:
            with self.subTest(key=key), self.upgrade_archive({key: value}) as archive, self.assertRaises(ValueError):
                publisher.verify_upgrade(archive, DECLARATION)

    def test_historical_or_missing_notification_section_is_rejected(self):
        line = '    NotificationRecord(0x1: pkg=app.lifeos.lifeos user=UserHandle{0} id=1 tag=test importance=4 key=test: Notification(channel=lifeos.important shortcut=null))\n'
        for report in (line, '  Notification List:\n  Historical Notifications:\n' + line,
                       '  Notification List:\n' + line.replace('importance=4', 'importance=3')):
            with self.subTest(report=report), self.upgrade_archive(report=report) as archive, self.assertRaises(ValueError):
                publisher.verify_upgrade(archive, DECLARATION)


class FakeGitHub:
    def __init__(self, release=None):
        self.release = copy.deepcopy(release)
        self.calls = []
        self.tag = None if not release or release['draft'] else DECLARATION['source']
        self.bad_upload = False

    def request(self, path, method='GET', payload=None):
        self.calls.append((path, method, copy.deepcopy(payload)))
        if path.startswith('git/matching-refs/'):
            return [] if self.tag is None else [{'ref': 'refs/tags/' + publisher.release_metadata(DECLARATION)['tag_name'],
                                                'object': {'type': 'commit', 'sha': self.tag}}]
        if path.startswith('releases?'):
            return [] if self.release is None else [copy.deepcopy(self.release)]
        if path == 'releases' and method == 'POST':
            self.release = {**payload, 'id': 321, 'assets': [], 'html_url': 'https://example.invalid/release'}
        elif path == 'releases/321' and method == 'PATCH':
            self.release['draft'] = payload['draft']
            self.tag = self.release['target_commitish']
        elif path != 'releases/321':
            raise AssertionError('Unexpected endpoint: ' + path)
        return copy.deepcopy(self.release)

    def upload(self, release_id, name, data):
        if release_id != 321:
            raise AssertionError('Upload did not retain release ID')
        self.calls.append(('upload/' + name, 'POST', None))
        asset = {'name': name, 'size': len(data), 'state': 'uploaded',
                 'digest': 'sha256:' + ('0' * 64 if self.bad_upload else publisher.sha256(data)),
                 'browser_download_url': 'https://example.invalid/' + name}
        self.release['assets'].append(asset)
        return asset


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.assets = {'ULADIM.apk': b'signed bytes', 'release-evidence.json': b'public proof'}

    def publish(self, api):
        return publisher.publish(api, DECLARATION, self.assets)

    def existing(self, draft=True):
        return {**publisher.release_metadata(DECLARATION), 'id': 321, 'draft': draft,
                'assets': [], 'html_url': 'https://example.invalid/release'}

    def test_create_uses_post_response_id_and_list_never_tag_lookup(self):
        api = FakeGitHub()
        result = self.publish(api)
        self.assertEqual(result['release_id'], 321)
        self.assertFalse(api.release['draft'])
        self.assertFalse(any(path.startswith('releases/tags/') for path, _, _ in api.calls))
        self.assertEqual(sum(method == 'PATCH' for _, method, _ in api.calls), 1)

    def test_partial_compatible_draft_resumes_by_id_without_duplicate_upload(self):
        api = FakeGitHub(self.existing())
        api.upload(321, 'ULADIM.apk', self.assets['ULADIM.apk'])
        api.calls.clear()
        self.publish(api)
        self.assertEqual([path for path, _, _ in api.calls if path.startswith('upload/')], ['upload/release-evidence.json'])
        self.assertFalse(any(path == 'releases' and method == 'POST' for path, method, _ in api.calls))

    def test_matching_public_release_is_idempotent_without_mutation(self):
        api = FakeGitHub()
        self.publish(api)
        api.calls.clear()
        self.publish(api)
        self.assertTrue(all(method == 'GET' for _, method, _ in api.calls))

    def test_mismatched_existing_metadata_stops_without_mutation(self):
        for key, value in [('target_commitish', '0' * 40), ('body', 'other notes'), ('name', 'other'), ('prerelease', True)]:
            api = FakeGitHub({**self.existing(), key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.publish(api)
            self.assertTrue(all(method == 'GET' for _, method, _ in api.calls))

    def test_wrong_existing_tag_stops_before_creating_draft(self):
        api = FakeGitHub()
        api.tag = '0' * 40
        with self.assertRaisesRegex(ValueError, 'another source'):
            self.publish(api)
        self.assertTrue(all(method == 'GET' for _, method, _ in api.calls))

    def test_uploaded_digest_mismatch_leaves_draft_unpublished(self):
        api = FakeGitHub()
        api.bad_upload = True
        with self.assertRaisesRegex(ValueError, 'digest/size'):
            self.publish(api)
        self.assertTrue(api.release['draft'])
        self.assertFalse(any(method == 'PATCH' for _, method, _ in api.calls))

    def test_mismatched_partial_asset_stops_without_clobber(self):
        api = FakeGitHub(self.existing())
        api.bad_upload = True
        api.upload(321, 'ULADIM.apk', self.assets['ULADIM.apk'])
        api.calls.clear()
        with self.assertRaises(ValueError):
            self.publish(api)
        self.assertTrue(all(method == 'GET' for _, method, _ in api.calls))

    def test_incomplete_public_release_stops_without_mutation(self):
        api = FakeGitHub(self.existing(draft=False))
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.publish(api)
        self.assertTrue(all(method == 'GET' for _, method, _ in api.calls))


if __name__ == '__main__':
    unittest.main()
