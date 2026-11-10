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
