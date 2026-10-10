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
  static const schemaVersion = 1;

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
    final id = action is CompleteTask ? action.id : _uuid.v4();
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
        final count = await tx.rawUpdate('UPDATE tasks SET completed = ?, updated_at = ?, revision = revision + 1 WHERE id = ? AND owner_id = ? AND workspace_id = ? AND deleted_at IS NULL',
          [action.completed ? 1 : 0, now, id, ownerId, workspaceId]);
        if (count != 1) throw const DomainFailure('record_missing');
    }
    await tx.insert('operations', {'id': action.operationId, 'payload': payload, 'result_id': id, 'created_at': now});
    return id;
  });

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
          date: row['occurred_on'] as String?, completed: row['completed'] == 1));
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
