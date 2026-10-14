import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/finance_foundation.dart';
import 'package:lifeos/ui/selection.dart';

import 'widget_test.dart' show UIStore;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late PackCatalog catalog;
  setUpAll(() async {
    catalog = await PackCatalog.load();
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
      expect(find.text('Кошелёк'), findsOneWidget);
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
}
