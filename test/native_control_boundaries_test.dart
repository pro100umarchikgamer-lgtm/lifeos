import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/appearance_editor.dart';
import 'package:lifeos/ui/design.dart';
import 'package:lifeos/ui/selection.dart';
import 'package:timezone/data/latest.dart' as timezone;

import 'controller_test.dart' show CountingStore, FakeNative;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  timezone.initializeTimeZones();
  late PackCatalog catalog;
  setUpAll(() async => catalog = await PackCatalog.load());

  testWidgets('a selection label is passive; its value opens the choices',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      theme: lifeTheme(Brightness.light),
      home: Scaffold(
        body: Padding(
          padding: const EdgeInsets.all(24),
          child: LifeSelect<String>(
            label: 'Currency',
            value: 'RUB',
            choices: const {'RUB': 'Russian ruble', 'USD': 'US dollar'},
            onChanged: (_) {},
          ),
        ),
      ),
    ));
    await tester.tap(find.text('Currency'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('selection_dialog_body')), findsNothing);
    await tester.tap(find.text('Russian ruble'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('selection_dialog_body')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('a card action responds inside its rounded visible surface only',
      (tester) async {
    var opened = 0;
    await tester.pumpWidget(MaterialApp(
      theme: lifeTheme(Brightness.light),
      home: Scaffold(
        body: Padding(
          padding: const EdgeInsets.all(24),
          child: LifeCard(
            key: const Key('action_card'),
            padding: EdgeInsets.zero,
            child: ListTile(
              title: const Text('Invite friends'),
              onTap: () => opened++,
            ),
          ),
        ),
      ),
    ));
    final rect = tester.getRect(find.byKey(const Key('action_card')));
    await tester.tapAt(rect.topLeft + const Offset(1, 1));
    await tester.pumpAndSettle();
    expect(opened, 0, reason: 'The transparent corner is outside the card.');
    await tester.tap(find.text('Invite friends'));
    await tester.pumpAndSettle();
    expect(opened, 1);
  });

  testWidgets('background intensity previews without saving until Apply',
      (tester) async {
    final store = CountingStore();
    final c = AppController(store, catalog, 'en', platform: FakeNative());
    await c.load();
    addTearDown(c.dispose);
    await tester.pumpWidget(MaterialApp(
      theme: lifeTheme(Brightness.light),
      home: AppearanceEditor(controller: c),
    ));
    await tester.pumpAndSettle();
    final slider = find.byType(Slider);
    expect(slider, findsOneWidget);
    await tester.ensureVisible(slider);
    await tester.drag(slider, const Offset(80, 0));
    await tester.pumpAndSettle();
    final preview = jsonDecode(c.appearance.encode()) as Map<String, dynamic>;
    expect(preview['intensity'], isA<num>());
    expect(preview['intensity'], isNot(50));
    expect(store.preferences.containsKey('appearance_v1'), isFalse);
    await tester.tap(find.byKey(const Key('apply_appearance')));
    await tester.pumpAndSettle();
    final saved = jsonDecode(store.preferences['appearance_v1']!)
        as Map<String, dynamic>;
    expect(saved['intensity'], preview['intensity']);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
  });
}
