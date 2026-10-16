import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/sync/contracts.dart';
import 'package:lifeos/sync/controller.dart';
import 'package:lifeos/ui/account_center.dart';
import 'package:lifeos/ui/design.dart';
import 'support/sync_memory.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late PackCatalog catalog;
  setUpAll(() async {catalog = await PackCatalog.load();});
  for (final width in [320.0, 390.0, 430.0]) {
    for (final brightness in Brightness.values) {
      testWidgets('account navigation all locales $width $brightness large text', (tester) async {
        tester.view.devicePixelRatio = 1;
        tester.view.physicalSize = Size(width, 844);
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final c = FamilyController(MemorySyncStore())..account = {'email': 'fixture@example.test'};
        addTearDown(c.dispose);
        for (final pack in catalog.packs.values) {
          await tester.pumpWidget(MaterialApp(theme: lifeTheme(brightness),
            builder: (context, child) => MediaQuery(data: MediaQuery.of(context).copyWith(textScaler: const TextScaler.linear(1.4)), child: child!),
            home: AccountCenter(controller: c, pack: pack)));
          await tester.pumpAndSettle();
          expect(find.text(pack.t('account_access')), findsOneWidget);
          expect(find.text(pack.t('account_privacy')), findsOneWidget);
          expect(tester.takeException(), isNull, reason: pack.tag);
          await tester.pumpWidget(const SizedBox());
        }
      });
    }
  }
  testWidgets('device revoke needs password and sends exactly the selected ID', (tester) async {
    final calls = <Json>[];
    final c = FamilyController(MemorySyncStore())..account = {'email': 'fixture@example.test'};
    addTearDown(c.dispose);
    final pack = catalog.packs['en']!;
    Future<Json> request(String path, {Json? body}) async {
      if (body != null) calls.add(body);
      return {'devices': [{'id': 'fixture-device', 'label': 'Test Android', 'last_seen_at': 1700000000, 'revoked_at': calls.isEmpty ? 0 : 1}]};
    }
    await tester.pumpWidget(MaterialApp(home: AccountCenter(controller: c, pack: pack, request: request)));
    await tester.tap(find.text(pack.t('account_devices')));
    await tester.pumpAndSettle();
    await tester.tap(find.text(pack.t('account_revoke')));
    await tester.pumpAndSettle();
    expect(calls, isEmpty);
    await tester.enterText(find.byType(TextField), 'synthetic-password');
    await tester.tap(find.text(pack.t('confirm')));
    await tester.pumpAndSettle();
    expect(calls, [{'device_id': 'fixture-device', 'password': 'synthetic-password'}]);
    expect(find.text(pack.t('account_revoke')), findsNothing);
    await tester.pump(const Duration(seconds: 1));
  });
}
