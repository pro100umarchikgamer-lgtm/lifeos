import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

import 'contracts.dart';
import 'api.dart';
import 'engine.dart';

class FamilyController extends ChangeNotifier {
  FamilyController(this.store, {FlutterSecureStorage? secure})
    : secure =
          secure ??
          const FlutterSecureStorage(
            aOptions: AndroidOptions(encryptedSharedPreferences: true),
          );
  final SyncStore store;
  final FlutterSecureStorage secure;
  static const uuid = Uuid();
  static const configuredOrigin = String.fromEnvironment('LIFEOS_API_ORIGIN');
  String get accountOrigin => api?.base.origin ?? configuredOrigin;
  FamilyApi? api;
  Json? account, roster;
  List<Json> spaces = [], records = [], pending = [], issues = [];
  String? workspace, error;
  bool busy = false;
  bool _disposed = false;
  Timer? _retry;
  int _recoveryFailures = 0;
  SyncEngine? _engine;
  int _generation = 0;
  String get scope => '${api!.base.origin}|${account!['user_id']}';
  bool get verified => account?['verified'] == true;
  Set<String> get creatableKinds {
    if (roster == null) return {};
    if (roster!['space']['role'] != 'child') {
      return {
        'note',
        'task',
        'account',
        'transaction',
        'transfer',
        'budget',
        'event',
        'shopping',
        'request',
      };
    }
    final profile = (roster!['profiles'] as List)
        .map(object)
        .where((p) => p['id'] == roster!['space']['profile_id'])
        .firstOrNull;
    final permissions = (profile?['permissions'] as List? ?? []).toSet();
    return {
      if (permissions.contains('record_spending')) 'transaction',
      if (permissions.contains('create_tasks')) 'task',
      if (permissions.contains('request_money')) 'request',
    };
  }

  bool get parent => ['parent', 'owner'].contains(roster?['space']?['role']);
  void publish() {
    if (!_disposed) notifyListeners();
  }

  Future<void> initialize() async {
    try {
      final raw = await secure.read(key: 'lifeos.sync.session');
      final saved = raw == null ? null : object(jsonDecode(raw));
      final endpoint = saved?['endpoint'] as String? ??
          await secure.read(key: 'lifeos.sync.endpoint');
      if (endpoint == null) return;
      api = FamilyApi(endpoint);
      api!.token = saved?['token'] as String? ??
          await secure.read(key: 'lifeos.sync.token');
      api!.refreshToken = saved?['refresh_token'] as String?;
      final initialized = api!;
      initialized.onRotated = (result) => _acceptRotation(initialized, result);
      // Identity is stored with the token; data never becomes another account's cache.
      final user = saved?['user_id'] as String? ??
          await secure.read(key: 'lifeos.sync.user');
      api!.userId = user;
      if (user != null && api!.token != null) {
        account = {'user_id': user, 'verified': false};
      }
      if (account != null) {
        account = await store.metadata(scope, 'account') ?? account;
        spaces =
            ((await store.metadata(scope, 'spaces'))?['spaces'] as List? ?? [])
                .map(object)
                .toList();
      }
      final selected = await secure.read(key: 'lifeos.sync.workspace');
      if (account != null && selected != null) {
        workspace = selected;
        roster = await store.metadata(scope, 'roster:$selected');
        await reloadLocal();
      }
      if (api!.token != null) await refresh();
      startRecovery();
    } catch (_) {
      error = 'client_error';
      publish();
    }
  }

  void startRecovery() {
    if (_disposed || _retry != null) return;
    final base = _recoveryFailures > 0
        ? math.min(900, 30 * (1 << math.min(_recoveryFailures - 1, 5)))
        : pending.isNotEmpty ? 15 : 120;
    final seconds = (base * (0.85 + math.Random().nextDouble() * 0.30)).round();
    _retry = Timer(Duration(seconds: seconds), () async {
      _retry = null;
      if (_disposed) return;
      if (account != null && !busy) {
        await refresh();
        _recoveryFailures = error == null ? 0 : _recoveryFailures + 1;
      }
      startRecovery();
    });
  }

