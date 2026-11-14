import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/app.dart';
import 'package:lifeos/ui/notification_center.dart';
import 'package:lifeos/ui/quick_add.dart';
import 'package:lifeos/domain/models.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'notification_center_test.dart' show InboxApi, message;
import 'widget_test.dart' show UIStore;
import 'notification_budget_preferences_test.dart' show BudgetInboxApi;
import 'package:lifeos/ui/notification_budget_settings.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  timezone.initializeTimeZones();
  late PackCatalog catalog;
  setUpAll(() async {
    catalog = await PackCatalog.load();
    final bytes = await File('test/fonts/NotoSans-Regular.ttf').readAsBytes();
    await (FontLoader('Roboto')
          ..addFont(Future.value(ByteData.sublistView(bytes))))
        .load();
    await (FontLoader('MaterialIcons')
          ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf')))
        .load();
  });
  for (final config in [(390.0, 1.0), (320.0, 1.6)]) {
    testWidgets('inbox readable at ${config.$1} and ${config.$2} text',
        (tester) async {
      tester.view.devicePixelRatio = 1;
      tester.view.physicalSize = Size(config.$1, 844);
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final c = AppController(UIStore(), catalog, 'ru');
      await c.load();
      addTearDown(c.dispose);
      final api = InboxApi()
        ..messages = [
          {
            ...message('a'),
            'title': 'Обновление ULADIM',
            'body':
                'Теперь важные сообщения всегда под рукой.\n\n${List.filled(20, 'Подробности обновления остаются в истории, и их можно прочитать в удобное время.').join('\n\n')}'
          },
          {
            ...message('b', readAt: 1700000001),
            'title': 'Новое в приложении',
            'body': 'История сохраняет прочитанные сообщения.'
          },
        ];
      await c.inbox.attachAccount('https://a.test|alice', api);
      await c.inbox.recordReminders([
        {
          'id': 'local:a',
          'entry_id': 'task',
          'title': 'Принять витамины',
          'body': 'Личное напоминание',
          'created_at': 1700000100,
          'status': 'delivered'
        }
      ]);
      await tester.pumpWidget(LifeOSApp(
          controller: c,
          builder: (ctx, child) => MediaQuery(
              data: MediaQuery.of(ctx)
                  .copyWith(textScaler: TextScaler.linear(config.$2)),
              child: child!)));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('notification_bell')), findsOneWidget);
      expect(tester.getRect(find.byKey(const Key('add_button'))).center.dx,
          greaterThan(config.$1 / 2));
      if (const bool.fromEnvironment('ULADIM_CAPTURE')) {
        await expectLater(
            find.byType(MaterialApp),
            matchesGoldenFile(
                'native_inbox_goldens/${config.$1.toInt()}_home.png'));
      }
      await tester.tap(find.byKey(const Key('notification_bell')));
      await tester.pumpAndSettle();
      expect(find.byType(NotificationInboxPage), findsOneWidget);
      expect(find.text('Принять витамины'), findsOneWidget);
      expect(tester.takeException(), isNull);
      if (const bool.fromEnvironment('ULADIM_CAPTURE')) {
        await expectLater(
            find.byType(MaterialApp),
            matchesGoldenFile(
                'native_inbox_goldens/${config.$1.toInt()}_inbox.png'));
      }
      await tester.ensureVisible(find.text('Обновление ULADIM'));
      await tester.tap(find.text('Обновление ULADIM'));
      await tester.pumpAndSettle();
      expect(find.byType(SelectableText), findsOneWidget);
      expect(tester.takeException(), isNull);
      if (const bool.fromEnvironment('ULADIM_CAPTURE')) {
        await expectLater(
            find.byType(MaterialApp),
            matchesGoldenFile(
                'native_inbox_goldens/${config.$1.toInt()}_detail.png'));
      }
    });
  }
  testWidgets(
      'startup fullscreen waits for an active draft and shows only once',
      (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(390, 844);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final c = AppController(UIStore(), catalog, 'ru');
    await c.load();
    addTearDown(c.dispose);
    await tester.pumpWidget(LifeOSApp(controller: c));
    await tester.pumpAndSettle();
    final context = tester.element(find.byType(HomeShell));
    showEntryEditor(context, c, EntryKind.note);
    await tester.pumpAndSettle();
    await tester.enterText(
        find.byKey(const Key('entry_text')), 'My draft survives');
    final api = InboxApi()
      ..messages = [
        {
          ...message('startup', presentation: 'fullscreen'),
          'title': 'Важные новости всегда под рукой',
          'body':
              'Новости приложения и важные сообщения теперь сохраняются здесь. Вы сможете вернуться к ним в разделе «Уведомления».',
          'created_at':
              DateTime(2026, 11, 13, 12).millisecondsSinceEpoch ~/ 1000
        }
      ];
    await c.inbox.attachAccount('https://a.test|alice', api);
    await tester.pumpAndSettle();
    expect(find.text('My draft survives'), findsOneWidget);
    expect(find.byKey(const Key('announcement_fullscreen')), findsNothing);
    // Return via the real editor cancellation flow without dropping its draft.
    Navigator.of(tester.element(find.byKey(const Key('entry_text')))).pop();
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('announcement_fullscreen')), findsOneWidget);
    if (const bool.fromEnvironment('ULADIM_CAPTURE')) {
      await expectLater(find.byType(MaterialApp),
          matchesGoldenFile('native_inbox_goldens/startup_fullscreen.png'));
    }
    await tester.tap(find.byKey(const Key('announcement_close')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('announcement_fullscreen')), findsNothing);
    await c.inbox.refresh();
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('announcement_fullscreen')), findsNothing);
    expect(tester.takeException(), isNull);
  });
  testWidgets('an open account message hides its content immediately on logout',
      (tester) async {
    final c = AppController(UIStore(), catalog, 'ru');
    await c.load();
    addTearDown(c.dispose);
    await c.inbox.attachAccount('https://a.test|alice', InboxApi());
    await tester.pumpWidget(LifeOSApp(controller: c));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('notification_bell')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('A helpful update'));
    await tester.pumpAndSettle();
    expect(find.text('Full details stay available in your history.'),
        findsOneWidget);
    await c.inbox.attachAccount(null, null);
    await tester.pumpAndSettle();
    expect(find.text('Full details stay available in your history.'),
        findsNothing);
  });
  testWidgets(
      'budget preferences remain readable and selectable at 320px with large text',
      (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(320, 844);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final c = AppController(UIStore(), catalog, 'ru');
    await c.load();
    addTearDown(c.dispose);
    final api = BudgetInboxApi();
    await c.inbox.attachAccount('https://a.test|alice', api);
    await tester.pumpWidget(LifeOSApp(
        controller: c,
        builder: (ctx, child) => MediaQuery(
            data: MediaQuery.of(ctx)
                .copyWith(textScaler: const TextScaler.linear(1.6)),
            child: child!)));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('notification_bell')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('inbox_budget_settings')));
    await tester.pumpAndSettle();
    expect(find.byType(NotificationBudgetSettingsPage), findsOneWidget);
    expect(c.inbox.budgetEnabled, isFalse);
    if (const bool.fromEnvironment('ULADIM_CAPTURE')) {
      await expectLater(
          find.byType(MaterialApp),
          matchesGoldenFile(
              'native_inbox_goldens/320_budget_preferences_top.png'));
    }
    final toggle = find.byKey(const Key('budget_reminders_enabled'));
    await tester.ensureVisible(toggle);
    await tester.tap(toggle);
    await tester.pumpAndSettle();
    expect(c.inbox.budgetEnabled, isTrue);
    final thresholds = find.byKey(const Key('budget_reminder_thresholds'));
    await tester.ensureVisible(thresholds);
    await tester.tap(thresholds);
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const ValueKey('choice_10')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('choice_10')));
    await tester.pumpAndSettle();
    expect(api.settings['budget_thresholds'],
        [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]);
    expect(tester.takeException(), isNull);
    if (const bool.fromEnvironment('ULADIM_CAPTURE')) {
      await expectLater(find.byType(MaterialApp),
          matchesGoldenFile('native_inbox_goldens/320_budget_preferences.png'));
    }
  });
}
