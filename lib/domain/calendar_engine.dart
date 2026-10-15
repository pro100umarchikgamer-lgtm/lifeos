import 'dart:math' as math;

import 'package:timezone/timezone.dart' as tz;

import 'models.dart';

class CalendarEngine {
  const CalendarEngine();
  static void validate(ScheduleSpec spec) {
    final start = DateTime.tryParse(spec.localStart);
    if (start == null ||
        start.year < 1900 ||
        start.year > 2200 ||
        !RegExp(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00$')
            .hasMatch(spec.localStart) ||
        spec.interval < 1 ||
        spec.interval > 365) {
      throw const DomainFailure('invalid_date');
    }
    final canonical =
        '${dateOnly(start)}T${start.hour.toString().padLeft(2, '0')}:${start.minute.toString().padLeft(2, '0')}:00';
    if (canonical != spec.localStart) throw const DomainFailure('invalid_date');
    if (spec.timezone != 'device') {
      try {
        tz.getLocation(spec.timezone);
      } catch (_) {
        throw const DomainFailure('invalid_timezone');
      }
    }
    if (spec.until != null &&
        (DateTime.tryParse(spec.until!) == null ||
            dateOnly(DateTime.parse(spec.until!)) != spec.until ||
            spec.until!.compareTo(dateOnly(start)) < 0)) {
      throw const DomainFailure('invalid_date');
    }
  }

  // Choose the earlier instant in a DST overlap; shift nonexistent times forward by the gap.
  // java.time.atZone uses the same policy in the native scheduler.
  tz.TZDateTime _wallTime(
    tz.Location zone,
    DateTime date,
    int hour,
    int minute,
  ) {
    final naive = DateTime.utc(date.year, date.month, date.day, hour, minute);
    final before = tz.TZDateTime.from(
      naive.subtract(const Duration(days: 2)),
      zone,
    ).timeZoneOffset;
    final after = tz.TZDateTime.from(
      naive.add(const Duration(days: 2)),
      zone,
    ).timeZoneOffset;
    final matches = <tz.TZDateTime>[];
    for (final offset in {before, after}) {
      final at = tz.TZDateTime.from(naive.subtract(offset), zone);
      if (at.year == date.year &&
          at.month == date.month &&
          at.day == date.day &&
          at.hour == hour &&
          at.minute == minute) {
        matches.add(at);
      }
    }
    matches.sort((a, b) => a.compareTo(b));
    return matches.firstOrNull ??
        tz.TZDateTime.from(naive.subtract(before), zone);
  }

  List<CalendarOccurrence> between(
    CalendarEntry entry,
    DateTime from,
    DateTime to,
    String deviceZone, {
    int limit = 5000,
  }) {
    if (!from.isBefore(to)) return [];
    final spec = entry.schedule;
    final local = DateTime.parse(spec.localStart);
    final zone = tz.getLocation(
      spec.timezone == 'device' ? deviceZone : spec.timezone,
    );
    final localFrom = tz.TZDateTime.from(from, zone);
    int index = 0;
    switch (spec.repeat) {
      case RepeatRule.none:
        break;
      case RepeatRule.daily || RepeatRule.weekly:
        final days = DateTime.utc(
          localFrom.year,
          localFrom.month,
          localFrom.day,
        ).difference(DateTime.utc(local.year, local.month, local.day)).inDays;
        index = math.max(
          0,
          days ~/ (spec.interval * (spec.repeat == RepeatRule.weekly ? 7 : 1)) -
              1,
        );
      case RepeatRule.monthly:
        index = math.max(
          0,
          ((localFrom.year - local.year) * 12 +
                      localFrom.month -
                      local.month) ~/
                  spec.interval -
              1,
        );
      case RepeatRule.yearly:
        index = math.max(0, (localFrom.year - local.year) ~/ spec.interval - 1);
    }
    final result = <CalendarOccurrence>[];
    // Bound only the requested view window; do not materialize years of dates.
    for (var n = index; n < index + limit + 3; n++) {
      DateTime date;
      switch (spec.repeat) {
        case RepeatRule.none:
          date = local;
        case RepeatRule.daily || RepeatRule.weekly:
          date = DateTime(
            local.year,
            local.month,
            local.day +
                n * spec.interval * (spec.repeat == RepeatRule.weekly ? 7 : 1),
          );
        case RepeatRule.monthly:
          final month = DateTime(local.year, local.month + n * spec.interval);
          date = DateTime(
            month.year,
            month.month,
            math.min(local.day, DateTime(month.year, month.month + 1, 0).day),
          );
        case RepeatRule.yearly:
          final year = local.year + n * spec.interval;
          date = DateTime(
            year,
            local.month,
            math.min(local.day, DateTime(year, local.month + 1, 0).day),
          );
      }
      // Recreate wall-clock time in its IANA zone on each date, including DST.
      final at = _wallTime(zone, date, local.hour, local.minute);
      if (!at.isBefore(to) ||
          at.year > 2200 ||
          (spec.until != null && dateOnly(at).compareTo(spec.until!) > 0)) {
        break;
      }
      if (!at.isBefore(from)) result.add(CalendarOccurrence(entry, at));
      if (spec.repeat == RepeatRule.none || result.length >= limit) break;
    }
    return result;
  }

  // Notification dismissal/snooze does not complete a task. Anchor ended
  // series at their final civil date, not an arbitrary window around today.
  CalendarOccurrence? completionOccurrence(
    CalendarEntry entry,
    DateTime now,
    String deviceZone,
  ) {
    final spec = entry.schedule;
    final zone = tz.getLocation(
      spec.timezone == 'device' ? deviceZone : spec.timezone,
    );
    var anchor = tz.TZDateTime.from(now, zone);
    if (spec.until != null) {
      final end = DateTime.parse(spec.until!);
      final until = tz.TZDateTime(zone, end.year, end.month, end.day + 1);
      if (until.isBefore(anchor)) anchor = until;
    }
    final span =
        switch (spec.repeat) {
          RepeatRule.none => 1,
          RepeatRule.daily => 2,
          RepeatRule.weekly => 14,
          RepeatRule.monthly => 64,
          RepeatRule.yearly => 732,
        } *
        spec.interval;
    final from = spec.repeat == RepeatRule.none
        ? DateTime.parse(spec.localStart)
              .toUtc()
              .subtract(const Duration(days: 2))
        : anchor.subtract(Duration(days: span));
    final due = between(
      entry,
      from,
      now.add(const Duration(milliseconds: 1)),
      deviceZone,
    );
    return due.lastOrNull ?? next(entry, now, deviceZone, const []);
  }

  CalendarOccurrence? next(
    CalendarEntry entry,
    DateTime now,
    String deviceZone,
    List<OccurrenceState> states,
  ) {
    for (final occurrence in between(
      entry,
      now,
      DateTime.utc(2201),
      deviceZone,
      limit:
          states
              .where(
                (s) => s.entryId == entry.id && s.revision == entry.revision,
              )
              .length +
          1,
    )) {
      final state = states
          .where(
            (s) =>
                s.entryId == entry.id &&
                s.revision == entry.revision &&
                s.epoch == occurrence.at.millisecondsSinceEpoch,
          )
          .firstOrNull;
      if (state == null) return occurrence;
    }
    return null;
  }
}
