"""Server validation is reusable only across explicitly bounded UI changes."""
import unittest

from tool.verify_backend_evidence import verify_runtime_manifest


class BackendEvidenceBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.before = {
            name: {'mode': '100644', 'type': 'blob', 'sha': 'a' * 40}
            for name in ['service.py', 'requirements.txt', 'webassets/app/app.js']
        }

    def changed(self, path, **values):
        return {**self.before, path: {**self.before[path], **values}}

    def test_ui_script_changes_still_require_fresh_ui_not_server_tests(self):
        after = self.changed('webassets/app/app.js', sha='b' * 40)
        self.assertEqual(verify_runtime_manifest(self.before, after),
                         ['webassets/app/app.js'])

    def test_server_or_dependency_change_forces_full_validation(self):
        for path in ['service.py', 'requirements.txt']:
            with self.subTest(path=path), self.assertRaises(AssertionError):
                verify_runtime_manifest(self.before,
                                        self.changed(path, sha='b' * 40))

    def test_new_server_file_cannot_be_hidden_by_the_ui_exception(self):
        with self.assertRaises(AssertionError):
            verify_runtime_manifest(self.before,
                                    {**self.before, 'new.py': self.before['service.py']})

    def test_ui_symlink_cannot_reuse_server_validation(self):
        with self.assertRaises(AssertionError):
            verify_runtime_manifest(self.before,
                                    self.changed('webassets/app/app.js', mode='120000'))


if __name__ == '__main__':
    unittest.main()
