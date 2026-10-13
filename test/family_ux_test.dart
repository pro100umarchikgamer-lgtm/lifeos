import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/domain/family_finance.dart';
import 'package:lifeos/domain/statement_import.dart';
import 'package:lifeos/domain/statement_detection.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/app.dart';
import 'package:lifeos/ui/personal_modules.dart';
import 'package:lifeos/ui/global_search.dart';

import 'widget_test.dart' show UIStore;

class PersistentViewStore extends UIStore {
  final saved = <String, String>{};
  @override
  Future<Map<String, String>> settings() async => {'language': 'ru', ...saved};
  @override
  Future<void> setSetting(String key, String value) async {
    saved[key] = value;
  }
}

void main() {
  timezone.initializeTimeZones();
  TestWidgetsFlutterBinding.ensureInitialized();
  late PackCatalog catalog;
  setUpAll(() async {
    catalog = await PackCatalog.load();
  });
  test('detect safe headers and require manual adjustment for ambiguous slash dates', () {
    final detected = StatementDetection.detect(
      StatementTable.checked([
        ['Назначение', 'Сумма', 'Дата', 'Валюта'],
        ['Кофе', '-12,50', '13.10.2026', 'RUB'],
      ]),
      'USD',
    );
    expect(detected, isNotNull);
    expect(detected!.mapping.date, 2);
    expect(detected.mapping.amount, 1);
    expect(
      detected.mapping.normalize([
        'Кофе',
        '-12,50',
        '13.10.2026',
        'RUB',
      ]).amountMinor,
      1250,
    );
    expect(
      StatementDetection.detect(
        StatementTable.checked([
          ['Date', 'Amount'],
          ['04/05/2026', '-12.50'],
        ]),
        'RUB',
      ),
      isNull,
    );
  });
  test('family budgets count assigned spending and retain negative rollover exactly', () {
    final rows = <Map<String, dynamic>>[
      {
        'id': 'transaction',
        'kind': 'transaction',
        'audience': ['child'],
        'data': {
          'kind': 'expense',
          'amount_minor': 150,
          'currency': 'RUB',
          'date': '2026-10-13',
          'label': 'Books',
          'account_id': null,
        },
      },
      {
        'id': 'other',
        'kind': 'transaction',
        'audience': ['sibling'],
        'data': {
          'kind': 'expense',
          'amount_minor': 9999,
          'currency': 'RUB',
          'date': '2026-10-13',
          'label': 'Other',
          'account_id': null,
        },
      },
    ];
    final budget = {
      'id': 'budget',
      'kind': 'budget',
      'data': {
        'name': 'Allowance',
        'currency': 'RUB',
        'limit_minor': 100,
        'period': 'month',
        'start_on': '2026-10-01',
        'end_on': null,
        'rollover': 'negative',
        'participants': ['child'],
      },
    };
    expect(
      const FamilyFinance().budgetRemaining(
        budget,
        rows,
        DateTime(2026, 10, 14),
      ),
      BigInt.from(-50),
    );
    expect(
      const FamilyFinance().budgetRemaining(
        budget,
        rows,
        DateTime(2026, 11, 1),
      ),
      BigInt.from(50),
    );
  });
  testWidgets('module view persists and search scopes personal records', (
    tester,
  ) async {
    final store = PersistentViewStore(),
        c = AppController(PersistentViewStore(), catalog, 'ru');
    final controller = AppController(store, catalog, 'ru');
    await controller.load();
    await controller.preference('modules_view', 'list');
    await controller.load();
    expect(controller.preferences['modules_view'], 'list');
    await tester.pumpWidget(LifeOSApp(controller: controller));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('nav_modules')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('modules_view_toggle')));
    await tester.pumpAndSettle();
    expect(store.saved['modules_view'], 'grid');
    await tester.tap(find.byTooltip(controller.pack.t('search')));
    await tester.pumpAndSettle();
    expect(find.byType(GlobalSearchPage), findsOneWidget);
    expect(find.byKey(const Key('global_search_input')), findsOneWidget);
    c.dispose();
    controller.dispose();
  });
  testWidgets('activity and sleep controls fit narrow large-text screen', (
    tester,
  ) async {
    final c = AppController(UIStore(), catalog, 'ru');
    await c.load();
    tester.view.physicalSize = const Size(320, 640);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        home: MediaQuery(
          data: const MediaQueryData(
            size: Size(320, 640),
            textScaler: TextScaler.linear(1.8),
          ),
          child: Scaffold(
            resizeToAvoidBottomInset: false,
            body: PersonalModuleEditor(
              controller: c,
              table: OfflineTable.wellness,
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.byKey(const Key('save')), findsOneWidget);
  });
}
