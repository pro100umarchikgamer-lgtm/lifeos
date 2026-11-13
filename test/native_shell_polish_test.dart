import 'dart:ui' as ui;
import 'dart:io';
import 'package:flutter/services.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/app.dart';
import 'package:lifeos/ui/calendar.dart';
import 'package:lifeos/ui/selection.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'widget_test.dart' show UIStore;

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
  testWidgets('calendar opens a full month and keeps it after selecting a date',
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
    await tester.tap(find.byKey(const Key('nav_calendar')));
    await tester.pumpAndSettle();
    expect(find.byType(CalendarGrid), findsOneWidget);
    if (const bool.fromEnvironment('ULADIM_CAPTURE')) {
      await expectLater(find.byType(MaterialApp),
          matchesGoldenFile('native_inbox_goldens/calendar_full_month.png'));
    }
    final now = c.now;
    await tester.tap(find.byKey(Key(
        'day_${DateTime(now.year, now.month, 1).toIso8601String().substring(0, 10)}')));
    await tester.pumpAndSettle();
    expect(find.byType(CalendarGrid), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  testWidgets(
      'scrolling selected currency never paints over the fixed picker header',
      (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(390, 844);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final capture = GlobalKey();
    await tester.pumpWidget(RepaintBoundary(
        key: capture,
        child: MaterialApp(
            debugShowCheckedModeBanner: false,
            home: Scaffold(
                body: LifeSelect<int>(
              label: 'Currency',
              value: 2,
              choices: {for (var i = 0; i < 30; i++) i: 'Currency $i'},
              searchLabel: 'Search currencies',
              dialog: true,
              onChanged: (_) {},
            )))));
    await tester.tap(find.byType(LifeSelect<int>));
    await tester.pumpAndSettle();
    final search = tester.getRect(find.byKey(const Key('selection_search')));
    Future<List<int>> headerPixels() async {
      final image = await (capture.currentContext!.findRenderObject()
              as RenderRepaintBoundary)
          .toImage();
      final data =
          (await image.toByteData(format: ui.ImageByteFormat.rawRgba))!;
      final result = <int>[];
      for (var y = search.top.toInt() - 42; y < search.bottom.toInt(); y++) {
        for (var x = 24; x < 366; x++) {
          final offset = (y * image.width + x) * 4;
          result.addAll([
            data.getUint8(offset),
            data.getUint8(offset + 1),
            data.getUint8(offset + 2)
          ]);
        }
      }
      image.dispose();
      return result;
    }

    final before = await tester.runAsync(headerPixels);
    await tester.drag(
        find.descendant(
            of: find.byType(BottomSheet), matching: find.byType(ListView)),
        const Offset(0, -205));
    await tester.pumpAndSettle();
    expect(await tester.runAsync(headerPixels), before);
    if (const bool.fromEnvironment('ULADIM_CAPTURE')) {
      await expectLater(find.byType(MaterialApp),
          matchesGoldenFile('native_inbox_goldens/currency_scrolled.png'));
    }
    expect(tester.takeException(), isNull);
  });
}
