import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/action_engine.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/app.dart';

// Isolated UI benchmark. Never opens, writes or restores a user's database.
class ProfileStore implements ActionStore {
  final items = List.generate(1000, (i) => Record(id:'profile-$i',kind:EntryKind.expense,
    text:'Profile fixture $i',createdAt:DateTime.now(),amountMinor:10000,
    currency:const Currency('USD',2),date:dateOnly(DateTime.now())));
  @override
  Future<List<Record>> records() async => items;
  @override
  Future<String> apply(AppAction action) async => throw UnsupportedError('read-only fixture');
  @override
  Future<Map<String,String>> settings() async => {'language':'ru'};
  @override
  Future<void> setSetting(String key,String value) async {}
  @override
  Future<void> close() async {}
}
void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  timezone.initializeTimeZones();
  testWidgets('profile navigation and scrolling with 1000 transactions', (tester) async {
    if (!kProfileMode) throw StateError('Run this benchmark with flutter drive --profile on a physical device.');
    final controller = AppController(ProfileStore(),await PackCatalog.load(),'ru'); await controller.load();
    await tester.pumpWidget(LifeOSApp(controller:controller)); await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('nav_finances'))); await tester.pumpAndSettle();
    await binding.watchPerformance(() async {
      for (var i=0;i<10;i++) {
        await tester.fling(find.byType(ListView).first,const Offset(0,-600),1500);
        await tester.pumpAndSettle();
      }
    },reportKey:'finance_scroll_1000');
    await binding.watchPerformance(() async {
      for (var i=0;i<10;i++) {
        await tester.tap(find.byKey(const Key('nav_today'))); await tester.pumpAndSettle();
        await tester.tap(find.byKey(const Key('nav_finances'))); await tester.pumpAndSettle();
      }
    },reportKey:'navigation');
    expect(tester.takeException(),isNull);
  });
}
