import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/app.dart';
import 'package:lifeos/ui/calendar.dart';
import 'widget_test.dart' show UIStore;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  timezone.initializeTimeZones();
  late PackCatalog catalog;
  setUpAll(() async {
    final font = await File('test/fonts/NotoSans-Regular.ttf').readAsBytes();
    await (FontLoader('Roboto')
          ..addFont(Future.value(ByteData.sublistView(font))))
        .load();
    await (FontLoader('MaterialIcons')
          ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf')))
        .load();
    catalog = await PackCatalog.load();
  });
  testWidgets('completed repeat never appears checked and upcoming on Today',
      (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(390, 900);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    final now = DateTime.now();
    final store = UIStore()
      ..items = [
        Record(
            id: 'repeat',
            kind: EntryKind.task,
            text: 'Повторяющаяся задача',
            createdAt: now)
      ];
    final c = AppController(store, catalog, 'ru');
    await c.load();
    final yesterday = DateTime(c.now.year, c.now.month, c.now.day - 1);
    final entry = CalendarEntry(
        id: 'repeat-calendar',
        title: 'Повторяющаяся задача',
        taskId: 'repeat',
        schedule: ScheduleSpec(
            localStart: '${dateOnly(yesterday)}T09:00:00',
            timezone: c.deviceZone,
            repeat: RepeatRule.daily));
    c.calendar = [entry];
    final due =
        c.calendarEngine.completionOccurrence(entry, c.now, c.deviceZone)!;
    c.occurrences = [
      OccurrenceState(
          entry.id, due.at.millisecondsSinceEpoch, OccurrenceStatus.completed)
    ];
    await tester.pumpWidget(LifeOSApp(controller: c));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('task_repeat')), findsNothing);
    await tester.tap(find.byKey(const Key('nav_tasks')));
    await tester.pumpAndSettle();
    await tester.ensureVisible(
        find.byKey(const PageStorageKey('completed_task_group')));
    await tester.tap(find.byKey(const PageStorageKey('completed_task_group')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('task_repeat')), findsOneWidget);
    expect(find.text(c.pack.t('task_upcoming')), findsNothing);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
    c.dispose();
  });
  for (final scenario in [
    (390.0, 'light', 1.0),
    (320.0, 'dark', 1.5),
    (834.0, 'dark', 1.0)
  ]) {
    testWidgets('independent planning and readable data ${scenario.$1}',
        (tester) async {
      tester.view.devicePixelRatio = 1;
      tester.view.physicalSize = Size(scenario.$1, 900);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.view.resetPhysicalSize);
      final now = DateTime.now();
      final store = UIStore()
        ..items = [
          for (var i = 0; i < 12; i++)
            Record(
                id: 'task-$i',
                kind: EntryKind.task,
                text:
                    'Подготовить документы для поездки и проверить время встречи $i',
                createdAt: now,
                completed: i >= 8),
          for (var i = 0; i < 9; i++)
            Record(
                id: 'note-$i',
                kind: EntryKind.note,
                text:
                    'Идеи для следующей недели $i\nСохранить адреса, документы и расходы в поездке.',
                createdAt: now),
          for (var i = 0; i < 60; i++)
            Record(
                id: 'money-$i',
                kind: EntryKind.expense,
                text: 'Покупка продуктов $i',
                createdAt: now.add(Duration(seconds: i)),
                amountMinor: i == 0 ? 999999999999999 : 125050,
                currency: const Currency('UZS', 2),
                date: dateOnly(now)),
        ];
      final c = AppController(store, catalog, 'ru');
      await c.load();
      c.preferences.addAll({'theme': scenario.$2, 'currency': 'UZS'});
      c.calendar = [
        for (var i = 0; i < 3; i++)
          CalendarEntry(
              id: 'event-$i',
              title: 'Встреча и планы на день $i',
              schedule: ScheduleSpec(
                  localStart:
                      '${dateOnly(now)}T${(10 + i).toString().padLeft(2, '0')}:00:00',
                  timezone: 'device'))
      ];
      const boundary = Key('planning_capture');
      await tester.pumpWidget(LifeOSApp(
          controller: c,
          builder: (context, child) => MediaQuery(
              data: MediaQuery.of(context)
                  .copyWith(textScaler: TextScaler.linear(scenario.$3)),
              child: RepaintBoundary(key: boundary, child: child!))));
      await tester.pumpAndSettle();
      Future<void> shot(String view) async {
        expect(tester.takeException(), isNull);
        await tester.runAsync(() async {
          final image = await tester
              .renderObject<RenderRepaintBoundary>(find.byKey(boundary))
              .toImage(pixelRatio: 1);
          final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
          final out = Directory('web_evidence/native-planning');
          await out.create(recursive: true);
          await File(
                  '${out.path}/${scenario.$1.toInt()}-${scenario.$2}-$view.png')
              .writeAsBytes(bytes!.buffer.asUint8List());
          image.dispose();
        });
      }

      Future<void> nav(String name) async {
        final target = find.byKey(Key('nav_$name'));
        if (target.evaluate().isNotEmpty) {
          await tester.ensureVisible(target);
          await tester.tap(target);
        } else {
          await tester.tap(find
              .text(c.pack.t(switch (name) {
                'tasks' => 'nav_tasks',
                'calendar' => 'nav_calendar',
                'notes' => 'nav_notes',
                _ => 'finances'
              }))
              .last);
        }
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
      }

      await shot('today');
      await nav('tasks');
      expect(find.byType(CalendarGrid), findsNothing);
      expect(find.byKey(const Key('create_task_header')), findsOneWidget);
      await shot('tasks');
      await nav('calendar');
      expect(find.byType(CalendarGrid), findsOneWidget);
      expect(find.text('Встреча и планы на день 0'), findsOneWidget);
      await shot('calendar');
      await tester
          .ensureVisible(find.byKey(const Key('calendar_month_toggle')));
      expect(find.byType(CalendarGrid), findsOneWidget);
      await shot('month');
      await nav('notes');
      expect(find.byKey(const Key('create_note_header')), findsOneWidget);
      await shot('notes');
      await nav('finances');
      await tester.scrollUntilVisible(
          find.byKey(const Key('finance_load_more')), 350,
          scrollable: find.byType(Scrollable).first);
      await tester.tap(find.byKey(const Key('finance_load_more')));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
          find.byKey(const Key('finance_load_more')), 350,
          scrollable: find.byType(Scrollable).first);
      expect(find.textContaining('50 / 60'), findsOneWidget);
      await tester.pumpWidget(const SizedBox.shrink());
      c.dispose();
    });
  }
}
