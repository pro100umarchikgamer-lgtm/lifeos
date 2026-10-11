import 'dart:convert';
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

class LocalStore implements ActionStore {
  LocalStore._(this._db, this.ownerId, this.workspaceId);
  final sql.Database _db;
  final String ownerId;
  final String workspaceId;
  static const _uuid = Uuid();
  static const schemaVersion = 2;

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
        if (identity.isNotEmpty) return;
        final owner = _uuid.v4();
        final workspace = _uuid.v4();
        final now = DateTime.now().toUtc().toIso8601String();
        await tx.insert('local_identity', {'id': owner, 'workspace_id': workspace, 'created_at': now});
        await tx.insert('workspaces', {'id': workspace, 'owner_id': owner, 'kind': 'personal', 'created_at': now});
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
      CompleteTask() => action.id, RecordMutation() => action.id, _ => _uuid.v4(),
    };
    final now = DateTime.now().toUtc().toIso8601String();
    final metadata = {'id': id, 'owner_id': ownerId, 'workspace_id': workspaceId,
      'visibility': 'private', 'created_at': now, 'updated_at': now};
    switch (action) {
      case CreateMoney():
        final currency = Currency.fromCode(action.currencyCode);
        await tx.insert('transactions', {...metadata, 'kind': action.kind.name,
          'amount_minor': currency.parse(action.amount), 'currency': currency.code,
          'minor_digits': currency.digits, 'label': action.label.trim(), 'occurred_on': dateOnly(action.date)});
      case CreateTask():
        await tx.insert('tasks', {...metadata, 'title': action.title.trim()});
      case CreateNote():
        await tx.insert('notes', {...metadata, 'body': action.body.trim()});
      case CompleteTask():
        await _mutate(tx, 'tasks', id, action.expectedRevision,
          {'completed': action.completed ? 1 : 0}, action.operationId, now);
      case RecordMutation():
        final table = switch (action.kind) {
          EntryKind.expense || EntryKind.income => 'transactions',
          EntryKind.task => 'tasks', EntryKind.note => 'notes',
        };
        final values = <String, Object?>{};
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
            values.addAll(Map<String, Object?>.from(jsonDecode(changes.single['before_json'] as String) as Map));
            for (final key in ['id', 'owner_id', 'workspace_id', 'visibility', 'created_at', 'updated_at', 'revision']) {
              values.remove(key);
            }
        }
        await _mutate(tx, table, id, action.expectedRevision, values, action.operationId, now,
          allowDeleted: action is UndoRecordChange);
    }
    await tx.insert('operations', {'id': action.operationId, 'payload': payload, 'result_id': id, 'created_at': now});
    return id;
  });

  Future<void> _mutate(sql.Transaction tx, String table, String id, int? revision,
      Map<String, Object?> values, String operationId, String now, {bool allowDeleted = false}) async {
    final rows = await tx.query(table, where: 'id = ? AND owner_id = ? AND workspace_id = ?',
      whereArgs: [id, ownerId, workspaceId]);
    if (rows.length != 1 || (!allowDeleted && rows.single['deleted_at'] != null)) {
      throw const DomainFailure('record_missing');
    }
    final before = rows.single;
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
          revision: row['revision'] as int, updatedAt: DateTime.parse(row['updated_at'] as String)));
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
}
