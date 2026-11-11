import 'package:lifeos/domain/task_day_progress.dart';
import 'package:lifeos/ui/quick_add.dart';
import 'package:lifeos/domain/models.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/design.dart';
import 'package:lifeos/ui/dashboard_editor.dart';
import 'widget_test.dart' show UIStore;

void main() {
  late PackCatalog catalog;
  setUpAll(() async {
    timezone.initializeTimeZones();
    catalog = await PackCatalog.load();
  });
  test('today progress follows the chosen civil day and excludes other records',
      () {
    final at = DateTime.utc(2026, 11, 11, 22);
    final tasks = [
      for (final id in ['a', 'b', 'c'])
        Record(
            id: id,
            kind: EntryKind.task,
            text: id,
            createdAt: at,
            completed: id == 'a')
    ];
    final entries = [
      for (final pair in [
        ('a', '2026-11-12T00:30:00'),
        ('b', '2026-11-12T23:30:00'),
        ('c', '2026-11-13T00:00:00')
      ])
        CalendarEntry(
            id: pair.$1,
            title: pair.$1,
            taskId: pair.$1,
            schedule:
                ScheduleSpec(localStart: pair.$2, timezone: 'Europe/Moscow')),
      const CalendarEntry(
          id: 'orphan',
          title: 'Deleted',
          taskId: 'missing',
          schedule: ScheduleSpec(
              localStart: '2026-11-12T10:00:00', timezone: 'Europe/Moscow')),
    ];
    expect(taskDayProgress(tasks, entries, [], at, 'Europe/Moscow', 'UTC'),
        (done: 1, total: 2));
    expect(taskDayProgress(tasks, entries, [], at, 'UTC', 'UTC'),
        (done: 1, total: 1));
  });
  test('repeating task progress requires the current occurrence and revision',
      () {
    final at = DateTime.utc(2026, 11, 12, 12);
    final task = Record(
        id: 'r',
        kind: EntryKind.task,
        text: 'Daily',
        createdAt: at,
        completed: true);
    const entry = CalendarEntry(
        id: 'e',
        taskId: 'r',
        title: 'Daily',
        revision: 2,
        schedule: ScheduleSpec(
            localStart: '2026-11-10T09:00:00',
            timezone: 'UTC',
            repeat: RepeatRule.daily));
    final epoch = DateTime.utc(2026, 11, 12, 9).millisecondsSinceEpoch;
    for (final state in [
      OccurrenceState('e', epoch, OccurrenceStatus.completed),
      OccurrenceState('e', epoch, OccurrenceStatus.dismissed, revision: 2),
      OccurrenceState('e', epoch - 86400000, OccurrenceStatus.completed,
          revision: 2)
    ]) {
      expect(taskDayProgress([task], [entry], [state], at, 'UTC', 'UTC'),
          (done: 0, total: 1));
    }
    expect(
        taskDayProgress([
          task
        ], [
          entry
        ], [
          OccurrenceState('e', epoch, OccurrenceStatus.completed, revision: 2)
        ], at, 'UTC', 'UTC'),
        (done: 1, total: 1));
  });
  test('today progress includes the late hour on a 25 hour DST day', () {
    final at = DateTime.utc(2026, 11, 1, 12);
    final task =
        Record(id: 't', kind: EntryKind.task, text: 'Late', createdAt: at);
    const entry = CalendarEntry(
        id: 'e',
        taskId: 't',
        title: 'Late',
        schedule: ScheduleSpec(
            localStart: '2026-11-01T23:30:00', timezone: 'America/New_York'));
    expect(
        taskDayProgress([task], [entry], [], at, 'device', 'America/New_York'),
        (done: 0, total: 1));
  });
  test('Clarity uses the shared web light and dark surfaces', () {
    expect(lifeTheme(Brightness.light).scaffoldBackgroundColor,
        const Color(0xfff7f8f7));
    expect(lifeTheme(Brightness.dark).scaffoldBackgroundColor,
        const Color(0xff101a18));
  });
  testWidgets('compact cards preserve readable content without heavy shadows',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
        theme: lifeTheme(Brightness.light),
        home: const Scaffold(body: LifeCard(child: Text('Daily task')))));
    final card = tester.widget<Container>(find
        .descendant(of: find.byType(LifeCard), matching: find.byType(Container))
        .first);
    expect(card.padding, const EdgeInsets.all(14));
    expect((card.decoration as BoxDecoration).boxShadow, isNull);
    expect(find.text('Daily task'), findsOneWidget);
  });
  test('Today prioritizes daily tasks by default and preserves saved ordering',
      () async {
    final c = AppController(UIStore(), catalog, 'ru');
    await c.load();
    expect(
        (dashboardChoice(c, 'tasks')['position'] as int) <
            (dashboardChoice(c, 'financial')['position'] as int),
        isTrue);
    c.dispose();
  });

  testWidgets(
      'financial entry uses a dedicated page with an exact localized amount',
      (tester) async {
    timezone.initializeTimeZones();
    final store = UIStore();
    final c = AppController(store, catalog, 'ru');
    await c.load();
    await tester.pumpWidget(MaterialApp(
        home: Builder(
            builder: (context) => Scaffold(
                body: TextButton(
                    onPressed: () =>
                        showEntryEditor(context, c, EntryKind.expense),
                    child: const Text('Open'))))));
    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
    expect(find.byType(BottomSheet), findsNothing);
    await tester.enterText(find.byKey(const Key('amount')), '12,50');
    await tester.pump();
    await tester.ensureVisible(find.byKey(const Key('save')));
    await tester.tap(find.byKey(const Key('save')));
    await tester.pumpAndSettle();
    expect((store.actions.single as CreateMoney).amount, '12,50');
    expect(tester.takeException(), isNull);
    c.dispose();
  });
}
