import unittest
from backend.service import Backend, Failure, validate_password
import tempfile
from pathlib import Path
class PasswordPolicy(unittest.TestCase):
    def test_seven_character_policy_and_weak_passwords(self):
        validate_password('River!7')
        validate_password('Очень-длинная-фраза')
        for value,code in [('short!','password_length'),('x'*257,'password_length'),('1234567','password_weak'),('password','password_weak'),('aaaaaaa','password_weak'),('qwerty123','password_weak')]:
            with self.subTest(value=value),self.assertRaises(Failure) as caught:validate_password(value)
            self.assertEqual(caught.exception.code,code)
    def test_registration_login_reset_and_change_share_policy(self):
        with tempfile.TemporaryDirectory() as folder:
            codes={};b=Backend(Path(folder)/'test.db',deliver=lambda e,c:codes.update({e:c}))
            r=b.register('policy@example.test','River!7');actor=b.authenticate(r['token']);b.verify(actor,codes['policy@example.test'])
            self.assertIn('token',b.login('policy@example.test','River!7'))
            actor=b.authenticate(r['token'])
            with self.assertRaises(Failure) as caught:b.password(actor,'River!7','password')
            self.assertEqual(caught.exception.code,'password_weak')
            b.password(actor,'River!7','Ocean!7')
            with self.assertRaises(Failure):b.authenticate(r['token'])
            self.assertIn('token',b.login('policy@example.test','Ocean!7'))
            b.recover('policy@example.test')
            with self.assertRaises(Failure) as caught:b.reset_password('policy@example.test',codes['policy@example.test'],'1234567')
            self.assertEqual(caught.exception.code,'password_weak')
            b.reset_password('policy@example.test',codes['policy@example.test'],'Forest7')
            self.assertIn('token',b.login('policy@example.test','Forest7'))
