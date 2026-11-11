import 'package:lifeos/ui/quick_add.dart';
import 'package:lifeos/domain/models.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/design.dart';
import 'package:lifeos/ui/dashboard_editor.dart';
import 'widget_test.dart' show UIStore;

void main() {
  late PackCatalog catalog;
  setUpAll(() async {
    timezone.initializeTimeZones();
    catalog = await PackCatalog.load();
  });
  test('Clarity uses the shared web light and dark surfaces', () {
    expect(lifeTheme(Brightness.light).scaffoldBackgroundColor,
        const Color(0xfff7f8f7));
    expect(lifeTheme(Brightness.dark).scaffoldBackgroundColor,
        const Color(0xff101a18));
  });
  testWidgets('compact cards preserve readable content without heavy shadows',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
        theme: lifeTheme(Brightness.light),
        home: const Scaffold(body: LifeCard(child: Text('Daily task')))));
    final card = tester.widget<Container>(find
        .descendant(of: find.byType(LifeCard), matching: find.byType(Container))
        .first);
    expect(card.padding, const EdgeInsets.all(14));
    expect((card.decoration as BoxDecoration).boxShadow, isNull);
    expect(find.text('Daily task'), findsOneWidget);
  });
  test('Today prioritizes daily tasks by default and preserves saved ordering',
      () async {
    final c = AppController(UIStore(), catalog, 'ru');
    await c.load();
    expect(
        (dashboardChoice(c, 'tasks')['position'] as int) <
            (dashboardChoice(c, 'financial')['position'] as int),
        isTrue);
    c.dispose();
  });

  testWidgets(
      'financial entry uses a dedicated page with an exact localized amount',
      (tester) async {
    timezone.initializeTimeZones();
    final store = UIStore();
    final c = AppController(store, catalog, 'ru');
    await c.load();
    await tester.pumpWidget(MaterialApp(
        home: Builder(
            builder: (context) => Scaffold(
                body: TextButton(
                    onPressed: () =>
                        showEntryEditor(context, c, EntryKind.expense),
                    child: const Text('Open'))))));
    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
    expect(find.byType(BottomSheet), findsNothing);
    await tester.enterText(find.byKey(const Key('amount')), '12,50');
    await tester.pump();
    await tester.ensureVisible(find.byKey(const Key('save')));
    await tester.tap(find.byKey(const Key('save')));
    await tester.pumpAndSettle();
    expect((store.actions.single as CreateMoney).amount, '12,50');
    expect(tester.takeException(), isNull);
    c.dispose();
  });
}
