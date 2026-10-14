import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:lifeos/platform/native_bridge.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:path/path.dart' as path;
import 'package:path_provider/path_provider.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:lifeos/data/local_store.dart';
import 'package:lifeos/domain/action_engine.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/domain/finance_engine.dart';
import 'package:lifeos/domain/statement_import.dart';
import 'package:lifeos/services/backup_service.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  timezone.initializeTimeZones();
  testWidgets(
    'money editor saves account and category atomically with replay and mismatch rejection',
    (tester) async {
      final name = 'test_ux31_${DateTime.now().microsecondsSinceEpoch}';
      const secure = FlutterSecureStorage(
        aOptions: AndroidOptions(encryptedSharedPreferences: true),
        iOptions: IOSOptions(
          accessibility: KeychainAccessibility.first_unlock_this_device,
        ),
      );
      LocalStore? store;
      final directory = await getApplicationSupportDirectory();
      final file = path.join(directory.path, '$name.db');
      try {
        store = await LocalStore.open(name: name);
        final engine = ActionEngine(store);
        await engine.execute(
          const SaveAccount(
            'account-op',
            'cash',
            0,
            name: 'Cash',
            currency: 'RUB',
            openingMinor: 10000,
          ),
        );
        await engine.execute(
          const SaveCategory('category-op', 'food', 0, 'Food'),
        );
        final action = CreateMoney(
          'atomic-money',
          kind: EntryKind.expense,
          amount: '12.50',
          currencyCode: 'RUB',
          date: DateTime(2026, 10, 14),
          accountId: 'cash',
          categoryId: 'food',
        );
        final id = await engine.execute(action);
        expect(await engine.execute(action), id);
        final record = (await store.records()).single;
        expect(record.accountId, 'cash');
        expect(record.categoryId, 'food');
        expect(record.amountMinor, 1250);
        await expectLater(
          engine.execute(
            CreateMoney(
              'bad-currency',
              kind: EntryKind.expense,
              amount: '12.50',
              currencyCode: 'USD',
              date: DateTime(2026, 10, 14),
              accountId: 'cash',
            ),
          ),
          throwsA(isA<DomainFailure>()),
        );
        expect((await store.records()).length, 1);
        await engine.execute(
          EditMoney(
            'edit-atomic',
            id,
            EntryKind.expense,
            1,
            amount: '10',
            currencyCode: 'RUB',
            date: DateTime(2026, 10, 14),
            updateDetails: true,
          ),
        );
        final edited = (await store.records()).single;
        expect(edited.accountId, isNull);
        expect(edited.categoryId, isNull);
        expect(edited.amountMinor, 1000);
        await engine.execute(
          UndoRecordChange('undo-atomic', id, EntryKind.expense, 2),
        );
        final restored = (await store.records()).single;
        expect(restored.accountId, 'cash');
        expect(restored.categoryId, 'food');
        expect(restored.amountMinor, 1250);
      } finally {
        await store?.close();
        for (final suffix in ['', '-wal', '-shm']) {
          final f = File('$file$suffix');
          if (await f.exists()) await f.delete();
        }
        await secure.delete(key: 'lifeos.database.key.$name');
      }
    },
  );
  testWidgets(
    'coordinated offline ledger, links, CAS, import reversal and encrypted restore',
    (tester) async {
      final name = 'test_expansion_${DateTime.now().microsecondsSinceEpoch}';
      const secure = FlutterSecureStorage(
        aOptions: AndroidOptions(encryptedSharedPreferences: true),
        iOptions: IOSOptions(
          accessibility: KeychainAccessibility.first_unlock_this_device,
        ),
      );
      LocalStore? store;
      final directory = await getApplicationSupportDirectory();
      final file = path.join(directory.path, '$name.db');
      try {
        store = await LocalStore.open(name: name);
        final engine = ActionEngine(store);
        await engine.execute(
          const SaveAccount(
            'a-op',
            'a',
            0,
            name: 'Cash',
            currency: 'RUB',
            openingMinor: 10000,
          ),
        );
        await engine.execute(
          const SaveAccount('b-op', 'b', 0, name: 'Card', currency: 'RUB'),
        );
        await engine.execute(
          const SaveAccount('usd-op', 'usd', 0, name: 'USD', currency: 'USD'),
        );
        final money = await engine.execute(
          CreateMoney(
            'money-op',
            kind: EntryKind.expense,
            amount: '10.00',
            currencyCode: 'RUB',
            date: DateTime(2026, 10, 11),
          ),
        );
        expect(
          const FinanceEngine().accountBalance(
            (await store.offlineData())[OfflineTable.accounts]!.singleWhere(
              (a) => a['id'] == 'a',
            ),
            await store.records(),
            [],
          ),
          BigInt.from(10000),
        );
        await engine.execute(const SaveCategory('cat1-op', 'cat1', 0, 'Food'));
        await engine.execute(const SaveCategory('cat2-op', 'cat2', 0, 'Home'));
        await engine.execute(
          SaveProject(
            'project-op',
            'project',
            0,
            name: 'Home',
            dueOn: DateTime(2026, 10, 20),
          ),
        );
        expect(
          (await store.calendarEntries())
              .where((e) => e.title == 'Home')
              .length,
          1,
        );
        await engine.execute(
          SetMoneyDetails(
            'split-op',
            money,
            1,
            accountId: 'a',
            splits: const [
              ExpenseSplit(
                'split1',
                600,
                categoryId: 'cat1',
                projectId: 'project',
              ),
              ExpenseSplit('split2', 400, categoryId: 'cat2'),
            ],
          ),
        );
        await expectLater(
          engine.execute(
            SetMoneyDetails(
              'bad-split',
              money,
              2,
              accountId: 'a',
              splits: const [ExpenseSplit('bad', 900)],
            ),
          ),
          throwsA(isA<DomainFailure>()),
        );
        expect(
          (await store.records()).singleWhere((r) => r.id == money).revision,
          2,
        );
        await engine.execute(
          SetMoneyDetails(
            'split-edit',
            money,
            2,
            accountId: 'a',
            amountMinor: 1200,
            splits: const [
              ExpenseSplit(
                'split1',
                800,
                categoryId: 'cat1',
                projectId: 'project',
              ),
              ExpenseSplit('split2', 400, categoryId: 'cat2'),
            ],
          ),
        );
        await engine.execute(
          UndoRecordChange('split-undo', money, EntryKind.expense, 3),
        );
        expect(
          (await store.splits()).fold<int>(
            0,
            (n, s) => n + (s['amount_minor'] as int),
          ),
          1000,
        );
        await engine.execute(
          SaveTransfer(
            'transfer-op',
            'transfer',
            0,
            fromId: 'a',
            toId: 'b',
            sentMinor: 2000,
            receivedMinor: 2000,
            date: DateTime(2026, 10, 11),
          ),
        );
        await engine.execute(
          SaveTransfer(
            'cross-op',
            'cross',
            0,
            fromId: 'b',
            toId: 'usd',
            sentMinor: 1000,
            receivedMinor: 125,
            date: DateTime(2026, 10, 11),
          ),
        );
        expect((await store.records()).length, 1);
        await engine.execute(
          const DeleteOffline(
            'transfer-delete',
            'transfer',
            1,
            OfflineTable.transfers,
          ),
        );
        await engine.execute(
          const UndoOffline(
            'transfer-undo',
            'transfer',
            2,
            OfflineTable.transfers,
          ),
        );
        const schedule = ScheduleSpec(
          localStart: '2026-10-11T09:00:00',
          timezone: 'UTC',
          repeat: RepeatRule.daily,
          reminder: true,
        );
        await engine.execute(
          const SavePlannedPayment(
            'plan-op',
            'plan',
            0,
            name: 'Bill',
            kind: EntryKind.expense,
            currency: 'RUB',
            amountMinor: 500,
            schedule: schedule,
          ),
        );
        expect((await store.records()).length, 1);
        final paid = await engine.execute(
          const ConfirmPlannedPayment('pay-op', 'plan', 1, '2026-10-11'),
        );
        expect(
          await engine.execute(
            const ConfirmPlannedPayment('pay-again', 'plan', 1, '2026-10-11'),
          ),
          paid,
        );
        await engine.execute(
          const SaveGoal(
            'goal-op',
            'goal',
            0,
            name: 'Holiday',
            currency: 'RUB',
            targetMinor: 100000,
          ),
        );
        await engine.execute(
          SaveGoalEntry(
            'goal-entry',
            'allocation',
            0,
            goalId: 'goal',
            amountMinor: 10000,
            date: DateTime(2026, 10, 11),
          ),
        );
        expect((await store.records()).length, 2);
        await engine.execute(
          const SaveDebt(
            'debt-op',
            'debt',
            0,
            name: 'Loan',
            currency: 'RUB',
            principalMinor: 50000,
          ),
        );
        await engine.execute(
          SaveDebtEntry(
            'repay-op',
            'repay',
            0,
            debtId: 'debt',
            principalMinor: 1000,
            interestMinor: 100,
            feeMinor: 20,
            date: DateTime(2026, 10, 11),
          ),
        );
        await engine.execute(
          const SaveAsset('asset-op', 'asset', 0, 'Manual fund', 'RUB'),
        );
        await engine.execute(
          SaveInvestmentEntry(
            'buy-op',
            'buy',
            0,
            assetId: 'asset',
            kind: 'buy',
            cashMinor: 10000,
            feeMinor: 10,
            quantityMicros: 2000000,
            date: DateTime(2026, 10, 11),
          ),
        );
        await expectLater(
          engine.execute(
            SaveInvestmentEntry(
              'oversell-op',
              'oversell',
              0,
              assetId: 'asset',
              kind: 'sell',
              cashMinor: 20000,
              quantityMicros: 3000000,
              date: DateTime(2026, 10, 12),
            ),
          ),
          throwsA(isA<DomainFailure>()),
        );
        final imported = ImportedMoney(
          kind: EntryKind.income,
          amountMinor: 4321,
          currency: 'RUB',
          date: '2026-10-10',
          label: 'Imported',
          originKey: await importDigest(['fixture', 1]),
        );
        final key = await importDigest({
          'rows': [imported.toJson()],
          'account': '',
        });
        final action = ConfirmImport(
          'import-op',
          'batch',
          0,
          contentKey: key,
          rows: [imported],
        );
        await engine.execute(action);
        await engine.execute(action);
        expect(
          (await store.records()).where((r) => r.text == 'Imported').length,
          1,
        );
        final snapshotWithImport = await store.exportSnapshot();
        await engine.execute(const ReverseImport('reverse-op', 'batch', 1));
        expect(
          (await store.records()).map((r) => r.id),
          containsAll([money, paid]),
        );
        expect(
          (await store.records()).where((r) => r.text == 'Imported'),
          isEmpty,
        );
        await store.restoreSnapshot(snapshotWithImport);
        final importedRecord = (await store.records()).singleWhere(
          (r) => r.text == 'Imported',
        );
        await engine.execute(
          EditMoney(
            'import-edit',
            importedRecord.id,
            EntryKind.income,
            1,
            amount: '43.22',
            currencyCode: 'RUB',
            date: DateTime(2026, 10, 10),
            label: 'Edited',
          ),
        );
        await expectLater(
          engine.execute(const ReverseImport('reverse-edited', 'batch', 1)),
          throwsA(isA<DomainFailure>()),
        );
        final task = await engine.execute(
          const CreateTask('task-op', 'Canonical task', schedule: schedule),
        );
        await engine.execute(
          SetTaskPlacement(
            'place-op',
            'place',
            0,
            taskId: task,
            projectId: 'project',
          ),
        );
        await engine.execute(
          const SaveHabit(
            'habit-op',
            'habit',
            0,
            name: 'Walk',
            schedule: schedule,
          ),
        );
        await engine.execute(
          const CheckHabit(
            'check-op',
            'check',
            0,
            habitId: 'habit',
            localDate: '2026-10-11',
            timezone: 'UTC',
          ),
        );
        await engine.execute(
          const SaveHabit(
            'pause-op',
            'habit',
            1,
            name: 'Walk',
            schedule: schedule,
            paused: true,
          ),
        );
        expect(
          (await store.calendarEntries()).where((e) => e.title == 'Walk'),
          isEmpty,
        );
        await engine.execute(
          const SaveHabit(
            'resume-op',
            'habit',
            2,
            name: 'Walk',
            schedule: schedule,
          ),
        );
        expect(
          (await store.calendarEntries())
              .where((e) => e.title == 'Walk')
              .length,
          1,
        );
        await engine.execute(
          const SaveSubject(
            'subject-op',
            'subject',
            0,
            name: 'Math',
            projectId: 'project',
          ),
        );
        await engine.execute(
          SaveStudyItem(
            'study-op',
            'study',
            0,
            subjectId: 'subject',
            name: 'Assignment',
            taskId: task,
          ),
        );
        final note = await engine.execute(
          const CreateNote('note-op', 'Keep this body'),
        );
        await engine.execute(
          SetNoteMetadata(
            'tags-op',
            'tags',
            0,
            noteId: note,
            tags: const ['home', 'study'],
          ),
        );
        await engine.execute(
          SaveRecordLink(
            'link-op',
            'link',
            0,
            noteId: note,
            targetType: 'task',
            targetId: task,
          ),
        );
        await engine.execute(
          SaveChecklist('list-op', 'list', 0, name: 'Shopping', noteId: note),
        );
        await engine.execute(
          const SaveChecklistItem(
            'item-op',
            'item',
            0,
            checklistId: 'list',
            name: 'Milk',
            quantity: '2',
          ),
        );
        await engine.execute(
          const SaveChecklist(
            'chore-op',
            'chores',
            0,
            name: 'Cleaning',
            kind: 'chores',
          ),
        );
        await engine.execute(
          const SaveChecklistItem(
            'chore-item',
            'chore-item',
            0,
            checklistId: 'chores',
            name: 'Sweep',
            completed: true,
          ),
        );
        await engine.execute(
          const CopyChecklist(
            'copy-chores',
            'copy',
            0,
            sourceId: 'chores',
            sourceRevision: 1,
            name: 'Cleaning copy',
          ),
        );
        expect(
          (await store.offlineData())[OfflineTable.checklistItems]!
              .where((r) => r['checklist_id'] == 'copy')
              .single['completed'],
          0,
        );
        await engine.execute(
          const SaveWellness(
            'sleep-op',
            'sleep',
            0,
            kind: 'sleep',
            localDate: '2026-10-11',
            minutes: 480,
          ),
        );
        await engine.execute(
          const SaveProfile('profile1-op', 'person1', 0, name: 'Alex'),
        );
        await engine.execute(
          const SaveProfile('profile2-op', 'person2', 0, name: 'Alex'),
        );
        await engine.execute(
          const SaveProfile('profile-edit', 'person1', 1, name: 'Renamed'),
        );
        await engine.execute(
          const SaveMembership(
            'membership-op',
            'membership',
            0,
            profileId: 'person1',
            role: 'contributor',
            permissions: 3,
          ),
        );
        await engine.execute(
          const SaveDashboard(
            'dash-op',
            'dash',
            0,
            widget: 'habits',
            position: 35,
            visible: true,
          ),
        );
        final finalSnapshot = await store.exportSnapshot();
        final backup = BackupService();
        final encrypted = await backup.encrypt(
          finalSnapshot,
          'long-fixture-password',
        );
        await expectLater(
          backup.decrypt(encrypted, 'incorrect-password'),
          throwsA(isA<DomainFailure>()),
        );
        await store.restoreSnapshot(
          await backup.decrypt(encrypted, 'long-fixture-password'),
        );
        expect(
          jsonEncode(await store.exportSnapshot()),
          jsonEncode(finalSnapshot),
        );
        // Embedded undo data must not introduce arbitrary columns or another transaction's split.
        final forged =
            jsonDecode(jsonEncode(finalSnapshot)) as Map<String, dynamic>;
        final changes = (forged['tables'] as Map)['record_changes'] as List;
        final change = changes.firstWhere(
          (r) => r['table_name'] == 'transactions',
        );
        final history =
            jsonDecode(change['before_json'] as String) as Map<String, dynamic>;
        history['unknown_column'] = 'injected';
        change['before_json'] = jsonEncode(history);
        await expectLater(
          store.restoreSnapshot(Map<String, Object?>.from(forged)),
          throwsA(isA<DomainFailure>()),
        );
        expect(
          (await store.records()).singleWhere((r) => r.id == note).text,
          'Keep this body',
        );
        await store.close();
        store = await LocalStore.open(name: name);
        final data = await store.offlineData();
        expect(
          data[OfflineTable.profiles]!
              .where((p) => p['id'] == 'person2')
              .single['name'],
          'Alex',
        );
        expect(data[OfflineTable.projects]!.length, 1);
      } finally {
        await store?.close();
        for (final suffix in ['', '-wal', '-shm', '-journal']) {
          final f = File('$file$suffix');
          if (await f.exists()) await f.delete();
        }
        await secure.delete(key: '$name.database.key.v1');
      }
    },
    timeout: const Timeout(Duration(minutes: 5)),
  );
  testWidgets(
    'Android bounded XLSX and XML adapters accept values and reject formulas and DTD',
    (tester) async {
      Future<Map<String, Object?>?> decode(Uint8List bytes, String format) =>
          NativeBridge.channel.invokeMapMethod<String, Object?>(
            'decodeStatement',
            {'bytes': bytes, 'format': format},
          );
      final sheets = await decode(
        base64Decode(
          'UEsDBBQAAAAIAAOaS11UfQFd2AAAALYBAAAYAAAAeGwvd29ya3NoZWV0cy9zaGVldDEueG1sdZFBjsIwDEWvUmVfnEQaFiiNNMANOEFUAo2mSarElNnPQeYKrFnAFcKNSNGoYqR2Z3/720+2OPvwFRutsfi2rYsVaRC7FUCsG21VXPhOu1w5+GAV5jQcIXZBq/3LZFvglC7BKuOIFC9tq1BJEfy5CBVhWa2H4JORAitiXGuc3mHIuolSoNwr1AJQChhyqP/613P9yvqTwwnHZnaDjnUwHRrv/tsgQ46kfCTlM3M45cuS0ZKxKd7B38uS8cUHFdC/g80NTL/plq6Pn3RP13SZYoO3i8L4KvkEUEsBAhQDFAAAAAgAA5pLXVR9AV3YAAAAtgEAABgAAAAAAAAAAAAAAIABAAAAAHhsL3dvcmtzaGVldHMvc2hlZXQxLnhtbFBLBQYAAAAAAQABAEYAAAAOAQAAAAA=',
        ),
        'xlsx',
      );
      expect((sheets!['sheet1'] as List)[1], [
        '2026-10-11',
        '-12.50',
        'Покупка',
      ]);
      await expectLater(
        decode(
          base64Decode(
            'UEsDBBQAAAAIAAOaS12+UJkC4AAAAMABAAAYAAAAeGwvd29ya3NoZWV0cy9zaGVldDEueG1sdZFRTsMwDIavUuUVdU6C2ANKLQG7ASeIupRGNEmVmG3vHIQr8LwHuEK4EemEqiG1b/Zv//YnWx1DfE29MVSd3OBTw3qi8R4gtb1xOm3CaHypdCE6TSWNL5DGaPT+YnIDSM634LT1DNVF22nSqGI4VrFhoqjtFDwIVlHDrB+sN88Ui24TKsK9JqOAUMGUQ/vX/7jWr11487TgeFrdYFIb7Ug2+P82KJAzqZxJ5cocyeW2FrwWYol38ncob24VdKgOWAu5ueMKDteIa6PzR/7K55/3/J3P+XOJEq5uC/PT8BdQSwECFAMUAAAACAADmktdvlCZAuAAAADAAQAAGAAAAAAAAAAAAAAAgAEAAAAAeGwvd29ya3NoZWV0cy9zaGVldDEueG1sUEsFBgAAAAABAAEARgAAABYBAAAAAA==',
          ),
          'xlsx',
        ),
        throwsA(isA<PlatformException>()),
      );
      const xml =
          '<statement><transaction><date>2026-10-11</date><amount>-12.50</amount><description>Shop</description><currency>RUB</currency></transaction></statement>';
      expect(
        (await decode(
          Uint8List.fromList(utf8.encode(xml)),
          'xml',
        ))!['statement'],
        isA<List>(),
      );
      await expectLater(
        decode(
          Uint8List.fromList(
            utf8.encode('<!DOCTYPE statement [<!ENTITY x "bad">]>$xml'),
          ),
          'xml',
        ),
        throwsA(isA<PlatformException>()),
      );
    },
  );
}
