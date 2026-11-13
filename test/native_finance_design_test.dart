import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/financial_period.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/design.dart';
import 'package:lifeos/ui/finance_foundation.dart';
import 'package:lifeos/ui/financial_overview.dart';
import 'package:lifeos/ui/quick_add.dart';
import 'package:lifeos/ui/wealth.dart';

import 'widget_test.dart' show UIStore;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  timezone.initializeTimeZones();
  late PackCatalog catalog;
  setUpAll(() async {
    final bytes = await File('test/fonts/NotoSans-Regular.ttf').readAsBytes();
    await (FontLoader('Roboto')
          ..addFont(Future.value(ByteData.sublistView(bytes))))
        .load();
    await (FontLoader('MaterialIcons')
          ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf')))
        .load();
    catalog = await PackCatalog.load();
    // Root integrates this shared UI key into every shipping language pack.
    catalog.packs['ru']!.strings
        .putIfAbsent('advanced_options', () => 'Дополнительные параметры');
  });
  for (final dark in [false, true]) {
    for (final compact in [false, true]) {
      testWidgets(
          'finance hierarchy ${dark ? 'dark' : 'light'} ${compact ? '320 large' : '390'}',
          (tester) async {
        final width = compact ? 320.0 : 390.0;
        tester.view.devicePixelRatio = 1;
        tester.view.physicalSize = Size(width, 844);
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final store = UIStore();
        final c = AppController(store, catalog, 'ru');
        await c.load();
        c.preferences['currency'] = 'RUB';
        Future<void> show(Widget screen) async {
          await tester.pumpWidget(MaterialApp(
            debugShowCheckedModeBanner: false,
            locale: const Locale('ru'),
            supportedLocales: const [Locale('ru')],
            localizationsDelegates: GlobalMaterialLocalizations.delegates,
            theme: lifeTheme(dark ? Brightness.dark : Brightness.light),
            builder: (context, child) => MediaQuery(
                data: MediaQuery.of(context)
                    .copyWith(textScaler: TextScaler.linear(compact ? 1.5 : 1)),
                child: child!),
            home: Scaffold(body: SafeArea(child: screen)),
          ));
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);
        }

        Future<void> shot(String name) async {
          expect(tester.takeException(), isNull);
          if (Platform.environment['ULADIM_NATIVE_FINANCE_SCREENSHOTS'] ==
              '1') {
            await expectLater(
                find.byType(MaterialApp),
                matchesGoldenFile(
                    'native_finance_evidence/${name}_${dark ? 'dark' : 'light'}_${width.toInt()}.png'));
          }
        }

        Widget overview() => SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: FinancialOverview(
                controller: c,
                period:
                    FinancialPeriod(DateTime(2026, 11), DateTime(2026, 11, 30)),
                currency: 'RUB',
                onCurrency: (_) {},
                onPeriod: () {},
                onRecord: (_) {},
                onAdd: (_) {}));
        await show(overview());
        expect(find.text(c.pack.t('empty_money')), findsOneWidget);
        expect(find.byType(Slider), findsNothing);
        expect(find.text(c.pack.t('insight_categories')), findsNothing);
        await shot('overview_empty');
        c.records = [
          for (var i = 0; i < 30; i++)
            Record(
                id: 'expense-$i',
                kind: EntryKind.expense,
                text: 'Продукты и покупки на неделю',
                createdAt: DateTime(2026, 11, 13),
                amountMinor: 124500 + i,
                currency: const Currency('RUB', 2),
                date: '2026-11-13',
                categoryId: 'food'),
        ];
        c.offline = {
          OfflineTable.accounts: [
            {
              'id': 'card',
              'name': 'Основная карта',
              'currency': 'RUB',
              'kind': 'card',
              'opening_minor': 9000000,
              'archived': 0,
              'revision': 1
            },
          ],
          OfflineTable.categories: [
            {'id': 'food', 'name': 'Продукты', 'revision': 1},
          ]
        };
        await show(overview());
        expect(find.byKey(const Key('cashflow_chart')), findsOneWidget);
        expect(find.text(c.pack.t('empty_money')), findsNothing);
        await shot('overview_populated');
        await show(FinanceEditor(controller: c, table: OfflineTable.budgets));
        expect(find.text(c.pack.t('rollover')), findsNothing);
        expect(
            tester
                .widget<FilledButton>(find.byKey(const Key('save')))
                .onPressed,
            isNull);
        final amount = find.byWidgetPredicate((w) =>
            w is TextField &&
            w.decoration?.labelText == c.pack.t('budget_limit'));
        expect(tester.widget<TextField>(amount).controller!.text, isEmpty);
        await shot('budget');
        await tester.ensureVisible(find.byKey(const Key('budget_advanced')));
        await tester.tap(find.byKey(const Key('budget_advanced')));
        await tester.pumpAndSettle();
        expect(find.text(c.pack.t('rollover')), findsOneWidget);
        await show(QuickAdd(controller: c, kind: EntryKind.expense));
        expect(
            tester
                .widget<TextField>(find.byKey(const Key('amount')))
                .controller!
                .text,
            isEmpty);
        await shot('expense');
        await tester.enterText(find.byKey(const Key('amount')), '12500,75');
        await tester.pumpAndSettle();
        expect(
            tester
                .widget<FilledButton>(find.byKey(const Key('save')))
                .onPressed,
            isNotNull);
        await shot('expense_filled');
        await show(WealthEditor(controller: c, table: OfflineTable.goals));
        final goalAmount = find.byWidgetPredicate((w) =>
            w is TextField &&
            w.decoration?.labelText == c.pack.t('target_amount'));
        expect(tester.widget<TextField>(goalAmount).controller!.text, isEmpty);
        expect(find.byType(TextField),
            findsNWidgets(2)); // Name + amount, currency is a bounded selector.
        expect(
            tester
                .widget<FilledButton>(find.byKey(const Key('save')))
                .onPressed,
            isNull);
        await shot('goal');
        expect(store.actions, isEmpty);
        await tester.pumpWidget(const SizedBox.shrink());
        c.dispose();
      });
    }
  }
}
