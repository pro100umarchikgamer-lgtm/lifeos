import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/sync/controller.dart';
import 'package:lifeos/ui/family.dart';
import 'package:lifeos/ui/app.dart';
import 'widget_test.dart' show openNativeProfile;
import 'controller_test.dart' show CountingStore, FakeNative;
import 'google_login_test.dart' show LoginApi, GoogleChooser;
import 'support/sync_memory.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  timezone.initializeTimeZones();
  late PackCatalog catalog;
  setUpAll(() async => catalog = await PackCatalog.load());
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  testWidgets(
      'Google-only password shortcut opens actionable email recovery without old password',
      (tester) async {
    final calls = <String>[];
    final f = FamilyController(MemorySyncStore(),
        apiFactory: (origin) => LoginApi(origin, (path, body) async {
              calls.add(path);
              return {};
            }))
      ..api = LoginApi('https://test.example', (path, body) async {
        calls.add(path);
        if (path == '/v1/account/google') return {'has_password': false};
        return {'google_enabled': false};
      })
      ..account = {
        'user_id': 'google-user',
        'verified': true,
        'email': 'test@example.test'
      };
    addTearDown(f.dispose);
    await tester.pumpWidget(MaterialApp(
        home: FamilyPage(controller: f, pack: catalog.packs['en']!)));
    await tester.pumpAndSettle();
    await tester
        .tap(find.text(catalog.packs['en']!.t('account_password_title')));
    await tester.pumpAndSettle();
    expect(
        find.text(catalog.packs['en']!.t('family_old_password')), findsNothing);
    expect(find.text(catalog.packs['en']!.t('account_google_password_first')),
        findsOneWidget);
    expect(find.text(catalog.packs['en']!.t('family_recovery_send')),
        findsOneWidget);
    expect(calls, contains('/v1/account/google'));
    await tester.tap(find.text(catalog.packs['en']!.t('family_recovery_send')));
    await tester.pumpAndSettle();
    expect(calls, contains('/v1/auth/recovery'));
    expect(f.error, isNull);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  for (final mode in ['success', 'cancel', 'mfa', 'unverified']) {
    final cancel = mode == 'cancel', landed = mode == 'success';
    testWidgets(
        'explicit Google $mode ${landed ? 'lands on existing personal account' : 'does not redirect'}',
        (tester) async {
      final c =
          AppController(CountingStore(), catalog, 'en', platform: FakeNative());
      await c.load();
      final f = FamilyController(MemorySyncStore(),
          native: GoogleChooser(cancel: cancel),
          apiFactory: (endpoint) => LoginApi(endpoint, (path, body) async {
                if (path == '/v1/auth/google/config') {
                  return {'google_enabled': true};
                }
                if (path == '/v1/auth/google/start') {
                  return {
                    'challenge': 'g' * 43,
                    'nonce': 'n' * 43,
                    'client_id': 'synthetic-client.apps.googleusercontent.com'
                  };
                }
                if (path == '/v1/auth/google/finish' && mode == 'mfa') {
                  return {'mfa_required': true, 'challenge': 'c' * 43};
                }
                if (path == '/v1/auth/google/finish') {
                  return {
                    'user_id': 'test-user',
                    'email': 'test@example.test',
                    'verified': mode != 'unverified',
                    'device_id': 'test-device',
                    'token': 'a' * 43,
                    'refresh_token': 'r' * 43
                  };
                }
                if (path == '/v1/me') {
                  return {
                    'user_id': 'test-user',
                    'verified': mode != 'unverified'
                  };
                }
                if (path == '/v1/spaces') {
                  return {
                    'spaces': [
                      {
                        'id': 'personal',
                        'kind': 'personal',
                        'role': 'owner',
                        'name': 'My account'
                      },
                    ]
                  };
                }
                if (path.startsWith('/v1/roster')) {
                  return {
                    'space': {
                      'id': 'personal',
                      'kind': 'personal',
                      'role': 'owner'
                    },
                    'profiles': [],
                    'members': []
                  };
                }
                if (path.startsWith('/v1/sync/pull')) {
                  return {
                    'protocol': 2,
                    'epoch': 'test',
                    'cursor': 0,
                    'reset': true,
                    'more': false,
                    'records': []
                  };
                }
                return {'messages': [], 'items': [], 'unread': 0};
              }));
      f.api = LoginApi('https://test.example',
          (path, body) async => {'google_enabled': true});
      c.family = f;
      var disposed = false;
      addTearDown(() {
        if (!disposed) c.dispose();
      });
      await tester.pumpWidget(LifeOSApp(controller: c));
      await tester.pumpAndSettle();
      await openNativeProfile(tester);
      await tester.tap(find.text(c.pack.t('account_manage')));

      await tester.pumpAndSettle();
      await tester.tap(find.text(c.pack.t('account_google_sign_in')));
      await tester.pumpAndSettle();
      expect(c.preferences['active_scope'] == 'family', landed);
      expect(f.loginMfaRequired, mode == 'mfa');
      expect(f.workspace, landed ? 'personal' : null);
      expect(find.byType(FamilyPage), landed ? findsNothing : findsOneWidget);
      if (landed) expect(find.byKey(const Key('today_page')), findsOneWidget);
      expect(c.records, isEmpty);
      expect(f.error, isNull);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      c.dispose();
      disposed = true;
    });
  }
}
