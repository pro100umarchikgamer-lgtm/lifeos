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
    addTearDown(tester.view.resetViewInsets);
    final capture = GlobalKey();
    final changes = <int>[];
    await tester.pumpWidget(RepaintBoundary(
        key: capture,
        child: MaterialApp(
            debugShowCheckedModeBanner: false,
            home: Scaffold(
                body: Padding(
                    padding: const EdgeInsets.fromLTRB(24, 160, 24, 0),
                    child: LifeSelect<int>(
                      label: 'Currency',
                      value: 2,
                      choices: {for (var i = 0; i < 30; i++) i: 'Currency $i'},
                      searchLabel: 'Search currencies',
                      dialog: true,
                      onChanged: changes.add,
                    ))))));
    final field = tester.getRect(find.byType(InputDecorator));
    await tester.tap(find.byType(LifeSelect<int>));
    await tester.pumpAndSettle();
    final menu = find.byKey(const Key('selection_dialog_body'));
    final search = find.byKey(const Key('selection_search'));
    final choices =
        find.descendant(of: menu, matching: find.byType(SingleChildScrollView));
    expect(menu, findsOneWidget);
    expect(choices, findsOneWidget);
    final menuBounds = tester.getRect(menu);
    final searchBounds = tester.getRect(search);
    final choicesBounds = tester.getRect(choices);
    expect(menuBounds.left, closeTo(field.left, 1));
    expect(menuBounds.width, closeTo(field.width, 1));
    expect(menuBounds.top - field.bottom, inInclusiveRange(0, 6));
    expect(menuBounds.height, inInclusiveRange(180, 400));
    expect(menuBounds.bottom, lessThanOrEqualTo(836));
    expect(searchBounds.top, greaterThan(menuBounds.top));
    expect(searchBounds.bottom, lessThanOrEqualTo(choicesBounds.top));
    final selected = find.byKey(const ValueKey('choice_2'));
    expect(selected.hitTestable(), findsOneWidget);
    final scrollable = tester.state<ScrollableState>(
        find.descendant(of: choices, matching: find.byType(Scrollable)));
    final initialOffset = scrollable.position.pixels;
    Future<List<int>> headerPixels() async {
      final image = await (capture.currentContext!.findRenderObject()
              as RenderRepaintBoundary)
          .toImage();
      final data =
          (await image.toByteData(format: ui.ImageByteFormat.rawRgba))!;
      final result = <int>[];
      // Compare the entire fixed header, including its bottom divider.
      for (var y = menuBounds.top.ceil(); y < choicesBounds.top.floor(); y++) {
        for (var x = menuBounds.left.ceil();
            x < menuBounds.right.floor();
            x++) {
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
    expect(before, isNotEmpty);
    await tester.drag(choices, const Offset(0, -205));
    await tester.pumpAndSettle();
    expect(scrollable.position.pixels, greaterThan(initialOffset + 150));
    expect(
        tester.getRect(selected).bottom, lessThanOrEqualTo(choicesBounds.top));
    expect(tester.getRect(menu), menuBounds);
    expect(tester.getRect(search), searchBounds);
    expect(tester.getRect(choices), choicesBounds);
    expect(await tester.runAsync(headerPixels), before);
    if (const bool.fromEnvironment('ULADIM_CAPTURE')) {
      await expectLater(find.byType(MaterialApp),
          matchesGoldenFile('native_inbox_goldens/currency_scrolled.png'));
    }
    await tester.enterText(search, 'Currency 29');
    tester.view.viewInsets = const FakeViewPadding(bottom: 300);
    await tester.pumpAndSettle();
    final result = find.byKey(const ValueKey('choice_29'));
    expect(result.hitTestable(), findsOneWidget);
    expect(selected, findsNothing);
    expect(find.byKey(const ValueKey('choice_28')), findsNothing);
    final keyboardMenu = tester.getRect(menu);
    expect(keyboardMenu.left, closeTo(field.left, 1));
    expect(keyboardMenu.width, closeTo(field.width, 1));
    expect(keyboardMenu.top - field.bottom, inInclusiveRange(0, 6));
    expect(keyboardMenu.bottom, lessThanOrEqualTo(536));
    expect(
        tester.getRect(result).bottom, lessThanOrEqualTo(keyboardMenu.bottom));
    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();
    expect(menu, findsNothing);
    expect(changes, isEmpty);
    expect(find.text('Currency 2'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
