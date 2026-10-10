import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/action_engine.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/app.dart';

class UIStore implements ActionStore {
  final List<AppAction> actions = [];
  bool failWrites = false;
  @override
  Future<String> apply(AppAction action) async {
    if (failWrites) throw const DomainFailure('save_failed');
    actions.add(action);
    return 'id';
  }
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
  late PackCatalog catalog;
  setUpAll(() async {
    catalog = await PackCatalog.load();
  });
  testWidgets('expense requires only amount; saving failure retains input', (tester) async {
    final store = UIStore();
    final controller = AppController(store, catalog, 'ru');
    await controller.load();
    await tester.pumpWidget(LifeOSApp(controller: controller));
    await tester.tap(find.byKey(const Key('quick_expense')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('amount')), '12,50');
    store.failWrites = true;
    await tester.tap(find.byKey(const Key('save')));
    await tester.pumpAndSettle();
    expect(find.text('12,50'), findsOneWidget);
    expect(find.text(controller.pack.t('save_failed')), findsOneWidget);
    store.failWrites = false;
    await tester.tap(find.byKey(const Key('save')));
    await tester.pumpAndSettle();
    expect(store.actions.length, 1);
    final action = store.actions.single as CreateMoney;
    expect(action.amount, '12,50');
    expect(action.label, '');
    expect(find.byKey(const Key('amount')), findsNothing);
  });
  testWidgets('Russian navigation fits a phone and changes to a tablet rail', (tester) async {
    final controller = AppController(UIStore(), catalog, 'ru');
    await controller.load();
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    tester.view.physicalSize = const Size(390, 844);
    await tester.pumpWidget(LifeOSApp(controller: controller));
    await tester.pumpAndSettle();
    expect(find.byType(NavigationBar), findsOneWidget);
    expect(tester.takeException(), isNull);
    tester.view.physicalSize = const Size(1100, 900);
    await tester.pumpAndSettle();
    expect(find.byType(NavigationRail), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
