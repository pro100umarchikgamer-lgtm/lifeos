import 'package:flutter/foundation.dart';
import 'package:timezone/timezone.dart' as tz;

import 'domain/action_engine.dart';
import 'domain/models.dart';
import 'domain/calendar_engine.dart';
import 'localization/language_pack.dart';
import 'platform/native_bridge.dart';

class AppController extends ChangeNotifier {
  AppController(this.store, this.catalog, this.deviceLanguage);
  final ActionStore store;
  final PackCatalog catalog;
  final String deviceLanguage;
  List<Record> records = [];
  Map<String, String> preferences = {};
  final Set<String> pendingTasks = {};
  final native = NativeBridge();
  final calendarEngine = const CalendarEngine();
  List<CalendarEntry> calendar = [];
  List<OccurrenceState> occurrences = [];
  Map<String, Object?> notificationStatus = {'supported': false};
  String deviceZone = 'UTC';
  String? schedulingError;
  String get region => preferences['region'] ?? pack.locale.languageCode;
  String get timezone => preferences['timezone'] ?? 'device';
  DateTime get now => tz.TZDateTime.now(tz.getLocation(timezone == 'device' ? deviceZone : timezone));
  int get weekStart => int.tryParse(preferences['week_start'] ?? '') ?? 1;
  LanguagePack get pack => catalog.resolve(preferences['language'] ?? deviceLanguage);
  String get currency => preferences['currency'] ?? 'USD';
  String get theme => preferences['theme'] ?? 'system';
  ActionEngine get engine => ActionEngine(store);

  Future<void> load() async {
    preferences = await store.settings();
    await refresh();
  }
  Future<void> _refreshTail = Future<void>.value();
  Future<void> refresh() {
    final next = _refreshTail.then((_) => _refresh());
    _refreshTail = next.catchError((Object _) {});
    return next;
  }
  Future<void> _refresh() async {
    records = await store.records();
    if (store case final PersonalStore personal) {
      calendar = await personal.calendarEntries();
      occurrences = await personal.occurrenceStates();
      await synchronizeReminders(personal);
    }
    notifyListeners();
  }
  Future<void> synchronizeReminders(PersonalStore personal) async {
    schedulingError = null;
    if (!native.supported) return;
    try {
      notificationStatus = await native.diagnostics();
      deviceZone = notificationStatus['zone'] as String? ?? 'UTC';
      final pending = await native.pendingActions();
      final acknowledged = <String>[];
      for (final p in pending) {
        final action = SetOccurrence(p['id'] as String, p['entryId'] as String, p['epoch'] as int,
          OccurrenceStatus.values.byName(p['status'] as String), expectedRevision: p['revision'] as int?, snoozedUntil: p['snoozedUntil'] as int?);
        try { await engine.execute(action); } on DomainFailure catch (e) {
          if (e.key != 'record_missing' && e.key != 'revision_conflict') rethrow;
        }
        acknowledged.add(p['id'] as String);
      }
      await native.acknowledge(acknowledged);
      occurrences = await personal.occurrenceStates();
      records = await personal.records();
      calendar = await personal.calendarEntries();
      final now = DateTime.now();
      final payload = <Map<String, Object?>>[];
      for (final entry in calendar.where((e) => e.schedule.reminder)) {
        if (entry.taskId != null && records.any((r) => r.id == entry.taskId && r.completed)) continue;
        final next = calendarEngine.next(entry, now, deviceZone, occurrences);
        final snoozes = occurrences.where((s) => s.entryId == entry.id && s.revision == entry.revision && s.status == OccurrenceStatus.snoozed &&
          (s.snoozedUntil ?? 0) > now.millisecondsSinceEpoch).toList();
        if (next == null && snoozes.isEmpty) continue;
        payload.add({'id': entry.id, 'revision': entry.revision, 'nextAt': next?.at.millisecondsSinceEpoch,
          'schedule': entry.schedule.toJson(), 'title': preferences['notification_content'] == 'show' ? entry.title : 'LifeOS',
          'message': pack.t('reminder_message'), 'snoozeLabel': pack.t('snooze'), 'dismissLabel': pack.t('dismiss'),
          'doneLabel': pack.t('complete'), 'snoozeMinutes': int.tryParse(preferences['snooze_minutes'] ?? '') ?? 10,
          'snoozes': [for (final s in snoozes) {'epoch': s.epoch, 'until': s.snoozedUntil}]});
      }
      await native.reconcile(payload);
      for (final entry in calendar) { await personal.markCalendarSynced(entry.id, entry.revision); }
    } catch (_) { schedulingError = 'scheduling_pending'; }
  }

  CalendarEntry? scheduleFor(Record record) => calendar.where((e) => e.taskId == record.id || e.noteId == record.id).firstOrNull;

  Future<void> execute(AppAction action) async {
    await engine.execute(action);
    await refresh();
  }
  Future<void> preference(String key, String value) async {
    switch (key) {
      case 'currency': Currency.fromCode(value);
      case 'language': if (!catalog.packs.containsKey(value)) throw const DomainFailure('invalid_setting');
      case 'theme': if (!['system','light','dark'].contains(value)) throw const DomainFailure('invalid_setting');
      case 'week_start': if (!['1','7'].contains(value)) throw const DomainFailure('invalid_setting');
      case 'snooze_minutes': if (!['5','10','15','30'].contains(value)) throw const DomainFailure('invalid_setting');
      case 'notification_content': if (!['hide','show'].contains(value)) throw const DomainFailure('invalid_setting');
      case 'region': if (!['ru','en','de','fr','es','it','pt','kk','uz','uk','ka','az','hy','tg','ky'].contains(value)) throw const DomainFailure('invalid_setting');
      case 'timezone': CalendarEngine.validate(ScheduleSpec(localStart: '2026-01-01T09:00:00', timezone: value));
      default: throw const DomainFailure('invalid_setting');
    }
    await store.setSetting(key, value);
    preferences[key] = value;
    await refresh();
  }
}
