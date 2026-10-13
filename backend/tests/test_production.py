import io
import unittest
from cryptography.fernet import Fernet
from cryptography.exceptions import InvalidTag
from backend.backup import encrypt,decrypt
from backend.config import Settings
from backend.mail import message
from backend.production import decode_json
from backend.service import Failure

class ProductionUnitTests(unittest.TestCase):
    def env(self):return {'DATABASE_URL':'postgresql://example/db','EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),'RATE_LIMIT_KEY':'r'*48,'SMTP_HOST':'smtp.example.test','EMAIL_FROM':'LifeOS <noreply@example.test>'}
    def test_configuration_fails_closed_without_keys_or_tls(self):
        with self.assertRaises(ValueError):Settings.load({})
        env=self.env();env['SMTP_TLS']='none'
        with self.assertRaises(ValueError):Settings.load(env)
        env['SMTP_HOST']='127.0.0.1';self.assertEqual(Settings.load(env).smtp_tls,'none')
    def test_duplicate_json_fields_cannot_override_identity(self):
        with self.assertRaises(Failure):decode_json(b'{"workspace_id":"one","workspace_id":"two"}')
    def test_authenticated_backup_roundtrip_and_tampering(self):
        password=b'test-only-backup-key-not-production-1234';plain=b'financial history\x00'+b'0123456789'*150000
        encoded=io.BytesIO();encrypt(io.BytesIO(plain),encoded,password)
        self.assertNotIn(b'financial history',encoded.getvalue())
        output=io.BytesIO();decrypt(io.BytesIO(encoded.getvalue()),output,password);self.assertEqual(output.getvalue(),plain)
        modified=bytearray(encoded.getvalue());modified[100]^=1
        with self.assertRaises(InvalidTag):decrypt(io.BytesIO(modified),io.BytesIO(),password)
        with self.assertRaises(InvalidTag):decrypt(io.BytesIO(encoded.getvalue()),io.BytesIO(),b'wrong-password-that-is-long-enough-for-test')
    def test_mail_has_purpose_and_stable_message_id(self):
        settings=Settings.load(self.env());email=message(settings,'test-job',{'email':'one@example.test','code':'synthetic-code','purpose':'recovery'})
        self.assertIn('восстановление',str(email['Subject']));self.assertEqual(email['Message-ID'],'<test-job@lifeos-mail>')
