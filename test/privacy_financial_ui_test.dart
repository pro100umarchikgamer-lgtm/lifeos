import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/ui/family.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/sync/controller.dart';
import 'package:lifeos/sync/api.dart';
import 'support/sync_memory.dart';
import 'privacy_financial_projection_test.dart' show row;
import 'google_login_test.dart' show LoginApi;
import 'package:lifeos/sync/contracts.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late PackCatalog catalog;
  setUpAll(() async => catalog = await PackCatalog.load());
  testWidgets(
      'a surviving transfer shows its exact amounts and currencies without editing erased accounts',
      (tester) async {
    final store = MemorySyncStore();
    final c = FamilyController(store)
      ..api = FamilyApi('https://example.test')
      ..account = {'user_id': 'alice', 'verified': true}
      ..workspace = 'family'
      ..roster = {
        'space': {'role': 'parent'}
      };
    addTearDown(c.dispose);
    await store.receive(c.scope, 'family', {
      'protocol': 2,
      'epoch': 'erase',
      'reset': true,
      'cursor': 3,
      'more': false,
      'records': [
        row('live', 'account', {
          'name': 'Own yen account',
          'currency': 'JPY',
          'opening_minor': 1000
        }),
        row('deleted', 'account', {},
            deleted: 1, erased: true, structural: true, currency: 'USD'),
        row('transfer', 'transfer', {
          'from_id': 'deleted',
          'to_id': 'live',
          'sent_minor': 1250,
          'received_minor': 1900,
          'date': '2026-11-13'
        }),
      ]
    });
    await c.reloadLocal();
    final transfer = c.records.singleWhere((r) => r['id'] == 'transfer');
    await tester.pumpWidget(MaterialApp(
        home: FamilyRecordEditor(
            controller: c, pack: catalog.packs['en']!, record: transfer)));
    await tester.pumpAndSettle();
    expect(find.textContaining('12.50'), findsOneWidget);
    expect(find.textContaining('1,900'), findsOneWidget);
    expect(find.byType(TextField), findsNothing);
    expect(find.text(catalog.packs['en']!.t('save')), findsNothing);
    expect(find.text(catalog.packs['en']!.t('delete')), findsNothing);
    expect(tester.takeException(), isNull);
    expect(transfer['data']['sent_minor'], 1250);
    expect(transfer['data']['received_minor'], 1900);
  });
  testWidgets(
      'an already-open erased account loses old text and money fields immediately',
      (tester) async {
    final store = MemorySyncStore();
    final c = FamilyController(store)
      ..api = FamilyApi('https://example.test')
      ..account = {'user_id': 'alice', 'verified': true}
      ..workspace = 'family'
      ..roster = {
        'space': {'role': 'parent'}
      };
    addTearDown(c.dispose);
    await store.receive(c.scope, 'family', {
      'protocol': 2,
      'epoch': 'old',
      'reset': true,
      'cursor': 1,
      'more': false,
      'records': [
        row('deleted', 'account', {
          'name': 'Hidden owner name',
          'currency': 'USD',
          'opening_minor': 999999
        })
      ]
    });
    await c.reloadLocal();
    final old = c.records.single;
    await tester.pumpWidget(MaterialApp(
        home: FamilyRecordEditor(
            controller: c, pack: catalog.packs['en']!, record: old)));
    await tester.pumpAndSettle();
    expect(find.text('Hidden owner name'), findsOneWidget);
    await store.receive(c.scope, 'family', {
      'protocol': 2,
      'epoch': 'erased',
      'reset': true,
      'cursor': 2,
      'more': false,
      'records': [
        row('deleted', 'account', {},
            deleted: 1, erased: true, structural: true, currency: 'USD')
      ]
    });
    await c.reloadLocal();
    await tester.pumpAndSettle();
    expect(find.text('Hidden owner name'), findsNothing);
    expect(find.byType(TextField), findsNothing);
    expect(old['data'], isEmpty);
    expect(tester.takeException(), isNull);
  });
  testWidgets('a pending delete cannot change a transfer after its account is erased',
      (tester) async {
    final store = MemorySyncStore();
    final c = FamilyController(store)
      ..api = LoginApi('https://example.test',
          (path, body) async => throw const SyncFailure('offline'))
      ..account = {'user_id': 'alice', 'verified': true}
      ..workspace = 'family'
      ..roster = {'space': {'role': 'parent'}};
    addTearDown(c.dispose);
    final transfer = row('transfer', 'transfer', {
      'from_id': 'deleted', 'to_id': 'live', 'sent_minor': 1250,
      'received_minor': 1900, 'date': '2026-11-13'
    });
    c.records = [
      row('deleted', 'account', {'name': 'USD', 'currency': 'USD',
        'opening_minor': 0}),
      row('live', 'account', {'name': 'JPY', 'currency': 'JPY',
        'opening_minor': 1000}),
      transfer,
    ];
    await tester.pumpWidget(MaterialApp(home: FamilyRecordEditor(
        controller: c, pack: catalog.packs['en']!, record: transfer)));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text(catalog.packs['en']!.t('delete')));
    await tester.pumpAndSettle();
    await tester.tap(find.text(catalog.packs['en']!.t('delete')));
    await tester.pumpAndSettle();
    c.records.removeWhere((r) => r['id'] == 'deleted');
    c.referenceCurrencies = {'deleted': 'USD'};
    c.erasedRecordIds = {'deleted'};
    c.publish();
    await tester.pump();
    await tester.tap(find.text(catalog.packs['en']!.t('confirm')));
    await tester.pumpAndSettle();
    expect(await store.pending(c.scope, 'family'), isEmpty);
    expect(find.byType(TextField), findsNothing);
    expect(transfer['data']['sent_minor'], 1250);
    expect(transfer['data']['received_minor'], 1900);
    expect(tester.takeException(), isNull);
  });
}
