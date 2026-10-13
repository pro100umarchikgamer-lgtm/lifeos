part of 'local_store.dart';

extension EncryptedSyncStore on LocalStore {
  Future<Json?> syncMetadata(String scope, String key) async {
    final row = (await _db.query(
      'sync_metadata',
      where: 'scope=? AND key=?',
      whereArgs: [scope, key],
    )).firstOrNull;
    return row == null ? null : object(jsonDecode(row['payload'] as String));
  }

  Future<void> syncSaveMetadata(String scope, String key, Json value) async {
    await _db.insert('sync_metadata', {
      'scope': scope,
      'key': key,
      'payload': jsonEncode(value),
    }, conflictAlgorithm: sql.ConflictAlgorithm.replace);
  }

  Future<void> syncEnqueue(String scope, String workspace, Json operation) =>
      _db.transaction((tx) => _enqueueSync(tx, scope, workspace, operation));
  Future<void> _enqueueSync(
    sql.Transaction tx,
    String scope,
    String workspace,
    Json operation,
  ) async {
    final id = operation['id'] as String,
        record = operation['record_id'] as String;
    final payload = jsonEncode(operation);
    final prior = await tx.query(
      'sync_outbox',
      where: 'scope=? AND operation_id=?',
      whereArgs: [scope, id],
    );
    if (prior.isNotEmpty) {
      if (prior.single['payload'] != payload) {
        throw const SyncFailure('operation_conflict');
      }
      return;
    }
    await tx.insert('sync_outbox', {
      'scope': scope,
      'workspace_id': workspace,
      'operation_id': id,
      'record_id': record,
      'payload': payload,
    });
  }

