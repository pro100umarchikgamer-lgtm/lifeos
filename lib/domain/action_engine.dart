import 'models.dart';
import 'calendar_engine.dart';

abstract interface class ActionStore {
  Future<String> apply(AppAction action);
  Future<List<Record>> records();
  Future<Map<String, String>> settings();
  Future<void> setSetting(String key, String value);
  Future<void> close();
}

abstract interface class PersonalStore implements ActionStore {
  Future<List<CalendarEntry>> calendarEntries();
  Future<List<OccurrenceState>> occurrenceStates();
  Future<void> markCalendarSynced(String id, int revision);
  Future<Map<String, Object?>> exportSnapshot();
  Future<void> restoreSnapshot(Map<String, Object?> data);
}

class ActionEngine {
  const ActionEngine(this.store);
  final ActionStore store;

  Future<String> execute(AppAction action) {
    if (action.operationId.trim().isEmpty) throw const DomainFailure('invalid_action');
    switch (action) {
      case CreateMoney():
        if (action.kind != EntryKind.expense && action.kind != EntryKind.income) {
          throw const DomainFailure('invalid_action');
        }
        Currency.fromCode(action.currencyCode).parse(action.amount);
        if (action.date.year < 1900 || action.date.year > 2200) {
          throw const DomainFailure('invalid_date');
        }
      case CreateTask():
        if (action.title.trim().isEmpty) throw const DomainFailure('required_text');
        if (action.schedule != null) CalendarEngine.validate(action.schedule!);
      case CreateNote():
        if (action.body.trim().isEmpty) throw const DomainFailure('required_text');
        if (action.schedule != null) CalendarEngine.validate(action.schedule!);
      case CompleteTask():
        if (action.id.isEmpty) throw const DomainFailure('invalid_action');
        if (action.expectedRevision != null && action.expectedRevision! < 1) {
          throw const DomainFailure('invalid_action');
        }
      case RecordMutation():
        if (action.id.trim().isEmpty || action.expectedRevision < 1) {
          throw const DomainFailure('invalid_action');
        }
        if (action is EditMoney) {
          if (action.kind != EntryKind.expense && action.kind != EntryKind.income) {
            throw const DomainFailure('invalid_action');
          }
          Currency.fromCode(action.currencyCode).parse(action.amount);
          if (action.date.year < 1900 || action.date.year > 2200) {
            throw const DomainFailure('invalid_date');
          }
        }
        if (action is EditTask && action.title.trim().isEmpty ||
            action is EditNote && action.body.trim().isEmpty) {
          throw const DomainFailure('required_text');
        }
        if (action is EditTask && action.updateSchedule && (action.expectedScheduleRevision == null || action.expectedScheduleRevision! < 0) ||
            action is EditNote && action.updateSchedule && (action.expectedScheduleRevision == null || action.expectedScheduleRevision! < 0)) throw const DomainFailure('invalid_action');
        if (action is EditTask && action.schedule != null) CalendarEngine.validate(action.schedule!);
        if (action is EditNote && action.schedule != null) CalendarEngine.validate(action.schedule!);
      case SaveCalendar():
        if (action.title.trim().isEmpty) throw const DomainFailure('required_text');
        if (action.taskId != null || action.noteId != null || action.id == null && action.expectedRevision != null ||
            action.id != null && (action.id!.isEmpty || action.expectedRevision == null || action.expectedRevision! < 1)) {
          throw const DomainFailure('invalid_action');
        }
        CalendarEngine.validate(action.schedule);
      case DeleteCalendar():
        if (action.id.isEmpty || action.expectedRevision < 1) throw const DomainFailure('invalid_action');
      case SetOccurrence():
        if (action.entryId.isEmpty || action.expectedRevision == null || action.expectedRevision! < 1 || action.epoch < -2208988800000 || action.epoch > 7289654400000 ||
            action.status == OccurrenceStatus.snoozed && (action.snoozedUntil == null || action.snoozedUntil! <= action.epoch) ||
            action.status != OccurrenceStatus.snoozed && action.snoozedUntil != null) {
          throw const DomainFailure('invalid_action');
        }
    }
    return store.apply(action);
  }
}
