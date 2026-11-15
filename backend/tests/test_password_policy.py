import unittest
import hashlib
from backend.service import Backend, Failure, validate_password
import tempfile
from pathlib import Path
class PasswordPolicy(unittest.TestCase):
    def test_new_password_has_eight_to_256_unicode_codepoints(self):
        validate_password('river731')
        validate_password('Москва42')
        validate_password('Rivera٧٣')
        validate_password('𐐀bcdefg7')
        longest='Rivera7'+''.join(chr(0x1f600+i) for i in range(249))
        validate_password(longest)
        for value in [None,7,'River!7','𐐀bcdef7',longest+'x']:
            with self.subTest(value=value):
                with self.assertRaises(Failure) as caught:validate_password(value)
                self.assertEqual(caught.exception.code,'password_length')

    def test_long_diverse_passphrase_needs_no_number_or_special_character(self):
        for value in ['Очень-длинная-фраза','synthetic-web-platform-password','sunlit meadow riverbank']:
            with self.subTest(value=value):validate_password(value)
        for value in ['onlyletters','longlettersword','aaaaaaaaaaaaaabb','1'*200,'riverwind       ']:
            with self.subTest(value=value):
                with self.assertRaises(Failure) as caught:validate_password(value)
                self.assertEqual(caught.exception.code,'password_weak')

    def test_common_sequences_and_repeated_patterns_are_rejected(self):
        for value in ['12345678','password','aaaaaaaa','qwerty123','Password1!','welcome2026!','test12345','abcd1234','4321dcba','Qwer1234','zxcv1234','абвг1234','a1b2c3d4','ab12ab12','leafleaf9','abcabc123','abcdefghijklmnop']:
            with self.subTest(value=value):
                with self.assertRaises(Failure) as caught:validate_password(value)
                self.assertEqual(caught.exception.code,'password_weak')

    def test_existing_short_common_and_numeric_passwords_still_log_in(self):
        with tempfile.TemporaryDirectory() as folder:
            codes={};b=Backend(Path(folder)/'test.db',deliver=lambda e,c:codes.update({e:c}))
            b.register('legacy@example.test','Rivera73')
            for password in ['River!7','password','12345678']:
                with self.subTest(password=password):
                    with b.connect() as db:
                        row=db.execute('SELECT salt FROM users WHERE email=?',('legacy@example.test',)).fetchone()
                        encoded=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(row['salt']),600000).hex()
                        db.execute('UPDATE users SET password_hash=? WHERE email=?',(encoded,'legacy@example.test'))
                    self.assertIn('token',b.login('legacy@example.test',password))

    def test_registration_cannot_bypass_new_password_policy(self):
        with tempfile.TemporaryDirectory() as folder:
            b=Backend(Path(folder)/'test.db',deliver=lambda e,c:None)
            for index,(value,code) in enumerate([('River!7','password_length'),('abcd1234','password_weak')]):
                with self.subTest(value=value):
                    with self.assertRaises(Failure) as caught:b.register(f'new{index}@example.test',value)
                    self.assertEqual(caught.exception.code,code)
            with b.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],0)

    def test_change_and_reset_cannot_bypass_new_password_policy(self):
        for method in ['change','reset']:
            for value,code in [('Ocean!7','password_length'),('abcd1234','password_weak')]:
                with self.subTest(method=method,value=value),tempfile.TemporaryDirectory() as folder:
                    codes={};b=Backend(Path(folder)/'test.db',deliver=lambda e,c:codes.update({e:c}))
                    r=b.register('new@example.test','Rivera73');actor=b.authenticate(r['token']);b.verify(actor,codes['new@example.test'])
                    if method=='change':
                        with self.assertRaises(Failure) as caught:b.password(actor,'Rivera73',value)
                    else:
                        b.recover('new@example.test')
                        with self.assertRaises(Failure) as caught:b.reset_password('new@example.test',codes['new@example.test'],value)
                    self.assertEqual(caught.exception.code,code)

    def test_registration_login_reset_and_change_share_policy(self):
        with tempfile.TemporaryDirectory() as folder:
            codes={};b=Backend(Path(folder)/'test.db',deliver=lambda e,c:codes.update({e:c}))
            r=b.register('policy@example.test','Rivera73');actor=b.authenticate(r['token']);b.verify(actor,codes['policy@example.test'])
            self.assertIn('token',b.login('policy@example.test','Rivera73'))
            actor=b.authenticate(r['token'])
            with self.assertRaises(Failure) as caught:b.password(actor,'Rivera73','password')
            self.assertEqual(caught.exception.code,'password_weak')
            b.password(actor,'Rivera73','Ocean973')
            with self.assertRaises(Failure):b.authenticate(r['token'])
            self.assertIn('token',b.login('policy@example.test','Ocean973'))
            b.recover('policy@example.test')
            with self.assertRaises(Failure) as caught:b.reset_password('policy@example.test',codes['policy@example.test'],'12345678')
            self.assertEqual(caught.exception.code,'password_weak')
            b.reset_password('policy@example.test',codes['policy@example.test'],'Forest79')
            self.assertIn('token',b.login('policy@example.test','Forest79'))
