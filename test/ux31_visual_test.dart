import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/app.dart';
import 'package:lifeos/ui/finance_foundation.dart';
import 'package:lifeos/ui/design.dart';
import 'package:lifeos/ui/preference_choices.dart';
import 'package:lifeos/ui/quick_add.dart';
import 'package:lifeos/ui/selection.dart';

import 'visual_snapshot_test.dart' show SnapshotStore;

class LaunchSnapshotStore extends SnapshotStore {
  LaunchSnapshotStore(super.items, super.mode, this.language);
  final String language;
  @override
  Future<Map<String, String>> settings() async => {
    'language': language,
    'currency': 'RUB',
    'theme': mode,
  };
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  timezone.initializeTimeZones();
  late PackCatalog catalog;
  setUpAll(() async {
    for (final entry in {
      'Roboto': 'test/fonts/NotoSans-Regular.ttf',
      'NotoSansGeorgian': 'assets/fonts/NotoSansGeorgian.ttf',
      'NotoSansArmenian': 'assets/fonts/NotoSansArmenian.ttf',
    }.entries) {
      final bytes = await File(entry.value).readAsBytes();
      await (FontLoader(
        entry.key,
      )..addFont(Future.value(ByteData.sublistView(bytes)))).load();
    }
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
    catalog = await PackCatalog.load();
  });
  for (final tag in [
    'en',
    'ru',
    'kk',
    'uz-Latn',
    'uz-Cyrl',
    'uk',
    'de',
    'fr',
    'es',
    'it',
    'pt',
    'ka',
    'az',
    'hy',
    'tg',
    'ky',
  ]) {
    for (final width in [320.0, 390.0, 430.0]) {
      for (final theme in ['light', 'dark']) {
        testWidgets('launch $tag $width $theme', (tester) async {
          tester.view.devicePixelRatio = 1;
          tester.view.physicalSize = Size(width, 844);
          addTearDown(tester.view.resetPhysicalSize);
          addTearDown(tester.view.resetDevicePixelRatio);
          addTearDown(tester.view.resetViewInsets);
          final pack = catalog.packs[tag]!;
          final records = [
            Record(
              id: 'synthetic-task',
              kind: EntryKind.task,
              text: pack.t('example_task'),
              createdAt: DateTime(2026, 10, 14),
            ),
          ];
          final c = AppController(
            LaunchSnapshotStore(records, theme, tag),
            catalog,
            tag,
          );
          await c.load();
          await tester.pumpWidget(LifeOSApp(controller: c));
          await tester.pumpAndSettle();
          final prefix = 'ux31_goldens/${tag}_${theme}_${width.toInt()}';
          Future<void> snapshot(String name) async {
            expect(tester.takeException(), isNull);
            await expectLater(
              find.byType(MaterialApp),
              matchesGoldenFile('${prefix}_$name.png'),
            );
          }

          expect(
            tester.getRect(find.text(pack.t('example_task'))).bottom,
            lessThan(600),
          );
          for (final tab in ['today', 'plans', 'finances', 'modules']) {
            expect(
              tester.getRect(find.byKey(Key('nav_$tab'))).height,
              greaterThanOrEqualTo(48),
            );
          }
          await snapshot('today');
          showEntryEditor(
            tester.element(find.byType(HomeShell)),
            c,
            EntryKind.expense,
          );
          await tester.pumpAndSettle();
          await snapshot('expense');
          expect(
            tester
                .renderObject<RenderParagraph>(
                  find.text(pack.t('label_optional')),
                )
                .didExceedMaxLines,
            isFalse,
          );
          tester.view.viewInsets = const FakeViewPadding(bottom: 330);
          await tester.pumpAndSettle();
          expect(
            tester.getRect(find.text(pack.t('create_expense'))).top,
            greaterThanOrEqualTo(0),
          );
          expect(
            tester.getRect(find.byKey(const Key('save'))).bottom,
            lessThanOrEqualTo(514),
          );
          await snapshot('expense_keyboard');
          Navigator.of(tester.element(find.byKey(const Key('save')))).pop();
          tester.view.viewInsets = const FakeViewPadding();
          await tester.pumpAndSettle();
          showEntryEditor(
            tester.element(find.byType(HomeShell)),
            c,
            EntryKind.income,
          );
          await tester.pumpAndSettle();
          tester.view.viewInsets = const FakeViewPadding(bottom: 330);
          await tester.pumpAndSettle();
          await snapshot('income_keyboard');
          Navigator.of(tester.element(find.byKey(const Key('save')))).pop();
          tester.view.viewInsets = const FakeViewPadding();
          await tester.pumpAndSettle();
          await tester.tap(find.byKey(const Key('nav_modules')));
          await tester.pumpAndSettle();
          await snapshot('modules');
          final context = tester.element(find.byType(HomeShell));
          Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => FinanceFoundation(controller: c),
            ),
          );
          await tester.pumpAndSettle();
          await snapshot('accounts');
          Navigator.of(tester.element(find.byType(FinanceFoundation))).pop();
          await tester.pumpAndSettle();
          c.offline = {
            OfflineTable.accounts: [
              {
                'id': 'demo-cash',
                'name': pack.t('account_cash'),
                'currency': 'RUB',
                'kind': 'cash',
                'opening_minor': 10000,
                'archived': 0,
                'revision': 1,
              },
            ],
            OfflineTable.budgets: [
              {
                'id': 'demo-budget',
                'name': pack.t('purpose_food'),
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
          c.records.add(
            Record(
              id: 'demo-expense',
              kind: EntryKind.expense,
              text: pack.t('purpose_food'),
              createdAt: c.now,
              amountMinor: 1250,
              currency: const Currency('RUB', 2),
              date: dateOnly(c.now),
              accountId: 'demo-cash',
            ),
          );
          Navigator.of(tester.element(find.byType(HomeShell))).push(
            MaterialPageRoute<void>(
              builder: (_) => FinanceFoundation(controller: c),
            ),
          );
          await tester.pumpAndSettle();
          await snapshot('accounts_populated');
          await tester.tap(find.byType(LifeSelect<OfflineTable>));
          await tester.pumpAndSettle();
          await tester.tap(find.text(pack.t('module_budgets')));
          await tester.pumpAndSettle();
          await snapshot('budgets_populated');
          Navigator.of(tester.element(find.byType(FinanceFoundation))).pop();
          await tester.pumpAndSettle();
          await tester.pumpWidget(
            LifeOSApp(
              controller: c,
              builder: (context, child) => MediaQuery(
                data: MediaQuery.of(context)
                    .copyWith(textScaler: const TextScaler.linear(1.8)),
                child: child!,
              ),
            ),
          );
          await tester.pumpAndSettle();
          for (final tab in ['today', 'plans', 'finances', 'modules']) {
            expect(
              tester.getRect(find.byKey(Key('nav_$tab'))).height,
              greaterThanOrEqualTo(48),
            );
          }
          await snapshot('modules_large_text');
          await tester.pumpWidget(
            MaterialApp(
              debugShowCheckedModeBanner: false,
              locale: pack.locale,
              supportedLocales: [pack.locale],
              localizationsDelegates: const [
                MaterialFallbackDelegate(),
                WidgetsFallbackDelegate(),
                CupertinoFallbackDelegate(),
              ],
              theme: lifeTheme(
                theme == 'dark' ? Brightness.dark : Brightness.light,
              ),
              builder: (context, child) => MediaQuery(
                data: MediaQuery.of(context)
                    .copyWith(textScaler: const TextScaler.linear(1.8)),
                child: child!,
              ),
              home: Scaffold(
                body: Center(
                  child: LifeSelect<String>(
                    label: pack.t('currency'),
                    value: 'RUB',
                    choices: currencyChoices(pack),
                    dialog: true,
                    searchLabel: pack.t('search_options'),
                    onChanged: (_) {},
                  ),
                ),
              ),
            ),
          );
          await tester.pumpAndSettle();
          await tester.tap(find.byType(LifeSelect<String>));
          await tester.pumpAndSettle();
          await snapshot('currency_dialog_large_text');
          Navigator.of(tester.element(find.byType(Dialog))).pop();
          await tester.pumpAndSettle();
          await tester.pumpWidget(
            MaterialApp(
              debugShowCheckedModeBanner: false,
              locale: pack.locale,
              supportedLocales: [pack.locale],
              localizationsDelegates: const [
                MaterialFallbackDelegate(),
                WidgetsFallbackDelegate(),
                CupertinoFallbackDelegate(),
              ],
              theme: lifeTheme(
                theme == 'dark' ? Brightness.dark : Brightness.light,
              ),
              home: Scaffold(
                body: Center(
                  child: LifeSelect<String>(
                    key: const Key('format_fixture'),
                    label: pack.t('region'),
                    value: c.region,
                    choices: formatChoices(catalog, c.region),
                    dialog: true,
                    searchLabel: pack.t('search_options'),
                    onChanged: (_) {},
                  ),
                ),
              ),
            ),
          );
          await tester.pumpAndSettle();
          await tester.tap(find.byType(LifeSelect<String>));
          await tester.pumpAndSettle();
          tester.view.viewInsets = const FakeViewPadding(bottom: 330);
          await tester.pumpAndSettle();
          await snapshot('format_dialog_keyboard');
          Navigator.of(tester.element(find.byType(Dialog))).pop();
          tester.view.viewInsets = const FakeViewPadding();
          await tester.pumpAndSettle();
          await tester.pumpWidget(
            LifeOSApp(
              key: const Key('large_money_fixture'),
              controller: c,
              builder: (context, child) => MediaQuery(
                data: MediaQuery.of(context)
                    .copyWith(textScaler: const TextScaler.linear(1.8)),
                child: child!,
              ),
            ),
          );
          await tester.pumpAndSettle();
          await snapshot('today_large_text');
          final allTasks = tester.getRect(find.text(pack.t('all_tasks')));
          expect(allTasks.left, greaterThanOrEqualTo(0));
          expect(allTasks.right, lessThanOrEqualTo(width));
          showEntryEditor(
            tester.element(find.byType(HomeShell)),
            c,
            EntryKind.expense,
          );
          await tester.pumpAndSettle();
          tester.view.viewInsets = const FakeViewPadding(bottom: 330);
          await tester.pumpAndSettle();
          expect(
            tester.getRect(find.text(pack.t('create_expense'))).top,
            greaterThanOrEqualTo(0),
          );
          expect(
            tester.getRect(find.byKey(const Key('save'))).bottom,
            lessThanOrEqualTo(514),
          );
          await snapshot('expense_keyboard_large_text');
          if (tag == 'ky' && width == 320) {
            final heading = pack.t('create_expense');
            final paragraph = tester.renderObject<RenderParagraph>(
              find.text(heading),
            );
            expect(
              paragraph
                  .getBoxesForSelection(
                    TextSelection(
                      baseOffset: 0,
                      extentOffset: heading.indexOf(' '),
                    ),
                  )
                  .length,
              1,
              reason: 'The first word of the money heading must stay whole',
            );
          }
          expect(
            tester
                .renderObject<RenderParagraph>(
                  find.text(pack.t('label_optional')),
                )
                .didExceedMaxLines,
            isFalse,
          );

          expect(tester.takeException(), isNull);
        });
      }
    }
  }
}
