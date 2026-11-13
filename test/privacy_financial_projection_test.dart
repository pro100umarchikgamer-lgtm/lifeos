import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/sync/record_projection.dart';
import 'package:lifeos/sync/controller.dart';
import 'package:lifeos/sync/api.dart';
import 'package:lifeos/sync/contracts.dart';
import 'package:lifeos/domain/family_finance.dart';
import 'support/sync_memory.dart';

Json row(String id, String kind, Json data,
        {int deleted = 0,
        bool erased = false,
        bool structural = false,
        String? currency}) =>
    {
      'id': id,
      'workspace_id': 'family',
      'owner_id': 'peer',
      'kind': kind,
      'revision': 2,
      'deleted': deleted,
      'visibility': 'shared',
      'audience': [],
      'editable': deleted == 0,
      'data': data,
      if (erased) 'privacy_erased': true,
      if (structural) 'structural_reference': true,
      if (currency != null) 'reference_currency': currency,
    };
void main() {
  test(
      'structural accounts retain only immutable currency metadata, never owner content',
      () {
    final value = projectSyncRecord(row('deleted', 'account', {},
        deleted: 1, erased: true, structural: true, currency: 'USD')
      ..addAll({
        'name': 'private-name',
        'opening_minor': 999999,
        'owner_email': 'erased@example.test'
      }));
    expect(value, {
      'id': 'deleted',
      'workspace_id': 'family',
      'kind': 'account',
      'revision': 2,
      'deleted': 1,
      'editable': false,
      'data': {},
      'privacy_erased': true,
      'structural_reference': true,
      'reference_currency': 'USD'
    });
    expect(isActiveSyncRecord(value), isFalse);
  });
  test(
      'non-empty structural data is rejected instead of caching hidden amounts',
      () {
    expect(
        () => projectSyncRecord(row(
            'deleted', 'account', {'opening_minor': 999},
            deleted: 1, erased: true, structural: true, currency: 'USD')),
        throwsA(isA<SyncFailure>()));
  });
  test('mirror keeps currency stub but active controller accounts exclude it',
      () async {
    final store = MemorySyncStore();
    final c = FamilyController(store)
      ..api = FamilyApi('https://example.test')
      ..account = {'user_id': 'alice', 'verified': true}
      ..workspace = 'family';
    await store.receive(c.scope, 'family', {
      'protocol': 2,
      'epoch': 'new',
      'reset': true,
      'cursor': 3,
      'more': false,
      'records': [
        row('live', 'account',
            {'name': 'Own account', 'currency': 'JPY', 'opening_minor': 1000}),
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
    expect((await store.records(c.scope, 'family')).map((r) => r['id']),
        contains('deleted'));
    expect(c.records.where((r) => r['kind'] == 'account').map((r) => r['id']),
        ['live']);
    expect(c.referenceCurrencies, {'deleted': 'USD'});
    expect(c.accountCurrency('deleted'), 'USD');
    expect(c.accountCurrency('live'), 'JPY');
    expect(const FamilyFinance().accountBalance(c.records.first, c.records),
        BigInt.from(2900));
    final transfer = c.records.singleWhere((r) => r['id'] == 'transfer');
    expect(transfer['data'], {
      'from_id': 'deleted',
      'to_id': 'live',
      'sent_minor': 1250,
      'received_minor': 1900,
      'date': '2026-11-13'
    });
    c.dispose();
  });
  test(
      'privacy tombstones prune old queued edit and restore payloads; dependent own work is quarantined',
      () async {
    final store = MemorySyncStore();
    for (final op in [
      {
        'id': 'old-edit',
        'record_id': 'deleted',
        'action': 'record.update',
        'data': {'name': 'private-name', 'opening_minor': 999999}
      },
      {'id': 'old-restore', 'record_id': 'deleted', 'action': 'record.restore'},
      {
        'id': 'own-edit',
        'record_id': 'own',
        'action': 'record.update',
        'data': {
          'account_id': 'deleted',
          'amount_minor': 1250,
          'currency': 'USD'
        }
      },
    ]) {
      await store.enqueue('scope', 'family', op);
    }
    await store.receive('scope', 'family', {
      'protocol': 2,
      'epoch': 'new',
      'reset': true,
      'cursor': 1,
      'more': false,
      'records': [
        row('deleted', 'account', {},
            deleted: 1, erased: true, structural: true, currency: 'USD')
      ]
    });
    expect(await store.pending('scope', 'family'), isEmpty);
    expect(
        store.outbox.values
            .any((v) => v['operation']['record_id'] == 'deleted'),
        isFalse);
    expect((await store.issues('scope', 'family')).single['result']['error'],
        'invalid_reference');
    await expectLater(
        store.enqueue('scope', 'family', {
          'id': 'revive',
          'record_id': 'deleted',
          'action': 'record.restore'
        }),
        throwsA(isA<SyncFailure>()));
  });
  test('ordinary grant resets still retain unsent local work', () async {
    final store = MemorySyncStore();
    await store.enqueue('scope', 'family', {
      'id': 'draft',
      'record_id': 'private',
      'action': 'record.update',
      'data': {'body': 'My unsent draft'}
    });
    await store.receive('scope', 'family', {
      'protocol': 2,
      'epoch': 'acl',
      'reset': true,
      'cursor': 1,
      'more': false,
      'records': []
    });
    expect((await store.pending('scope', 'family')).single['data']['body'],
        'My unsent draft');
  });
  test(
      'erased non-account tombstones also scrub payloads and remove queued revival',
      () async {
    final store = MemorySyncStore();
    await store.enqueue('scope', 'family', {
      'id': 'note-edit',
      'record_id': 'note',
      'action': 'record.update',
      'data': {'body': 'Erased owner text'}
    });
    final erased = row('note', 'note', {}, deleted: 1, erased: true)
      ..['editable'] = true;
    await store.receive('scope', 'family', {
      'protocol': 2,
      'epoch': 'erase',
      'reset': true,
      'cursor': 2,
      'more': false,
      'records': [erased]
    });
    final saved = (await store.records('scope', 'family')).single;
    expect(saved['data'], isEmpty);
    expect(saved['editable'], isFalse);
    expect(saved.containsKey('owner_id'), isFalse);
    expect(store.outbox, isEmpty);
  });
  test(
      'detached peer transactions preserve their own amount currency date and identity',
      () {
    final transaction = row('peer-transaction', 'transaction', {
      'kind': 'expense',
      'label': 'My purchase',
      'currency': 'USD',
      'amount_minor': 550,
      'date': '2026-11-13',
      'account_id': null
    });
    final values = const FamilyFinance().transactions([
      transaction,
      row('deleted', 'account', {},
          deleted: 1, erased: true, structural: true, currency: 'USD')
    ]);
    expect(values.single.id, 'peer-transaction');
    expect(values.single.amountMinor, 550);
    expect(values.single.currency!.code, 'USD');
    expect(values.single.date, '2026-11-13');
    expect(values.single.accountId, isNull);
  });
}
