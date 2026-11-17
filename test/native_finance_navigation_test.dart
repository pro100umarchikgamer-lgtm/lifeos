import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/app.dart';
import 'package:lifeos/ui/finance_foundation.dart';
import 'package:timezone/data/latest.dart' as timezone;

import 'widget_test.dart' show UIStore, openNativeSections;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late PackCatalog catalog;
  setUpAll(() async {
    timezone.initializeTimeZones();
    catalog = await PackCatalog.load();
  });
  testWidgets('accounts and financial plans are reached through Finance',
      (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(390, 844);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final c = AppController(UIStore(), catalog, 'ru');
    await c.load();
    await tester.pumpWidget(LifeOSApp(controller: c));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('nav_finances')));
    await tester.pumpAndSettle();
    final accounts = find.byKey(const Key('finance_accounts'));
    await tester.ensureVisible(accounts);
    await tester.tap(accounts);
    await tester.pumpAndSettle();
    expect(find.byType(FinanceFoundation), findsOneWidget);
    Navigator.of(tester.element(find.byType(FinanceFoundation))).pop();
    await tester.pumpAndSettle();
    await openNativeSections(tester);
    expect(find.text(c.pack.t('financial_foundation')), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