  Future<void> run(Future<void> Function() action) async {
    if (busy) {
      error = "client_busy";
      publish();
      return;
    }
    busy = true;
    error = null;
    publish();
    try {
      await action();
    } on SyncFailure catch (e) {
      error = e.code;
      if (e.code == 'workspace_forbidden' || e.code == 'profile_forbidden') {
        if (workspace != null && account != null) {
          await store.forgetAccess(scope, workspace!);
          await reloadLocal();
          roster = null;
        }
      }
    } catch (_) {
      error = 'client_error';
    } finally {
      busy = false;
      publish();
    }
  }

  Future<void> signIn(
    String endpoint,
    String email,
    String password, {
    bool register = false,
  }) => run(() async {
    final candidate = FamilyApi(endpoint);
    try {
      final result = await candidate.request(
        '/v1/auth/${register ? 'register' : 'login'}',
        body: {'email': email, 'password': password},
      );
      candidate.token = result['token'] as String;
      candidate.refreshToken = result['refresh_token'] as String?;
      candidate.userId = result['user_id'] as String;
      candidate.onRotated = (value) => _acceptRotation(candidate, value);
      await _persistSession(candidate, result);
      // A failed login cannot overwrite a saved identity or its outbox.
      await secure.write(
        key: 'lifeos.sync.endpoint',
        value: candidate.base.origin,
      );
      await secure.write(key: 'lifeos.sync.token', value: candidate.token);
      await secure.write(
        key: 'lifeos.sync.user',
        value: result['user_id'] as String,
      );
      await secure.delete(key: 'lifeos.sync.workspace');
      api?.close();
      api = candidate;
      account = {'user_id': result['user_id'], 'verified': result['verified'], 'email': email};
      workspace = null;
      roster = null;
      spaces = [];
      records = [];
      pending = [];
      issues = [];
      _engine = null;
      _generation++;
      if (verified) await _refresh();
      startRecovery();
    } catch (_) {
      if (!identical(api, candidate)) candidate.close();
      rethrow;
    }
  });
  Future<void> _acceptRotation(FamilyApi client, Json result) {
    if (_disposed || !identical(api, client) ||
        account?['user_id'] != result['user_id']) {
      throw const SyncFailure('identity_mismatch');
    }
    return _persistSession(client, result);
  }

  Future<void> _persistSession(FamilyApi client, Json result) => secure.write(
    key: 'lifeos.sync.session',
    value: jsonEncode({
      'endpoint': client.base.origin,
      'user_id': result['user_id'],
      'token': result['token'],
      'refresh_token': result['refresh_token'],
      'device_id': result['device_id'],
    }),
  );

  Future<void> recover(String endpoint, String email) => run(() async {
    final candidate = FamilyApi(endpoint);
    try {
      await candidate.request('/v1/auth/recovery', body: {'email': email});
    } finally {
      candidate.close();
    }
  });
  Future<void> resetPassword(
    String endpoint,
    String email,
    String code,
    String password,
  ) => run(() async {
    final candidate = FamilyApi(endpoint);
    try {
      await candidate.request(
        '/v1/auth/reset',
        body: {'email': email, 'code': code, 'password': password},
      );
    } finally {
      candidate.close();
    }
  });
  Future<void> verify(String code) => run(() async {
    await api!.request('/v1/auth/verify', body: {'code': code});
    account!['verified'] = true;
    await _refresh();
  });
  Future<void> resendVerification() => run(() async {
    await api!.request('/v1/auth/verification/resend', body: {});
  });
  Future<void> refresh() => run(_refresh);
  Future<void> _refresh() async {
    if (api == null || account == null) return;
    final me = await api!.request('/v1/me');
    if (me['user_id'] != account!['user_id']) {
      throw const SyncFailure('identity_mismatch');
    }
    account = me;
    await store.saveMetadata(scope, 'account', me);
    if (!verified) return;
    spaces = (await api!.request(
      '/v1/spaces',
    ))['spaces'].map<Json>(object).toList();
    await store.saveMetadata(scope, 'spaces', {'spaces': spaces});
    if (workspace != null && !spaces.any((s) => s['id'] == workspace)) {
      await store.forgetAccess(scope, workspace!);
      roster = null;
      records = [];
      pending = [];
      issues = await store.issues(scope, workspace!);
      _engine = null;
      // Keep the recovery workspace selected until the user handles retained work.
      error = 'workspace_forbidden';
      publish();
      return;
    }
    if (workspace != null) {
      roster = await api!.request(
        '/v1/roster?workspace=${Uri.encodeQueryComponent(workspace!)}',
      );
      await store.saveMetadata(scope, 'roster:$workspace', roster!);
      _engine ??= SyncEngine(store, api!, scope, workspace!);
      try {
        await _engine!.synchronize();
      } finally {
        await reloadLocal();
      }
    }
  }

