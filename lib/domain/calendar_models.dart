part of 'models.dart';

enum RepeatRule { none, daily, weekly, monthly, yearly }
enum ReminderMode { standard, important, alarm }
enum OccurrenceStatus { dismissed, completed, snoozed }

class ScheduleSpec {
  const ScheduleSpec({required this.localStart, required this.timezone, this.allDay = false,
    this.repeat = RepeatRule.none, this.interval = 1, this.until, this.reminder = false,
    this.mode = ReminderMode.standard});
  final String localStart;
  final String timezone;
  final bool allDay;
  final RepeatRule repeat;
  final int interval;
  final String? until;
  final bool reminder;
  final ReminderMode mode;
  Map<String, Object?> toJson() => {'localStart': localStart, 'timezone': timezone, 'allDay': allDay,
    'repeat': repeat.name, 'interval': interval, 'until': until, 'reminder': reminder, 'mode': mode.name};
  factory ScheduleSpec.fromJson(Map<String, Object?> data) => ScheduleSpec(
    localStart: data['localStart'] as String, timezone: data['timezone'] as String,
    allDay: data['allDay'] as bool, repeat: RepeatRule.values.byName(data['repeat'] as String),
    interval: data['interval'] as int, until: data['until'] as String?, reminder: data['reminder'] as bool,
    mode: ReminderMode.values.byName(data['mode'] as String));
}

class CalendarEntry {
  const CalendarEntry({required this.id, required this.title, required this.schedule,
    this.taskId, this.noteId, this.revision = 1, this.syncedRevision = 0});
  final String id;
  final String title;
  final ScheduleSpec schedule;
  final String? taskId;
  final String? noteId;
  final int revision;
  final int syncedRevision;
}

class CalendarOccurrence {
  const CalendarOccurrence(this.entry, this.at);
  final CalendarEntry entry;
  final DateTime at;
  String get key => '${entry.id}:${at.millisecondsSinceEpoch}';
}

class OccurrenceState {
  const OccurrenceState(this.entryId, this.epoch, this.status, {this.snoozedUntil, this.revision = 1});
  final String entryId;
  final int epoch;
  final OccurrenceStatus status;
  final int? snoozedUntil;
  final int revision;
}

class SaveCalendar extends AppAction {
  const SaveCalendar(super.operationId, {this.id, this.expectedRevision, required this.title,
    required this.schedule, this.taskId, this.noteId});
  final String? id;
  final int? expectedRevision;
  final String title;
  final ScheduleSpec schedule;
  final String? taskId;
  final String? noteId;
  @override
  Map<String, Object?> get payload => {'action': 'calendar.save', 'id': id, 'expectedRevision': expectedRevision,
    'title': title.trim(), 'schedule': schedule.toJson(), 'taskId': taskId, 'noteId': noteId};
}

class DeleteCalendar extends AppAction {
  const DeleteCalendar(super.operationId, this.id, this.expectedRevision);
  final String id;
  final int expectedRevision;
  @override
  Map<String, Object?> get payload => {'action': 'calendar.delete', 'id': id, 'expectedRevision': expectedRevision};
}

class SetOccurrence extends AppAction {
  const SetOccurrence(super.operationId, this.entryId, this.epoch, this.status, {this.snoozedUntil, this.expectedRevision});
  final String entryId;
  final int epoch;
  final OccurrenceStatus status;
  final int? snoozedUntil;
  final int? expectedRevision;
  @override
  Map<String, Object?> get payload => {'action': 'calendar.occurrence', 'entryId': entryId,
    'epoch': epoch, 'status': status.name, 'snoozedUntil': snoozedUntil, 'expectedRevision': expectedRevision};
}
