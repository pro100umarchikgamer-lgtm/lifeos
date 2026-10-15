import 'package:timezone/data/latest.dart' as timezone;

import 'dart:io';
import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:sqflite_sqlcipher/sqflite.dart' as sql;
import 'package:lifeos/platform/native_bridge.dart';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:lifeos/data/local_store.dart';
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/domain/action_engine.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/domain/appearance.dart';
import 'package:path/path.dart' as path;
import 'package:path_provider/path_provider.dart';

void main() {
  timezone.initializeTimeZones();
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'overdue task completion survives dismissal, snooze, stale render, double tap and SQLCipher reopen',
    (tester) async {
      final name = 'completion_${DateTime.now().microsecondsSinceEpoch}';
      var store = await LocalStore.open(name: name);
      final catalog = await PackCatalog.load();
      var controller = AppController(store, catalog, 'ru');
      final engine = ActionEngine(store);
      final now = DateTime.utc(2026, 10, 15, 18);
      final ids = <String>[];
      for (final state in [
        OccurrenceStatus.dismissed,
        OccurrenceStatus.snoozed,
      ]) {
        final id = await engine.execute(
          CreateTask(
            'create-${state.name}',
            'Подтвердить выполнение обязанностей',
            schedule: const ScheduleSpec(
              localStart: '2026-10-01T09:00:00',
              timezone: 'Europe/Moscow',
              repeat: RepeatRule.daily,
              until: '2026-10-11',
            ),
          ),
        );
        ids.add(id);
        final entry = (await store.calendarEntries()).singleWhere(
          (e) => e.taskId == id,
        );
        final epoch = DateTime.utc(2026, 10, 11, 6).millisecondsSinceEpoch;
        await engine.execute(
          SetOccurrence(
            'notice-${state.name}',
            entry.id,
            epoch,
            state,
            expectedRevision: entry.revision,
            snoozedUntil: state == OccurrenceStatus.snoozed
                ? epoch + 600000
                : null,
          ),
        );
        await Future.wait([
          controller.completeTask(id, true, at: now),
          controller.completeTask(id, true, at: now),
        ]);
        await controller.completeTask(id, true, at: now);
        final done = (await store.occurrenceStates()).where(
          (s) =>
              s.entryId == entry.id && s.status == OccurrenceStatus.completed,
        );
        expect(done.length, 1);
        expect(done.single.epoch, epoch);
      }
      final plain = await engine.execute(
        const CreateTask(
          'plain-overdue',
          'Plain',
          schedule: ScheduleSpec(
            localStart: '2026-10-11T09:00:00',
            timezone: 'Europe/Moscow',
          ),
        ),
      );
      await Future.wait([
        controller.completeTask(plain, true, at: now),
        controller.completeTask(plain, true, at: now),
      ]);
      expect(
        (await store.records()).singleWhere((r) => r.id == plain).completed,
        isTrue,
      );
      controller.dispose();
      await store.close();
      store = await LocalStore.open(name: name);
      controller = AppController(store, catalog, 'ru');
      expect(
        (await store.records()).singleWhere((r) => r.id == plain).completed,
        isTrue,
      );
      expect(
        (await store.occurrenceStates())
            .where((s) => s.status == OccurrenceStatus.completed)
            .length,
        2,
      );
      for (final id in ids) {
        await controller.completeTask(id, true, at: now);
      }
      expect(
        (await store.occurrenceStates())
            .where((s) => s.status == OccurrenceStatus.completed)
            .length,
        2,
      );
      controller.dispose();
      await store.close();
    },
  );
  testWidgets(
    'encrypted offline records survive reopen, retry cannot duplicate, lost key fails closed',
    (tester) async {
      final name = 'test_${DateTime.now().microsecondsSinceEpoch}';
      const secure = FlutterSecureStorage(
        aOptions: AndroidOptions(encryptedSharedPreferences: true),
        iOptions: IOSOptions(
          accessibility: KeychainAccessibility.first_unlock_this_device,
        ),
      );
      final keyName = '$name.database.key.v1';
      LocalStore? store;
      final directory = await getApplicationSupportDirectory();
      final file = File(path.join(directory.path, '$name.db'));
      try {
        store = await LocalStore.open(name: name);
        final engine = ActionEngine(store);
        final money = CreateMoney(
          'expense-op',
          kind: EntryKind.expense,
          amount: '12,50',
          currencyCode: 'RUB',
          date: DateTime(2026, 10, 10),
        );
        final id = await engine.execute(money);
        expect(await engine.execute(money), id);
        await engine.execute(const CreateTask('task-op', 'Offline task'));
        await engine.execute(
          const CreateNote('note-op', 'secret_offline_note_9381'),
        );
        await expectLater(
          engine.execute(
            CreateMoney(
              'expense-op',
              kind: EntryKind.expense,
              amount: '99',
              currencyCode: 'RUB',
              date: DateTime(2026, 10, 10),
            ),
          ),
          throwsA(isA<DomainFailure>()),
        );
        await store.close();
        store = null;
        final bytes = await file.readAsBytes();
        expect(
          String.fromCharCodes(bytes.take(16)),
          isNot('SQLite format 3\u0000'),
        );
        expect(
          String.fromCharCodes(bytes),
          isNot(contains('secret_offline_note_9381')),
        );
        store = await LocalStore.open(name: name);
        final records = await store.records();
        expect(records.length, 3);
        expect(records.singleWhere((r) => r.id == id).amountMinor, 1250);
        final task = records.singleWhere((r) => r.kind == EntryKind.task);
        final edit = EditMoney(
          'edit-op',
          id,
          EntryKind.expense,
          1,
          amount: '20.01',
          currencyCode: 'RUB',
          date: DateTime(2026, 10, 11),
          label: 'Corrected',
        );
        await ActionEngine(store).execute(edit);
        await ActionEngine(store).execute(edit);
        expect(
          (await store.records()).singleWhere((r) => r.id == id).revision,
          2,
        );
        await expectLater(
          ActionEngine(store).execute(
            EditMoney(
              'stale-op',
              id,
              EntryKind.expense,
              1,
              amount: '99',
              currencyCode: 'RUB',
              date: DateTime(2026, 10, 11),
            ),
          ),
          throwsA(isA<DomainFailure>()),
        );
        await ActionEngine(store)
            .execute(DeleteRecord('delete-op', id, EntryKind.expense, 2));
        expect((await store.records()).where((r) => r.id == id), isEmpty);
        await ActionEngine(store)
            .execute(UndoRecordChange('undo-op', id, EntryKind.expense, 3));
        expect(
          (await store.records()).singleWhere((r) => r.id == id).amountMinor,
          2001,
        );
        final currentEngine = ActionEngine(store);
        final note = (await store.records()).singleWhere(
          (r) => r.kind == EntryKind.note,
        );
        await currentEngine.execute(
          EditNote('note-edit', note.id, 1, 'secret_edited_note'),
        );
        await currentEngine.execute(
          DeleteRecord('note-delete', note.id, EntryKind.note, 2),
        );
        await currentEngine.execute(
          UndoRecordChange('note-undo', note.id, EntryKind.note, 3),
        );
        expect(
          (await store.records()).singleWhere((r) => r.id == note.id).text,
          'secret_edited_note',
        );
        await currentEngine.execute(
          EditTask('task-edit', task.id, 1, 'Edited task'),
        );
        await currentEngine.execute(
          DeleteRecord('task-delete', task.id, EntryKind.task, 2),
        );
        await currentEngine.execute(
          UndoRecordChange('task-undo', task.id, EntryKind.task, 3),
        );
        await currentEngine.execute(
          CompleteTask('done-op', task.id, true, expectedRevision: 4),
        );
        final income = await currentEngine.execute(
          CreateMoney(
            'income-create',
            kind: EntryKind.income,
            amount: '30',
            currencyCode: 'RUB',
            date: DateTime(2026, 10, 11),
          ),
        );
        await currentEngine.execute(
          EditMoney(
            'income-edit',
            income,
            EntryKind.income,
            1,
            amount: '40.02',
            currencyCode: 'RUB',
            date: DateTime(2026, 10, 12),
          ),
        );
        await expectLater(
          currentEngine.execute(
            DeleteRecord('wrong-kind', income, EntryKind.expense, 2),
          ),
          throwsA(isA<DomainFailure>()),
        );
        await currentEngine.execute(
          DeleteRecord('income-delete', income, EntryKind.income, 2),
        );
        await currentEngine.execute(
          UndoRecordChange('income-undo', income, EntryKind.income, 3),
        );
        expect(
          (await store.records())
              .singleWhere((r) => r.id == income)
              .amountMinor,
          4002,
        );
        await store.close();
        store = null;
        final key = await secure.read(key: keyName);
        await secure.delete(key: keyName);
        await expectLater(
          LocalStore.open(name: name),
          throwsA(isA<DomainFailure>()),
        );
        expect(await file.exists(), isTrue);
        await secure.write(key: keyName, value: key!);
        store = await LocalStore.open(name: name);
        expect(
          (await store.records()).singleWhere((r) => r.id == task.id).completed,
          isTrue,
        );
      } finally {
        await store?.close();
        for (final suffix in ['', '-wal', '-shm', '-journal']) {
          final testFile = File('${file.path}$suffix');
          if (await testFile.exists()) await testFile.delete();
        }
        await secure.delete(key: keyName);
      }
    },
  );
  for (final legacyVersion in [1, 2, 3]) {
    testWidgets(
      'real encrypted v$legacyVersion database upgrades atomically and restore keeps IDs and rejects corrupt data',
      (tester) async {
        final name = 'test_upgrade_${DateTime.now().microsecondsSinceEpoch}';
        final directory = await getApplicationSupportDirectory();
        final file = File(path.join(directory.path, '$name.db'));
        const secure = FlutterSecureStorage(
          aOptions: AndroidOptions(encryptedSharedPreferences: true),
          iOptions: IOSOptions(
            accessibility: KeychainAccessibility.first_unlock_this_device,
          ),
        );
        final keyName = '$name.database.key.v1';
        final password = base64UrlEncode(
          List<int>.generate(32, (i) => i),
        ); // Disposable fixture key, never used by production.
        LocalStore? store;
        sql.Database? legacy;
        try {
          await secure.write(key: keyName, value: password);
          legacy = await sql.openDatabase(
            file.path,
            password: password,
            version: legacyVersion,
            onConfigure: (db) async {
              await db.execute('PRAGMA foreign_keys=ON');
            },
            onCreate: (db, version) async {
              for (var n = 1; n <= legacyVersion; n++) {
                for (final statement in (await rootBundle.loadString(
                  'assets/migrations/${n.toString().padLeft(3, '0')}.sql',
                )).split(';')) {
                  if (statement.trim().isNotEmpty) await db.execute(statement);
                }
              }
            },
          );
          final now = DateTime(2026, 10, 11).toUtc().toIso8601String();
          await legacy.transaction((tx) async {
            await tx.insert('local_identity', {
              'id': 'old-owner',
              'workspace_id': 'old-space',
              'created_at': now,
            });
            await tx.insert('workspaces', {
              'id': 'old-space',
              'owner_id': 'old-owner',
              'kind': 'personal',
              'created_at': now,
            });
            await tx.insert('transactions', {
              'id': 'old-money',
              'owner_id': 'old-owner',
              'workspace_id': 'old-space',
              'kind': 'income',
              'amount_minor': 10001,
              'currency': 'RUB',
              'minor_digits': 2,
              'occurred_on': '2026-10-11',
              'created_at': now,
              'updated_at': now,
            });
            await tx.insert('tasks', {
              'id': 'old-task',
              'owner_id': 'old-owner',
              'workspace_id': 'old-space',
              'title': 'Старая задача',
              'created_at': now,
              'updated_at': now,
            });
            await tx.insert('notes', {
              'id': 'old-note',
              'owner_id': 'old-owner',
              'workspace_id': 'old-space',
              'body': 'Старая заметка',
              'created_at': now,
              'updated_at': now,
            });
            await tx.insert('operations', {
              'id': 'old-op',
              'payload': 'legacy',
              'result_id': 'old-money',
              'created_at': now,
            });
          });
          await legacy.close();
          legacy = null;
          store = await LocalStore.open(name: name);
          expect((await store.records()).map((r) => r.id).toSet(), {
            'old-money',
            'old-task',
            'old-note',
          });
          expect(
            (await store.records())
                .singleWhere((r) => r.id == 'old-money')
                .amountMinor,
            10001,
          );
          final engine = ActionEngine(store);
          const schedule = ScheduleSpec(
            localStart: '2026-10-11T09:00:00',
            timezone: 'UTC',
            repeat: RepeatRule.daily,
            reminder: true,
          );
          await engine.execute(
            const EditTask(
              'schedule-edit',
              'old-task',
              1,
              'Задача со сроком',
              schedule: schedule,
              updateSchedule: true,
              expectedScheduleRevision: 0,
            ),
          );
          final linked = (await store.calendarEntries()).single;
          expect(linked.taskId, 'old-task');
          await expectLater(
            engine.execute(
              const EditTask(
                'stale-schedule',
                'old-task',
                2,
                'Must not change',
                schedule: schedule,
                updateSchedule: true,
                expectedScheduleRevision: 0,
              ),
            ),
            throwsA(isA<DomainFailure>()),
          );
          expect(
            (await store.records())
                .singleWhere((r) => r.id == 'old-task')
                .revision,
            2,
          );
          final epoch = DateTime.utc(2026, 10, 11, 9).millisecondsSinceEpoch;
          await engine.execute(
            SetOccurrence(
              'occurrence-done',
              linked.id,
              epoch,
              OccurrenceStatus.completed,
              expectedRevision: linked.revision,
            ),
          );
          await engine.execute(
            const EditTask(
              'replace-schedule',
              'old-task',
              2,
              'Changed series',
              schedule: ScheduleSpec(
                localStart: '2026-10-12T10:00:00',
                timezone: 'UTC',
                repeat: RepeatRule.weekly,
              ),
              updateSchedule: true,
              expectedScheduleRevision: 1,
            ),
          );
          expect(await store.occurrenceStates(), isEmpty);
          await engine.execute(
            const UndoRecordChange(
              'undo-series',
              'old-task',
              EntryKind.task,
              3,
            ),
          );
          expect(
            (await store.occurrenceStates()).single.status,
            OccurrenceStatus.completed,
          );
          await engine.execute(
            const DeleteRecord('delete-linked', 'old-task', EntryKind.task, 4),
          );
          expect(await store.calendarEntries(), isEmpty);
          await engine.execute(
            const UndoRecordChange(
              'undo-linked',
              'old-task',
              EntryKind.task,
              5,
            ),
          );
          expect((await store.calendarEntries()).single.id, linked.id);
          const appearance = Appearance(
            palette: 'pistachio',
            shape: 'rounded',
            surface: 'tonal',
            mode: 'dark',
          );
          await store.setSetting('appearance_v1', appearance.encode());
          final snapshot = await store.exportSnapshot();
          await store.restoreSnapshot(snapshot);
          expect(
            (await store.records())
                .singleWhere((r) => r.id == 'old-task')
                .revision,
            6,
          );
          final damagedTheme =
              jsonDecode(jsonEncode(snapshot)) as Map<String, dynamic>;
          final damagedSettings =
              (damagedTheme['tables'] as Map)['settings'] as List;
          damagedSettings.singleWhere(
            (row) => row['key'] == 'appearance_v1',
          )['value'] = '{"version":999}';
          await expectLater(
            store.restoreSnapshot(Map<String, Object?>.from(damagedTheme)),
            throwsA(isA<DomainFailure>()),
          );
          expect(
            Appearance.decode((await store.settings())['appearance_v1'])
                .encode(),
            appearance.encode(),
          );
          expect(
            (await store.records())
                .singleWhere((r) => r.id == 'old-money')
                .amountMinor,
            10001,
          );
          final invalid =
              jsonDecode(jsonEncode(snapshot)) as Map<String, dynamic>;
          final tables = invalid['tables'] as Map<String, dynamic>;
          (tables['transactions'] as List).first['amount_minor'] = -1;
          await expectLater(
            store.restoreSnapshot(Map<String, Object?>.from(invalid)),
            throwsA(anyOf(isA<DomainFailure>(), isA<sql.DatabaseException>())),
          );
          expect(
            (await store.records())
                .singleWhere((r) => r.id == 'old-money')
                .amountMinor,
            10001,
          );
          await store.close();
          store = null;
          store = await LocalStore.open(name: name);
          expect((await store.calendarEntries()).single.taskId, 'old-task');
          expect((await store.records()).length, 3);
          expect(
            Appearance.decode((await store.settings())['appearance_v1'])
                .palette,
            'pistachio',
          );
        } finally {
          await legacy?.close();
          await store?.close();
          for (final suffix in ['', '-wal', '-shm', '-journal']) {
            final f = File('${file.path}$suffix');
            if (await f.exists()) await f.delete();
          }
          await secure.delete(key: keyName);
        }
      },
    );
  }
  testWidgets(
    'Android bridge installs and cancels native schedules on the disposable CI emulator',
    (tester) async {
      final bridge = NativeBridge();
      final diagnostics = await bridge.diagnostics();
      expect(diagnostics['supported'], true);
      expect(diagnostics['zone'], isA<String>());
      expect(
        await bridge.wallpaperSeed(),
        isA<int>(),
      ); // API 35 disposable emulator.
      final at = DateTime.now().add(const Duration(hours: 1));
      try {
        await bridge.reconcile([
          {
            'id': 'integration-only',
            'revision': 1,
            'nextAt': at.millisecondsSinceEpoch,
            'schedule': ScheduleSpec(
              localStart:
                  '${dateOnly(at)}T${at.hour.toString().padLeft(2, '0')}:${at.minute.toString().padLeft(2, '0')}:00',
              timezone: 'device',
              reminder: true,
            ).toJson(),
            'title': 'LifeOS test',
            'message': 'Test',
            'doneLabel': 'Done',
            'dismissLabel': 'Dismiss',
            'snoozeLabel': 'Snooze',
            'snoozeMinutes': 10,
            'snoozes': <Object?>[],
          },
        ]);
        expect((await bridge.diagnostics())['entriesCount'], 1);
      } finally {
        await bridge.reconcile([]);
      }
      expect((await bridge.diagnostics())['entriesCount'], 0);
    },
  );
}
