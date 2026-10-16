import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/sync/contracts.dart';
import 'package:lifeos/sync/controller.dart';
import 'package:lifeos/ui/account_center.dart';
import 'package:lifeos/ui/design.dart';
import 'support/sync_memory.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late PackCatalog catalog;
  setUpAll(() async {
    for (final entry in {
      'Roboto': 'test/fonts/NotoSans-Regular.ttf',
      'NotoSansGeorgian': 'assets/fonts/NotoSansGeorgian.ttf',
      'NotoSansArmenian': 'assets/fonts/NotoSansArmenian.ttf',
    }.entries) {
      final bytes = await File(entry.value).readAsBytes();
      await (FontLoader(entry.key)..addFont(Future.value(ByteData.sublistView(bytes)))).load();
    }
    await (FontLoader('MaterialIcons')..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
    catalog = await PackCatalog.load();
  });
  for (final tag in ['en','ru','kk','uz-Latn','uz-Cyrl','uk','de','fr','es','it','pt','ka','az','hy','tg','ky']) {
    for (final mode in ['light','dark']) {
      for (final width in (tag == 'en' || tag == 'ru' ? [320,390,430] : [320])) {
        testWidgets('account rendered $tag $mode $width', (tester) async {
          tester.view.devicePixelRatio = 1;
          tester.view.physicalSize = Size(width.toDouble(), 844);
          addTearDown(tester.view.resetPhysicalSize);
          addTearDown(tester.view.resetDevicePixelRatio);
          final c = FamilyController(MemorySyncStore())..account = {'email': 'fixture@example.test'};
          addTearDown(c.dispose);
          final pack = catalog.packs[tag]!;
          Future<Json> request(String path, {Json? body}) async => switch (path) {
            '/v1/account/entitlements' => {'tier': 'Free', 'valid_until': null},
            '/v1/account/devices' => {'devices': [{'id': 'synthetic-device', 'label': 'Android · Pixel', 'last_seen_at': 1700000000, 'revoked_at': 0}]},
            '/v1/support' => {'tickets': []},
            _ => {'request': null, 'ownership_transfer_required': []},
          };
          await tester.pumpWidget(MaterialApp(debugShowCheckedModeBanner: false,
            locale: pack.locale, supportedLocales: [pack.locale],
            localizationsDelegates: const [MaterialFallbackDelegate(),WidgetsFallbackDelegate(),CupertinoFallbackDelegate()],
            theme: lifeTheme(mode == 'dark' ? Brightness.dark : Brightness.light),
            builder: (context, child) => MediaQuery(data: MediaQuery.of(context).copyWith(textScaler: const TextScaler.linear(1.4)),child: child!),
            home: AccountCenter(controller: c, pack: pack, request: request)));
          await tester.pumpAndSettle();
          expect(tester.takeException(),isNull);
          await expectLater(find.byType(MaterialApp), matchesGoldenFile('control_goldens/${tag}_${mode}_${width}_hub.png'));
          if (tag == 'en' || tag == 'ru') {
            for (final key in ['account_access','account_devices','account_support','account_privacy']) {
              await tester.ensureVisible(find.text(pack.t(key)));
              await tester.tap(find.text(pack.t(key)));
              await tester.pumpAndSettle();
              expect(tester.takeException(),isNull);
              await expectLater(find.byType(MaterialApp), matchesGoldenFile('control_goldens/${tag}_${mode}_${width}_$key.png'));
              expect(find.byType(BackButton), findsOneWidget);
              await tester.tap(find.byType(BackButton));
              await tester.pumpAndSettle();
              expect(find.text(pack.t('account_manage')), findsOneWidget);
            }
          }
        });
      }
    }
  }
}
