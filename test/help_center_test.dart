import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/ui/help_center.dart';
import 'package:lifeos/localization/language_pack.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late PackCatalog catalog;
  setUpAll(() async => catalog = await PackCatalog.load());
  testWidgets('selected language updates help without rewriting typed search',
      (tester) async {
    final selected = ValueNotifier(catalog.resolve('de'));
    addTearDown(selected.dispose);
    await tester.pumpWidget(ValueListenableBuilder<LanguagePack>(
      valueListenable: selected,
      builder: (context, pack, _) => LanguagePackScope(
          pack: pack,
          child: MaterialApp(
            home: HelpCenterScreen(
                pack: catalog.resolve('ru'), onOpenLink: (_) async {}),
          )),
    ));
    expect(find.text(catalog.resolve('de').t('help_title')), findsOneWidget);
    await tester.enterText(
        find.byKey(const Key('help_search')), 'PRIVATE USER QUERY');
    selected.value = catalog.resolve('uz-Cyrl');
    await tester.pumpAndSettle();
    expect(
        find.text(catalog.resolve('uz-Cyrl').t('help_title')), findsOneWidget);
    expect(find.text('PRIVATE USER QUERY'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  testWidgets('help works without an account and search reveals useful answers',
      (tester) async {
    final links = <Uri>[];
    await tester.pumpWidget(MaterialApp(
        home: HelpCenterScreen(
            pack: catalog.resolve('ru'),
            onOpenLink: (uri) async => links.add(uri))));
    expect(find.text('Найдём ответ'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('help_search')), 'удалить');
    await tester.pumpAndSettle();
    expect(find.text('Ответов: 1'), findsOneWidget);
    expect(find.textContaining('24 часов'), findsOneWidget);
    await tester.tap(find.text('Подробнее на сайте'));
    await tester.pumpAndSettle();
    expect(links.single.toString(),
        'https://getuladim.space/faq?lang=ru#deletion');
    await tester.enterText(
        find.byKey(const Key('help_search')), 'nothingmatches');
    await tester.pumpAndSettle();
    expect(find.text('Ответов: 0'), findsOneWidget);
    expect(find.textContaining('Попробуйте другое слово'), findsOneWidget);
    await tester.tap(find.byTooltip('Очистить поиск'));
    await tester.pumpAndSettle();
    expect(find.text('Ответов: 11'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('large text and narrow screen keep help readable',
      (tester) async {
    tester.view.physicalSize = const Size(320, 780);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(
        builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context)
                .copyWith(textScaler: const TextScaler.linear(1.5)),
            child: child!),
        home: HelpCenterScreen(
            pack: catalog.resolve('en'), onOpenLink: (_) async {})));
    await tester.enterText(find.byKey(const Key('help_search')), 'trackers');
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
        find.textContaining('advertising trackers'), 250,
        scrollable: find.byType(Scrollable).first);
    expect(find.textContaining('advertising trackers'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
