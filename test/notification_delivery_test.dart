import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/action_engine.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/platform/native_bridge.dart';
import 'package:lifeos/ui/settings.dart';
import 'package:timezone/data/latest.dart' as timezone;

class AndroidNativeBridge extends NativeBridge {
  @override
  bool get supported => true;
}

class NotificationSettingsStore implements ActionStore {
  @override
  Future<String> apply(AppAction action) async => 'id';
  @override
  Future<List<Record>> records() async => [];
  @override
  Future<Map<String, String>> settings() async => {'language': 'ru'};
  @override
  Future<void> setSetting(String key, String value) async {}
  @override
  Future<void> close() async {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  timezone.initializeTimeZones();
  final messenger =
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  final native = AndroidNativeBridge();
  late PackCatalog catalog;
  setUpAll(() async => catalog = await PackCatalog.load());
  tearDown(
      () => messenger.setMockMethodCallHandler(NativeBridge.channel, null));

  test(
      'an unconfirmed or legacy null native response never claims a posted notification',
      () async {
    for (final response in [
      null,
      <String, Object?>{},
      {'status': 'unexpected'},
      {'status': 'unconfirmed'}
    ]) {
      messenger.setMockMethodCallHandler(
          NativeBridge.channel, (_) async => response);
      final result = await native.testNotification({'title': 'ULADIM'});
      expect(result.status, NotificationTestStatus.unconfirmed);
    }
  });

  test('OS-posted confirmation is returned through the native bridge',
      () async {
    messenger.setMockMethodCallHandler(NativeBridge.channel, (call) async {
      expect(call.method, 'testNotification');
      expect((call.arguments as Map)['title'], 'ULADIM');
      return {'status': 'posted'};
    });
    expect((await native.testNotification({'title': 'ULADIM'})).status,
        NotificationTestStatus.posted);
  });

  test('app permission and per-channel blocks remain distinguishable',
      () async {
    for (final reason in ['permission', 'channel']) {
      messenger.setMockMethodCallHandler(NativeBridge.channel,
          (_) async => {'status': 'blocked', 'reason': reason});
      final result = await native.testNotification({'title': 'ULADIM'});
      expect(result.status, NotificationTestStatus.blocked);
      expect(result.channelBlocked, reason == 'channel');
    }
  });

  test('a platform posting failure is never converted into success', () async {
    messenger.setMockMethodCallHandler(NativeBridge.channel,
        (_) async => throw PlatformException(code: 'native_failed'));
    await expectLater(native.testNotification({'title': 'ULADIM'}),
        throwsA(isA<PlatformException>()));
  });

  testWidgets('settings show actual channel limits and the posting result',
      (tester) async {
    var status = 'blocked';
    messenger.setMockMethodCallHandler(NativeBridge.channel, (call) async {
      if (call.method == 'testNotification') {
        return {'status': status, 'reason': 'channel'};
      }
      return null;
    });
    final c = AppController(
        NotificationSettingsStore(), catalog, 'ru',
        platform: native);
    await c.load();
    addTearDown(c.dispose);
    c.notificationStatus = {
      'supported': true,
      'enabled': true,
      'channels': {
        'standard': {'importance': 2, 'sound': true},
        'important': {'importance': 4, 'sound': true},
        'alarm': {'importance': 0, 'sound': true},
      },
    };
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: PersonalSettings(controller: c, section: 1),
        ),
      ),
    ));
    await tester.tap(find.text(c.pack.t('notification_details')));
    await tester.pumpAndSettle();
    expect(
        find.text(
            '${c.pack.t('notification_priority_silent')}\n${c.pack.t('audible_restricted')}'),
        findsOneWidget);
    expect(
        find.text(
            '${c.pack.t('notification_priority_high')}\n${c.pack.t('audible_enabled')}'),
        findsOneWidget);
    final button =
        find.widgetWithText(FilledButton, c.pack.t('test_notification'));
    await tester.scrollUntilVisible(button, 250);
    await tester.tap(button);
    await tester.pumpAndSettle();
    expect(find.text(c.pack.t('notification_channel_blocked')), findsOneWidget);
    expect(find.text(c.pack.t('test_notification_posted')), findsNothing);
    status = 'posted';
    await tester.tap(button);
    await tester.pumpAndSettle();
    // SnackBars queue, so let the first result expire before inspecting the next.
    await tester.pump(const Duration(seconds: 5));
    await tester.pumpAndSettle();
    expect(find.text(c.pack.t('test_notification_posted')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
