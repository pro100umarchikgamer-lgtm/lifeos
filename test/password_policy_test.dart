import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/sync/api.dart';
import 'package:lifeos/sync/contracts.dart';
import 'package:lifeos/sync/controller.dart';

import 'support/sync_memory.dart';

class PasswordApi extends FamilyApi {
  PasswordApi(super.endpoint, this.respond);
  final Future<Json> Function(String, Json?) respond;
  @override
  Future<Json> request(String path, {Json? body}) => respond(path, body);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  test('registration rejects new weak secrets before transport', () async {
    for (final entry in {
      'River!7': 'password_length',
      '𐐀bcdef7': 'password_length',
      'onlyletters': 'password_weak',
      'riverwind       ': 'password_weak',
      'Password1!': 'password_weak',
      'welcome2026!': 'password_weak',
      'abcd1234': 'password_weak',
      '4321dcba': 'password_weak',
      'Qwer1234': 'password_weak',
      'zxcv1234': 'password_weak',
      'абвг1234': 'password_weak',
      'a1b2c3d4': 'password_weak',
      'ab12ab12': 'password_weak',
      'leafleaf9': 'password_weak',
      'abcdefghijklmnop': 'password_weak',
      'aaaaaaaaaaaaaabb': 'password_weak',
      '1234567890123456': 'password_weak',
    }.entries) {
      var sent = 0;
      final c = FamilyController(MemorySyncStore(),
          apiFactory: (origin) => PasswordApi(origin, (path, body) async {
                sent++;
                return {};
              }));
      await c.signIn('https://api.example.test', 'person@example.test', entry.key,
          register: true);
      expect(c.error, entry.value, reason: entry.key);
      expect(c.pendingRegistrationEmail, isNull);
      expect(sent, 0);
      c.dispose();
    }
  });

  test('registration accepts mixed Unicode or a long diverse passphrase',
      () async {
    for (final password in [
      'river731',
      'Москва42',
      'Rivera٧٣',
      '𐐀bcdefg7',
      'Очень-длинная-фраза',
      'synthetic-web-platform-password',
      'sunlit meadow riverbank',
    ]) {
      final c = FamilyController(MemorySyncStore(),
          apiFactory: (origin) => PasswordApi(origin, (path, body) async {
                expect(path, '/v1/auth/signup');
                expect(body?['password'], password);
                return {};
              }));
      await c.signIn('https://api.example.test', 'person@example.test', password,
          register: true);
      expect(c.error, isNull, reason: password);
      expect(c.pendingRegistrationEmail, 'person@example.test');
      c.dispose();
    }
  });

  test('Unicode codepoint maximum does not count surrogate pairs twice',
      () async {
    final password = 'Rivera7' +
        String.fromCharCodes(List.generate(249, (index) => 0x1f600 + index));
    var sent = 0;
    final c = FamilyController(MemorySyncStore(),
        apiFactory: (origin) => PasswordApi(origin, (path, body) async {
              sent++;
              return {};
            }));
    addTearDown(c.dispose);
    await c.signIn('https://api.example.test', 'person@example.test', password,
        register: true);
    expect(c.error, isNull);
    expect(sent, 1);
    await c.resetPassword(
        'https://api.example.test', 'person@example.test', 'code', '${password}x');
    expect(c.error, 'password_length');
    expect(sent, 1);
  });

  test('recovery checks the new password before transport', () async {
    var sent = 0;
    final c = FamilyController(MemorySyncStore(),
        apiFactory: (origin) => PasswordApi(origin, (path, body) async {
              sent++;
              return {};
            }));
    addTearDown(c.dispose);
    await c.resetPassword(
        'https://api.example.test', 'person@example.test', 'code', 'ab12ab12');
    expect(c.error, 'password_weak');
    expect(sent, 0);
  });

  test('password change rejection preserves the current account', () async {
    var sent = 0;
    final c = FamilyController(MemorySyncStore());
    c.api = PasswordApi('https://api.example.test', (path, body) async {
      sent++;
      return {};
    });
    c.account = {'user_id': 'retained-user', 'verified': false};
    addTearDown(c.dispose);
    await c.password('old', 'River!7');
    expect(c.error, 'password_length');
    expect(c.account?['user_id'], 'retained-user');
    expect(sent, 0);
  });

  test('existing login secrets are sent without applying the new policy',
      () async {
    for (final password in ['River!7', 'password', '12345678']) {
      final c = FamilyController(MemorySyncStore(),
          apiFactory: (origin) => PasswordApi(origin, (path, body) async {
                expect(path, '/v1/auth/login/start');
                expect(body?['password'], password);
                return {'mfa_required': true, 'challenge': 'c' * 43};
              }));
      await c.signIn('https://api.example.test', 'person@example.test', password);
      expect(c.error, isNull);
      expect(c.loginMfaRequired, isTrue);
      c.dispose();
    }
  });
}
