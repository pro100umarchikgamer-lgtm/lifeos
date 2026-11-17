import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/sync/contracts.dart';
import 'package:lifeos/sync/controller.dart';
import 'package:lifeos/ui/family.dart';

import 'google_login_test.dart' show LoginApi;
import 'support/sync_memory.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late PackCatalog catalog;
  setUpAll(() async {
    catalog = await PackCatalog.load();
  });
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  test('a configuration outage does not assert that Google is disabled',
      () async {
    var failed = false;
    final c = FamilyController(MemorySyncStore(),
        apiFactory: (origin) => LoginApi(origin, (path, body) async {
              if (failed) throw const SyncFailure('service_unavailable', 503);
              return {'google_enabled': true};
            }));
    addTearDown(c.dispose);
    c.api = LoginApi('https://api.example.test', (path, body) async => {});
    await c.refreshLoginMethods();
    expect(c.googleAvailable, isTrue);
    failed = true;
    await c.refreshLoginMethods();
    expect(c.googleAvailable, isTrue);
  });

  testWidgets('configuration outage explains Google availability and can retry',
      (tester) async {
    var failed = true;
    var calls = 0;
    final c = FamilyController(MemorySyncStore(),
        apiFactory: (origin) => LoginApi(origin, (path, body) async {
              calls++;
              if (failed) throw const SyncFailure('service_unavailable', 503);
              return {'google_enabled': true};
            }));
    addTearDown(c.dispose);
    c.api = LoginApi('https://api.example.test', (path, body) async => {});
    await tester.pumpWidget(MaterialApp(
        home: FamilyPage(controller: c, pack: catalog.packs['ru']!)));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('retry_login_methods')), findsOneWidget);
    expect(
        find.text(catalog.packs['ru']!.t('family_error_service_unavailable')),
        findsOneWidget);
    failed = false;
    await tester.tap(find.byKey(const Key('retry_login_methods')));
    await tester.pumpAndSettle();
    expect(calls, 2);
    expect(find.byKey(const Key('retry_login_methods')), findsNothing);
    expect(find.text(catalog.packs['ru']!.t('account_google_sign_in')),
        findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
