import 'package:flutter/services.dart';
import 'package:flutter/material.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/family.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/platform/native_bridge.dart';
import 'package:lifeos/sync/api.dart';
import 'package:lifeos/sync/contracts.dart';
import 'package:lifeos/sync/controller.dart';
import 'support/sync_memory.dart';

class LoginApi extends FamilyApi {
  LoginApi(super.endpoint, this.respond);
  final Future<Json> Function(String, Json?) respond;
  @override
  Future<Json> request(String path, {Json? body}) => respond(path, body);
}

class GoogleChooser extends NativeBridge {
  GoogleChooser({this.cancel = false});
  final bool cancel;
  @override
  Future<String> googleSignIn(String clientId, String nonce) async {
    expect(clientId, 'synthetic-client.apps.googleusercontent.com');
    expect(nonce, 'n' * 43);
    if (cancel) throw PlatformException(code: 'google_cancelled');
    return 'synthetic-provider-token-never-persist';
  }
}

Json signedIn() => {
      'user_id': 'synthetic-user',
      'device_id': 'synthetic-device',
      'token': 'a' * 43,
      'refresh_token': 'r' * 43,
      'verified': false
    };

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late PackCatalog catalog;
  setUpAll(() async {
    catalog = await PackCatalog.load();
  });
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  test('password is sent only in primary step; MFA challenge is memory-only',
      () async {
    final calls = <Map<String, Object?>>[];
    final c = FamilyController(MemorySyncStore(),
        apiFactory: (origin) => LoginApi(origin, (path, body) async {
              calls.add({'path': path, 'body': body});
              if (path.endsWith('/start')) {
                return {'mfa_required': true, 'challenge': 'c' * 43};
              }
              expect(path, '/v1/auth/login/finish');
              expect(body, {'challenge': 'c' * 43, 'code': '123456'});
              return signedIn();
            }));
    addTearDown(c.dispose);
    await c.signIn('https://api.example.test', 'synthetic@example.test',
        'primary-password');
    expect(c.loginMfaRequired, isTrue);
    expect(c.account, isNull);
    final stored = await c.secure.readAll();
    expect(stored.values.join(), isNot(contains('primary-password')));
    expect(stored.values.join(), isNot(contains('c' * 43)));
    await c.signIn('https://api.example.test', 'synthetic@example.test', '',
        mfaCode: '123456');
    expect(c.error, isNull);
    expect(c.loginMfaRequired, isFalse);
    expect(c.account?['user_id'], 'synthetic-user');
    expect(calls.length, 2);
    expect(calls.last.toString(), isNot(contains('primary-password')));
  });

  test('Google hands off to ULADIM MFA and never persists the Google token',
      () async {
    final c = FamilyController(MemorySyncStore(),
        native: GoogleChooser(),
        apiFactory: (origin) => LoginApi(origin, (path, body) async {
              if (path == '/v1/auth/google/start') {
                return {
                  'challenge': 'g' * 43,
                  'nonce': 'n' * 43,
                  'client_id': 'synthetic-client.apps.googleusercontent.com'
                };
              }
              if (path == '/v1/auth/google/finish') {
                expect(body, {
                  'challenge': 'g' * 43,
                  'id_token': 'synthetic-provider-token-never-persist'
                });
                return {'mfa_required': true, 'challenge': 'm' * 43};
              }
              expect(path, '/v1/auth/login/finish');
              expect(body, {'challenge': 'm' * 43, 'code': '654321'});
              return signedIn();
            }));
    addTearDown(c.dispose);
    await c.signInGoogle('https://api.example.test');
    expect(c.loginMfaRequired, isTrue);
    expect(c.account, isNull);
    expect((await c.secure.readAll()).values.join(),
        isNot(contains('synthetic-provider-token')));
    await c.signIn('https://api.example.test', '', '', mfaCode: '654321');
    expect(c.error, isNull);
    expect(c.account?['user_id'], 'synthetic-user');
    expect((await c.secure.readAll()).values.join(),
        isNot(contains('synthetic-provider-token')));
  });

  test('Google cancellation preserves the previous account and local outbox',
      () async {
    final store = MemorySyncStore();
    final c = FamilyController(store,
        native: GoogleChooser(cancel: true),
        apiFactory: (origin) => LoginApi(
            origin,
            (path, body) async => {
                  'challenge': 'g' * 43,
                  'nonce': 'n' * 43,
                  'client_id': 'synthetic-client.apps.googleusercontent.com'
                }));
    addTearDown(c.dispose);
    c.account = {'user_id': 'retained-user', 'verified': true};
    c.pending = [
      {'id': 'retained-operation'}
    ];
    await c.signInGoogle('https://api.example.test');
    expect(c.error, isNull);
    expect(c.account?['user_id'], 'retained-user');
    expect(c.pending.single['id'], 'retained-operation');
    expect(c.loginMfaRequired, isFalse);
  });
  testWidgets('Android MFA is a separate screen with no primary password field',
      (tester) async {
    final pack = catalog.packs['ru']!;
    final c = FamilyController(MemorySyncStore(),
        apiFactory: (origin) =>
            LoginApi(origin, (path, body) async => {'google_enabled': false}));
    addTearDown(c.dispose);
    c.api = LoginApi('https://api.example.test',
        (path, body) async => {'google_enabled': false});
    c.loginMfaRequired = true;
    await tester
        .pumpWidget(MaterialApp(home: FamilyPage(controller: c, pack: pack)));
    await tester.pumpAndSettle();
    expect(find.text(pack.t('account_mfa')), findsOneWidget);
    expect(find.text(pack.t('family_email')), findsNothing);
    expect(find.byType(TextField), findsOneWidget);
    final code = tester.widget<TextField>(find.byType(TextField));
    expect(code.obscureText, isFalse);
    expect(tester.takeException(), isNull);
  });
}
