import 'dart:async';
import 'package:flutter/material.dart';
import 'package:lifeos/ui/account_center.dart';
import 'package:lifeos/ui/privacy_lifecycle.dart';
import 'privacy_lifecycle_ui_test.dart' show status;
import 'package:lifeos/localization/language_pack.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:lifeos/sync/controller.dart';
import 'package:lifeos/sync/contracts.dart';
import 'google_login_test.dart' show LoginApi;
import 'support/sync_memory.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => FlutterSecureStorage.setMockInitialValues(
      {'lifeos.sync.token': 'credential'}));
  test(
      'an unavailable transfer recipient cannot sign out a valid current principal',
      () async {
    final api = LoginApi('https://example.test',
        (path, body) async => {'user_id': 'alice', 'verified': true})
      ..token = 'alice-token';
    final c = FamilyController(MemorySyncStore())
      ..api = api
      ..account = {'user_id': 'alice', 'verified': true}
      ..records = [
        {'id': 'own-draft'}
      ];
    addTearDown(c.dispose);
    await c
        .run(() async => throw const SyncFailure('account_unavailable', 403));
    expect(c.account?['user_id'], 'alice');
    expect(api.token, 'alice-token');
    expect(c.records.single['id'], 'own-draft');
    expect(await c.secure.read(key: 'lifeos.sync.token'), 'credential');
  });
  test(
      'confirmed self unavailability detaches cloud identity and queues from active UI',
      () async {
    final api = LoginApi(
        'https://example.test',
        (path, body) async =>
            throw const SyncFailure('account_unavailable', 403))
      ..token = 'alice-token';
    final store = MemorySyncStore();
    await store.enqueue('personal-offline', 'local', {
      'id': 'local-draft',
      'record_id': 'local',
      'action': 'record.create',
      'data': {'body': 'My local draft'}
    });
    final c = FamilyController(store)
      ..api = api
      ..account = {'user_id': 'alice', 'verified': true}
      ..records = [
        {'id': 'old-private'}
      ]
      ..pending = [
        {'id': 'old-queued'}
      ];
    addTearDown(c.dispose);
    await c
        .run(() async => throw const SyncFailure('account_unavailable', 403));
    expect(c.account, isNull);
    expect(api.token, isNull);
    expect(c.records, isEmpty);
    expect(c.pending, isEmpty);
    expect(c.error, 'account_unavailable');
    expect(await c.secure.read(key: 'lifeos.sync.token'), isNull);
    expect(
        (await store.pending('personal-offline', 'local')).single['data']
            ['body'],
        'My local draft');
  });
  test('late self-session check cannot detach a newly selected account',
      () async {
    final reply = Completer<Json>();
    final alice = LoginApi('https://example.test', (path, body) => reply.future)
      ..token = 'alice-token';
    final bob = LoginApi(
        'https://example.test', (path, body) async => {'user_id': 'bob'})
      ..token = 'bob-token';
    final c = FamilyController(MemorySyncStore())
      ..api = alice
      ..account = {'user_id': 'alice'};
    addTearDown(c.dispose);
    final checking = c.recheckUnavailablePrincipal(
        expectedPrincipal: c.capturePrincipal());
    await Future<void>.delayed(Duration.zero);
    c.api = bob;
    c.account = {'user_id': 'bob'};
    reply.completeError(const SyncFailure('account_unavailable', 403));
    expect(await checking, isFalse);
    expect(c.account?['user_id'], 'bob');
    expect(bob.token, 'bob-token');
    alice.close();
  });
  testWidgets(
      'account screens restrict confirmed self failure instead of generic retry',
      (tester) async {
    final catalog = await tester.runAsync(PackCatalog.load);
    final api = LoginApi(
        'https://example.test',
        (path, body) async =>
            throw const SyncFailure('account_unavailable', 403))
      ..token = 'old-token';
    final c = FamilyController(MemorySyncStore())
      ..api = api
      ..account = {'user_id': 'alice', 'email': 'alice@example.test'};
    addTearDown(c.dispose);
    await tester.pumpWidget(MaterialApp(
        home: AccountCenter(controller: c, pack: catalog!.packs['en']!)));
    await tester.tap(find.text(catalog.packs['en']!.t('account_privacy')));
    await tester.pumpAndSettle();
    expect(c.account, isNull);
    expect(find.text(catalog.packs['en']!.t('privacy_cloud_unavailable')),
        findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  test('a stale action principal is rejected before consulting its transport', () async {
    final alice = LoginApi('https://example.test', (path, body) async => {})
      ..token = 'alice';
    final bob = LoginApi('https://example.test', (path, body) async => {})
      ..token = 'bob';
    final c = FamilyController(MemorySyncStore())
      ..api = alice
      ..account = {'user_id': 'alice'};
    addTearDown(c.dispose);
    addTearDown(alice.close);
    final principal = c.capturePrincipal();
    c.api = bob;
    c.account = {'user_id': 'bob'};
    var requests = 0;
    expect(await c.recheckUnavailablePrincipal(
      expectedPrincipal: principal,
      request: (path, {body}) async {
        requests++;
        throw const SyncFailure('account_unavailable', 403);
      },
    ), isFalse);
    expect(requests, 0);
    expect(c.account?['user_id'], 'bob');
    expect(bob.token, 'bob');
  });
  testWidgets('late AccountCenter request scoped to Alice must not detach valid Bob',
      (tester) async {
    final catalog = await tester.runAsync(PackCatalog.load);
    final reply = Completer<Json>();
    final alice = LoginApi('https://example.test', (path, body) async => {})
      ..token = 'alice';
    final bob = LoginApi('https://example.test',
        (path, body) async => {'user_id': 'bob', 'verified': true})
      ..token = 'bob';
    final c = FamilyController(MemorySyncStore())
      ..api = alice
      ..account = {'user_id': 'alice'};
    addTearDown(c.dispose);
    addTearDown(alice.close);
    Future<Json> aliceRequest(String path, {Json? body}) async {
      if (path == '/v1/me') throw const SyncFailure('account_unavailable', 403);
      return reply.future;
    }
    await tester.pumpWidget(MaterialApp(home: AccountCenter(
        controller: c, pack: catalog!.packs['en']!, request: aliceRequest)));
    await tester.tap(find.text(catalog.packs['en']!.t('account_privacy')));
    await tester.pump();
    c.api = bob;
    c.account = {'user_id': 'bob'};
    c.publish();
    reply.completeError(const SyncFailure('account_unavailable', 403));
    await tester.pumpAndSettle();
    expect(c.account?['user_id'], 'bob');
    expect(bob.token, 'bob');
  });
  testWidgets('late unavailable Alice lifecycle response must not detach valid Bob',
      (tester) async {
    final catalog = await tester.runAsync(PackCatalog.load);
    final reply = Completer<Json>();
    final alice = LoginApi('https://example.test', (path, body) async =>
        throw const SyncFailure('account_unavailable', 403))..token = 'alice';
    final bob = LoginApi('https://example.test',
        (path, body) async => {'user_id': 'bob', 'verified': true})
      ..token = 'bob';
    final c = FamilyController(MemorySyncStore())
      ..api = alice
      ..account = {'user_id': 'alice'};
    addTearDown(c.dispose);
    addTearDown(alice.close);
    var oldMeCalls = 0;
    Future<Json> aliceRequest(String path, {Json? body}) async {
      if (path == '/v1/me') {
        oldMeCalls++;
        throw const SyncFailure('account_unavailable', 403);
      }
      return reply.future;
    }
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: ListView(children: [
      AccountPrivacyLifecycle(
        controller: c, pack: catalog!.packs['en']!, request: aliceRequest,
        initialData: {...status(), 'request': const {'state': 'pending',
          'due_at': 1900000000}, 'cancel_available': true},
        onSupport: () {},
      )
    ]))));
    await tester.ensureVisible(find.byKey(const Key('privacy_cancel_deletion')));
    await tester.tap(find.byKey(const Key('privacy_cancel_deletion')));
    await tester.pump();
    c.api = bob;
    c.account = {'user_id': 'bob'};
    c.publish();
    reply.completeError(const SyncFailure('account_unavailable', 403));
    await tester.pumpAndSettle();
    expect(c.account?['user_id'], 'bob',
        reason: 'The failed response and request belong to Alice, not Bob');
    expect(bob.token, 'bob');
    expect(oldMeCalls, 0,
        reason: 'The old widget must stop before consulting its old transport');
  });
}
