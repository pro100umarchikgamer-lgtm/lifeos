import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;
import 'package:lifeos/domain/calendar_engine.dart';
import 'package:lifeos/domain/models.dart';

void main() {
  tzdata.initializeTimeZones();
  const engine = CalendarEngine();
  CalendarEntry series(
    String start,
    RepeatRule repeat, {
    String zone = 'UTC',
    int interval = 1,
    String? until,
  }) => CalendarEntry(
    id: 'series',
    title: 'Calendar',
    schedule: ScheduleSpec(
      localStart: start,
      timezone: zone,
      repeat: repeat,
      interval: interval,
      until: until,
    ),
  );
  test('month end and leap day stay anchored rather than drifting', () {
    final dates = engine.between(
      series('2024-01-31T09:00:00', RepeatRule.monthly),
      DateTime.utc(2024, 1, 1),
      DateTime.utc(2024, 5, 1),
      'UTC',
    );
    expect(dates.map((o) => dateOnly(o.at)), [
      '2024-01-31',
      '2024-02-29',
      '2024-03-31',
      '2024-04-30',
    ]);
    final leap = engine.between(
      series('2024-02-29T09:00:00', RepeatRule.yearly),
      DateTime.utc(2024),
      DateTime.utc(2029),
      'UTC',
    );
    expect(leap.map((o) => dateOnly(o.at)), [
      '2024-02-29',
      '2025-02-28',
      '2026-02-28',
      '2027-02-28',
      '2028-02-29',
    ]);
  });
  test('DST changes elapsed hours while retaining wall clock', () {
    final e = series(
      '2026-03-07T09:00:00',
      RepeatRule.daily,
      zone: 'America/New_York',
    );
    final dates = engine.between(
      e,
      DateTime.utc(2026, 3, 7),
      DateTime.utc(2026, 3, 10),
      'UTC',
    );
    expect(dates.map((o) => o.at.hour), [9, 9, 9]);
    expect(dates[1].at.difference(dates[0].at).inHours, 23);
    expect(dates[2].at.difference(dates[1].at).inHours, 24);
  });
  test(
    'DST gaps shift forward and ambiguous times choose the earlier instant',
    () {
      final gap = series(
        '2026-03-08T02:30:00',
        RepeatRule.none,
        zone: 'America/New_York',
      );
      expect(
        engine.next(gap, DateTime.utc(2026, 3, 8), 'UTC', [])?.at.toUtc(),
        DateTime.utc(2026, 3, 8, 7, 30),
      );
      final overlap = series(
        '2026-10-25T02:30:00',
        RepeatRule.none,
        zone: 'Europe/Berlin',
      );
      expect(
        engine.next(overlap, DateTime.utc(2026, 10, 25), 'UTC', [])?.at.toUtc(),
        DateTime.utc(2026, 10, 25, 0, 30),
      );
    },
  );
  test(
    'day windows are exclusive at the end and repeat until is inclusive',
    () {
      final e = series(
        '2026-10-01T09:00:00',
        RepeatRule.daily,
        interval: 2,
        until: '2026-10-05',
      );
      expect(
        engine
            .between(
              e,
              DateTime.utc(2026, 10, 1),
              DateTime.utc(2026, 10, 9),
              'UTC',
            )
            .map((o) => o.at.day),
        [1, 3, 5],
      );
      final at = DateTime.utc(2026, 10, 3, 9);
      expect(
        engine
            .between(e, at, at.add(const Duration(days: 2)), 'UTC')
            .map((o) => o.at.day),
        [3],
      );
    },
  );
  test('future schedules beyond one year are not lost; handled repeats are skipped', () {
    final future = series('2029-01-01T09:00:00', RepeatRule.none);
    expect(
      engine.next(future, DateTime.utc(2026), 'UTC', [])?.at.toUtc(),
      DateTime.utc(2029, 1, 1, 9),
    );
    final e = series('2026-10-01T09:00:00', RepeatRule.daily);
    final at = DateTime.utc(2026, 10, 1, 9);
    expect(
      engine
          .next(e, DateTime.utc(2026, 10, 1), 'UTC', [
            OccurrenceState(
              e.id,
              at.millisecondsSinceEpoch,
              OccurrenceStatus.completed,
            ),
          ])
          ?.at
          .toUtc(),
      DateTime.utc(2026, 10, 2, 9),
    );
  });
  test('device zone affects device schedules but never a fixed zone', () {
    final e = series('2026-10-11T09:00:00', RepeatRule.none, zone: 'device');
    expect(
      engine.next(e, DateTime.utc(2026, 10, 10), 'Asia/Almaty', [])?.at.toUtc(),
      DateTime.utc(2026, 10, 11, 4),
    );
    expect(tz.getLocation('Asia/Almaty').name, 'Asia/Almaty');
  });
  test('invalid canonical dates and unknown zones fail before persistence', () {
    for (final start in [
      '2026-02-30T09:00:00',
      '2026-01-01T25:00:00',
      '2026-01-01T09:00:00Z',
    ]) {
      expect(
        () => CalendarEngine.validate(
          ScheduleSpec(localStart: start, timezone: 'UTC'),
        ),
        throwsA(isA<DomainFailure>()),
      );
    }
    expect(
      () => CalendarEngine.validate(
        const ScheduleSpec(
          localStart: '2026-01-01T09:00:00',
          timezone: 'unknown',
        ),
      ),
      throwsA(isA<DomainFailure>()),
    );
  });
  test('Oct 11 overdue occurrence remains completable on Oct 15, including ended old series', () {
    for (final year in [2023, 2026]) {
      final entry = series(
        '$year-10-01T09:00:00',
        RepeatRule.daily,
        zone: 'Europe/Moscow',
        until: '$year-10-11',
      );
      final due = engine.completionOccurrence(
        entry,
        DateTime.utc(2026, 10, 15, 18),
        'UTC',
      );
      expect(due?.at.toUtc(), DateTime.utc(year, 10, 11, 6));
    }
  });
  test('completion handles month end, leap day and device timezone', () {
    final month = series(
      '2026-01-31T09:00:00',
      RepeatRule.monthly,
      zone: 'Asia/Almaty',
    );
    expect(
      engine
          .completionOccurrence(month, DateTime.utc(2026, 3, 1), 'UTC')
          ?.at
          .toUtc(),
      DateTime.utc(2026, 2, 28, 4),
    );
    final leap = series(
      '2024-02-29T09:00:00',
      RepeatRule.yearly,
      zone: 'device',
    );
    expect(
      engine
          .completionOccurrence(leap, DateTime.utc(2026, 3, 1), 'Europe/Moscow')
          ?.at
          .toUtc(),
      DateTime.utc(2026, 2, 28, 6),
    );
  });
}
