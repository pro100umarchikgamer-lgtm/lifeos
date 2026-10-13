import unittest
from tool.validate_api_origin import validate

class ApiOriginTests(unittest.TestCase):
    def test_explicit_https_origin(self):
        for origin in ['https://sync.example.test','https://sync.example.test:8443/']:
            self.assertEqual(validate(origin),origin)
    def test_plaintext_credentials_paths_and_metadata_are_refused(self):
        for origin in ['http://sync.example.test','https://user:secret@example.test',
            'https://example.test/path','https://example.test/?token=value','https://example.test/#fragment',
            'https://169.254.169.254','https://metadata.google.internal','https://[fd00:ec2::254]',
            'https://example.test:99999','https://example.test\n']:
            with self.subTest(origin=origin),self.assertRaises(ValueError):validate(origin)
