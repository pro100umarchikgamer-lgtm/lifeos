import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:timezone/timezone.dart' as tz;
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/family_dashboard.dart';
import 'package:lifeos/ui/family.dart';
import 'package:lifeos/ui/design.dart';
import 'package:lifeos/ui/calendar.dart';
import 'package:lifeos/ui/cloud_record_detail.dart';
import 'package:lifeos/ui/money_format.dart';
import 'package:lifeos/domain/models.dart';
import 'controller_test.dart' show CountingStore, FakeNative;
import 'family_completion_visual_test.dart' show familyFixture;

class _ViewClockController extends AppController {
  _ViewClockController(PackCatalog catalog)
      : super(CountingStore(), catalog, 'en', platform: FakeNative());
  DateTime clock =
      tz.TZDateTime(tz.getLocation('Asia/Tashkent'), 2027, 4, 1, 12);
  @override
  DateTime get now => clock;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  timezone.initializeTimeZones();
  late PackCatalog catalog;
  setUpAll(() async => catalog = await PackCatalog.load());

  testWidgets('budget read view uses its supplied civil UI clock',
      (tester) async {
    final f = familyFixture();
    final now = DateTime.now(), pack = catalog.packs['en']!;
    final first = DateTime(now.year, now.month),
        next = DateTime(now.year, now.month + 1);
    final budget = <String, dynamic>{
      'id': 'budget',
      'kind': 'budget',
      'revision': 1,
      'editable': false,
      'data': {
        'name': 'Monthly budget',
        'currency': 'RUB',
        'limit_minor': 10000,
        'period': 'month',
        'start_on': dateOnly(first),
        'end_on': null,
        'rollover': 'none',
        'participants': []
      }
    };
    f.records = [
      budget,
      {
        'id': 'expense',
        'kind': 'transaction',
        'data': {
          'kind': 'expense',
          'label': 'Spent this month',
          'currency': 'RUB',
          'amount_minor': 5000,
          'date': dateOnly(now),
          'account_id': null
        },
        'audience': []
      }
    ];
    await tester.pumpWidget(MaterialApp(
        home: CloudRecordDetail(
            controller: f,
            pack: pack,
            id: 'budget',
            region: 'en',
            clock: () => next)));
    await tester.pumpAndSettle();
    final expected = formatMoney(Currency.fromCode('RUB'), 10000, locale: 'en');
    expect(
        find.byWidgetPredicate(
            (w) => w is SelectableText && w.data == expected),
        findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
    f.dispose();
  });

  testWidgets(
      'cloud calendar includes the view-zone month edge and converts agenda time',
      (tester) async {
    expect(DateTime(2027, 4, 1).timeZoneOffset, Duration.zero);
    final c = _ViewClockController(catalog);
    await c.load();
    c.preferences['timezone'] = 'Asia/Tashkent';
    c.deviceZone = 'UTC';
    final f = familyFixture();
    f.records = [
      {
        'id': 'edge',
        'revision': 1,
        'kind': 'event',
        'data': {
          'title': 'Month boundary event',
          'schedule': {
            'localStart': '2027-04-01T01:00:00',
            'timezone': 'Asia/Tashkent',
            'allDay': false,
            'repeat': 'none',
            'interval': 1,
            'until': null
          }
        }
      },
      {
        'id': 'utc',
        'revision': 1,
        'kind': 'event',
        'data': {
          'title': 'UTC evening event',
          'schedule': {
            'localStart': '2027-04-01T21:15:00',
            'timezone': 'UTC',
            'allDay': false,
            'repeat': 'none',
            'interval': 1,
            'until': null
          }
        }
      },
    ];
    c.family = f;
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: SingleChildScrollView(
                child: FamilyDashboard(
                    controller: c, visibleKinds: const {'event'})))));
    await tester.pumpAndSettle();
    tester
        .widget<CalendarGrid>(find.byType(CalendarGrid))
        .onMonth(DateTime(2027, 4));
    await tester.pumpAndSettle();
    tester
        .widget<CalendarGrid>(find.byType(CalendarGrid))
        .onDay(DateTime(2027, 4, 1));
    await tester.pumpAndSettle();
    expect(find.text('Month boundary event'), findsOneWidget);
    tester
        .widget<CalendarGrid>(find.byType(CalendarGrid))
        .onDay(DateTime(2027, 4, 2));
    await tester.pumpAndSettle();
    final context = tester.element(find.byType(CalendarGrid));
    final expected = MaterialLocalizations.of(context)
        .formatTimeOfDay(const TimeOfDay(hour: 2, minute: 15));
    expect(find.text('UTC evening event'), findsOneWidget);
    expect(find.text(expected), findsOneWidget);
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: SingleChildScrollView(
                child: FamilyDashboard(
                    key: const Key('clock_today'), controller: c)))));
    await tester.pumpAndSettle();
    expect(find.text('Month boundary event'), findsOneWidget);
    c.clock = tz.TZDateTime(tz.getLocation('Asia/Tashkent'), 2027, 4, 2, 12);
    f.publish();
    await tester.pumpAndSettle();
    expect(find.text('Month boundary event'), findsNothing,
        reason: "Today must not keep the previous day cached after midnight.");
    expect(find.text('UTC evening event'), findsOneWidget);

    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
    c.dispose();
  });

  for (final changeWorkspace in [false, true]) {
    testWidgets(
        'cloud notes open for reading and clear on ${changeWorkspace ? 'workspace' : 'principal'} change',
        (tester) async {
      final c =
          AppController(CountingStore(), catalog, 'en', platform: FakeNative());
      await c.load();
      final f = familyFixture();
      f.spaces.single['kind'] = 'personal';
      f.roster!['space']['kind'] = 'personal';
      c.family = f;
      addTearDown(() {
        c.dispose();
      });
      await tester.pumpWidget(MaterialApp(
          theme: lifeTheme(Brightness.light),
          home: Scaffold(
              body: SingleChildScrollView(
                  child: FamilyDashboard(
                      controller: c, visibleKinds: const {'note'})))));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Планы на выходные'));
      await tester.pumpAndSettle();
      expect(find.byType(FamilyRecordEditor), findsNothing,
          reason: 'Opening an existing cloud record must not begin editing.');
      expect(find.byType(TextField), findsNothing);
      expect(find.byKey(const Key('cloud_record_edit')), findsOneWidget);
      if (changeWorkspace) {
        f.workspace = 'other';
      } else {
        f.account = {'user_id': 'other-user', 'verified': true};
      }
      f.publish();
      await tester.pumpAndSettle();
      expect(find.text('Планы на выходные'), findsNothing);
      expect(find.byKey(const Key('cloud_record_edit')), findsNothing);
      expect(find.text(c.pack.t('privacy_record_unavailable')), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
    });
  }
}
