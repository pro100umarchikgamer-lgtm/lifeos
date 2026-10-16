import 'package:flutter/material.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/finance_foundation.dart';
import 'package:lifeos/ui/financial_overview.dart';
import 'package:lifeos/domain/financial_period.dart';
import 'package:lifeos/ui/design.dart';
import 'package:lifeos/ui/selection.dart';
import 'package:lifeos/ui/money_format.dart';

import 'widget_test.dart' show UIStore;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  timezone.initializeTimeZones();
  late PackCatalog catalog;
  setUpAll(() async {
    catalog = await PackCatalog.load();
  });
  test('category shares follow selected decimal formatting', () {
    expect(formatShare(BigInt.from(4), BigInt.from(5), locale: 'ru'), contains('80,0'));
    expect(formatShare(BigInt.from(4), BigInt.from(5), locale: 'en'), contains('80.0'));
    expect(formatShare(BigInt.zero, BigInt.zero, locale: 'de'), contains('0,0'));
    final huge = BigInt.parse('9999999999999999999999999999999999');
    expect(formatShare(huge, huge, locale: 'ru'), contains('100,0'));
  });
  testWidgets(
    'account search retains history and budget progress uses real spending',
    (tester) async {
      final store = UIStore();
      final c = AppController(store, catalog, 'ru');
      await c.load();
      c.offline = {
        OfflineTable.accounts: [
          {
            'id': 'cash',
            'name': 'Кошелёк',
            'currency': 'RUB',
            'kind': 'cash',
            'opening_minor': 10000,
            'archived': 0,
            'revision': 1,
          },
          {
            'id': 'old',
            'name': 'Старый счёт',
            'currency': 'RUB',
            'kind': 'cash',
            'opening_minor': 2000,
            'archived': 1,
            'revision': 1,
          },
        ],
        OfflineTable.budgets: [
          {
            'id': 'budget',
            'name': 'Покупки',
            'currency': 'RUB',
            'limit_minor': 5000,
            'period': 'month',
            'rollover': 'none',
            'start_on': dateOnly(DateTime(c.now.year, c.now.month)),
            'category_id': null,
            'revision': 1,
          },
        ],
      };
      c.records = [
        Record(
          id: 'expense',
          kind: EntryKind.expense,
          text: '',
          createdAt: c.now,
          amountMinor: 1000,
          currency: const Currency('RUB', 2),
          date: dateOnly(c.now),
        ),
      ];
      await tester.pumpWidget(
        MaterialApp(home: FinanceFoundation(controller: c)),
      );
      await tester.pumpAndSettle();
      expect(find.text('Старый счёт'), findsOneWidget);
      await tester.tap(find.byKey(const Key('finance_archive_filter')));
      await tester.pumpAndSettle();
      expect(find.text('Старый счёт'), findsNothing);
      expect(c.offline[OfflineTable.accounts]!.length, 2);
      await tester.tap(find.byTooltip(c.pack.t('search')));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('finance_search')),
        'Кошелёк',
      );
      await tester.pumpAndSettle();
      expect(
        find.byWidgetPredicate((w) => w is Text && w.data == 'Кошелёк'),
        findsOneWidget,
      );
      await tester.tap(find.byType(LifeSelect<OfflineTable>));
      await tester.pumpAndSettle();
      await tester.tap(find.text(c.pack.t('module_budgets')));
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<LinearProgressIndicator>(
              find.byType(LinearProgressIndicator),
            )
            .value,
        closeTo(.2, .00001),
      );
      expect(store.actions, isEmpty);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets(
    'account creation disables invalid saves and permits a signed opening balance',
    (tester) async {
      final store = UIStore();
      final c = AppController(store, catalog, 'ru');
      await c.load();
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: FinanceEditor(controller: c, table: OfflineTable.accounts),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final save = find.byKey(const Key('save'));
      expect(tester.widget<FilledButton>(save).onPressed, isNull);
      await tester.enterText(find.byType(TextField).first, 'Карта');
      await tester.pump();
      expect(tester.widget<FilledButton>(save).onPressed, isNotNull);
      final money = find.byWidgetPredicate(
        (w) =>
            w is TextField &&
            w.decoration?.labelText == c.pack.t('opening_balance'),
      );
      await tester.enterText(money, 'abc');
      await tester.pump();
      expect(tester.widget<FilledButton>(save).onPressed, isNull);
      await tester.enterText(money, '-12,50');
      await tester.pump();
      expect(tester.widget<FilledButton>(save).onPressed, isNotNull);
      expect(store.actions, isEmpty);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets(
    'financial chart drilldown keeps currencies isolated and categories open the underlying record',
    (tester) async {
      tester.view.devicePixelRatio = 1;
      tester.view.physicalSize = const Size(320, 844);
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final c = AppController(UIStore(), catalog, 'ru');
      await c.load();
      c.preferences['currency'] = 'RUB';
      c.records = [
        Record(
          id: 'salary',
          kind: EntryKind.income,
          text: 'Salary',
          createdAt: DateTime(2026),
          amountMinor: 50000,
          currency: const Currency('RUB', 2),
          date: '2026-10-01',
          accountId: 'cash',
        ),
        Record(
          id: 'shop',
          kind: EntryKind.expense,
          text: 'Weekly shop',
          createdAt: DateTime(2026),
          amountMinor: 1250,
          currency: const Currency('RUB', 2),
          date: '2026-10-15',
          accountId: 'cash',
          categoryId: 'food',
        ),
        Record(
          id: 'usd',
          kind: EntryKind.expense,
          text: 'Other currency',
          createdAt: DateTime(2026),
          amountMinor: 99999,
          currency: const Currency('USD', 2),
          date: '2026-10-15',
        ),
      ];
      c.offline = {
        OfflineTable.accounts: [
          {'id': 'cash', 'currency': 'RUB', 'opening_minor': 10000},
        ],
        OfflineTable.categories: [
          {'id': 'food', 'name': 'Food'},
        ],
      };
      String? opened;
      await tester.pumpWidget(
        MaterialApp(
          theme: lifeTheme(Brightness.light),
          home: Scaffold(
            body: SingleChildScrollView(
              child: FinancialOverview(
                controller: c,
                period: FinancialPeriod(
                  DateTime(2026, 10),
                  DateTime(2026, 10, 31),
                ),
                currency: 'RUB',
                onCurrency: (_) {},
                onPeriod: () {},
                onAdd: (_) {},
                onRecord: (r) => opened = r.id,
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(
        tester.widget<Text>(find.byKey(const Key('insight_balance'))).data,
        '587,50 ₽',
      );
      await tester.ensureVisible(find.text(c.pack.t('insight_month')));
      await tester.tap(find.text(c.pack.t('insight_month')));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.byKey(const Key('cashflow_chart')));
      await tester.tap(find.byKey(const Key('cashflow_chart')));
      await tester.pumpAndSettle();
      expect(find.textContaining('Доход: 500 ₽'), findsOneWidget);
      await tester.ensureVisible(find.text('Food'));
      await tester.tap(find.text('Food'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Weekly shop'));
      await tester.tap(find.text('Weekly shop'));
      expect(opened, 'shop');
      expect(find.text('Other currency'), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      c.dispose();
    },
  );
}
