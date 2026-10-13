// Standalone Dart protocol runner also works before Flutter dependency resolution.
// ignore_for_file: avoid_relative_lib_imports

import 'dart:convert';
import 'dart:io';

import '../lib/sync/api.dart';
import '../lib/sync/contracts.dart';
import '../lib/sync/engine.dart';
import '../test/support/sync_memory.dart';

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

Future<void> main() async {
  final config = object(jsonDecode(await stdin.transform(utf8.decoder).join()));
  final one = FamilyApi(config['endpoint'] as String)
    ..token = config['one'] as String;
  final two = FamilyApi(config['endpoint'] as String)
    ..token = config['two'] as String;
  final store1 = MemorySyncStore(), store2 = MemorySyncStore();
  final w = config['workspace'] as String;
  const s1 = 'one', s2 = 'two';
  final engine1 = SyncEngine(store1, LostReply(one), s1, w),
      engine2 = SyncEngine(store2, two, s2, w);
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
    stdout.writeln(
      'PASS: real two-client Dart HTTP sync, lost reply replay, conflict resolution, privacy, malformed reply, revocation',
    );
  } finally {
    one.close();
    two.close();
  }
}
