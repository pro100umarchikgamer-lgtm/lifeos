import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:lifeos/data/local_store.dart';
import 'package:lifeos/domain/action_engine.dart';
import 'package:lifeos/domain/models.dart';
import 'package:path/path.dart' as path;
import 'package:path_provider/path_provider.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('encrypted offline records survive reopen, retry cannot duplicate, lost key fails closed', (tester) async {
    final name = 'test_${DateTime.now().microsecondsSinceEpoch}';
    const secure = FlutterSecureStorage(
      aOptions: AndroidOptions(encryptedSharedPreferences: true),
      iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock_this_device));
    final keyName = '$name.database.key.v1';
    LocalStore? store;
    final directory = await getApplicationSupportDirectory();
    final file = File(path.join(directory.path, '$name.db'));
    try {
      store = await LocalStore.open(name: name);
      final engine = ActionEngine(store);
      final money = CreateMoney('expense-op', kind: EntryKind.expense, amount: '12,50',
        currencyCode: 'RUB', date: DateTime(2026, 10, 10));
      final id = await engine.execute(money);
      expect(await engine.execute(money), id);
      await engine.execute(const CreateTask('task-op', 'Offline task'));
      await engine.execute(const CreateNote('note-op', 'secret_offline_note_9381'));
      await expectLater(engine.execute(CreateMoney('expense-op', kind: EntryKind.expense,
        amount: '99', currencyCode: 'RUB', date: DateTime(2026, 10, 10))),
        throwsA(isA<DomainFailure>()));
      await store.close();
      store = null;
      final bytes = await file.readAsBytes();
      expect(String.fromCharCodes(bytes.take(16)), isNot('SQLite format 3\u0000'));
      expect(String.fromCharCodes(bytes), isNot(contains('secret_offline_note_9381')));
      store = await LocalStore.open(name: name);
      final records = await store.records();
      expect(records.length, 3);
      expect(records.singleWhere((r) => r.id == id).amountMinor, 1250);
      final task = records.singleWhere((r) => r.kind == EntryKind.task);
      final edit = EditMoney('edit-op', id, EntryKind.expense, 1, amount: '20.01',
        currencyCode: 'RUB', date: DateTime(2026, 10, 11), label: 'Corrected');
      await ActionEngine(store).execute(edit);
      await ActionEngine(store).execute(edit);
      expect((await store.records()).singleWhere((r) => r.id == id).revision, 2);
      await expectLater(ActionEngine(store).execute(EditMoney('stale-op', id, EntryKind.expense, 1,
        amount: '99', currencyCode: 'RUB', date: DateTime(2026, 10, 11))), throwsA(isA<DomainFailure>()));
      await ActionEngine(store).execute(DeleteRecord('delete-op', id, EntryKind.expense, 2));
      expect((await store.records()).where((r) => r.id == id), isEmpty);
      await ActionEngine(store).execute(UndoRecordChange('undo-op', id, EntryKind.expense, 3));
      expect((await store.records()).singleWhere((r) => r.id == id).amountMinor, 2001);
      await ActionEngine(store).execute(CompleteTask('done-op', task.id, true));
      await store.close();
      store = null;
      final key = await secure.read(key: keyName);
      await secure.delete(key: keyName);
      await expectLater(LocalStore.open(name: name), throwsA(isA<DomainFailure>()));
      expect(await file.exists(), isTrue);
      await secure.write(key: keyName, value: key!);
      store = await LocalStore.open(name: name);
      expect((await store.records()).singleWhere((r) => r.id == task.id).completed, isTrue);
    } finally {
      await store?.close();
      for (final suffix in ['', '-wal', '-shm', '-journal']) {
        final testFile = File('${file.path}$suffix');
        if (await testFile.exists()) await testFile.delete();
      }
      await secure.delete(key: keyName);
    }
  });
}
