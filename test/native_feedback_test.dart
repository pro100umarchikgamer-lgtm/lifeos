import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/cloud_record_detail.dart';
import 'package:lifeos/ui/design.dart';
import 'package:lifeos/ui/family.dart';
import 'package:lifeos/ui/family_dashboard.dart';
import 'package:lifeos/ui/money_format.dart';
import 'package:lifeos/ui/selection.dart';
import 'package:lifeos/ui/settings_surfaces.dart';
import 'controller_test.dart' show CountingStore, FakeNative;
import 'family_completion_visual_test.dart' show familyFixture;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  timezone.initializeTimeZones();
  late PackCatalog catalog;
  setUpAll(() async => catalog = await PackCatalog.load());

  testWidgets(
      'small selector opens at its field and supports keyboard and cancel',
      (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(390, 844);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    String selected = 'RUB';
    await tester.pumpWidget(MaterialApp(
        theme: lifeTheme(Brightness.light),
        home: Scaffold(
            body: Padding(
                padding: const EdgeInsets.fromLTRB(24, 160, 24, 0),
                child: StatefulBuilder(
                    builder: (context, setState) => LifeSelect<String>(
                        label: 'Currency',
                        value: selected,
                        choices: const {'RUB': 'Ruble', 'USD': 'Dollar'},
                        onChanged: (value) =>
                            setState(() => selected = value)))))));
    final field = tester.getRect(find.byType(InputDecorator));
    await tester.tap(find.byType(LifeSelect<String>));
    await tester.pumpAndSettle();
    expect(find.byType(BottomSheet), findsNothing);
    expect(find.byType(Dialog), findsNothing);
    final menu = tester.getRect(find.byKey(const Key('selection_dialog_body')));
    expect(menu.left, closeTo(field.left, 1));
    expect(menu.width, closeTo(field.width, 1));
    expect(menu.top - field.bottom, inInclusiveRange(0, 6));
    expect(menu.height, lessThan(200));
    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();
    expect(selected, 'RUB');
    expect(find.byKey(const Key('selection_dialog_body')), findsNothing);
    await tester.tap(find.byType(LifeSelect<String>));
    await tester.pumpAndSettle();
    await tester.sendKeyEvent(LogicalKeyboardKey.arrowDown);
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pumpAndSettle();
    expect(selected, 'USD');
    expect(find.text('Dollar'), findsOneWidget);
    await tester.tap(find.byType(LifeSelect<String>));
    await tester.pumpAndSettle();
    await tester.tapAt(const Offset(8, 8));
    await tester.pumpAndSettle();
    expect(selected, 'USD');
    expect(find.byKey(const Key('selection_dialog_body')), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'account management has single card controls and no record browser',
      (tester) async {
    final family = familyFixture();
    addTearDown(family.dispose);
    family.spaces.single['kind'] = 'personal';
    family.roster!['space']['kind'] = 'personal';
    final pack = catalog.packs['en']!;
    await tester.pumpWidget(MaterialApp(
        theme: lifeTheme(Brightness.light),
        home: FamilyPage(controller: family, pack: pack)));
    await tester.pumpAndSettle();
    final manage = find.widgetWithText(SettingsRow, pack.t('account_manage'));
    expect(find.ancestor(of: manage, matching: find.byType(SettingsGroup)),
        findsOneWidget);
    await tester.drag(find.byType(ListView).first, const Offset(0, -700));
    await tester.pumpAndSettle();
    expect(find.text('Семейный кошелёк'), findsNothing);
    expect(find.text('Планы на выходные'), findsNothing);
    expect(find.text(pack.t('family_record_add')), findsNothing);
    final space = find.byKey(const ValueKey('managed_space_family'));
    await tester.ensureVisible(space);
    expect(find.ancestor(of: space, matching: find.byType(SettingsGroup)),
        findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'cloud Today has cards, exact monthly currencies and account action',
      (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(320, 844);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final c =
        AppController(CountingStore(), catalog, 'en', platform: FakeNative());
    await c.load();
    addTearDown(c.dispose);
    final family = familyFixture();
    family.spaces.single['kind'] = 'personal';
    family.roster!['space']['kind'] = 'personal';
    family.records.first['data']['opening_minor'] = 9007199254740991;
    c.family = family;
    final today = dateOnly(c.now);
    for (final (id, currency, minor, date) in [
      ('kwd', 'KWD', 12345, today),
      ('rub', 'RUB', 5010, today),
      ('old', 'RUB', 999999, '2000-01-01'),
    ]) {
      family.records.add({
        'id': id,
        'revision': 1,
        'kind': 'transaction',
        'visibility': 'private',
        'data': {
          'kind': 'expense',
          'currency': currency,
          'amount_minor': minor,
          'date': date,
          'label': id,
          'account_id': null
        }
      });
    }
    await tester.pumpWidget(MaterialApp(
        theme: lifeTheme(Brightness.light),
        builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context)
                .copyWith(textScaler: const TextScaler.linear(1.4)),
            child: child!),
        home: Scaffold(
            body: SingleChildScrollView(
                padding: const EdgeInsets.all(16),
                child: FamilyDashboard(controller: c)))));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('cloud_today_tasks')), findsOneWidget);
    expect(find.byKey(const Key('cloud_quick_task')), findsOneWidget);
    final finance = find.byKey(const Key('cloud_today_expenses'));
    await tester.ensureVisible(finance);
    for (final (code, minor) in [('KWD', 12345), ('RUB', 5010)]) {
      expect(
          find.descendant(
              of: finance,
              matching: find.text(formatMoney(Currency.fromCode(code), minor,
                  locale: c.region))),
          findsOneWidget);
    }
    expect(tester.takeException(), isNull);
    final balance = find.byKey(const Key('cloud_current_balance'));
    await tester.ensureVisible(balance);
    await tester.tap(balance);
    await tester.pumpAndSettle();
    expect(find.byType(CloudRecordDetail), findsOneWidget);
    expect(find.text('Семейный кошелёк'), findsAtLeastNWidgets(1));
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets(
      'Today handles empty and large completed sets and child action rights',
      (tester) async {
    final c =
        AppController(CountingStore(), catalog, 'en', platform: FakeNative());
    await c.load();
    addTearDown(c.dispose);
    final family = familyFixture();
    family.records = [];
    family.spaces.single['kind'] = 'personal';
    family.roster!['space']['kind'] = 'personal';
    c.family = family;
    await tester.pumpWidget(MaterialApp(
        theme: lifeTheme(Brightness.dark),
        home: Scaffold(
            body: SingleChildScrollView(
                padding: const EdgeInsets.all(16),
                child: FamilyDashboard(controller: c)))));
    await tester.pumpAndSettle();
    expect(find.text(c.pack.t('today_no_open_tasks')), findsOneWidget);
    expect(find.text(c.pack.t('today_no_month_expenses')), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsNothing);
    expect(find.byKey(const Key('cloud_current_balance')), findsNothing);
    family.records = [
      for (var index = 0; index < 1024; index++)
        {
          'id': 'task$index',
          'kind': 'task',
          'visibility': 'private',
          'data': {'title': 'Task $index', 'completed': 1}
        }
    ];
    family.publish();
    await tester.pumpAndSettle();
    final card = find.byKey(const Key('cloud_today_tasks'));
    expect(find.descendant(of: card, matching: find.text('0')), findsOneWidget);
    expect(find.text('${c.pack.t('completed')}: 1024 / 1024'), findsOneWidget);
    expect(
        tester
            .widget<LinearProgressIndicator>(
                find.byType(LinearProgressIndicator))
            .value,
        1);
    family.records.first['data']['completed'] = 0;
    family.publish();
    await tester.pumpAndSettle();
    expect(find.descendant(of: card, matching: find.text('1')), findsOneWidget);
    expect(find.text('Task 0'), findsOneWidget);
    expect(find.text('${c.pack.t('completed')}: 1023 / 1024'), findsOneWidget);
    family.roster!['space']
        .addAll({'role': 'child', 'profile_id': 'child-profile'});
    family.roster!['profiles'] = [
      {
        'id': 'child-profile',
        'permissions': ['record_spending', 'create_tasks']
      }
    ];
    family.publish();
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('cloud_quick_expense')), findsOneWidget);
    expect(find.byKey(const Key('cloud_quick_task')), findsOneWidget);
    expect(find.byKey(const Key('cloud_quick_income')), findsNothing);
    expect(find.byKey(const Key('cloud_quick_note')), findsNothing);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
}
