"""Retain the single CI134 APK while repairing release acceptance automation."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

SOURCE = '6acbde34f499d7c740322687416abc3aa542f9ac'
APK_SHA = 'a7f93159a138e464227fa2259d9c54c67063a280708e8dafbd95c27ec3ab8356'
CERT = '5fa37e4abf1ec90d5787bd0d7dc4cf0b3f49022172f9d25e91f4d8a76702a96e'
ACCEPTANCE_ONLY = {'.github/workflows/stage1.yml', 'tool/check_release_upgrade.py',
                   'tool/reuse_signed_apk.py', 'tool/tests/test_release_upgrade.py'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('build/app/outputs/flutter-apk/app-release.apk'))
    args = parser.parse_args()
    changed=set(subprocess.check_output(['git','diff','--name-only',SOURCE,'HEAD']).decode().splitlines())
    assert changed <= ACCEPTANCE_ONLY, 'APK reuse refused: application or other non-acceptance inputs changed'
    target = Path(os.environ['RUNNER_TEMP']) / 'uladim-single-apk'
    target.mkdir(exist_ok=True)
    subprocess.run(['gh', 'run', 'download', '38984254821', '--repo', 'pro100umarchikgamer-lgtm/lifeos', '--name', 'lifeos-release-test-apk-' + SOURCE, '--dir', str(target)], check=True)
    apk = target / 'build/app/outputs/flutter-apk/app-release.apk'
    assert hashlib.sha256(apk.read_bytes()).hexdigest() == APK_SHA, 'Retained APK bytes changed'
    identity = dict(line.split('=', 1) for line in (target/'apk-identity.txt').read_text().splitlines())
    assert identity['commit'] == SOURCE and identity['versionCode'] == '134001'
    assert identity['applicationId'] == 'app.lifeos.lifeos' and identity['certificateSHA256'] == CERT
    assert identity['apiOrigin'] == 'https://api.getuladim.space'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(apk, args.output)
    for name in ['apk-identity.txt', 'apk-certificate.txt', 'apk-manifest.txt']:
        shutil.copyfile(target/name, name)
    print('Reused exact signed APK134001; application inputs unchanged from ' + SOURCE)
    print('APK SHA256=' + APK_SHA)

if __name__ == '__main__':
    main()
