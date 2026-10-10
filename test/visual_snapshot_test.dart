import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/action_engine.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/app.dart';

// Sample records exist only in this visual test; production always reads its store.
class SnapshotStore implements ActionStore {
  SnapshotStore(this.items, this.mode);
  final List<Record> items;
  final String mode;
  @override
  Future<String> apply(AppAction action) async => 'test-only';
  @override
  Future<List<Record>> records() async => items;
  @override
  Future<Map<String, String>> settings() async => {'language': 'ru', 'currency': 'RUB', 'theme': mode};
  @override
  Future<void> setSetting(String key, String value) async {}
  @override
  Future<void> close() async {}
}

List<Record> sampleRecords() {
  final now = DateTime.now();
  final currency = Currency.fromCode('RUB');
  Record money(String id, EntryKind kind, int amount, int day) => Record(
    id: id, kind: kind, text: kind == EntryKind.income ? 'Зарплата' : 'Покупка продуктов',
    createdAt: now, amountMinor: amount, currency: currency,
    date: dateOnly(DateTime(now.year, now.month, day)));
  return [
    Record(id: 'n1', kind: EntryKind.note, text: 'Идеи на выходные\nИсследовать новый маршрут в парке, посмотреть выставку и собрать список мест.', createdAt: now),
    Record(id: 't1', kind: EntryKind.task, text: 'Разобрать почту', createdAt: now),
    Record(id: 't2', kind: EntryKind.task, text: 'Купить продукты', createdAt: now),
    Record(id: 't3', kind: EntryKind.task, text: 'Подготовить документы', createdAt: now),
    money('i1', EntryKind.income, 12000000, 2),
    money('e1', EntryKind.expense, 4835000, 4),
    money('e2', EntryKind.expense, 150000, 8),
    money('i2', EntryKind.income, 250000, 11),
    money('e3', EntryKind.expense, 85000, 15),
  ];
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late PackCatalog catalog;
  setUpAll(() async {
    // Flutter's test font lacks Cyrillic. Keep this font in test/ only and
    // register it as Roboto, the family used by the Material test theme.
    final bytes = await File('test/fonts/NotoSans-Regular.ttf').readAsBytes();
    final loader = FontLoader('Roboto')..addFont(Future<ByteData>.value(ByteData.sublistView(bytes)));
    await loader.load();
    catalog = await PackCatalog.load();
  });

  for (final mode in ['light', 'dark']) {
    for (final populated in [true, false]) {
      for (final width in [390.0, 320.0]) {
        final state = populated ? 'populated' : 'empty';
        final name = 'home_${state}_${mode}_${width.toInt()}';
        testWidgets(name, (tester) async {
          tester.view.devicePixelRatio = 1;
          tester.view.physicalSize = Size(width, 844);
          addTearDown(tester.view.resetDevicePixelRatio);
          addTearDown(tester.view.resetPhysicalSize);
          final controller = AppController(SnapshotStore(populated ? sampleRecords() : [], mode), catalog, 'ru');
          await controller.load();
          await tester.pumpWidget(LifeOSApp(controller: controller));
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);
          if (populated) {
            expect(find.text('122500.00 RUB'), findsOneWidget);
          } else {
            expect(find.text(controller.pack.t('welcome_title')), findsOneWidget);
          }
          await expectLater(find.byType(MaterialApp), matchesGoldenFile('goldens/$name.png'));
          expect(tester.takeException(), isNull);
        });
      }
    }
  }

  for (final page in ['finances', 'plans', 'notes', 'profile', 'quick_expense']) {
    testWidgets('page_$page', (tester) async {
      tester.view.devicePixelRatio = 1;
      tester.view.physicalSize = const Size(390, 844);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.view.resetPhysicalSize);
      final controller = AppController(SnapshotStore(sampleRecords(), 'light'), catalog, 'ru');
      await controller.load();
      await tester.pumpWidget(LifeOSApp(controller: controller));
      await tester.pumpAndSettle();
      if (page == 'finances' || page == 'plans' || page == 'notes') {
        await tester.tap(find.byKey(Key('nav_${page == 'notes' ? 'modules' : page}')));
        await tester.pumpAndSettle();
      }
      if (page == 'notes') {
        await tester.tap(find.text(controller.pack.t('recent_notes')).last);
        await tester.pumpAndSettle();
        await tester.tap(find.text('Идеи на выходные').first);
        await tester.pumpAndSettle();
      }
      if (page == 'profile') {
        await tester.tap(find.byKey(const Key('profile_button')));
        await tester.pumpAndSettle();
      }
      if (page == 'quick_expense') {
        await tester.tap(find.byKey(const Key('quick_expense')));
        await tester.pumpAndSettle();
      }
      expect(tester.takeException(), isNull);
      await expectLater(find.byType(MaterialApp), matchesGoldenFile('goldens/page_$page.png'));
      expect(tester.takeException(), isNull);
    });
  }
  testWidgets('home_populated_light_tablet', (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(900, 900);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    final controller = AppController(SnapshotStore(sampleRecords(), 'light'), catalog, 'ru');
    await controller.load();
    await tester.pumpWidget(LifeOSApp(controller: controller));
    await tester.pumpAndSettle();
    expect(find.byType(NavigationRail), findsOneWidget);
    expect(tester.takeException(), isNull);
    await expectLater(find.byType(MaterialApp), matchesGoldenFile('goldens/home_populated_light_tablet.png'));
    expect(tester.takeException(), isNull);
  });
}
