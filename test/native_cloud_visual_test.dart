import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/appearance.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/app.dart';
import 'package:lifeos/ui/appearance_editor.dart';
import 'package:lifeos/ui/family.dart';
import 'package:lifeos/ui/cloud_record_detail.dart';
import 'controller_test.dart' show CountingStore, FakeNative;
import 'family_completion_visual_test.dart' show familyFixture;

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
  for (final size in [const Size(390, 844), const Size(820, 1100)]) {
    for (final mode in ['light', 'dark']) {
      testWidgets(
          'cloud destinations and account read/edit ${size.width} $mode',
          (tester) async {
        tester.view.devicePixelRatio = 1;
        tester.view.physicalSize = size;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final c = AppController(CountingStore(), catalog, 'ru',
            platform: FakeNative());
        await c.load();
        c.preferences['active_scope'] = 'family';
        c.previewAppearance(
            Appearance(palette: 'pistachio', mode: mode, intensity: 70));
        final f = familyFixture();
        f.spaces.single.addAll(
            {'kind': 'personal', 'name': 'Моё пространство', 'role': 'owner'});
        f.roster!['space'].addAll({'kind': 'personal', 'role': 'owner'});
        f.records.first['data'].addAll({
          'name': 'TBank — основной счёт для повседневных расходов',
          'opening_minor': 0
        });
        f.records[1]['editable'] = true;
        f.records[2]['data']['body'] =
            'Планы на выходные\nВыбрать маршрут, купить билеты и провести время с близкими.\nВажные детали всегда под рукой.';
        final today = dateOnly(c.now);
        f.records.addAll([
          {
            'id': 'salary',
            'revision': 1,
            'kind': 'transaction',
            'visibility': 'private',
            'audience': [],
            'editable': true,
            'data': {
              'kind': 'income',
              'amount_minor': 24000000,
              'currency': 'RUB',
              'date': today,
              'label': 'Зарплата',
              'account_id': 'shared-account'
            }
          },
          {
            'id': 'purchase',
            'revision': 1,
            'kind': 'transaction',
            'visibility': 'private',
            'audience': [],
            'editable': true,
            'data': {
              'kind': 'expense',
              'amount_minor': 400000,
              'currency': 'RUB',
              'date': today,
              'label': 'Покупка продуктов',
              'account_id': 'shared-account'
            }
          },
          {
            'id': 'budget',
            'revision': 1,
            'kind': 'budget',
            'visibility': 'private',
            'audience': [],
            'editable': true,
            'data': {
              'name': 'Повседневные расходы',
              'limit_minor': 3000000,
              'currency': 'RUB',
              'period': 'month',
              'start_on': '${today.substring(0, 7)}-01',
              'end_on': null,
              'rollover': 'none',
              'participants': []
            }
          },
          {
            'id': 'event',
            'revision': 1,
            'kind': 'event',
            'visibility': 'private',
            'audience': [],
            'editable': true,
            'data': {
              'title': 'Встреча с близкими',
              'schedule': {
                'localStart': '${today}T18:30:00',
                'timezone': 'UTC',
                'allDay': false,
                'repeat': 'weekly',
                'interval': 1,
                'until': null
              }
            }
          },
        ]);
        c.family = f;
        final boundary = GlobalKey();
        await tester.pumpWidget(LifeOSApp(
            controller: c,
            builder: (context, child) => MediaQuery(
                data: MediaQuery.of(context).copyWith(
                    textScaler: TextScaler.linear(size.width > 600 ? 1.3 : 1)),
                child: RepaintBoundary(key: boundary, child: child!))));
        await tester.pumpAndSettle();
        Future<void> capture(String name) async {
          expect(tester.takeException(), isNull);
          final directory = Platform.environment['ULADIM_NATIVE_EVIDENCE'];
          if (directory == null) return;
          await tester.runAsync(() async {
            final renderer = boundary.currentContext!.findRenderObject()!
                as RenderRepaintBoundary;
            final image = await renderer.toImage(pixelRatio: 1);
            final bytes =
                await image.toByteData(format: ui.ImageByteFormat.png);
            await Directory(directory).create(recursive: true);
            await File('$directory/$name-${size.width.toInt()}-$mode.png')
                .writeAsBytes(bytes!.buffer.asUint8List());
            image.dispose();
          });
        }

        await capture('today');
        for (final (index, name) in [
          (1, 'tasks'),
          (2, 'calendar'),
          (3, 'notes'),
          (4, 'finances')
        ]) {
          if (size.width > 600) {
            final rail =
                tester.widget<NavigationRail>(find.byType(NavigationRail));
            await tester.tap(find.byWidget(rail.destinations[index].label));
          } else {
            await tester.tap(find.byKey(Key('nav_$name')));
          }
          await tester.pumpAndSettle();
          await capture(name);
        }
        await tester.ensureVisible(
            find.text('TBank — основной счёт для повседневных расходов'));
        await tester
            .tap(find.text('TBank — основной счёт для повседневных расходов'));
        await tester.pumpAndSettle();
        expect(find.byType(CloudRecordDetail), findsOneWidget);
        expect(find.byType(TextField), findsNothing);
        expect(find.text(c.pack.t('opening_balance')), findsOneWidget);
        await capture('account-read');
        await tester.tap(find.byKey(const Key('cloud_record_edit')));
        await tester.pumpAndSettle();
        expect(find.byType(FamilyRecordEditor), findsOneWidget);
        expect(find.widgetWithText(TextField, '0.00'), findsOneWidget);
        await capture('account-edit');
        if (size.width < 600) {
          tester.view.viewInsets = const FakeViewPadding(bottom: 300);
          addTearDown(tester.view.resetViewInsets);
          await tester.pumpAndSettle();
          await tester.ensureVisible(find.text(c.pack.t('save')));
          await tester.pumpAndSettle();
          await capture('account-edit-keyboard');
          tester.view.resetViewInsets();
          await tester.pumpAndSettle();
        }
        Navigator.of(tester.element(find.byType(FamilyRecordEditor))).push<
                void>(
            MaterialPageRoute(builder: (_) => AppearanceEditor(controller: c)));
        await tester.pumpAndSettle();
        expect(find.byType(Slider), findsOneWidget);
        await tester.ensureVisible(find.byType(Slider));
        await tester.pumpAndSettle();
        await capture('appearance');
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pumpAndSettle();
        c.dispose();
      });
    }
  }
}
