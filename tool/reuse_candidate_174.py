"""Retry acceptance of the immutable APK174001; never sign or compile another APK."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

SOURCE = 'dd07b8d0d14eb52eab9c84a8a3a644e9a8124253'
RUN = '42898055354'
APK_SHA = '77dd9a039286c46240e9b542e47024cf1c5aadcd1c3915a605bd629d29b150cc'
CERT = '5fa37e4abf1ec90d5787bd0d7dc4cf0b3f49022172f9d25e91f4d8a76702a96e'
ACCEPTANCE_ONLY = {
    '.github/workflows/stage1.yml', 'tool/check_release_upgrade.py',
    'tool/reuse_candidate_174.py', 'tool/tests/test_candidate_reuse.py',
    'tool/tests/test_platform_privacy.py', 'tool/tests/test_release_policy.py',
}


def verify_candidate(apk, identity):
    """Require the retained APK bytes and original application/signing identity."""
    assert hashlib.sha256(apk.read_bytes()).hexdigest() == APK_SHA, 'Candidate APK bytes changed'
    assert identity['commit'] == SOURCE and identity['versionCode'] == '174001'
    assert identity['applicationId'] == 'app.lifeos.lifeos'
    assert identity['certificateSHA256'] == CERT
    assert identity['apiOrigin'] == 'https://api.getuladim.space'


def verify_changes(changed):
    """Refuse reuse when any application or backend input changed since signing."""
    assert set(changed) <= ACCEPTANCE_ONLY, 'Candidate reuse refused: application inputs changed'


def main():
    """Download only the pinned signed artifact and verify it before installation."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    changed = subprocess.check_output(['git', 'diff', '--name-only', SOURCE, 'HEAD']).decode().splitlines()
    verify_changes(changed)
    target = Path(os.environ['RUNNER_TEMP']) / 'uladim-signed-174'
    target.mkdir(exist_ok=True)
    subprocess.run(['gh', 'run', 'download', RUN, '--repo', 'pro100umarchikgamer-lgtm/lifeos',
                    '--name', 'lifeos-release-test-apk-' + SOURCE, '--dir', str(target)], check=True)
    apk = target / 'build/app/outputs/flutter-apk/app-release.apk'
    identity = dict(line.split('=', 1) for line in (target / 'apk-identity.txt').read_text().splitlines())
    verify_candidate(apk, identity)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(apk, args.output)
    print('Reused exact signed APK174001; SHA256=' + APK_SHA)


if __name__ == '__main__':
    main()
