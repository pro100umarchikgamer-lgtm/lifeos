import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/sync/contracts.dart';
import 'package:lifeos/sync/controller.dart';
import 'package:lifeos/ui/account_center.dart';
import 'package:lifeos/ui/design.dart';
import 'package:lifeos/ui/subscription_access.dart';
import 'support/sync_memory.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late PackCatalog catalog;
  setUpAll(() async => catalog = await PackCatalog.load());

  for (final brightness in Brightness.values) {
    testWidgets('plans remain readable in all locales at 320px $brightness',
        (tester) async {
      tester.view.devicePixelRatio = 1;
      tester.view.physicalSize = const Size(320, 844);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.view.resetPhysicalSize);
      for (final pack in catalog.packs.values) {
        await tester.pumpWidget(MaterialApp(
          theme: lifeTheme(brightness),
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context)
                .copyWith(textScaler: const TextScaler.linear(1.4)),
            child: child!,
          ),
          home: Scaffold(
            body: ListView(padding: const EdgeInsets.all(16), children: [
              SubscriptionAccess(
                pack: pack,
                access: const {'tier': 'Free', 'valid_until': null},
                verified: true,
              ),
            ]),
          ),
        ));
        await tester.pumpAndSettle();
        expect(find.text('${pack.t('plans_current_access')}: Free'),
            findsOneWidget,
            reason: pack.tag);
        await tester.ensureVisible(find.text(pack.t('plans_no_billing')));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull, reason: pack.tag);
        expect(find.byWidgetPredicate((widget) => widget is ButtonStyleButton),
            findsNothing);
        expect(find.text(pack.t('plan_premium_description')), findsOneWidget);
      }
    });
  }

  testWidgets('cached access and legacy Premium never offer AI or payment',
      (tester) async {
    final pack = catalog.packs['en']!;
    for (final access in [
      {'tier': 'Premium', 'valid_until': null},
      {'tier': 'Plus', 'valid_until': 1},
      {'tier': 'Plus', 'valid_until': null},
    ]) {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: SubscriptionAccess(
              pack: pack,
              access: access,
              verified: false,
            ),
          ),
        ),
      ));
      expect(find.text(pack.t('plans_access_unverified')), findsOneWidget);
      expect(
          find.text('${pack.t('plans_current_access')}: Plus'), findsNothing);
      expect(find.text('${pack.t('plans_current_access')}: Premium'),
          findsNothing);
      expect(find.byWidgetPredicate((widget) => widget is ButtonStyleButton),
          findsNothing);
    }
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: SubscriptionAccess(
            pack: pack,
            access: const {'tier': 'Premium', 'valid_until': null},
            verified: true,
          ),
        ),
      ),
    ));
    expect(
        find.text('${pack.t('plans_current_access')}: Premium'), findsNothing);
    expect(
        find.text('Premium · ${pack.t('plans_unavailable')}'), findsOneWidget);
  });

  testWidgets('access opens offline without claiming a confirmed subscription',
      (tester) async {
    final pack = catalog.packs['en']!;
    final controller = FamilyController(MemorySyncStore())
      ..account = {'email': 'fixture@example.test'};
    addTearDown(controller.dispose);
    Future<Json> offline(String path, {Json? body}) async =>
        throw const SyncFailure('offline');
    await tester.pumpWidget(MaterialApp(
      home: AccountCenter(
        controller: controller,
        pack: pack,
        request: offline,
      ),
    ));
    await tester.tap(find.text(pack.t('account_access')));
    await tester.pumpAndSettle();
    expect(find.text(pack.t('plans_available_free')), findsOneWidget);
    expect(find.text(pack.t('plans_access_unverified')), findsOneWidget);
    expect(find.text('${pack.t('plans_current_access')}: Plus'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
