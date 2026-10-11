import 'package:timezone/data/latest.dart' as timezone;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/action_engine.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/app.dart';
import 'package:lifeos/ui/quick_add.dart';
import 'package:lifeos/ui/calendar.dart';
import 'package:lifeos/domain/appearance.dart';
import 'package:lifeos/ui/appearance_editor.dart';

class UIStore implements ActionStore {
  final List<AppAction> actions = [];
  List<Record> items = [];
  bool failWrites = false;
  @override
  Future<String> apply(AppAction action) async {
    if (failWrites) throw const DomainFailure('save_failed');
    actions.add(action);
    return 'id';
  }
  @override
  Future<List<Record>> records() async => items;
  @override
  Future<Map<String, String>> settings() async => {'language': 'ru'};
  @override
  Future<void> setSetting(String key, String value) async {}
  @override
  Future<void> close() async {}
}

void main() {
  timezone.initializeTimeZones();
  TestWidgetsFlutterBinding.ensureInitialized();
  late PackCatalog catalog;
  setUpAll(() async {
    catalog = await PackCatalog.load();
  });
  testWidgets('appearance preview cancels without changing saved preferences', (tester) async {
    final c = AppController(UIStore(), catalog, 'ru'); await c.load();
    await tester.pumpWidget(LifeOSApp(controller: c));
    final context = tester.element(find.byType(HomeShell));
    Navigator.push<void>(context, MaterialPageRoute(builder: (_) => AppearanceEditor(controller: c)));
    await tester.pumpAndSettle();
    await tester.tap(find.text(c.pack.t('appearance_pistachio'))); await tester.pumpAndSettle();
    expect(c.appearance.palette, 'pistachio'); expect(c.preferences.containsKey('appearance_v1'), isFalse);
    await tester.pageBack(); await tester.pumpAndSettle();
    expect(c.appearance.palette, const Appearance().palette); expect(tester.takeException(), isNull);
  });
  testWidgets('note editor is full screen and keeps text after save failure', (tester) async {
    final store = UIStore()..failWrites = true;
    final c = AppController(store, catalog, 'ru'); await c.load();
    await tester.pumpWidget(LifeOSApp(controller: c));
    final context = tester.element(find.byType(HomeShell));
    showEntryEditor(context, c, EntryKind.note); await tester.pumpAndSettle();
    expect(find.byType(BottomSheet), findsNothing);
    await tester.enterText(find.byKey(const Key('entry_text')), 'Моя заметка');
    await tester.tap(find.byKey(const Key('save'))); await tester.pumpAndSettle();
    expect(find.text('Моя заметка'), findsOneWidget); expect(find.text(c.pack.t('save_failed')), findsOneWidget);
  });
  testWidgets('date shortcuts preserve repeat and reminder settings and No Date clears the schedule', (tester) async {
    final c = AppController(UIStore(), catalog, 'ru'); await c.load();
    ScheduleSpec? value = const ScheduleSpec(localStart:'2026-10-11T10:30:00',timezone:'UTC',repeat:RepeatRule.weekly,reminder:true);
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: StatefulBuilder(builder: (context, update) =>
      SingleChildScrollView(child: ScheduleEditor(controller: c, value: value, onChanged: (v) => update(() => value = v)))))));
    await tester.tap(find.text(c.pack.t('tomorrow'))); await tester.pumpAndSettle();
    expect(value!.repeat, RepeatRule.weekly); expect(value!.reminder, isTrue);
    final next = DateTime(c.now.year,c.now.month,c.now.day+1);
    expect(value!.localStart, '${dateOnly(next)}T10:30:00');
    await tester.tap(find.text(c.pack.t('no_date'))); await tester.pumpAndSettle(); expect(value, isNull);
    expect(tester.takeException(), isNull);
  });
  testWidgets('save remains reachable above a phone keyboard', (tester) async {
    final c = AppController(UIStore(), catalog, 'ru'); await c.load();
    tester.view.devicePixelRatio = 1; tester.view.physicalSize = const Size(320,844);
    addTearDown(tester.view.resetPhysicalSize); addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(LifeOSApp(controller: c, builder: (context, child) => MediaQuery(
      data: MediaQuery.of(context).copyWith(viewInsets: const EdgeInsets.only(bottom: 300)), child: child!)));
    await tester.tap(find.byKey(const Key('quick_expense'))); await tester.pumpAndSettle();
    final bounds = tester.getRect(find.byKey(const Key('save')));
    expect(bounds.bottom, lessThanOrEqualTo(544)); expect(tester.takeException(), isNull);
  });
  testWidgets('expense requires only amount; saving failure retains input', (tester) async {
    final store = UIStore();
    final controller = AppController(store, catalog, 'ru');
    await controller.load();
    await tester.pumpWidget(LifeOSApp(controller: controller));
    await tester.tap(find.byKey(const Key('quick_expense')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('amount')), '12,50');
    store.failWrites = true;
    await tester.tap(find.byKey(const Key('save')));
    await tester.pumpAndSettle();
    expect(find.text('12,50'), findsOneWidget);
    expect(find.text(controller.pack.t('save_failed')), findsOneWidget);
    store.failWrites = false;
    await tester.tap(find.byKey(const Key('save')));
    await tester.pumpAndSettle();
    expect(store.actions.length, 1);
    final action = store.actions.single as CreateMoney;
    expect(action.amount, '12,50');
    expect(action.label, '');
    expect(find.byKey(const Key('amount')), findsNothing);
  });
  testWidgets('Russian navigation fits a phone and changes to a tablet rail', (tester) async {
    final controller = AppController(UIStore(), catalog, 'ru');
    await controller.load();
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    tester.view.physicalSize = const Size(390, 844);
    await tester.pumpWidget(LifeOSApp(controller: controller));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('nav_today')), findsOneWidget);
    expect(find.byKey(const Key('nav_modules')), findsOneWidget);
    expect(find.byKey(const Key('add_button')), findsOneWidget);
    expect(tester.takeException(), isNull);
    tester.view.physicalSize = const Size(1100, 900);
    await tester.pumpAndSettle();
    expect(find.byType(NavigationRail), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  testWidgets('existing note opens shared edit form and keeps stable target and revision', (tester) async {
    final store = UIStore()..items = [Record(id: 'original-note', kind: EntryKind.note, text: 'Записанная заметка', createdAt: DateTime(2026,10,11), revision: 4)];
    final c = AppController(store, catalog, 'ru'); await c.load();
    await tester.pumpWidget(LifeOSApp(controller: c)); await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Записанная заметка'), 300); await tester.tap(find.text('Записанная заметка')); await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('edit_record'))); await tester.pumpAndSettle();
    expect(find.text('Записанная заметка'), findsWidgets);
    await tester.enterText(find.byKey(const Key('entry_text')), 'Исправленная заметка');
    await tester.ensureVisible(find.byKey(const Key('save'))); await tester.tap(find.byKey(const Key('save'))); await tester.pumpAndSettle();
    final edit = store.actions.single as EditNote;
    expect(edit.id, 'original-note'); expect(edit.expectedRevision, 4); expect(edit.body, 'Исправленная заметка');
    expect(edit.expectedScheduleRevision, 0);
  });
  testWidgets('calendar day navigation and financial period picker fit a narrow phone', (tester) async {
    tester.view.devicePixelRatio = 1; tester.view.physicalSize = const Size(320,844);
    addTearDown(tester.view.resetDevicePixelRatio); addTearDown(tester.view.resetPhysicalSize);
    final store = UIStore()..items = [Record(id: 'money', kind: EntryKind.income, text: 'Доход', createdAt: DateTime.now(),
      date: dateOnly(DateTime.now()), amountMinor: 10000, currency: Currency.fromCode('RUB'))];
    final c = AppController(store,catalog,'ru'); await c.load();
    await tester.pumpWidget(LifeOSApp(controller:c)); await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('financial_period'))); await tester.pumpAndSettle();
    expect(find.text(c.pack.t('current_month')),findsOneWidget); expect(tester.takeException(),isNull);
    await tester.tap(find.text(c.pack.t('cancel'))); await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('nav_plans'))); await tester.pumpAndSettle();
    final first = dateOnly(DateTime(DateTime.now().year,DateTime.now().month));
    await tester.tap(find.byKey(Key('day_$first'))); await tester.pumpAndSettle();
    expect(find.text(c.pack.t('empty_day')),findsOneWidget); expect(tester.takeException(),isNull);
  });
  testWidgets('large text home and settings remain scrollable without layout exceptions', (tester) async {
    tester.view.devicePixelRatio = 1; tester.view.physicalSize = const Size(320,844);
    addTearDown(tester.view.resetDevicePixelRatio); addTearDown(tester.view.resetPhysicalSize);
    final c = AppController(UIStore(),catalog,'ru'); await c.load();
    await tester.pumpWidget(LifeOSApp(controller:c, builder:(context,child) => MediaQuery(
      data:MediaQuery.of(context).copyWith(textScaler:const TextScaler.linear(1.5)),child:child!)));
    await tester.pumpAndSettle(); expect(tester.takeException(),isNull);
    await tester.tap(find.byKey(const Key('profile_button'))); await tester.pumpAndSettle();
    expect(find.text(c.pack.t('language')),findsOneWidget); expect(tester.takeException(),isNull);
  });

}
