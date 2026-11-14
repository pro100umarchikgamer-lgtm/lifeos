import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/sync/api.dart';
import 'package:lifeos/sync/contracts.dart';
import 'package:lifeos/sync/controller.dart';
import 'package:lifeos/ui/account_center.dart';
import 'package:lifeos/ui/appearance_editor.dart';
import 'package:lifeos/ui/dashboard_editor.dart';
import 'package:lifeos/ui/design.dart';
import 'package:lifeos/ui/family.dart';
import 'package:lifeos/ui/family_dashboard.dart';
import 'package:lifeos/ui/personal_modules.dart';
import 'package:lifeos/ui/settings.dart';
import 'support/sync_memory.dart';
import 'visual_snapshot_test.dart' show SnapshotStore;
import 'family_completion_visual_test.dart' show familyFixture;

class _LoginApi extends FamilyApi {
  _LoginApi() : super('https://example.test');
  @override
  Future<Json> request(String path, {Json? body}) async =>
      {'google_enabled': true};
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  timezone.initializeTimeZones();
  late PackCatalog catalog;
  setUpAll(() async {
    final bytes = await File('test/fonts/NotoSans-Regular.ttf').readAsBytes();
    await (FontLoader('Roboto')
          ..addFont(Future.value(ByteData.sublistView(bytes))))
        .load();
    await (FontLoader('MaterialIcons')
          ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf')))
        .load();
    catalog = await PackCatalog.load();
  });
  for (final config in [
    (390.0, Brightness.light, 1.0),
    (320.0, Brightness.dark, 1.4)
  ]) {
    testWidgets('account design readable ${config.$1} ${config.$2}',
        (tester) async {
      tester.view.devicePixelRatio = 1;
      tester.view.physicalSize = Size(config.$1, 844);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.view.resetPhysicalSize);
      final c = AppController(SnapshotStore([], config.$2.name), catalog, 'ru');
      await c.load();
      final pack = catalog.packs['ru']!;
      Future<void> show(Widget widget, String screen) async {
        await tester.pumpWidget(MaterialApp(
            debugShowCheckedModeBanner: false,
            theme: lifeTheme(config.$2),
            locale: pack.locale,
            supportedLocales: [pack.locale],
            localizationsDelegates: const [
              MaterialFallbackDelegate(),
              WidgetsFallbackDelegate(),
              CupertinoFallbackDelegate()
            ],
            builder: (context, child) => MediaQuery(
                data: MediaQuery.of(context)
                    .copyWith(textScaler: TextScaler.linear(config.$3)),
                child: child!),
            home: widget));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull, reason: screen);
        if (const bool.fromEnvironment('ULADIM_CAPTURE')) {
          await expectLater(
              find.byType(MaterialApp),
              matchesGoldenFile(
                  'native_account_goldens/${config.$1.toInt()}_${config.$2.name}_$screen.png'));
        }
      }

      await show(
          Scaffold(
              appBar: AppBar(title: Text(pack.t('profile'))),
              body: SafeArea(
                  child: ListView(
                      padding: const EdgeInsets.all(16),
                      children: [PersonalSettings(controller: c)]))),
          'settings');
      expect(find.byKey(const Key('settings_1')), findsOneWidget);
      await show(
          Scaffold(
              appBar: AppBar(title: Text(pack.t('language_region'))),
              body: ListView(
                  padding: const EdgeInsets.all(16),
                  children: [PersonalSettings(controller: c, section: 0)])),
          'language');
      await show(AppearanceEditor(controller: c), 'appearance');
      await show(DashboardEditor(controller: c), 'dashboard');
      final local = FamilyController(MemorySyncStore());
      await show(
          FamilyPage(
              key: const ValueKey('local'), controller: local, pack: pack),
          'local');
      expect(find.byType(TextField), findsNothing);
      final cloud =
          FamilyController(MemorySyncStore(), apiFactory: (_) => _LoginApi())
            ..api = _LoginApi();
      await show(
          FamilyPage(
              key: const ValueKey('cloud'), controller: cloud, pack: pack),
          'login');
      expect(find.byType(TextField), findsNWidgets(2));
      expect(find.text(pack.t('family_optional')), findsNothing);
      final family = familyFixture();
      family.account!['email'] = 'owner@example.test';
      await show(
          FamilyPage(
              key: const ValueKey('family'), controller: family, pack: pack),
          'family');
      Future<Json> request(String path, {Json? body}) async => switch (path) {
            '/v1/account/entitlements' => {'tier': 'Free', 'valid_until': null},
            '/v1/account/devices' => {
                'devices': [
                  {
                    'id': 'device',
                    'label': 'Android · Pixel',
                    'last_seen_at': 1700000000,
                    'revoked_at': 0
                  }
                ]
              },
            '/v1/support' => {'tickets': []},
            _ => {'request': null, 'ownership_transfer_required': []},
          };
      await show(
          AccountCenter(controller: family, pack: pack, request: request),
          'account');
      for (final section in [
        'account_access',
        'account_devices',
        'account_privacy'
      ]) {
        await tester.ensureVisible(find.text(pack.t(section)));
        await tester.tap(find.text(pack.t(section)));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull, reason: section);
        if (const bool.fromEnvironment('ULADIM_CAPTURE')) {
          await expectLater(
              find.byType(MaterialApp),
              matchesGoldenFile(
                  'native_account_goldens/${config.$1.toInt()}_${config.$2.name}_$section.png'));
        }
        await tester.tap(find.byType(BackButton));
        await tester.pumpAndSettle();
      }
      c.offline[OfflineTable.projects] = [
        for (var i = 0; i < 12; i++)
          {
            'id': 'project$i',
            'name': 'Ремонт кухни · этап ${i + 1}',
            'goal': 'Удобное пространство',
            'status': 'active',
            'revision': 1
          }
      ];
      await show(
          PersonalModulesPage(controller: c, table: OfflineTable.projects),
          'projects');
      expect(find.text(pack.t('delete')), findsNothing);
      await tester.tap(find.text('Ремонт кухни · этап 1'));
      await tester.pumpAndSettle();
      expect(find.text(pack.t('edit')), findsOneWidget);
      await tester.tap(find.text(pack.t('edit')));
      await tester.pumpAndSettle();
      expect(find.widgetWithText(TextField, 'Ремонт кухни · этап 1'),
          findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
      c.dispose();
      local.dispose();
      cloud.dispose();
      family.dispose();
    });
  }
  testWidgets('family destinations keep one kind and child create rights',
      (tester) async {
    final c = AppController(SnapshotStore([], 'light'), catalog, 'ru');
    await c.load();
    final family = familyFixture(child: true);
    c.family = family;
    family.records.addAll([
      {
        'id': 'event',
        'kind': 'event',
        'visibility': 'shared',
        'data': {
          'title': 'Calendar only',
          'schedule': {'localStart': '2026-11-13T09:00:00'}
        }
      },
      {
        'id': 'shopping',
        'kind': 'shopping',
        'visibility': 'shared',
        'data': {'name': 'Shopping only', 'items': []}
      },
    ]);
    for (final kinds in [
      <String>{'event'},
      <String>{'task'},
      <String>{'note'},
      <String>{'shopping'}
    ]) {
      await tester.pumpWidget(MaterialApp(
          theme: lifeTheme(Brightness.light),
          home: Scaffold(
              body: SingleChildScrollView(
                  child:
                      FamilyDashboard(controller: c, visibleKinds: kinds)))));
      await tester.pumpAndSettle();
      expect(find.text('Calendar only'),
          kinds.contains('event') ? findsOneWidget : findsNothing);
      expect(find.text('Shopping only'),
          kinds.contains('shopping') ? findsOneWidget : findsNothing);
      expect(find.text('Подготовить вещи к поездке'),
          kinds.contains('task') ? findsOneWidget : findsNothing);
      expect(find.text('Планы на выходные'),
          kinds.contains('note') ? findsOneWidget : findsNothing);
      if (kinds.contains('event')) {
        expect(find.byType(FilledButton), findsNothing);
      }
      expect(tester.takeException(), isNull);
    }
    final parent = familyFixture();
    c.family = parent;
    await tester.pumpWidget(MaterialApp(
        theme: lifeTheme(Brightness.light),
        locale: catalog.packs['ru']!.locale,
        supportedLocales: [catalog.packs['ru']!.locale],
        localizationsDelegates: const [
          MaterialFallbackDelegate(),
          WidgetsFallbackDelegate(),
          CupertinoFallbackDelegate()
        ],
        home: Scaffold(
            body: SingleChildScrollView(
                child: FamilyDashboard(
                    controller: c, visibleKinds: const {'event'})))));
    await tester.pumpAndSettle();
    await tester.tap(find.text(c.pack.t('family_record_add')));
    await tester.pumpAndSettle();
    expect(find.text(c.pack.t('all_day')), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
    c.dispose();
    family.dispose();
  });
}
