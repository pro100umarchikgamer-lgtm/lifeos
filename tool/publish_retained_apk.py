"""Publish verified retained bytes; never build, install or execute the APK."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile

from tool.native_release_mode import BRANCH, DECLARATION, REPOSITORY, choose_mode

PUBLIC_EVIDENCE = ('apk-identity.txt', 'apk-certificate.txt', 'apk-manifest.txt')
APK_PATH = 'build/app/outputs/flutter-apk/app-release.apk'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class NoUploadRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


class GitHub:
    """gh handles authenticated artifact redirects without exposing credentials."""
    def request(self, path, method='GET', payload=None):
        endpoint = f'repos/{REPOSITORY}' + ('/' + path if path else '')
        args = ['gh', 'api', '--method', method, endpoint,
                '-H', 'X-GitHub-Api-Version: 2022-11-28']
        data = None
        if payload is not None:
            args += ['--input', '-']
            data = json.dumps(payload).encode()
        return json.loads(subprocess.check_output(args, input=data, timeout=120))

    def download(self, artifact_id):
        return subprocess.check_output([
            'gh', 'api', f'repos/{REPOSITORY}/actions/artifacts/{artifact_id}/zip'], timeout=300)

    def upload(self, release_id, name, data):
        # Fixed host/path: a release payload can never redirect the token elsewhere.
        url = f'https://uploads.github.com/repos/{REPOSITORY}/releases/{release_id}/assets?name={quote(name)}'
        request = Request(url, data=data, method='POST', headers={
            'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'Content-Type': 'application/octet-stream',
        })
        with build_opener(NoUploadRedirect()).open(request, timeout=300) as response:
            return json.load(response)


def verify_run(run, pin, declaration):
    require(run['id'] == pin['id'] and run['run_number'] == pin['number'], 'Run identity mismatch')
    require(run['status'] == 'completed' and run['conclusion'] == 'success', 'Pinned run did not pass')
    require(run['event'] == pin['event'], 'Pinned run event mismatch')
    require(run['path'] == '.github/workflows/' + pin['workflow'], 'Pinned workflow mismatch')
    require(run['head_sha'] == declaration['source'] and run['head_branch'] == BRANCH, 'Pinned run source mismatch')
    for key in ('repository', 'head_repository'):
        require(run[key]['full_name'] == REPOSITORY and run[key]['id'] == declaration['repository_id'],
                'Run repository mismatch')


def verify_artifact(artifact, pin, declaration):
    require(artifact['id'] == pin['id'] and artifact['name'] == pin['name'] and artifact['expired'] is False,
            'Retained artifact identity/expiry mismatch')
    require(artifact.get('digest') == 'sha256:' + pin['sha256'], 'Artifact metadata digest mismatch')
    run = artifact['workflow_run']
    require(run['id'] == declaration['signed_run']['id'] and run['head_sha'] == declaration['source']
            and run['head_branch'] == BRANCH, 'Artifact source/run mismatch')
    require(run['repository_id'] == run['head_repository_id'] == declaration['repository_id'],
            'Artifact repository mismatch')


def read_member(archive, name):
    require(archive.namelist().count(name) == 1, 'Missing/duplicate retained member: ' + name)
    return archive.read(name)


def verify_certificate(report, expected):
    digests = {value.lower() for value in re.findall(
        r'^(?:Signer #1|V[0-9.]+ Signer):? certificate SHA-256 digest: ([0-9a-fA-F]{64})\s*$', report, re.M)}
    require(re.search(r'^Number of signers: 1\s*$', report, re.M) and digests == {expected},
            'APK signature certificate mismatch')


def verify_manifest(report, declaration):
    package = re.search(r"^package: name='([^']+)' versionCode='([0-9]+)'", report, re.M)
    require(package and package.groups() == (declaration['application_id'], str(declaration['version_code'])),
            'Binary APK package/version mismatch')
    require("application-label:'" + declaration['display_name'] + "'" in report, 'APK display name mismatch')


def android_tool(name):
    direct = shutil.which(name)
    if direct:
        return direct
    root = Path(os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT', '/usr/local/lib/android/sdk'))
    candidates = list((root / 'build-tools').glob('*/' + name))
    require(bool(candidates), 'Required installed Android SDK tool unavailable: ' + name)
    return str(sorted(candidates, key=lambda p: [int(v) for v in re.findall(r'\d+', p.parent.name)])[-1])


def verify_upgrade(archive, declaration):
    evidence = json.loads(read_member(archive, 'upgrade-result.json'))
    expected = {
        'previousVersionCode': 134001, 'intermediateVersionCode': 303001,
        'installedVersionCode': declaration['version_code'], 'samePackageUid': True,
        'syntheticTaskSurvivesUpdateAndRestart': True, 'uninstallOrDataClearUsed': False,
        'intermediateTaskAndFinancialDataRetained': True,
        'baselineDeviceTimezone': 'Europe/Moscow', 'candidateDeviceTimezone': 'Etc/UTC',
        'financialAmountsRetained': {'incomeMinor': 10000, 'expenseMinor': 1250, 'differenceMinor': 8750, 'currency': 'USD'},
        'nativeNavigationScreenshots': ['Today', 'Tasks', 'Calendar', 'Notes', 'Finances', 'Profile'],
        'notificationDelivery': {
            'runtimePermissionGranted': True, 'freshBridgeResult': 'posted', 'activeOsNotification': True,
            'channel': 'lifeos.important', 'importance': 'high', 'physicalSoundOrBannerVerified': False,
        },
    }
    require(all(evidence.get(key) == value for key, value in expected.items()), 'Retained upgrade evidence mismatch')
    for page in expected['nativeNavigationScreenshots']:
        for theme in ('light', 'dark'):
            require(read_member(archive, page.lower() + '-' + theme + '.png').startswith(b'\x89PNG\r\n\x1a\n'),
                    'Retained native screenshot missing')
    report = read_member(archive, 'notification-dumpsys.txt').decode()
    header = re.search(r'^  Notification List:\s*$', report, re.M)
    require(header is not None, 'Retained active notification section missing')
    active = re.split(r'^  \S[^\n]*:\s*$', report[header.end():], maxsplit=1, flags=re.M)[0]
    require(re.search(r'NotificationRecord\([^\n]*pkg=app\.lifeos\.lifeos user=[^\n]* tag=test importance=4 [^\n]*channel=lifeos\.important ', active),
            'Retained active HIGH OS notification missing')
    return evidence


def prepare_assets(declaration, apk_zip, upgrade_zip):
    for raw, key in ((apk_zip, 'apk_artifact'), (upgrade_zip, 'upgrade_artifact')):
        require(sha256(raw) == declaration[key]['sha256'], 'Downloaded artifact ZIP digest mismatch')
    with zipfile.ZipFile(io.BytesIO(apk_zip)) as archive:
        apk = read_member(archive, APK_PATH)
        require(sha256(apk) == declaration['apk_sha256'], 'Retained APK bytes mismatch')
        assets = {name: read_member(archive, name) for name in PUBLIC_EVIDENCE}
    identity = dict(line.split('=', 1) for line in assets['apk-identity.txt'].decode().splitlines())
    require(identity == {
        'commit': declaration['source'], 'applicationId': declaration['application_id'],
        'versionCode': str(declaration['version_code']), 'certificateSHA256': declaration['certificate_sha256'],
        'displayName': declaration['display_name'], 'apiOrigin': declaration['api_origin'],
    }, 'Retained public identity mismatch')
    verify_certificate(assets['apk-certificate.txt'].decode(), declaration['certificate_sha256'])
    verify_manifest(assets['apk-manifest.txt'].decode(), declaration)
    # Mandatory independent inspection of signed binary bytes; no emulator/app execution.
    with tempfile.TemporaryDirectory(prefix='uladim-retained-') as folder:
        path = Path(folder) / 'ULADIM.apk'
        path.write_bytes(apk)
        certificate = subprocess.check_output([android_tool('apksigner'), 'verify', '--verbose', '--print-certs', str(path)], timeout=120).decode()
        manifest = subprocess.check_output([android_tool('aapt'), 'dump', 'badging', str(path)], timeout=120).decode()
    verify_certificate(certificate, declaration['certificate_sha256'])
    verify_manifest(manifest, declaration)
    with zipfile.ZipFile(io.BytesIO(upgrade_zip)) as archive:
        upgrade = verify_upgrade(archive, declaration)
    run_id = declaration['signed_run']['id']
    provenance = {
        'source': declaration['source'], 'run_url': f'https://github.com/{REPOSITORY}/actions/runs/{run_id}',
        'run_id': run_id, 'artifact_id': declaration['apk_artifact']['id'],
        'artifact_digest': 'sha256:' + declaration['apk_artifact']['sha256'],
        'upgrade_artifact_id': declaration['upgrade_artifact']['id'],
        'upgrade_artifact_digest': 'sha256:' + declaration['upgrade_artifact']['sha256'],
        'apk_sha256': declaration['apk_sha256'], 'certificate_sha256': declaration['certificate_sha256'],
        'identity': identity, 'independent_apksigner_check': True, 'independent_binary_manifest_check': True,
        'required_run_ids': [pin['id'] for pin in declaration['required_runs']], 'upgrade': upgrade,
    }
    assets['ULADIM.apk'] = apk
    assets['release-evidence.json'] = (json.dumps(provenance, indent=2) + '\n').encode()
    assets['SHA256SUMS'] = ''.join(sha256(assets[name]) + '  ' + name + '\n' for name in sorted(assets)).encode()
    return assets


def release_metadata(declaration):
    source = declaration['source']
    run_url = f"https://github.com/{REPOSITORY}/actions/runs/{declaration['signed_run']['id']}"
    return {
        'tag_name': 'uladim-native-' + source[:12], 'target_commitish': source,
        'name': 'ULADIM Android ' + str(declaration['version_code']),
        'body': 'ULADIM reviewed native release\nSource: ' + source + '\nValidation: ' + run_url + '\nAPK SHA256: ' + declaration['apk_sha256'],
        'prerelease': False,
    }


def verify_assets(uploaded, expected, complete):
    names = [asset['name'] for asset in uploaded]
    require(len(names) == len(set(names)) and set(names) <= set(expected), 'Unexpected/duplicate release assets')
    for asset in uploaded:
        require(asset['state'] == 'uploaded' and asset.get('digest') == 'sha256:' + sha256(expected[asset['name']])
                and asset['size'] == len(expected[asset['name']]), 'Release asset digest/size mismatch: ' + asset['name'])
    if complete:
        require(set(names) == set(expected), 'Release assets incomplete')


def verify_tag(api, tag, source, required=False):
    refs = api.request('git/matching-refs/tags/' + tag)
    matching = [ref for ref in refs if ref['ref'] == 'refs/tags/' + tag]
    require(len(matching) <= 1 and (matching or not required), 'Release tag missing/duplicated')
    if not matching:
        return
    target = matching[0]['object']
    for _ in range(5):
        if target['type'] == 'commit':
            require(target['sha'] == source, 'Release tag targets another source')
            return
        require(target['type'] == 'tag', 'Release tag does not target a commit')
        target = api.request('git/tags/' + target['sha'])['object']
    raise ValueError('Release tag nesting exceeds limit')


def publish(api, declaration, assets):
    metadata = release_metadata(declaration)
    verify_tag(api, metadata['tag_name'], declaration['source'])
    matches = []
    page = 1
    while True:
        releases = api.request(f'releases?per_page=100&page={page}')
        matches.extend(release for release in releases if release['tag_name'] == metadata['tag_name'])
        if len(releases) < 100:
            break
        page += 1
    require(len(matches) <= 1, 'Duplicate matching releases')
    if matches:
        release = matches[0]
        require(all(release.get(key) == value for key, value in metadata.items()), 'Existing release metadata mismatch')
    else:
        # Retain the POST response ID. GET-by-tag cannot reliably find drafts.
        release = api.request('releases', 'POST', {**metadata, 'draft': True})
    release_id = release['id']
    endpoint = f'releases/{release_id}'
    release = api.request(endpoint)
    require(all(release.get(key) == value for key, value in metadata.items()), 'Release metadata changed')
    verify_assets(release['assets'], assets, complete=not release['draft'])
    if release['draft']:
        present = {asset['name'] for asset in release['assets']}
        for name in sorted(assets):
            if name not in present:
                uploaded = api.upload(release_id, name, assets[name])
                verify_assets([uploaded], {name: assets[name]}, complete=True)
        release = api.request(endpoint)
        require(release['draft'] and all(release.get(key) == value for key, value in metadata.items()), 'Draft metadata changed')
        verify_assets(release['assets'], assets, complete=True)
        verify_tag(api, metadata['tag_name'], declaration['source'])
        # This is the only publication action, after every uploaded digest passed.
        api.request(endpoint, 'PATCH', {'draft': False, 'make_latest': 'false'})
    published = api.request(endpoint)
    require(published['draft'] is False and all(published.get(key) == value for key, value in metadata.items()), 'Public release metadata mismatch')
    verify_assets(published['assets'], assets, complete=True)
    verify_tag(api, metadata['tag_name'], declaration['source'], required=True)
    apk = next(asset for asset in published['assets'] if asset['name'] == 'ULADIM.apk')
    return {'release_url': published['html_url'], 'apk_url': apk['browser_download_url'],
            'sha256': declaration['apk_sha256'], 'source': declaration['source'], 'release_id': release_id}


def main():
    declaration = json.loads(Path(DECLARATION).read_text())
    require(choose_mode(declaration, os.environ) == 'publish-retained', 'Retained publication context/diff rejected')
    api = GitHub()
    repo = api.request('')
    require(repo['private'] is False and repo['id'] == declaration['repository_id'], 'Expected existing public repository')
    for pin in [*declaration['required_runs'], declaration['signed_run']]:
        verify_run(api.request(f"actions/runs/{pin['id']}"), pin, declaration)
    for key in ('apk_artifact', 'upgrade_artifact'):
        pin = declaration[key]
        verify_artifact(api.request(f"actions/artifacts/{pin['id']}"), pin, declaration)
    assets = prepare_assets(declaration, api.download(declaration['apk_artifact']['id']),
                            api.download(declaration['upgrade_artifact']['id']))
    receipt = publish(api, declaration, assets)
    Path('native-release-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write(f"Published retained APK{declaration['version_code']} from `{declaration['source']}`.\n\n"
                         f"[Release]({receipt['release_url']}) · [APK]({receipt['apk_url']})\n\n"
                         f"SHA256: `{receipt['sha256']}`\n")


if __name__ == '__main__':
    main()
