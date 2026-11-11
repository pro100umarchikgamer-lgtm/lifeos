"""Acceptance retries must never substitute changed application inputs or APKs."""
from pathlib import Path
import tempfile
import unittest
from tool.reuse_candidate_174 import verify_candidate, verify_changes


class CandidateReuseTests(unittest.TestCase):
    def test_runtime_change_refuses_acceptance_reuse(self):
        """Frontend, server, dependency and signing edits require a new candidate."""
        for path in ['lib/main.dart', 'backend/service.py', 'pubspec.yaml', 'tool/ci_signing.sh']:
            with self.subTest(path=path), self.assertRaises(AssertionError):
                verify_changes(['.github/workflows/stage1.yml', path])

    def test_acceptance_only_change_can_reuse_the_signed_artifact(self):
        """KVM and regression-test repairs do not change installed application bytes."""
        verify_changes(['.github/workflows/stage1.yml', 'tool/tests/test_platform_privacy.py'])

    def test_changed_apk_bytes_are_rejected_before_metadata_is_trusted(self):
        """A certificate report cannot authorize a different APK payload."""
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory) / 'candidate.apk'
            apk.write_bytes(b'synthetic-untrusted-APK')
            with self.assertRaisesRegex(AssertionError, 'Candidate APK bytes changed'):
                verify_candidate(apk, {})

class LauncherDialogTests(unittest.TestCase):
    def dialog(self, title, package='android'):
        """Build a system-dialog fixture without application data."""
        import xml.etree.ElementTree as ET
        return ET.fromstring(f'''<hierarchy><node package="{package}" text="{title}"/><node package="android" resource-id="android:id/aerr_close" enabled="true" bounds="[0,0][100,100]"/></hierarchy>''')

    def test_recognizes_only_emulator_pixel_launcher_anr(self):
        """An unrelated launcher dialog must not obscure the app under test."""
        from tool.check_release_upgrade import launcher_anr_close
        self.assertIsNotNone(launcher_anr_close(self.dialog("Pixel Launcher isn't responding")))

    def test_never_dismisses_uladim_or_other_application_anr(self):
        """Application freezes remain failures rather than being hidden by tests."""
        from tool.check_release_upgrade import launcher_anr_close
        for title in ["ULADIM isn't responding", "Settings isn't responding"]:
            self.assertIsNone(launcher_anr_close(self.dialog(title)))
        self.assertIsNone(launcher_anr_close(self.dialog("Pixel Launcher isn't responding", 'app.lifeos.lifeos')))
