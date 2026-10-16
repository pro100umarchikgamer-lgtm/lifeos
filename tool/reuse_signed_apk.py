"""Retain the single CI112 APK while repairing release acceptance automation."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

SOURCE = 'f8632cdd5cf4dad40f0163a44183016d23121abd'
APK_SHA = '0594d97502523901e9d8b7d6b0ceb5ec995f7379b66faabd886f8f75ea58908e'
CERT = '5fa37e4abf1ec90d5787bd0d7dc4cf0b3f49022172f9d25e91f4d8a76702a96e'
APP_INPUTS = ['lib', 'assets', 'backend', 'tool/native', 'tool/prepare_platforms.sh', 'tool/ci_signing.sh', 'pubspec.yaml', 'pubspec.lock', 'docs/ANDROID_TEST_CERT.sha256']

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('build/app/outputs/flutter-apk/app-release.apk'))
    args = parser.parse_args()
    subprocess.run(['git', 'diff', '--exit-code', SOURCE, 'HEAD', '--', *APP_INPUTS], check=True)
    target = Path(os.environ['RUNNER_TEMP']) / 'uladim-single-apk'
    target.mkdir(exist_ok=True)
    subprocess.run(['gh', 'run', 'download', '38883235405', '--repo', 'pro100umarchikgamer-lgtm/lifeos', '--name', 'lifeos-release-test-apk-' + SOURCE, '--dir', str(target)], check=True)
    apk = target / 'build/app/outputs/flutter-apk/app-release.apk'
    assert hashlib.sha256(apk.read_bytes()).hexdigest() == APK_SHA, 'Retained APK bytes changed'
    identity = dict(line.split('=', 1) for line in (target/'apk-identity.txt').read_text().splitlines())
    assert identity['commit'] == SOURCE and identity['versionCode'] == '112001'
    assert identity['applicationId'] == 'app.lifeos.lifeos' and identity['certificateSHA256'] == CERT
    assert identity['apiOrigin'] == 'https://api.getuladim.space'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(apk, args.output)
    for name in ['apk-identity.txt', 'apk-certificate.txt', 'apk-manifest.txt']:
        shutil.copyfile(target/name, name)
    print('Reused exact signed APK112001; application inputs unchanged from ' + SOURCE)
    print('APK SHA256=' + APK_SHA)

if __name__ == '__main__':
    main()