  Future<void> select(String id) => run(() async {
    if (!spaces.any((s) => s['id'] == id)) {
      throw const SyncFailure('workspace_forbidden');
    }
    workspace = id;
    _engine = null;
    roster = await store.metadata(scope, 'roster:$id');
    await secure.write(key: 'lifeos.sync.workspace', value: id);
    await reloadLocal();
    await _refresh();
  });
  Future<void> reloadLocal() async {
    if (workspace == null || account == null) return;
    final version = _generation, s = scope, w = workspace!;
    final r = await store.records(s, w),
        p = await store.pending(s, w),
        i = await store.issues(s, w);
    if (version != _generation || w != workspace) return;
    records = r;
    pending = p;
    issues = i;
    publish();
  }

  Future<Json> family(String action, Json values) async {
    final result = await api!.request(
      '/v1/family',
      body: {
        'id': uuid.v4(),
        'workspace_id': workspace ?? uuid.v4(),
        'action': action,
        ...values,
      },
    );
    await _refresh();
    return result;
  }

  Future<void> accept(String invitation) => run(() async {
    await api!.request(
      '/v1/invitations/accept',
      body: {'id': uuid.v4(), 'invitation': invitation},
    );
    await _refresh();
  });
  Future<void> enqueue(Json operation) => run(() async {
    if (workspace == null || !verified || roster == null) {
      throw const SyncFailure('verify_email');
    }
    // A second local edit of the same record requires the first acknowledgement.
    if ([
      ...pending,
      ...issues.map((i) => object(i['operation'])),
    ].any((p) => p['record_id'] == operation['record_id'])) {
      throw const SyncFailure('record_pending');
    }
    await store.enqueue(scope, workspace!, operation);
    await reloadLocal();
    await _refresh();
  });
  Future<void> resolve(Json issue, bool keepLocal) => run(() async {
    final op = object(issue['operation']), result = object(issue['result']);
    Json? replacement;
    if (keepLocal) {
      if (result['status'] != 'conflict' || result['server'] == null) {
        throw const SyncFailure('record_forbidden');
      }
      replacement = {
        ...op,
        'id': uuid.v4(),
        'revision': object(result['server'])['revision'],
      };
    }
    await store.resolve(scope, workspace!, op['id'] as String, replacement);
    await reloadLocal();
    await _refresh();
  });
  Future<void> password(String oldPassword, String newPassword) =>
      run(() async {
        await api!.request(
          '/v1/auth/password',
          body: {'old_password': oldPassword, 'new_password': newPassword},
        );
        await _clearSession();
      });
  Future<void> signOut() => run(() async {
    // Always detach locally, even when remote session revocation is offline.
    try {
      await api?.request('/v1/auth/logout', body: {});
    } finally {
      await _clearSession();
    }
  });
  Future<void> _clearSession() async {
    _generation++;
    api?.token = null;
    api?.refreshToken = null;
    api?.userId = null;
    account = null;
    await secure.delete(key: 'lifeos.sync.session');
    await secure.delete(key: 'lifeos.sync.token');
    await secure.delete(key: 'lifeos.sync.user');
    await secure.delete(key: 'lifeos.sync.workspace');
    api?.token = null;
    api?.refreshToken = null;
    api?.userId = null;
    account = null;
    workspace = null;
    roster = null;
    spaces = [];
    records = [];
    pending = [];
    issues = [];
    _engine = null;
  }

  @override
  void dispose() {
    _disposed = true;
    _retry?.cancel();
    api?.close();
    super.dispose();
  }
}
