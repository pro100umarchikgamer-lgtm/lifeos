"""Bad signing inputs must fail before invoking Flutter and leave no private file."""
import base64
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class SigningSafetyTests(unittest.TestCase):
    def check_rejected(self, secret):
        with tempfile.TemporaryDirectory(prefix='lifeos-signing-test-') as directory:
            root = Path(directory)
            marker = root / 'flutter-called'
            flutter = root / 'flutter'
            flutter.write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 99\n')
            flutter.chmod(0o700)
            env = dict(os.environ, RUNNER_TEMP=directory, PATH=f'{directory}:{os.environ["PATH"]}')
            env.pop('LIFEOS_TEST_KEYSTORE_BASE64', None)
            if secret is not None:
                env['LIFEOS_TEST_KEYSTORE_BASE64'] = secret
            result = subprocess.run(['bash', 'tool/ci_signing.sh'], cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists(), 'No APK may be built with unverified signing input')
            self.assertFalse((root / 'lifeos-signing/debug.keystore').exists())

    def test_missing_secret_never_builds(self):
        self.check_rejected(None)

    def test_invalid_base64_is_cleaned_and_never_builds(self):
        self.check_rejected('not-valid-base64!')

    @unittest.skipUnless(shutil.which('keytool'), 'JDK keytool is unavailable')
    def test_invalid_keystore_is_cleaned_and_never_builds(self):
        self.check_rejected(base64.b64encode(b'disposable invalid fixture').decode())