  Future<List<Json>> syncPending(String scope, String workspace) async => [
    for (final row in await _db.query(
      'sync_outbox',
      where: 'scope=? AND workspace_id=? AND state=?',
      whereArgs: [scope, workspace, 'pending'],
      orderBy: 'seq',
      limit: 100,
    ))
      object(jsonDecode(row['payload'] as String)),
  ];
  Future<List<Json>> syncIssues(String scope, String workspace) async => [
    for (final row in await _db.query(
      'sync_outbox',
      where: 'scope=? AND workspace_id=? AND state<>?',
      whereArgs: [scope, workspace, 'pending'],
      orderBy: 'seq',
    ))
      {
        'operation': object(jsonDecode(row['payload'] as String)),
        'result': object(jsonDecode(row['result'] as String)),
      },
  ];
  Future<List<Json>> syncRecords(String scope, String workspace) async => [
    for (final row in await _db.query(
      'sync_records',
      where: 'scope=? AND workspace_id=?',
      whereArgs: [scope, workspace],
    ))
      object(jsonDecode(row['payload'] as String)),
  ];
  Future<int> syncCursor(String scope, String workspace) async =>
      (await _db.query(
            'sync_cursors',
            where: 'scope=? AND workspace_id=?',
            whereArgs: [scope, workspace],
          )).firstOrNull?['cursor']
          as int? ??
      0;
  Future<void> syncAcknowledge(
    String scope,
    String workspace,
    List<Json> results,
  ) => _db.transaction((tx) async {
    for (final result in results) {
      final rows = await tx.query(
        'sync_outbox',
        where: 'scope=? AND workspace_id=? AND operation_id=?',
        whereArgs: [scope, workspace, result['id']],
      );
      if (rows.isEmpty) throw const SyncFailure('invalid_sync_response');
      if (result['status'] == 'accepted') {
        await tx.delete(
          'sync_outbox',
          where: 'seq=?',
          whereArgs: [rows.single['seq']],
        );
      } else if (['conflict', 'rejected'].contains(result['status'])) {
        await tx.update(
          'sync_outbox',
          {'state': result['status'], 'result': jsonEncode(result)},
          where: 'seq=?',
          whereArgs: [rows.single['seq']],
        );
      } else {
        throw const SyncFailure('invalid_sync_response');
      }
    }
  });
  Future<void> syncReceive(String scope, String workspace, Json page) =>
      _db.transaction((tx) async {
        final visible = (page['visible_ids'] as List).cast<String>().toSet();
        // Revoked grants purge readable mirrors, but preserve unsent work for explicit recovery.
        for (final row in await tx.query(
          'sync_records',
          where: 'scope=? AND workspace_id=?',
          whereArgs: [scope, workspace],
        )) {
          if (!visible.contains(row['id'])) {
            await tx.delete(
              'sync_records',
              where: 'scope=? AND workspace_id=? AND id=?',
              whereArgs: [scope, workspace, row['id']],
            );
          }
        }
        for (final raw in page['records'] as List) {
          final record = object(raw);
          if (record['workspace_id'] != workspace) {
            throw const SyncFailure('invalid_sync_response');
          }
          if (record['deleted'] == 0 && visible.contains(record['id'])) {
            await tx.insert('sync_records', {
              'scope': scope,
              'workspace_id': workspace,
              'id': record['id'],
              'payload': jsonEncode(record),
            }, conflictAlgorithm: sql.ConflictAlgorithm.replace);
          }
        }
        await tx.insert('sync_cursors', {
          'scope': scope,
          'workspace_id': workspace,
          'cursor': page['cursor'],
        }, conflictAlgorithm: sql.ConflictAlgorithm.replace);
      });
  Future<void> syncResolve(
    String scope,
    String workspace,
    String operationId,
    Json? replacement,
  ) => _db.transaction((tx) async {
    final rows = await tx.query(
      'sync_outbox',
      where: 'scope=? AND workspace_id=? AND operation_id=? AND state<>?',
      whereArgs: [scope, workspace, operationId, 'pending'],
    );
    if (rows.length != 1) throw const SyncFailure('record_missing');
    if (replacement != null) {
      await _enqueueSync(tx, scope, workspace, replacement);
    }
    await tx.delete(
      'sync_outbox',
      where: 'seq=?',
      whereArgs: [rows.single['seq']],
    );
  });
  Future<void> syncForgetAccess(String scope, String workspace) =>
      _db.transaction((tx) async {
        await tx.delete(
          'sync_records',
          where: 'scope=? AND workspace_id=?',
          whereArgs: [scope, workspace],
        );
        await tx.delete(
          'sync_metadata',
          where: 'scope=? AND key=?',
          whereArgs: [scope, 'roster:$workspace'],
        );
        await tx.delete(
          'sync_cursors',
          where: 'scope=? AND workspace_id=?',
          whereArgs: [scope, workspace],
        );
        await tx.update(
          'sync_outbox',
          {
            'state': 'rejected',
            'result': jsonEncode({
              'status': 'rejected',
              'error': 'workspace_forbidden',
            }),
          },
          where: 'scope=? AND workspace_id=? AND state=?',
          whereArgs: [scope, workspace, 'pending'],
        );
      });
}

class LocalSyncStore implements SyncStore {
  LocalSyncStore(this.local);
  final LocalStore local;
  @override
  Future<Json?> metadata(String s, String k) => local.syncMetadata(s, k);
  @override
  Future<void> saveMetadata(String s, String k, Json v) =>
      local.syncSaveMetadata(s, k, v);
  @override
  Future<void> enqueue(String s, String w, Json o) =>
      local.syncEnqueue(s, w, o);
  @override
  Future<List<Json>> pending(String s, String w) => local.syncPending(s, w);
  @override
  Future<List<Json>> issues(String s, String w) => local.syncIssues(s, w);
  @override
  Future<List<Json>> records(String s, String w) => local.syncRecords(s, w);
  @override
  Future<int> cursor(String s, String w) => local.syncCursor(s, w);
  @override
  Future<void> acknowledge(String s, String w, List<Json> r) =>
      local.syncAcknowledge(s, w, r);
  @override
  Future<void> receive(String s, String w, Json p) =>
      local.syncReceive(s, w, p);
  @override
  Future<void> resolve(String s, String w, String id, Json? r) =>
      local.syncResolve(s, w, id, r);
  @override
  Future<void> forgetAccess(String s, String w) => local.syncForgetAccess(s, w);
}
