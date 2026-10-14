import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/app.dart';
import 'package:lifeos/ui/quick_add.dart';
import 'package:lifeos/ui/selection.dart';

import 'widget_test.dart' show UIStore;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late PackCatalog catalog;
  setUpAll(() async {
    catalog = await PackCatalog.load();
  });
  for (final width in [320.0, 390.0, 430.0]) {
    testWidgets(
      'money header, validation and save survive keyboard at $width',
      (tester) async {
        tester.view.devicePixelRatio = 1;
        tester.view.physicalSize = Size(width, 844);
        addTearDown(tester.view.resetDevicePixelRatio);
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetViewInsets);
        final store = UIStore();
        final c = AppController(store, catalog, 'ru');
        await c.load();
        await tester.pumpWidget(LifeOSApp(controller: c));
        await tester.pumpAndSettle();
        final context = tester.element(find.byType(HomeShell));
        showEntryEditor(context, c, EntryKind.expense);
        await tester.pumpAndSettle();
        expect(
          tester.widget<FilledButton>(find.byKey(const Key('save'))).onPressed,
          isNull,
        );
        tester.view.viewInsets = const FakeViewPadding(bottom: 330);
        await tester.pumpAndSettle();
        final header = find.text(c.pack.t('create_expense'));
        expect(tester.getRect(header).top, greaterThanOrEqualTo(0));
        expect(tester.getRect(header).bottom, lessThan(514));
        expect(
          tester.getRect(find.byKey(const Key('save'))).bottom,
          lessThanOrEqualTo(514),
        );
        await tester.enterText(find.byKey(const Key('amount')), '12,50');
        await tester.pump();
        expect(
          tester.widget<FilledButton>(find.byKey(const Key('save'))).onPressed,
          isNotNull,
        );
        await tester.tap(find.byKey(const Key('save')));
        await tester.pumpAndSettle();
        expect((store.actions.single as CreateMoney).amount, '12,50');
        expect(tester.takeException(), isNull);
      },
    );
    testWidgets(
      'tasks precede compact money and module grid aligns at $width',
      (tester) async {
        tester.view.devicePixelRatio = 1;
        tester.view.physicalSize = Size(width, 844);
        addTearDown(tester.view.resetDevicePixelRatio);
        addTearDown(tester.view.resetPhysicalSize);
        final store = UIStore()
          ..items = [
            Record(
              id: 'today-task',
              kind: EntryKind.task,
              text: 'Prepare for class',
              createdAt: DateTime.now(),
            ),
            Record(
              id: 'income',
              kind: EntryKind.income,
              text: '',
              createdAt: DateTime.now(),
              amountMinor: 10000,
              currency: const Currency('RUB', 2),
              date: dateOnly(DateTime.now()),
            ),
          ];
        final c = AppController(store, catalog, 'ru');
        await c.load();
        await tester.pumpWidget(LifeOSApp(controller: c));
        await tester.pumpAndSettle();
        expect(
          tester.getRect(find.text('Prepare for class')).bottom,
          lessThan(600),
        );
        expect(find.byKey(const Key('financial_period')), findsNothing);
        await tester.tap(find.byKey(const Key('nav_modules')));
        await tester.pumpAndSettle();
        final cards = [
          for (var i = 0; i < 4; i++)
            tester.getRect(find.byKey(ValueKey('module_card_$i'))),
        ];
        expect(cards[0].height, closeTo(cards[1].height, .1));
        expect(cards[0].top, closeTo(cards[1].top, .1));
        expect(cards[2].top, closeTo(cards[3].top, .1));
        expect(tester.takeException(), isNull);
      },
    );
  }
  testWidgets('currency selection is bounded, searchable and keyboard-safe', (
    tester,
  ) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(320, 844);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetViewInsets);
    String value = 'RUB';
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: LifeSelect<String>(
            label: 'Валюта',
            value: value,
            choices: {
              'RUB': 'Российский рубль · RUB',
              'USD': 'Доллар США · USD',
            },
            dialog: true,
            searchLabel: 'Поиск',
            onChanged: (v) => value = v,
          ),
        ),
      ),
    );
    await tester.tap(find.byType(LifeSelect<String>));
    await tester.pumpAndSettle();
    expect(find.byType(BottomSheet), findsNothing);
    expect(tester.getSize(find.byType(Dialog)).height, lessThanOrEqualTo(480));
    await tester.enterText(find.byKey(const Key('selection_search')), 'USD');
    tester.view.viewInsets = const FakeViewPadding(bottom: 330);
    await tester.pumpAndSettle();
    final choice = find.byKey(const ValueKey('choice_USD'));
    expect(tester.getRect(choice).bottom, lessThanOrEqualTo(514));
    await tester.tap(choice);
    await tester.pumpAndSettle();
    expect(value, 'USD');
    expect(tester.takeException(), isNull);
  });
}
