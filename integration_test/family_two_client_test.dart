import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path/path.dart' as path;
import 'package:path_provider/path_provider.dart';
import 'package:lifeos/data/local_store.dart';
import 'package:lifeos/sync/api.dart';
import 'package:lifeos/sync/contracts.dart';
import 'package:lifeos/sync/engine.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'two encrypted clients recover after restart, resolve conflicts and enforce privacy',
    (tester) async {
      await runScenario();
    },
  );
}

void check(bool condition, String description) {
  if (!condition) throw StateError(description);
}

class LostReply implements SyncTransport {
  LostReply(this.api);
  final SyncTransport api;
  bool lose = true;
  @override
  Future<Json> request(String p, {Json? body}) async {
    final result = await api.request(p, body: body);
    if (p == '/v1/sync/push' && lose) {
      lose = false;
      throw const SyncFailure('offline');
    }
    return result;
  }
}

class InvalidReply implements SyncTransport {
  @override
  Future<Json> request(String p, {Json? body}) async => {'results': []};
}

Future<void> runScenario() async {
  final one = FamilyApi('http://127.0.0.1:8787');
  final two = FamilyApi('http://127.0.0.1:8787');
  for (final pair in [
    (one, 'android-one@example.test'),
    (two, 'android-two@example.test'),
  ]) {
    final login = await pair.$1.request(
      '/v1/auth/login',
      body: {
        'email': pair.$2,
        'password': 'isolated-integration-test-password',
      },
    );
    pair.$1.token = login['token'] as String;
  }
  final spaces = await one.request('/v1/spaces');
  final w = (spaces['spaces'] as List).single['id'] as String;
  const s1 = 'loopback|one', s2 = 'loopback|two';
  final prefix = 'family_http_${DateTime.now().microsecondsSinceEpoch}';
  var local1 = await LocalStore.open(name: '${prefix}_one');
  final local2 = await LocalStore.open(name: '${prefix}_two');
  var store1 = LocalSyncStore(local1);
  final store2 = LocalSyncStore(local2);
  var engine1 = SyncEngine(store1, LostReply(one), s1, w);
  final engine2 = SyncEngine(store2, two, s2, w);
  Json note(
    String id,
    String record,
    String body, {
    int revision = 0,
    String visibility = 'shared',
  }) => {
    'id': id,
    'record_id': record,
    'action': 'record.put',
    'revision': revision,
    'kind': 'note',
    'visibility': visibility,
    'audience': [],
    'data': {'body': body},
  };
  String id(int n) =>
      '00000000-0000-4000-8000-${n.toString().padLeft(12, '0')}';
  try {
    final op = note(id(1), id(2), 'offline addition');
    await store1.enqueue(s1, w, op);
    try {
      await engine1.synchronize();
      throw StateError('Expected lost reply');
    } on SyncFailure catch (e) {
      check(e.code == 'offline', 'Loss was transport-only');
    }
    check(
      (await store1.pending(s1, w)).length == 1,
      'Unacknowledged operation retained',
    );
    // Close/reopen the encrypted database after a committed server write whose reply was lost.
    await local1.close();
    local1 = await LocalStore.open(name: '${prefix}_one');
    store1 = LocalSyncStore(local1);
    engine1 = SyncEngine(store1, one, s1, w);
    await engine1.synchronize();
    await engine2.synchronize();
    check((await store1.pending(s1, w)).isEmpty, 'Replay acknowledged');
    check(
      (await store2.records(s2, w)).length == 1,
      'Replay did not duplicate',
    );
    final record = (await store2.records(s2, w)).single;
    await store1.enqueue(
      s1,
      w,
      note(id(3), id(2), 'parent one', revision: record['revision'] as int),
    );
    await store2.enqueue(
      s2,
      w,
      note(id(4), id(2), 'parent two', revision: record['revision'] as int),
    );
    await engine1.synchronize();
    await engine2.synchronize();
    final conflict = (await store2.issues(s2, w)).single;
    check(
      conflict['operation']['data']['body'] == 'parent two',
      'Local conflict version preserved',
    );
    check(
      conflict['result']['server']['data']['body'] == 'parent one',
      'Server conflict version preserved',
    );
    await store2.resolve(s2, w, id(4), {
      ...object(conflict['operation']),
      'id': id(5),
      'revision': conflict['result']['server']['revision'],
    });
    await engine2.synchronize();
    await engine1.synchronize();
    check(
      (await store1.records(s1, w)).single['data']['body'] == 'parent two',
      'Explicit resolution reaches other client',
    );
    await store1.enqueue(
      s1,
      w,
      note(id(6), id(7), 'private diary', visibility: 'private'),
    );
    await engine1.synchronize();
    await engine2.synchronize();
    check((await store2.records(s2, w)).length == 1, 'Private diary isolated');
    await store2.enqueue(
      s2,
      w,
      note(id(8), id(9), 'malformed response recovery'),
    );
    try {
      await SyncEngine(store2, InvalidReply(), s2, w).synchronize();
      throw StateError('Expected invalid reply');
    } on SyncFailure catch (e) {
      check(e.code == 'invalid_sync_response', 'Malformed reply rejected');
    }
    check(
      (await store2.pending(s2, w)).length == 1,
      'Bad reply cannot drop outbox',
    );
    check(
      (await store2.pending('different account', w)).isEmpty,
      'Outbox account isolation',
    );
    await engine2.synchronize();
    await one.request(
      '/v1/family',
      body: {
        'id': id(10),
        'workspace_id': w,
        'action': 'workspace.dissolve',
        'revision': 1,
      },
    );
    await store2.enqueue(
      s2,
      w,
      note(id(11), id(12), 'retain revoked unsent work'),
    );
    try {
      await engine2.synchronize();
      throw StateError('Expected revocation');
    } on SyncFailure catch (e) {
      check(e.code == 'workspace_forbidden', 'Revocation rejected');
    }
    check((await store2.records(s2, w)).isEmpty, 'Revoked mirrors purged');
    check(
      (await store2.issues(s2, w)).isNotEmpty,
      'Revoked work retained for recovery',
    );
  } finally {
    one.close();
    two.close();
    await local1.close();
    await local2.close();
    final directory = await getApplicationSupportDirectory();
    const secure = FlutterSecureStorage(
      aOptions: AndroidOptions(encryptedSharedPreferences: true),
    );
    for (final name in ['${prefix}_one', '${prefix}_two']) {
      for (final suffix in ['', '-wal', '-shm', '-journal']) {
        final file = File(path.join(directory.path, '$name.db$suffix'));
        if (await file.exists()) await file.delete();
      }
      await secure.delete(key: '$name.database.key.v1');
    }
  }
}
