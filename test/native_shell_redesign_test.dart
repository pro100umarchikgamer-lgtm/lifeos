import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/app.dart';
import 'package:lifeos/ui/design.dart';
import 'package:lifeos/ui/global_search.dart';
import 'package:lifeos/ui/selection.dart';
import 'visual_snapshot_test.dart' show SnapshotStore, sampleRecords;

const boundaryKey = Key('native_shell_capture');
Future<void> capture(WidgetTester tester, String name) async {
  expect(tester.takeException(), isNull);
  final boundary =
      tester.renderObject<RenderRepaintBoundary>(find.byKey(boundaryKey));
  await tester.runAsync(() async {
    final picture = await boundary.toImage(pixelRatio: 1);
    final bytes = await picture.toByteData(format: ui.ImageByteFormat.png);
    final directory = Directory('web_evidence/native-shell');
    await directory.create(recursive: true);
    await File('${directory.path}/$name.png')
        .writeAsBytes(bytes!.buffer.asUint8List());
    picture.dispose();
  });
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
  for (final scenario in [
    (390.0, 'light', true),
    (320.0, 'dark', false),
    (834.0, 'dark', true)
  ]) {
    testWidgets('clear native destinations ${scenario.$1} ${scenario.$2}',
        (tester) async {
      tester.view.devicePixelRatio = 1;
      tester.view.physicalSize = Size(scenario.$1, 1000);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.view.resetPhysicalSize);
      final c = AppController(
          SnapshotStore(scenario.$3 ? sampleRecords() : [], scenario.$2),
          catalog,
          'ru');
      await c.load();
      await tester.pumpWidget(LifeOSApp(
          controller: c,
          builder: (_, child) =>
              RepaintBoundary(key: boundaryKey, child: child!)));
      await tester.pumpAndSettle();
      await capture(tester, '${scenario.$1.toInt()}-${scenario.$2}-today');
      expect(find.byType(FloatingActionButton), findsNothing);
      if (scenario.$1 < 720) {
        expect(tester.getRect(find.byKey(const Key('nav_profile'))).right,
            lessThanOrEqualTo(scenario.$1));
      }
      expect(find.byKey(const Key('add_button')), findsOneWidget);
      if (scenario.$1 < 720) {
        for (final tab in [
          'today',
          'tasks',
          'calendar',
          'notes',
          'finances',
          'profile'
        ]) {
          final target = find.byKey(Key('nav_$tab'));
          expect(target, findsOneWidget);
          expect(tester.getSize(target).height, greaterThanOrEqualTo(44));
          await tester.ensureVisible(target);
          await tester.tap(target);
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);
        }
        await capture(tester, '${scenario.$1.toInt()}-${scenario.$2}-profile');
        await tester.ensureVisible(find.byKey(const Key('nav_modules')));
        await tester.tap(find.byKey(const Key('nav_modules')));
        await tester.pumpAndSettle();
        expect(find.text(c.pack.t('modules')), findsWidgets);
        expect(tester.takeException(), isNull);
      }
      await tester.pumpWidget(const SizedBox.shrink());
      c.dispose();
    });
  }

  testWidgets(
      'currency choices stay closed then bounded and searchable above keyboard',
      (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(390, 844);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetViewInsets);
    var selected = 'RUB';
    await tester.pumpWidget(MaterialApp(
        theme: lifeTheme(Brightness.light),
        builder: (_, child) => RepaintBoundary(key: boundaryKey, child: child!),
        home: Scaffold(
            body: SafeArea(
                child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: StatefulBuilder(
                        builder: (_, update) => LifeSelect<String>(
                              label: 'Валюта',
                              value: selected,
                              choices: const {
                                'RUB': 'RUB · Российский рубль',
                                'USD': 'USD · Доллар США'
                              },
                              searchLabel: 'Код или название',
                              queryChoices: (query) =>
                                  query.toUpperCase().contains('KWD')
                                      ? {'KWD': 'KWD · Кувейтский динар'}
                                      : {},
                              onChanged: (v) => update(() => selected = v),
                            )))))));
    expect(find.byKey(const Key('selection_search')), findsNothing);
    await tester.tap(find.byType(LifeSelect<String>));
    await tester.pumpAndSettle();
    final picker = find.byKey(const Key('selection_dialog_body'));
    expect(tester.getSize(picker).height, lessThan(600));
    await capture(tester, '390-light-currency');
    await tester.enterText(find.byKey(const Key('selection_search')), 'KWD');
    tester.view.viewInsets = const FakeViewPadding(bottom: 300);
    await tester.pumpAndSettle();
    final option = find.byKey(const ValueKey('choice_KWD'));
    expect(tester.getRect(option).bottom, lessThanOrEqualTo(544));
    await capture(tester, '390-light-currency-keyboard');
    await tester.tap(option);
    await tester.pumpAndSettle();
    expect(selected, 'KWD');
    expect(find.byKey(const Key('selection_search')), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('search preserves long record and opens readable detail',
      (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(390, 844);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    final c = AppController(
        SnapshotStore([
          Record(
              id: 'long-note',
              kind: EntryKind.note,
              createdAt: DateTime(2026, 11, 13),
              text:
                  'Длинная заметка о поездке\n${List.filled(8, 'Сохранить документы и выбрать удобное время без спешки.').join(' ')}'),
        ], 'dark'),
        catalog,
        'ru');
    await c.load();
    await tester.pumpWidget(MaterialApp(
        theme: lifeTheme(Brightness.dark),
        builder: (_, child) => RepaintBoundary(key: boundaryKey, child: child!),
        home: GlobalSearchPage(controller: c, family: false)));
    await tester.pumpAndSettle();
    await tester.enterText(
        find.byKey(const Key('global_search_input')), 'Длинная');
    await tester.pumpAndSettle();
    await capture(tester, '390-dark-search');
    await tester.tap(find.textContaining('Длинная заметка').first);
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('edit_record')), findsOneWidget);
    await capture(tester, '390-dark-record');
    await tester.pumpWidget(const SizedBox.shrink());
    c.dispose();
  });
  testWidgets('multiline controls grow with large accessibility text',
      (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(320, 844);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    await tester.pumpWidget(MaterialApp(
        theme: lifeTheme(Brightness.dark),
        builder: (_, child) => MediaQuery(
            data: const MediaQueryData(
                size: Size(320, 844), textScaler: TextScaler.linear(1.5)),
            child: RepaintBoundary(key: boundaryKey, child: child!)),
        home: Scaffold(
            body: SafeArea(
                child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: SizedBox(
                        width: double.infinity,
                        child: OutlinedButton(
                          key: const Key('large_multiline_control'),
                          onPressed: () {},
                          child: const Text('Срок цели\n(необязательно)'),
                        )))))));
    await tester.pumpAndSettle();
    final control =
        tester.getRect(find.byKey(const Key('large_multiline_control')));
    final text = tester.getRect(find.text('Срок цели\n(необязательно)'));
    expect(text.top - control.top, greaterThanOrEqualTo(10));
    expect(control.bottom - text.bottom, greaterThanOrEqualTo(10));
    await capture(tester, '320-dark-large-controls');
  });
}
