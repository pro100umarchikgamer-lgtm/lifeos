import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:path/path.dart' as path;
import 'package:path_provider/path_provider.dart';
import 'package:lifeos/data/local_store.dart';
import 'package:lifeos/sync/contracts.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'encrypted queue survives reopen, conflicts resolve atomically, revoked data is purged',
    (tester) async {
      final name = 'sync_test_${DateTime.now().microsecondsSinceEpoch}';
      const secure = FlutterSecureStorage(
        aOptions: AndroidOptions(encryptedSharedPreferences: true),
      );
      LocalStore? local;
      final directory = await getApplicationSupportDirectory();
      final file = File(path.join(directory.path, '$name.db'));
      final op = <String, dynamic>{
        'id': 'operation',
        'record_id': 'record',
        'action': 'record.put',
        'revision': 0,
        'data': {'body': 'encrypted_outbox_secret_673291'},
      };
      try {
        local = await LocalStore.open(name: name);
        var store = LocalSyncStore(local);
        await store.enqueue('server|one', 'family', op);
        await store.enqueue('server|one', 'family', op);
        expect((await store.pending('server|one', 'family')).length, 1);
        await expectLater(
          store.enqueue('server|one', 'family', {
            ...op,
            'data': {'body': 'changed retry'},
          }),
          throwsA(isA<SyncFailure>()),
        );
        await local.close();
        local = null;
        final bytes = await file.readAsBytes();
        expect(
          String.fromCharCodes(bytes),
          isNot(contains('encrypted_outbox_secret_673291')),
        );
        expect(
          String.fromCharCodes(bytes.take(16)),
          isNot('SQLite format 3\u0000'),
        );
        local = await LocalStore.open(name: name);
        store = LocalSyncStore(local);
        expect(
          (await store.pending('server|one', 'family')).single['data']['body'],
          'encrypted_outbox_secret_673291',
        );
        expect(await store.pending('server|two', 'family'), isEmpty);
        await store.acknowledge('server|one', 'family', [
          {
            'id': 'operation',
            'status': 'conflict',
            'server': {
              'revision': 2,
              'data': {'body': 'other version'},
            },
          },
        ]);
        expect(await store.pending('server|one', 'family'), isEmpty);
        expect(
          (await store.issues(
            'server|one',
            'family',
          )).single['operation']['data']['body'],
          'encrypted_outbox_secret_673291',
        );
        await store.resolve('server|one', 'family', 'operation', {
          ...op,
          'id': 'replacement',
          'revision': 2,
        });
        expect(await store.issues('server|one', 'family'), isEmpty);
        expect(
          (await store.pending('server|one', 'family')).single['id'],
          'replacement',
        );
        await store.receive('server|one', 'family', {
          'visible_ids': ['record'],
          'records': [
            {
              'id': 'record',
              'workspace_id': 'family',
              'deleted': 0,
              'data': {'body': 'shared'},
            },
          ],
          'cursor': 2,
        });
        expect((await store.records('server|one', 'family')).length, 1);
        await store.receive('server|one', 'family', {
          'protocol': 2,
          'epoch': 'initial-access',
          'reset': false,
          'records': [],
          'cursor': 3,
        });
        expect((await store.records('server|one', 'family')).length, 1);
        await store.receive('server|one', 'family', {
          'protocol': 2,
          'epoch': 'revoked-access',
          'reset': true,
          'records': [],
          'cursor': 1,
        });
        expect(await store.records('server|one', 'family'), isEmpty);
        expect(await store.cursor('server|one', 'family'), 1);
        expect(
          (await store.metadata('server|one', 'epoch:family'))!['value'],
          'revoked-access',
        );
        expect(
          (await store.pending('server|one', 'family')).single['id'],
          'replacement',
        );
        await store.forgetAccess('server|one', 'family');
        expect(await store.records('server|one', 'family'), isEmpty);
        expect(
          (await store.issues(
            'server|one',
            'family',
          )).single['operation']['id'],
          'replacement',
        );
        expect(await store.cursor('server|one', 'family'), 0);
      } finally {
        await local?.close();
        for (final suffix in ['', '-wal', '-shm', '-journal']) {
          final f = File('${file.path}$suffix');
          if (await f.exists()) await f.delete();
        }
        await secure.delete(key: '$name.database.key.v1');
      }
    },
  );
}
