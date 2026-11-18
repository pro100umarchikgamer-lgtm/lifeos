"""Verification against actual v2/v3-signed Android packages."""
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

from backend.native_download import CERTIFICATE
from backend.service import Failure


FIXTURES = Path(__file__).resolve().parents[2] / 'tool' / 'testdata' / 'android-releases'


def verifier(test_case, *, retained=False):
    from backend.apk_verifier import ApkVerifier
    def tool(name):
        value = os.getenv('ULADIM_TEST_' + name.upper()) or shutil.which(name)
        if value:
            return value
        root = Path(os.getenv('ANDROID_HOME', '/missing')) / 'build-tools'
        versions = sorted(root.glob('*/' + name), reverse=True)
        if versions:
            return str(versions[0])
        if os.getenv('ULADIM_REQUIRE_APK_TOOLS') == '1':
            test_case.fail('Required CI Android build-tool missing: ' + name)
        test_case.skipTest('Android build-tools required for real APK verification: ' + name)
    return ApkVerifier(apksigner=tool('apksigner'), aapt=tool('aapt'),
                       certificate=CERTIFICATE if retained else (FIXTURES / 'certificate.sha256').read_text().strip())


class ApkVerifierTests(unittest.TestCase):
    def setUp(self):
        # Skip before entering a subTest/exception assertion on a machine
        # without the optional Android SDK. CI explicitly requires the tools.
        self.fixture_verifier = verifier(self)
        self.production_verifier = verifier(self, retained=True)

    def verify(self, name, retained=False):
        with open(FIXTURES / name, 'rb') as stream:
            return (self.production_verifier if retained else self.fixture_verifier).verify(stream.fileno())

    def test_valid_signature_and_identity_come_from_binary(self):
        self.assertEqual(self.verify('first.apk'), {'version_code': 400002, 'version_name': '1.2.3',
            'package_name': 'app.lifeos.lifeos', 'certificate_sha256': (FIXTURES / 'certificate.sha256').read_text().strip()})

    def test_production_signer_and_package_are_independent_requirements(self):
        for name, retained, expected in [('first.apk', True, 'apk_signer'), ('wrong-package.apk', False, 'apk_package')]:
            with self.subTest(name=name), self.assertRaises(Failure) as failure:
                self.verify(name, retained=retained)
            self.assertEqual(failure.exception.code, expected)

    def test_tampered_and_unsigned_apks_fail_signature_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            tampered = Path(directory) / 'tampered.apk'
            data = bytearray((FIXTURES / 'first.apk').read_bytes())
            data[160] ^= 1
            tampered.write_bytes(data)
            unsigned = Path(directory) / 'unsigned.apk'
            with zipfile.ZipFile(FIXTURES / 'first.apk') as src, zipfile.ZipFile(unsigned, 'w') as dest:
                dest.writestr('AndroidManifest.xml', src.read('AndroidManifest.xml'))
            for filename in (tampered, unsigned):
                with self.subTest(filename=filename.name), filename.open('rb') as stream, self.assertRaises(Failure) as failure:
                    self.fixture_verifier.verify(stream.fileno())
                self.assertEqual(failure.exception.code, 'apk_signature')
