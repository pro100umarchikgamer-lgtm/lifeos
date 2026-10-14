import 'package:timezone/data/latest.dart' as timezone;
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/action_engine.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/app.dart';
import 'package:lifeos/domain/appearance.dart';
import 'package:lifeos/ui/appearance_editor.dart';
import 'package:lifeos/ui/quick_add.dart';
import 'package:lifeos/ui/calendar.dart';
import 'package:lifeos/ui/notices.dart';
import 'package:lifeos/ui/selection.dart';

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
    Record(id: 'n1', kind: EntryKind.note, text: 'Идеи на выходные\nИсследовать новый маршрут в парке, посмотреть выставку и собрать список мест. Бюджет: 100 ₽.', createdAt: now),
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
  timezone.initializeTimeZones();
  TestWidgetsFlutterBinding.ensureInitialized();
  late PackCatalog catalog;
  setUpAll(() async {
    // Flutter's test font lacks Cyrillic. Keep this font in test/ only and
    // register it as Roboto, the family used by the Material test theme.
    final bytes = await File('test/fonts/NotoSans-Regular.ttf').readAsBytes();
    final loader = FontLoader('Roboto')..addFont(Future<ByteData>.value(ByteData.sublistView(bytes)));
    await loader.load();
    final iconLoader = FontLoader('MaterialIcons')
      ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
    await iconLoader.load();
    catalog = await PackCatalog.load();
  });

  for (final screen in ['pistachio', 'sky_dark', 'appearance', 'note_editor', 'task_entry', 'event_entry']) {
    testWidgets('premium_$screen', (tester) async {
      tester.view.devicePixelRatio = 1; tester.view.physicalSize = const Size(320,844);
      addTearDown(tester.view.resetDevicePixelRatio); addTearDown(tester.view.resetPhysicalSize);
      final c = AppController(SnapshotStore(sampleRecords(), 'light'), catalog, 'ru'); await c.load();
      if (screen == 'pistachio') c.preferences['appearance_v1'] = const Appearance(palette:'pistachio',mode:'light').encode();
      if (screen == 'sky_dark') c.preferences['appearance_v1'] = const Appearance(palette:'sky',mode:'dark',surface:'outlined').encode();
      await tester.pumpWidget(LifeOSApp(controller:c)); await tester.pumpAndSettle();
      final context = tester.element(find.byType(HomeShell));
      if (screen == 'appearance') Navigator.push<void>(context, MaterialPageRoute(builder: (_) => AppearanceEditor(controller:c)));
      if (screen == 'note_editor') showEntryEditor(context,c,EntryKind.note,record:sampleRecords().first);
      if (screen == 'task_entry') showEntryEditor(context,c,EntryKind.task);
      if (screen == 'event_entry') {
        showModalBottomSheet<void>(context: context,isScrollControlled:true,useSafeArea:true,
          builder: (_) => EventEditor(controller:c,date:c.now));
      }
      await tester.pumpAndSettle(); expect(tester.takeException(),isNull);
      await expectLater(find.byType(MaterialApp),matchesGoldenFile('goldens/premium_$screen.png'));
      expect(tester.takeException(),isNull);
    });
  }
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
            // Today starts with tasks and a collapsed, accurate net balance.
            expect(find.text('71 800 ₽'), findsOneWidget);
            expect(find.byKey(const Key('financial_period')), findsNothing);
            expect(tester.getRect(find.text('Разобрать почту')).bottom, lessThan(600));
            final summary = find.byKey(const Key('home_financial_summary'));
            await tester.ensureVisible(summary);
            await tester.pumpAndSettle();
            await tester.tap(summary.hitTestable());
            await tester.pumpAndSettle();
            // Preserve the original income assertion and also verify expenses.
            expect(find.text('122 500 ₽'), findsOneWidget);
            expect(find.text('50 700 ₽'), findsOneWidget);
            expect(find.byKey(const Key('financial_period')), findsOneWidget);
            await tester.tap(summary.hitTestable());
            await tester.pumpAndSettle();
            expect(find.text('122 500 ₽'), findsNothing);
            expect(find.byKey(const Key('financial_period')), findsNothing);
            final scrollable = find.descendant(
              of: find.byKey(const Key('today')),
              matching: find.byType(Scrollable),
            ).first;
            tester.state<ScrollableState>(scrollable).position.jumpTo(0);
            await tester.pumpAndSettle();
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
        await tester.scrollUntilVisible(find.text(controller.pack.t('recent_notes')).hitTestable(),200,scrollable:find.descendant(of:find.byKey(const Key('modules')),matching:find.byType(Scrollable)).first); expect(find.text(controller.pack.t('recent_notes')).hitTestable(), findsOneWidget); await tester.tap(find.text(controller.pack.t('recent_notes')).hitTestable());
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
      if (page == 'notes') {
        expect(find.textContaining('100 ₽'), findsOneWidget);
      }
      expect(tester.takeException(), isNull);
      await expectLater(find.byType(MaterialApp), matchesGoldenFile('goldens/page_$page.png'));
      expect(tester.takeException(), isNull);
    });
  }
  for (final mode in ['light', 'dark']) {
    for (final width in [320.0, 390.0]) {
      if (mode == 'light' && width == 390) continue; // Existing page_finances.
      final name = 'finances_${mode}_${width.toInt()}';
      testWidgets(name, (tester) async {
        tester.view.devicePixelRatio = 1;
        tester.view.physicalSize = Size(width, 844);
        addTearDown(tester.view.resetDevicePixelRatio);
        addTearDown(tester.view.resetPhysicalSize);
        final controller = AppController(SnapshotStore(sampleRecords(), mode), catalog, 'ru');
        await controller.load();
        await tester.pumpWidget(LifeOSApp(controller: controller));
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(const Key('nav_finances')));
        await tester.pumpAndSettle();
        expect(find.text('122 500 ₽'), findsOneWidget);
        expect(tester.takeException(), isNull);
        final button = tester.getRect(find.byKey(const Key('add_button')));
        final bar = tester.getRect(find.byType(BottomAppBar));
        expect(button.top, greaterThanOrEqualTo(bar.top));
        expect(button.bottom, lessThanOrEqualTo(bar.bottom));
        await expectLater(find.byType(MaterialApp), matchesGoldenFile('goldens/$name.png'));
        expect(tester.takeException(), isNull);
      });
    }
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
  for (final mode in ['light','dark']) {
    for (final screen in ['home_430','home_scrolled_320','home_scrolled_390','language','repeat','undo','undo_keyboard']) {
      testWidgets('polish_${screen}_$mode', (tester) async {
        tester.view.devicePixelRatio = 1;
        tester.view.physicalSize = Size(screen == 'home_430' ? 430 : screen == 'home_scrolled_390' ? 390 : 320,844);
        addTearDown(tester.view.resetDevicePixelRatio); addTearDown(tester.view.resetPhysicalSize);
        final c = AppController(SnapshotStore(sampleRecords(),mode),catalog,'ru'); await c.load();
        await tester.pumpWidget(LifeOSApp(controller:c)); await tester.pumpAndSettle();
        if (screen.startsWith('home_scrolled')) {
          await tester.drag(find.byType(ListView).first,const Offset(0,-550)); await tester.pumpAndSettle();
        }
        if (screen == 'language') {
          await tester.tap(find.byKey(const Key('profile_button'))); await tester.pumpAndSettle();
          await tester.tap(find.byKey(const Key('settings_0'))); await tester.pumpAndSettle();
          await tester.tap(find.byType(LifeSelect<String>).first); await tester.pumpAndSettle();
        }
        if (screen == 'repeat') {
          final context = tester.element(find.byType(HomeShell));
          showEntryEditor(context,c,EntryKind.task); await tester.pumpAndSettle();
          await tester.tap(find.text(c.pack.t('tomorrow'))); await tester.pumpAndSettle();
          await tester.scrollUntilVisible(find.text(c.pack.t('repeat')).first,150, scrollable: find.descendant(of: find.byType(BottomSheet).last, matching: find.byType(Scrollable)).first); await tester.pumpAndSettle();
          await tester.tap(find.text(c.pack.t('repeat')).first); await tester.pumpAndSettle();
          await tester.ensureVisible(find.byType(LifeSelect<RepeatRule>)); await tester.pumpAndSettle();
          await tester.tap(find.byType(LifeSelect<RepeatRule>)); await tester.pumpAndSettle();
        }
        if (screen.startsWith('undo')) {
          if (screen == 'undo_keyboard') {
            tester.view.viewInsets = const FakeViewPadding(bottom:300); addTearDown(tester.view.resetViewInsets);
            tester.view.padding = const FakeViewPadding(bottom:24); addTearDown(tester.view.resetPadding);
          }
          LifeNoticeScope.of(tester.element(find.byType(HomeShell))).show(c.pack.t('deleted'),
            undoLabel:c.pack.t('undo'), undo:() async {});
          await tester.pump(); await tester.pump(const Duration(milliseconds:300));
          expect(find.byType(SnackBar),findsOneWidget);
          if (screen == 'undo_keyboard') expect(tester.getRect(find.byType(SnackBar)).bottom,lessThanOrEqualTo(544));
        }
        expect(tester.takeException(),isNull);
        await expectLater(find.byType(MaterialApp),matchesGoldenFile('goldens/polish_${screen}_$mode.png'));
        expect(tester.takeException(),isNull);
        await tester.pumpWidget(const SizedBox()); await tester.pumpAndSettle();
      });
    }
  }

}
