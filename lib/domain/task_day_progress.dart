import 'package:timezone/timezone.dart' as tz;
import 'calendar_engine.dart';
import 'models.dart';
import 'timezones.dart';

/// Counts task occurrences in the selected civil day, including DST changes.
({int done, int total}) taskDayProgress(
  Iterable<Record> records,
  Iterable<CalendarEntry> entries,
  Iterable<OccurrenceState> states,
  DateTime instant,
  String timezone,
  String deviceZone,
) {
  final zone = calendarLocation(timezone == 'device' ? deviceZone : timezone);
  final day = tz.TZDateTime.from(instant, zone);
  final from = tz.TZDateTime(zone, day.year, day.month, day.day);
  final to = tz.TZDateTime(zone, day.year, day.month, day.day + 1);
  final tasks = {
    for (final r in records)
      if (r.kind == EntryKind.task) r.id: r
  };
  final completed = {
    for (final s in states)
      if (s.status == OccurrenceStatus.completed)
        (s.entryId, s.revision, s.epoch)
  };
  var total = 0;
  var done = 0;
  for (final entry in entries) {
    final task = tasks[entry.taskId];
    if (task == null) continue;
    for (final occurrence
        in const CalendarEngine().between(entry, from, to, deviceZone)) {
      total++;
      if (completed.contains((
            entry.id,
            entry.revision,
            occurrence.at.millisecondsSinceEpoch
          )) ||
          (entry.schedule.repeat == RepeatRule.none && task.completed)) {
        done++;
      }
    }
  }
  return (done: done, total: total);
}
