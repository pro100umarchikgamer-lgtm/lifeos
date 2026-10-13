import '../sync/contracts.dart';
import '../domain/offline_validation.dart';
import '../domain/statement_import.dart';
import 'dart:convert';
import '../domain/appearance.dart';
import 'dart:io';
import 'dart:math';

import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path/path.dart' as path;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite_sqlcipher/sqflite.dart' as sql;
import 'package:uuid/uuid.dart';

import '../domain/action_engine.dart';
import '../domain/models.dart';
import '../domain/calendar_engine.dart';
import '../domain/wealth_engine.dart';
import 'package:timezone/timezone.dart' as tz;
part 'offline_store.dart';
part 'wealth_store.dart';
part 'import_store.dart';
part 'personal_modules_store.dart';
part 'history_validation.dart';
part 'sync_store.dart';

class LocalStore implements OfflineStore {
  LocalStore._(this._db, this.ownerId, this.workspaceId);
  final sql.Database _db;
  String ownerId;
  String workspaceId;
  static const _uuid = Uuid();
  static const schemaVersion = 11;

  static Future<LocalStore> open({String name = 'lifeos'}) async {
    if (!RegExp(r'^[a-z0-9_]+$').hasMatch(name)) throw const DomainFailure('invalid_action');
    final directory = await getApplicationSupportDirectory();
    await directory.create(recursive: true);
    final file = path.join(directory.path, '$name.db');
    const secure = FlutterSecureStorage(
      aOptions: AndroidOptions(encryptedSharedPreferences: true),
      iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock_this_device),
    );
    var key = await secure.read(key: '$name.database.key.v1');
    if (key == null) {
      // Never silently replace a lost key for an existing encrypted database.
      if (await File(file).exists()) throw const DomainFailure('storage_key_missing');
      final random = Random.secure();
      key = base64UrlEncode(List.generate(32, (_) => random.nextInt(256)));
      await secure.write(key: '$name.database.key.v1', value: key);
    }
    try {
      if (base64Url.decode(key).length != 32) throw const FormatException();
    } on FormatException {
      throw const DomainFailure('storage_key_missing');
    }
    final db = await sql.openDatabase(file, password: key, version: schemaVersion,
      onConfigure: (db) async { await db.execute('PRAGMA foreign_keys = ON'); },
      onCreate: (db, version) => _migrate(db, 0, version),
      onUpgrade: _migrate,
    );
    try {
      await db.transaction((tx) async {
        final identity = await tx.query('local_identity');
        if (identity.isEmpty) {
        final owner = _uuid.v4();
        final workspace = _uuid.v4();
        final now = DateTime.now().toUtc().toIso8601String();
        await tx.insert('local_identity', {'id': owner, 'workspace_id': workspace, 'created_at': now});
        await tx.insert('workspaces', {'id': workspace, 'owner_id': owner, 'kind': 'personal', 'created_at': now});
        }
        await tx.rawInsert("INSERT OR IGNORE INTO local_profiles(id,owner_id,workspace_id,name,kind,created_at,updated_at) SELECT id,id,workspace_id,'LifeOS','adult',created_at,created_at FROM local_identity");
        await tx.rawInsert("INSERT OR IGNORE INTO local_memberships(id,owner_id,workspace_id,profile_id,role,permissions,created_at,updated_at) SELECT id,id,workspace_id,id,'owner',7,created_at,created_at FROM local_identity");
      });
      final identity = (await db.query('local_identity')).single;
      return LocalStore._(db, identity['id'] as String, identity['workspace_id'] as String);
    } catch (_) {
      await db.close();
      rethrow;
    }
  }

  static Future<void> _migrate(sql.Database db, int oldVersion, int newVersion) async {
    for (var version = oldVersion + 1; version <= newVersion; version++) {
      final source = await rootBundle.loadString('assets/migrations/${version.toString().padLeft(3, '0')}.sql');
      for (final statement in source.split(';')) {
        if (statement.trim().isNotEmpty) await db.execute(statement);
      }
      if(version==10){for(final table in ['projects','project_milestones']){for(final row in await db.query(table,where:'due_on IS NOT NULL')){
        final id=_uuid.v4();
        await db.insert('calendar_entries',{'id':id,'owner_id':row['owner_id'],'workspace_id':row['workspace_id'],'title':row['name'],'local_start':'${row['due_on']}T09:00:00','timezone':'device','all_day':1,'repeat_rule':'none','reminder':0,'reminder_mode':'standard','created_at':row['created_at'],'updated_at':row['updated_at'],'deleted_at':row['deleted_at']??(row['status']=='done'||row['completed']==1?DateTime.now().toUtc().toIso8601String():null)});
        await db.update(table,{'calendar_id':id},where:'id=?',whereArgs:[row['id']]);
      }}}
    }
  }

  @override
  Future<String> apply(AppAction action) => _db.transaction((tx) async {
    final payload = jsonEncode(action.payload);
    final previous = await tx.query('operations', where: 'id = ?', whereArgs: [action.operationId]);
    if (previous.isNotEmpty) {
      if (previous.single['payload'] != payload) throw const DomainFailure('operation_conflict');
      return previous.single['result_id'] as String;
    }
    final id = switch (action) {
      OfflineAction() => action.id, CompleteTask() => action.id, RecordMutation() => action.id,
      SaveCalendar() => action.id ?? _uuid.v4(), DeleteCalendar() => action.id,
      SetOccurrence() => action.entryId, _ => _uuid.v4(),
    };
    final now = DateTime.now().toUtc().toIso8601String();
    var resultId=id;
    final metadata = {'id': id, 'owner_id': ownerId, 'workspace_id': workspaceId,
      'visibility': 'private', 'created_at': now, 'updated_at': now};
    switch (action) {
      case OfflineAction(): resultId=await _applyOffline(tx,action,now);
      case CreateMoney():
        final currency = Currency.fromCode(action.currencyCode);
        await tx.insert('transactions', {...metadata, 'kind': action.kind.name,
          'amount_minor': currency.parse(action.amount), 'currency': currency.code,
          'minor_digits': currency.digits, 'label': action.label.trim(), 'occurred_on': dateOnly(action.date)});
      case CreateTask():
        await tx.insert('tasks', {...metadata, 'title': action.title.trim()});
        if (action.schedule != null) await _saveCalendar(tx, _uuid.v4(), action.title.trim(), action.schedule!, now, taskId: id);
      case CreateNote():
        await tx.insert('notes', {...metadata, 'body': action.body.trim()});
        if (action.schedule != null) await _saveCalendar(tx, _uuid.v4(), action.body.trim().split('\n').first, action.schedule!, now, noteId: id);
      case CompleteTask():
        await _mutate(tx, 'tasks', id, action.expectedRevision,
          {'completed': action.completed ? 1 : 0}, action.operationId, now);
      case RecordMutation():
        final table = switch (action.kind) {
          EntryKind.expense || EntryKind.income => 'transactions',
          EntryKind.task => 'tasks', EntryKind.note => 'notes',
        };
        final values = <String, Object?>{};
        if (action is EditTask && action.updateSchedule || action is EditNote && action.updateSchedule) {
          final expected = action is EditTask ? action.expectedScheduleRevision : (action as EditNote).expectedScheduleRevision;
          final linked = await tx.query('calendar_entries', where: '${table == 'tasks' ? 'task_id' : 'note_id'} = ? AND deleted_at IS NULL', whereArgs: [id]);
          if (expected == null || expected != (linked.firstOrNull?['revision'] ?? 0)) throw const DomainFailure('revision_conflict');
        }
        switch (action) {
          case EditMoney():
            final currency = Currency.fromCode(action.currencyCode);
            values.addAll({'kind': action.kind.name, 'amount_minor': currency.parse(action.amount),
              'currency': currency.code, 'minor_digits': currency.digits,
              'label': action.label.trim(), 'occurred_on': dateOnly(action.date)});
          case EditTask(): values['title'] = action.title.trim();
          case EditNote(): values['body'] = action.body.trim();
          case DeleteRecord(): values['deleted_at'] = now;
          case UndoRecordChange():
            final changes = await tx.query('record_changes', where: 'table_name = ? AND record_id = ? AND revision = ?',
              whereArgs: [table, id, action.expectedRevision]);
            if (changes.isEmpty) throw const DomainFailure('undo_unavailable');
            values.addAll(await _historySnapshot(tx,table,jsonDecode(changes.single['before_json'] as String),id));
            for (final key in ['id', 'owner_id', 'workspace_id', 'visibility', 'created_at', 'updated_at', 'revision']) {
              values.remove(key);
            }
            values.remove('__schedule'); values.remove('__splits');
            if(table=='transactions') values.putIfAbsent('category_id',()=>null);
        }
        await _mutate(tx, table, id, action.expectedRevision, values, action.operationId, now,
          allowDeleted: action is UndoRecordChange, expectedKind: action.kind);
        if(table=='transactions') {
          if(action is UndoRecordChange) {
            final change=(await tx.query('record_changes',where:'table_name=? AND record_id=? AND revision=?',whereArgs:[table,id,action.expectedRevision])).single;
            final before=jsonDecode(change['before_json'] as String) as Map;
            final rows=before['__splits'] as List? ?? [];
            await tx.delete('transaction_splits',where:'transaction_id=?',whereArgs:[id]);
            for(final row in rows) { await tx.insert('transaction_splits',Map<String,Object?>.from(row as Map)); }
          }
          await _auditMoneyAfter(tx,id,action.operationId);
          await _validateWealth(tx);
        }
        if (action is EditTask && action.updateSchedule) {
          await _linkedSchedule(tx, id, 'task_id', action.title.trim(), action.schedule, now);
        }
        if (action is EditNote && action.updateSchedule) {
          await _linkedSchedule(tx, id, 'note_id', action.body.trim().split('\n').first, action.schedule, now);
        }
        if (action is UndoRecordChange && table != 'transactions') {
          final changes = await tx.query('record_changes', where: 'table_name = ? AND record_id = ? AND revision = ?',
            whereArgs: [table, id, action.expectedRevision]);
          final before = Map<String, Object?>.from(jsonDecode(changes.single['before_json'] as String) as Map);
          if (before.containsKey('__schedule')) {
            await _restoreLinked(tx, id, table == 'tasks' ? 'task_id' : 'note_id', before['__schedule'], now);
          }
        }
        if (table != 'transactions') {
          final updated = (await tx.query(table, where: 'id = ?', whereArgs: [id])).single;
          final schedule = await tx.query('calendar_entries', where: '${table == 'tasks' ? 'task_id' : 'note_id'} = ? AND deleted_at IS NULL', whereArgs: [id]);
          await tx.update('record_changes', {'after_json': jsonEncode({...updated, '__schedule': schedule.firstOrNull})},
            where: 'operation_id = ?', whereArgs: [action.operationId]);
        }
      case SaveCalendar():
        if(action.id!=null)await _guardModuleCalendar(tx,id);
        if (action.taskId != null || action.noteId != null) throw const DomainFailure('invalid_action');
        if (action.id != null) {
          final existing = await tx.query('calendar_entries', where: 'id = ?', whereArgs: [id]);
          if (existing.isNotEmpty && (existing.single['task_id'] != null || existing.single['note_id'] != null)) throw const DomainFailure('invalid_action');
        }
        await _saveCalendar(tx, id, action.title.trim(), action.schedule, now,
          taskId: action.taskId, noteId: action.noteId, expectedRevision: action.expectedRevision);
      case DeleteCalendar():
        await _guardModuleCalendar(tx,id);
        final linked = await tx.query('calendar_entries', where: 'id = ? AND (task_id IS NOT NULL OR note_id IS NOT NULL)', whereArgs: [id]);
        if (linked.isNotEmpty) throw const DomainFailure('invalid_action');
        final count = await tx.update('calendar_entries', {'deleted_at': now, 'updated_at': now, 'revision': action.expectedRevision + 1},
          where: 'id = ? AND owner_id = ? AND workspace_id = ? AND revision = ? AND deleted_at IS NULL',
          whereArgs: [id, ownerId, workspaceId, action.expectedRevision]);
        if (count != 1) throw const DomainFailure('revision_conflict');
      case SetOccurrence():
        final entry = await tx.query('calendar_entries', where: 'id = ? AND owner_id = ? AND workspace_id = ? AND deleted_at IS NULL',
          whereArgs: [id, ownerId, workspaceId]);
        if (entry.isEmpty) throw const DomainFailure('record_missing');
        if (action.expectedRevision != null && entry.single['revision'] != action.expectedRevision) throw const DomainFailure('revision_conflict');
        if (action.status == OccurrenceStatus.completed && entry.single['task_id'] != null && entry.single['repeat_rule'] == 'none') {
          final task = (await tx.query('tasks', where: 'id = ?', whereArgs: [entry.single['task_id']])).single;
          if (task['completed'] != 1) await _mutate(tx, 'tasks', entry.single['task_id'] as String, null, {'completed': 1}, action.operationId, now);
        }
        await tx.insert('calendar_occurrences', {'entry_id': id, 'revision': entry.single['revision'], 'epoch': action.epoch,
          'status': action.status.name, 'snoozed_until': action.snoozedUntil, 'updated_at': now},
          conflictAlgorithm: sql.ConflictAlgorithm.replace);
        final habits=await tx.query('habits',where:'calendar_id=? AND deleted_at IS NULL AND paused=0',whereArgs:[id]);
        if(habits.isNotEmpty&&action.status==OccurrenceStatus.completed){
          final habit=habits.single,spec=entry.single;
          final utc=DateTime.fromMillisecondsSinceEpoch(action.epoch,isUtc:true);
          final civil=(spec['timezone']=='device'?utc.toLocal():tz.TZDateTime.from(utc,tz.getLocation(spec['timezone'] as String)));
          final checks=await tx.query('habit_checks',where:'habit_id=? AND local_date=?',whereArgs:[habit['id'],dateOnly(civil)]);
          final prior=checks.firstOrNull;
          await _writeEntity(tx,'habit_checks',CheckHabit(action.operationId,prior?['id'] as String? ?? _uuid.v4(),prior?['revision'] as int? ?? 0,habitId:habit['id'] as String,localDate:dateOnly(civil),timezone:spec['timezone'] as String),{'habit_id':habit['id'],'local_date':dateOnly(civil),'timezone':spec['timezone'],'completed':1,'deleted_at':null},now,undo:true);
        }
    }
    await tx.insert('operations', {'id': action.operationId, 'payload': payload, 'result_id': resultId, 'created_at': now});
    return resultId;
  });

  Future<void> _mutate(sql.Transaction tx, String table, String id, int? revision,
      Map<String, Object?> values, String operationId, String now, {bool allowDeleted = false, EntryKind? expectedKind}) async {
    final rows = await tx.query(table, where: 'id = ? AND owner_id = ? AND workspace_id = ?',
      whereArgs: [id, ownerId, workspaceId]);
    if (rows.length != 1 || (!allowDeleted && rows.single['deleted_at'] != null)) {
      throw const DomainFailure('record_missing');
    }
    final before = <String, Object?>{...rows.single};
    if (table == 'transactions' && expectedKind != null && before['kind'] != expectedKind.name) throw const DomainFailure('invalid_action');
    if (table == 'tasks' || table == 'notes') {
      final linked = await tx.query('calendar_entries', where: '${table == 'tasks' ? 'task_id' : 'note_id'} = ? AND deleted_at IS NULL', whereArgs: [id]);
      before['__schedule'] = linked.firstOrNull;
    }
    if(table=='transactions') before['__splits']=await tx.query('transaction_splits',where:'transaction_id=?',whereArgs:[id]);
    final actual = before['revision'] as int;
    if (revision != null && actual != revision) throw const DomainFailure('revision_conflict');
    final after = {...before, ...values, 'updated_at': now, 'revision': actual + 1};
    final count = await tx.update(table, {...values, 'updated_at': now, 'revision': actual + 1},
      where: 'id = ? AND owner_id = ? AND workspace_id = ? AND revision = ?',
      whereArgs: [id, ownerId, workspaceId, actual]);
    if (count != 1) throw const DomainFailure('revision_conflict');
    await tx.insert('record_changes', {'id': _uuid.v4(), 'operation_id': operationId,
      'table_name': table, 'record_id': id, 'revision': actual + 1,
      'before_json': jsonEncode(before), 'after_json': jsonEncode(after), 'created_at': now});
  }

  Future<void> _saveCalendar(sql.Transaction tx, String id, String title, ScheduleSpec spec, String now,
      {String? taskId, String? noteId, int? expectedRevision}) async {
    for (final link in [(taskId, 'tasks'), (noteId, 'notes')]) {
      if (link.$1 != null) {
        final rows = await tx.query(link.$2, where: 'id = ? AND owner_id = ? AND workspace_id = ? AND deleted_at IS NULL',
          whereArgs: [link.$1, ownerId, workspaceId]);
        if (rows.length != 1) throw const DomainFailure('record_missing');
      }
    }
    final values = {'title': title, 'task_id': taskId, 'note_id': noteId, 'local_start': spec.localStart,
      'timezone': spec.timezone, 'all_day': spec.allDay ? 1 : 0, 'repeat_rule': spec.repeat.name,
      'repeat_interval': spec.interval, 'until_date': spec.until, 'reminder': spec.reminder ? 1 : 0,
      'reminder_mode': spec.mode.name, 'updated_at': now};
    if (expectedRevision == null) {
      await tx.insert('calendar_entries', {...values, 'id': id, 'owner_id': ownerId,
        'workspace_id': workspaceId, 'created_at': now});
    } else {
      final changed = await tx.update('calendar_entries', {...values, 'revision': expectedRevision + 1},
        where: 'id = ? AND owner_id = ? AND workspace_id = ? AND revision = ? AND deleted_at IS NULL',
        whereArgs: [id, ownerId, workspaceId, expectedRevision]);
      if (changed != 1) throw const DomainFailure('revision_conflict');
      // Old occurrence revisions remain in the encrypted history; they cannot affect the edited series.
    }
  }

  Future<void> _linkedSchedule(sql.Transaction tx, String recordId, String column, String title, ScheduleSpec? spec, String now) async {
    final rows = await tx.query('calendar_entries', where: '$column = ? AND deleted_at IS NULL', whereArgs: [recordId]);
    if (spec == null) {
      if (rows.isNotEmpty) { await tx.update('calendar_entries', {'deleted_at': now, 'updated_at': now,
        'revision': (rows.single['revision'] as int) + 1}, where: 'id = ?', whereArgs: [rows.single['id']]); }
      return;
    }
    await _saveCalendar(tx, rows.isEmpty ? _uuid.v4() : rows.single['id'] as String, title, spec, now,
      taskId: column == 'task_id' ? recordId : null, noteId: column == 'note_id' ? recordId : null,
      expectedRevision: rows.isEmpty ? null : rows.single['revision'] as int);
  }

  Future<void> _restoreLinked(sql.Transaction tx, String id, String column, Object? snapshot, String now) async {
    final active = await tx.query('calendar_entries', where: '$column = ? AND deleted_at IS NULL', whereArgs: [id]);
    for (final row in active) {
      await tx.update('calendar_entries', {'deleted_at': now, 'updated_at': now, 'revision': (row['revision'] as int) + 1},
        where: 'id = ?', whereArgs: [row['id']]);
    }
    if (snapshot is Map) {
      final old = Map<String, Object?>.from(snapshot);
      final current = (await tx.query('calendar_entries', where: 'id = ?', whereArgs: [old['id']])).single;
      old['revision'] = (current['revision'] as int) + 1;
      old['updated_at'] = now;
      old['native_synced_revision'] = 0;
      await tx.update('calendar_entries', old, where: 'id = ?', whereArgs: [old['id']]);
      final previousRevision = (snapshot['revision'] as int);
      await tx.rawInsert('''INSERT INTO calendar_occurrences(entry_id,revision,epoch,status,snoozed_until,updated_at)
        SELECT entry_id,?,epoch,status,snoozed_until,? FROM calendar_occurrences WHERE entry_id=? AND revision=?''',
        [old['revision'],now,old['id'],previousRevision]);
    }
  }

  @override
  Future<List<Record>> records() async {
    final result = <Record>[];
    for (final table in ['transactions', 'tasks', 'notes']) {
      final rows = await _db.query(table,
        where: 'owner_id = ? AND workspace_id = ? AND deleted_at IS NULL', whereArgs: [ownerId, workspaceId]);
      for (final row in rows) {
        final kind = table == 'transactions' ? EntryKind.values.byName(row['kind'] as String)
          : table == 'tasks' ? EntryKind.task : EntryKind.note;
        result.add(Record(id: row['id'] as String, kind: kind,
          text: (row[table == 'transactions' ? 'label' : table == 'tasks' ? 'title' : 'body'] as String),
          createdAt: DateTime.parse(row['created_at'] as String),
          amountMinor: row['amount_minor'] as int?,
          currency: table == 'transactions' ? Currency(row['currency'] as String, row['minor_digits'] as int) : null,
          date: row['occurred_on'] as String?, completed: row['completed'] == 1,
          accountId: row['account_id'] as String?, categoryId: row['category_id'] as String?, revision: row['revision'] as int, updatedAt: DateTime.parse(row['updated_at'] as String)));
      }
    }
    result.sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return result;
  }

  @override
  Future<Map<String, String>> settings() async => {
    for (final row in await _db.query('settings')) row['key'] as String: row['value'] as String,
  };

  @override
  Future<void> setSetting(String key, String value) async {
    await _db.insert('settings', {'key': key, 'value': value}, conflictAlgorithm: sql.ConflictAlgorithm.replace);
  }

  @override
  Future<void> close() => _db.close();

  @override
  Future<List<CalendarEntry>> calendarEntries() async {
    final rows = await _db.rawQuery('''SELECT c.*, COALESCE(t.title, n.body, c.title) AS display_title FROM calendar_entries c
      LEFT JOIN tasks t ON c.task_id = t.id LEFT JOIN notes n ON c.note_id = n.id
      WHERE c.owner_id = ? AND c.workspace_id = ? AND c.deleted_at IS NULL
      AND (c.task_id IS NULL OR t.deleted_at IS NULL)
      AND (c.note_id IS NULL OR n.deleted_at IS NULL)''', [ownerId, workspaceId]);
    return [for (final r in rows) CalendarEntry(id: r['id'] as String, title: (r['display_title'] as String).split('\n').first,
      taskId: r['task_id'] as String?, noteId: r['note_id'] as String?, revision: r['revision'] as int,
      syncedRevision: r['native_synced_revision'] as int,
      schedule: ScheduleSpec(localStart: r['local_start'] as String, timezone: r['timezone'] as String,
        allDay: r['all_day'] == 1, repeat: RepeatRule.values.byName(r['repeat_rule'] as String),
        interval: r['repeat_interval'] as int, until: r['until_date'] as String?, reminder: r['reminder'] == 1,
        mode: ReminderMode.values.byName(r['reminder_mode'] as String)))];
  }

  @override
  Future<List<OccurrenceState>> occurrenceStates() async => [
    for (final r in await _db.rawQuery('''SELECT o.* FROM calendar_occurrences o JOIN calendar_entries c ON c.id = o.entry_id
      WHERE c.owner_id = ? AND c.workspace_id = ? AND o.revision = c.revision''', [ownerId, workspaceId]))
      OccurrenceState(r['entry_id'] as String, r['epoch'] as int, OccurrenceStatus.values.byName(r['status'] as String),
        snoozedUntil: r['snoozed_until'] as int?, revision: r['revision'] as int),
  ];

  @override
  Future<void> markCalendarSynced(String id, int revision) async {
    await _db.update('calendar_entries', {'native_synced_revision': revision},
      where: 'id = ? AND revision = ? AND owner_id = ? AND workspace_id = ?', whereArgs: [id, revision, ownerId, workspaceId]);
  }

  @override
  Future<Map<OfflineTable,List<Map<String,Object?>>>> offlineData({Set<OfflineTable>? tables}) async {
    final result=<OfflineTable,List<Map<String,Object?>>>{};
    for(final table in tables ?? {OfflineTable.accounts,OfflineTable.categories,OfflineTable.transfers,OfflineTable.budgets,OfflineTable.plannedPayments,OfflineTable.goals,OfflineTable.goalEntries,OfflineTable.debts,OfflineTable.debtEntries,OfflineTable.assets,OfflineTable.investmentEntries,OfflineTable.importBatches,OfflineTable.projects,OfflineTable.milestones,OfflineTable.taskPlacements,OfflineTable.habits,OfflineTable.habitChecks,OfflineTable.subjects,OfflineTable.studyItems,OfflineTable.checklists,OfflineTable.checklistItems,OfflineTable.noteMetadata,OfflineTable.recordLinks,OfflineTable.wellness,OfflineTable.dashboard,OfflineTable.profiles,OfflineTable.memberships}) {
      final rows=[for(final row in await _db.query(table.sqlName,where:'owner_id=? AND workspace_id=? AND deleted_at IS NULL',whereArgs:[ownerId,workspaceId],orderBy:'created_at DESC,id')) Map<String,Object?>.from(row)];
      if(table==OfflineTable.habits){for(final row in rows){row['__pauses']=await _db.query('habit_pauses',where:'habit_id=?',whereArgs:[row['id']]);}}
      if([OfflineTable.projects,OfflineTable.milestones,OfflineTable.habits,OfflineTable.studyItems,OfflineTable.debts,OfflineTable.plannedPayments].contains(table)) {
        for(final row in rows){if(row['calendar_id']!=null)row['__schedule']=(await _db.query('calendar_entries',where:'id=? AND owner_id=? AND workspace_id=?',whereArgs:[row['calendar_id'],ownerId,workspaceId])).firstOrNull;}
      }
      result[table]=rows;
    }
    return result;
  }
  @override
  Future<List<Map<String,Object?>>> splits() async => [for(final row in await _db.rawQuery('SELECT s.* FROM transaction_splits s JOIN transactions t ON t.id=s.transaction_id WHERE t.owner_id=? AND t.workspace_id=? AND t.deleted_at IS NULL',[ownerId,workspaceId])) Map<String,Object?>.from(row)];

  @override
  Future<Set<String>> importedOrigins() async => {for(final r in await _db.rawQuery('SELECT r.origin_key FROM import_rows r JOIN import_batches b ON b.id=r.batch_id WHERE b.owner_id=? AND b.workspace_id=?',[ownerId,workspaceId]))r['origin_key'] as String};

  static const _snapshotTables = ['local_identity','workspaces','accounts','categories','transactions','tasks','notes','operations','record_changes','calendar_entries','calendar_occurrences','settings','transfers','transaction_splits','budgets','planned_payments','planned_confirmations','savings_goals','savings_entries','debts','debt_entries','investment_assets','investment_entries','import_batches','import_rows','projects','project_milestones','task_placements','habits','habit_checks','learning_subjects','study_items','checklists','checklist_items','note_metadata','record_links','wellness_entries','dashboard_configs','local_profiles','local_memberships','habit_pauses','entity_changes'];

  @override
  Future<Map<String, Object?>> exportSnapshot() => _db.transaction((tx) async => {
    'schemaVersion': schemaVersion, 'tables': {for (final table in _snapshotTables) table: await tx.query(table)},
  });

  Map<String,Object?> _upgradeBackup(Map<String,Object?> data) {
    if(data['schemaVersion']==schemaVersion) return data;
    if(![1,2,3,4,5,6,7,8,9,10].contains(data['schemaVersion'])||data['tables'] is! Map) throw const DomainFailure('backup_invalid');
    final tables=Map<String,Object?>.from(jsonDecode(jsonEncode(data['tables'])) as Map);
    final version=data['schemaVersion'] as int;
    final legacy=['local_identity','workspaces','accounts','transactions','tasks','notes','settings','operations',if(version>=2)'record_changes',if(version>=3)...['calendar_entries','calendar_occurrences'],if(version>=4)...['categories','transfers','transaction_splits','budgets','planned_payments','planned_confirmations','entity_changes'],if(version>=5)...['savings_goals','savings_entries','debts','debt_entries','investment_assets','investment_entries'],if(version>=6)...['import_batches','import_rows'],if(version>=7)...['projects','project_milestones','task_placements','habits','habit_checks','learning_subjects','study_items','checklists','checklist_items','note_metadata','record_links','wellness_entries','dashboard_configs'],if(version>=8)...['local_profiles','local_memberships'],if(version>=9)'habit_pauses'];
    if(tables.length!=legacy.length||!legacy.every(tables.containsKey)) throw const DomainFailure('backup_invalid');
    for(final table in _snapshotTables) { tables.putIfAbsent(table,()=> <Object?>[]); }
    if(version<4) { for(final raw in tables['accounts'] as List) {
      final r=raw as Map; final owner=(tables['local_identity'] as List).first as Map;
      r.addAll({'name':r['currency'],'kind':'cash','archived':0,'revision':1,'created_at':owner['created_at'],'updated_at':owner['created_at'],'deleted_at':null});
    }
    }
    if(version<4) for(final raw in tables['transactions'] as List) { (raw as Map)['category_id']=null; }
    if(version<8) {
      final identity=(tables['local_identity'] as List).single as Map;
      final meta={'id':identity['id'],'owner_id':identity['id'],'workspace_id':identity['workspace_id'],'created_at':identity['created_at'],'updated_at':identity['created_at'],'revision':1,'deleted_at':null};
      tables['local_profiles']=[{...meta,'name':'LifeOS','kind':'adult','guardian_id':null,'archived':0}];
      tables['local_memberships']=[{...meta,'profile_id':identity['id'],'role':'owner','permissions':7}];
    }
    if(version<10){for(final table in ['projects','project_milestones']){for(final raw in tables[table] as List){
      final row=raw as Map;row['calendar_id']=null;if(row['due_on']==null)continue;
      final id=_uuid.v4();row['calendar_id']=id;
      (tables['calendar_entries'] as List).add({'id':id,'owner_id':row['owner_id'],'workspace_id':row['workspace_id'],'title':row['name'],'task_id':null,'note_id':null,'local_start':'${row['due_on']}T09:00:00','timezone':'device','all_day':1,'repeat_rule':'none','repeat_interval':1,'until_date':null,'reminder':0,'reminder_mode':'standard','revision':1,'native_synced_revision':0,'created_at':row['created_at'],'updated_at':row['updated_at'],'deleted_at':row['deleted_at']??(row['status']=='done'||row['completed']==1?DateTime.now().toUtc().toIso8601String():null)});
    }}}
    return {'schemaVersion':schemaVersion,'tables':tables};
  }

  @override
  Future<void> restoreSnapshot(Map<String, Object?> data) async {
    data=_upgradeBackup(data);
    if (data['schemaVersion'] != schemaVersion || data['tables'] is! Map) throw const DomainFailure('backup_invalid');
    final tables = Map<String, Object?>.from(data['tables'] as Map);
    if (tables.length != _snapshotTables.length || !_snapshotTables.every(tables.containsKey)) {
      throw const DomainFailure('backup_invalid');
    }
    for (final value in tables.values) {
      if (value is! List || value.length > 50000 || value.any((r) => r is! Map)) throw const DomainFailure('backup_invalid');
    }
    final identityRows = tables['local_identity'] as List;
    if (identityRows.length != 1) throw const DomainFailure('backup_invalid');
    final identity = Map<String, Object?>.from(identityRows.single as Map);
    final newOwner = identity['id'] as String?, newSpace = identity['workspace_id'] as String?;
    if (newOwner == null || newSpace == null) throw const DomainFailure('backup_invalid');
    final workspaces = tables['workspaces'] as List;
    if (workspaces.length != 1 || (workspaces.single as Map)['id'] != newSpace) throw const DomainFailure('backup_invalid');
    await _db.transaction((tx) async {
      await tx.execute('PRAGMA defer_foreign_keys=ON');
      for (final table in _snapshotTables.reversed) { await tx.delete(table); }
      for (final table in _snapshotTables) {
        final definitions = await tx.rawQuery('PRAGMA table_info($table)');
        final columns = definitions.map((c) => c['name']).toSet();
        for (final raw in tables[table] as List) {
          final row = Map<String, Object?>.from(raw as Map);
          if (row.length != columns.length || row.keys.any((key) => !columns.contains(key)) ||
              row.values.any((v) => v != null && v is! String && v is! num) ||
              row.containsKey('owner_id') && row['owner_id'] != newOwner ||
              row.containsKey('workspace_id') && row['workspace_id'] != newSpace) {
            throw const DomainFailure('backup_invalid');
          }
          for (final column in definitions) {
            final value = row[column['name']];
            if (value == null && (column['notnull'] == 1 || (column['pk'] as int) > 0) ||
                value != null && column['type'] == 'INTEGER' && value is! int ||
                value != null && column['type'] == 'TEXT' && value is! String) { throw const DomainFailure('backup_invalid'); }
          }
          if (row.containsKey('id') && (row['id'] as String).isEmpty) throw const DomainFailure('backup_invalid');
          for (final field in ['created_at','updated_at','deleted_at']) {
            if (row[field] != null && DateTime.tryParse(row[field] as String) == null) throw const DomainFailure('backup_invalid');
          }
          if (table == 'settings') {
            final key = row['key'], value = row['value'];
            final choices = <String,List<String>>{
              'theme':['system','light','dark'], 'week_start':['1','7'], 'snooze_minutes':['5','10','15','30'],
              'notification_content':['hide','show'], 'region':['ru','en','de','fr','es','it','pt','kk','uz','uk','ka','az','hy','tg','ky']};
            if (choices.containsKey(key) && !choices[key]!.contains(value)) throw const DomainFailure('backup_invalid');
            if (key == 'appearance_v1') {
              try { Appearance.decode(value as String); } catch (_) { throw const DomainFailure('backup_invalid'); }
            }
            if (key == 'currency') Currency.fromCode(value as String);
            if (key == 'language' && !RegExp(r'^[a-z]{2,3}(?:-[A-Za-z]{2,8})*$').hasMatch(value as String)) throw const DomainFailure('backup_invalid');
            if (key == 'timezone') CalendarEngine.validate(ScheduleSpec(localStart:'2026-01-01T09:00:00',timezone:value as String));
          }
          if (table == 'transactions') {
            final currency = Currency.fromCode(row['currency'] as String);
            final date = DateTime.tryParse(row['occurred_on'] as String);
            if (currency.digits != row['minor_digits'] || date == null || dateOnly(date) != row['occurred_on'] || date.year < 1900 || date.year > 2200) throw const DomainFailure('backup_invalid');
          }
          if (table == 'calendar_entries') {
            CalendarEngine.validate(ScheduleSpec(localStart: row['local_start'] as String, timezone: row['timezone'] as String,
              repeat: RepeatRule.values.byName(row['repeat_rule'] as String), interval: row['repeat_interval'] as int, until: row['until_date'] as String?));
            row['native_synced_revision'] = 0;
          }
          _entitySemantics(table,row);
          await tx.insert(table, row);
        }
      }
      for (final raw in tables['record_changes'] as List) {
        final change = Map<String,Object?>.from(raw as Map);
        final table = change['table_name'] as String;
        if (!['transactions','tasks','notes'].contains(table) ||
            (await tx.query(table,columns:['id'],where:'id = ?',whereArgs:[change['record_id']])).isEmpty) { throw const DomainFailure('backup_invalid'); }
        for (final field in ['before_json','after_json']) {
          final decoded = await _historySnapshot(tx,table,jsonDecode(change[field] as String),change['record_id'] as String,owner:newOwner,space:newSpace);
          if (decoded['id'] != change['record_id'] || decoded['owner_id'] != newOwner ||
              decoded['workspace_id'] != newSpace || decoded['revision'] is! int) { throw const DomainFailure('backup_invalid'); }
          final schedule = decoded['__schedule'];
          if (schedule != null) {
            if (schedule is! Map || schedule['owner_id'] != newOwner || schedule['workspace_id'] != newSpace ||
                schedule[table == 'tasks' ? 'task_id' : 'note_id'] != change['record_id'] || schedule['revision'] is! int ||
                (await tx.query('calendar_entries',columns:['id'],where:'id = ?',whereArgs:[schedule['id']])).isEmpty) { throw const DomainFailure('backup_invalid'); }
          }
        }
      }
      for(final row in await tx.query('transactions')) { await _moneyRelations(tx,row['id'] as String,owner:newOwner,space:newSpace); }
      await _validateOfflineRestore(tx,newOwner,newSpace);
      if ((await tx.rawQuery('PRAGMA foreign_key_check')).isNotEmpty) throw const DomainFailure('backup_invalid');
    });
    ownerId = newOwner;
    workspaceId = newSpace;
  }
}
