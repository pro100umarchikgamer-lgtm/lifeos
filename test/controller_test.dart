import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/action_engine.dart';
import 'package:lifeos/domain/appearance.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/platform/native_bridge.dart';

class CountingStore implements PersonalStore {
  int reads = 0, calendarReads = 0, occurrenceReads = 0, marks = 0;
  final preferences = <String, String>{'language': 'ru'};
  @override
  Future<List<Record>> records() async { reads++; return []; }
  @override
  Future<List<CalendarEntry>> calendarEntries() async { calendarReads++; return []; }
  @override
  Future<List<OccurrenceState>> occurrenceStates() async { occurrenceReads++; return []; }
  @override
  Future<void> markCalendarSynced(String id, int revision) async { marks++; }
  @override
  Future<Map<String, String>> settings() async => Map.of(preferences);
  @override
  Future<void> setSetting(String key, String value) async { preferences[key] = value; }
  @override
  Future<String> apply(AppAction action) async => 'id';
  @override
  Future<Map<String, Object?>> exportSnapshot() async => {};
  @override
  Future<void> restoreSnapshot(Map<String, Object?> data) async {}
  @override
  Future<void> close() async {}
}
class FakeNative extends NativeBridge {
  int reconciliations = 0, acknowledgements = 0;
  bool failReconcile = false;
  List<Map<String, Object?>> pending = [];
  @override
  bool get supported => true;
  @override
  Future<int?> wallpaperSeed() async => null;
  @override
  Future<Map<String, Object?>> diagnostics({Map<String,String>? labels}) async => {'zone':'UTC','enabled':true,'exact':true};
  @override
  Future<List<Map<String, Object?>>> pendingActions() async => pending;
  @override
  Future<void> acknowledge(List<String> ids) async { acknowledgements += ids.length; pending = []; }
  @override
  Future<void> reconcile(List<Map<String, Object?>> entries) async {
    reconciliations++; if (failReconcile) throw StateError('native unavailable');
  }
}
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  timezone.initializeTimeZones();
  late PackCatalog catalog;
  setUpAll(() async { catalog = await PackCatalog.load(); });
  test('Android UTC aliases keep the controller clock and civil dates usable', () async {
    final catalog = await PackCatalog.load();
    final c = AppController(CountingStore(), catalog, 'en', platform: FakeNative());
    await c.load();
    c.deviceZone = 'Etc/UTC';
    expect(c.now.timeZoneOffset, Duration.zero);
    expect(c.civilDate(DateTime.utc(2026, 10, 11, 23)), '2026-10-11');
    c.preferences['timezone'] = 'Etc/UTC';
    expect(c.now.timeZoneOffset, Duration.zero);
    c.dispose();
  });

  test('appearance preview is not persisted; Apply survives a new controller without database refresh', () async {
    final store = CountingStore(), native = FakeNative();
    final c = AppController(store, catalog, 'ru', platform: native);
    await c.load();
    c.previewAppearance(const Appearance(palette: 'pistachio'));
    expect(store.preferences.containsKey('appearance_v1'), isFalse);
    await c.preference('appearance_v1', c.appearance.encode());
    expect(c.appearancePreview, isNull);
    expect(store.reads, 1); expect(native.reconciliations, 1);
    final reopened = AppController(store, catalog, 'ru', platform: FakeNative());
    await reopened.load(); expect(reopened.appearance.palette, 'pistachio');
    c.dispose(); reopened.dispose();
  });
  test('refresh reads each collection once and skips an unchanged native payload; resume forces reconciliation', () async {
    final store = CountingStore(), native = FakeNative();
    final c = AppController(store, catalog, 'ru', platform: native);
    await c.load(); await c.refresh();
    expect([store.reads,store.calendarReads,store.occurrenceReads], [2,2,2]);
    expect(native.reconciliations, 1);
    await c.refresh(forceReminders: true); expect(native.reconciliations, 2);
    c.dispose();
  });
  test('failed native delivery is retried without publishing a successful fingerprint', () async {
    final native = FakeNative()..failReconcile = true;
    final c = AppController(CountingStore(), catalog, 'ru', platform: native);
    await c.load(); expect(c.schedulingError, 'scheduling_pending');
    native.failReconcile = false; await c.refresh();
    expect(native.reconciliations, 2); expect(c.schedulingError, isNull); c.dispose();
  });
  test('invalid appearance and pending action do not bypass validation', () async {
    final store = CountingStore(), native = FakeNative();
    final c = AppController(store, catalog, 'ru', platform: native); await c.load();
    await expectLater(c.preference('appearance_v1', '{"version":999}'), throwsA(isA<DomainFailure>()));
    expect(store.preferences.containsKey('appearance_v1'), isFalse);
    native.pending = [{'id':'bad','entryId':'event','epoch':1791710000000,'status':'dismissed','revision':0}];
    await c.refresh(); expect(c.schedulingError, 'scheduling_pending');
    expect(native.acknowledgements, 0); expect(native.pending.length, 1); c.dispose();
  });
  test('pending native actions are acknowledged only after domain processing and reread data', () async {
    final store = CountingStore(), native = FakeNative();
    final c = AppController(store, catalog, 'ru', platform: native);
    await c.load();
    native.pending = [{'id':'notification-action','entryId':'event','epoch': 1791710000000,
      'status':'dismissed','revision':1}];
    await c.refresh();
    expect(native.acknowledgements, 1); expect(store.reads, 3); c.dispose();
  });
}
