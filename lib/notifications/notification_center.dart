import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';
import '../sync/contracts.dart';
import '../domain/public_links.dart';

/// The production adapter stores this metadata in the existing SQLCipher DB.
/// Personal history and each authenticated origin/user use separate scopes.
abstract interface class NotificationCache {
  String get localNotificationScope;
  Future<Json?> readNotificationCache(String scope);
  Future<void> writeNotificationCache(String scope, Json value);
}

class MemoryNotificationCache implements NotificationCache {
  final _values = <String, Json>{};
  @override
  String get localNotificationScope => 'notification:local';
  @override
  Future<Json?> readNotificationCache(String scope) async => _values[scope];
  @override
  Future<void> writeNotificationCache(String scope, Json value) async {
    _values[scope] = clone(value);
  }
}

class InboxMessage {
  InboxMessage(Json value, {this.local = false}) : data = clone(value);
  final Json data;
  final bool local;
  String get id => data['id'] as String;
  String get title => data['title'] as String? ?? 'ULADIM';
  String get body => data['body'] as String? ?? '';
  String get kind => data['kind'] as String? ?? 'reminder';
  String get presentation => data['presentation'] as String? ?? 'inbox';
  String? get entryId => data['entry_id'] as String?;
  int number(String key) => (data[key] as num?)?.toInt() ?? 0;
  DateTime get createdAt =>
      DateTime.fromMillisecondsSinceEpoch(number('created_at') * 1000);
  bool get read => number('read_at') > 0;
  bool get dismissed => number('dismissed_at') > 0;
  String? get status => data['status'] as String?;
  Uri? get link => notificationMessageLink(data['link']);

  bool activeAt(int now) =>
      data['active'] != false &&
      (number('starts_at') == 0 || number('starts_at') <= now) &&
      (number('expires_at') == 0 || number('expires_at') > now);
  InboxMessage changed(String action, int at) {
    final result = clone(data);
    if (action == 'read' || action == 'dismiss') result['read_at'] = at;
    if (action == 'presented' || action == 'dismiss') {
      result['presented_at'] = at;
    }
    if (action == 'dismiss') result['dismissed_at'] = at;
    return InboxMessage(result, local: local);
  }
}

class NotificationCenter extends ChangeNotifier {
  NotificationCenter({required this.cache, DateTime Function()? clock})
      : _clock = clock ?? DateTime.now;
  final NotificationCache cache;
  final DateTime Function() _clock;
  List<InboxMessage> _personal = [], _remote = [];
  List<Json> _pending = [];
  SyncTransport? _api;
  String? _scope;
  int _generation = 0, _serverUnread = 0;
  bool _disposed = false, loading = false;
  bool _localReady = false, _accountCacheReady = false;
  String? error, nextBefore, budgetError;
  bool budgetBusy = false;
  Json _budgetSettings = _defaultBudgetSettings();
  static Json _defaultBudgetSettings() => {
        'budget_enabled': false,
        'budget_thresholds': [50, 80, 100],
        'timezone': 'UTC'
      };
  bool get budgetEnabled => _budgetSettings['budget_enabled'] == true;
  List<int> get budgetThresholds =>
      List<int>.from(_budgetSettings['budget_thresholds'] as List);
  bool get budgetPending =>
      _pending.any((operation) => operation['action'] == 'settings');
  Json _decodeBudgetSettings(Json raw) {
    final thresholds = raw['budget_thresholds'];
    if (raw['budget_enabled'] is! bool ||
        raw['timezone'] is! String ||
        thresholds is! List ||
        thresholds.isEmpty ||
        thresholds.length > 20 ||
        thresholds.any((v) => v is! int || v < 1 || v > 100)) {
      throw const SyncFailure('invalid_sync_response');
    }
    final sorted = thresholds.cast<int>().toSet().toList()..sort();
    return {
      'budget_enabled': raw['budget_enabled'],
      'budget_thresholds': sorted,
      'timezone': raw['timezone']
    };
  }

  void _loadCachedBudget(Json? saved) {
    _budgetSettings = saved?['budget_settings'] is Map
        ? _decodeBudgetSettings(object(saved!['budget_settings']))
        : _defaultBudgetSettings();
  }

  Future<void> _mutations = Future<void>.value();
  Future<void>? _refreshing;
  final Map<String, Future<void>> _writes = {};
  bool get hasAccount => _scope != null;
  String? get accountScope => _scope;
  int get _seconds => _clock().millisecondsSinceEpoch ~/ 1000;
  List<InboxMessage> get messages => [..._personal, ..._remote]
    ..sort((a, b) => b.number('created_at').compareTo(a.number('created_at')));
  bool isUnread(InboxMessage message) =>
      !message.read &&
      !message.dismissed &&
      (message.local || message.activeAt(_seconds));
  int get unreadCount => _personal.where((m) => !m.read).length + _serverUnread;

  List<InboxMessage> get announcements => _remote
      .where((m) =>
          m.kind == 'announcement' &&
          m.presentation != 'inbox' &&
          m.activeAt(_seconds) &&
          !m.dismissed &&
          m.number('presented_at') == 0)
      .toList();
  InboxMessage? get nextAnnouncement => announcements.firstOrNull;

  void _publish() {
    if (!_disposed) notifyListeners();
  }

  List<InboxMessage> _decode(Object? raw, {bool local = false}) => [
        for (final value in raw as List? ?? [])
          if (value is Map &&
              value['id'] is String &&
              value['title'] is String &&
              value['body'] is String)
            InboxMessage(object(value), local: local),
      ];
  Future<void> initialize() async {
    try {
      final saved =
          await cache.readNotificationCache(cache.localNotificationScope);
      _personal = _decode(saved?['messages'], local: true);
      _localReady = true;
      if (error == 'inbox_storage_failed') error = null;
    } catch (_) {
      error = 'inbox_storage_failed';
    }
    _publish();
  }

  Future<void> _write(String scope, Json data) {
    final snapshot = clone(data);
    final next = (_writes[scope] ?? Future<void>.value())
        .catchError((Object _) {})
        .then((_) => cache.writeNotificationCache(scope, snapshot));
    _writes[scope] = next;
    return next;
  }

  Json _remoteData(
          {List<InboxMessage>? messages,
          List<Json>? pending,
          int? unread,
          Json? budget}) =>
      {
        'messages': (messages ?? _remote).map((m) => m.data).toList(),
        'pending': pending ?? _pending,
        'unread_count': unread ?? _serverUnread,
        'next_before': nextBefore,
        'budget_settings': budget ?? _budgetSettings,
      };

  Future<void> attachAccount(String? scope, SyncTransport? api) async {
    if (scope == _scope && identical(api, _api)) return;
    final generation = ++_generation;
    _scope = scope;
    _api = api;
    _remote = [];
    _pending = [];
    _accountCacheReady = false;
    _budgetSettings = _defaultBudgetSettings();
    budgetError = null;
    budgetBusy = false;
    _serverUnread = 0;
    nextBefore = null;
    error = _localReady ? null : 'inbox_storage_failed';
    loading = false;
    _refreshing = null;
    _publish(); // Detach account content synchronously, before any awaited IO.
    if (scope == null || api == null) return;
    try {
      await _writes[scope]?.catchError((Object _) {});
      if (_generation != generation) return;
      final saved = await cache.readNotificationCache(scope);
      if (_generation != generation) return;
      _remote = _decode(saved?['messages']);
      _loadCachedBudget(saved);
      _pending = (saved?['pending'] as List? ?? []).map(object).toList();
      _serverUnread = (saved?['unread_count'] as num?)?.toInt() ?? 0;
      nextBefore = saved?['next_before'] as String?;
      _accountCacheReady = true;
      _publish();
    } catch (_) {
      if (_generation == generation) {
        error = 'inbox_storage_failed';
        _publish();
      }
      return;
    }
    if (_generation == generation) await refresh();
  }

  Future<void> retry() async {
    if (!_localReady) await initialize();
    await refresh();
  }

  Future<void> refresh({bool loadMore = false}) {
    if (_api == null || _scope == null) return Future<void>.value();
    if (_refreshing != null) return _refreshing!;
    late final Future<void> next;
    next = _refresh(loadMore: loadMore).whenComplete(() {
      if (identical(_refreshing, next)) _refreshing = null;
    });
    _refreshing = next;
    return next;
  }

  Future<void> _refresh({required bool loadMore}) async {
    final generation = _generation, scope = _scope!, api = _api!;
    loading = true;
    _publish();
    try {
      if (!_accountCacheReady) {
        final saved = await cache.readNotificationCache(scope);
        if (_generation != generation) return;
        _remote = _decode(saved?['messages']);
        _loadCachedBudget(saved);
        _pending = (saved?['pending'] as List? ?? []).map(object).toList();
        _serverUnread = (saved?['unread_count'] as num?)?.toInt() ?? 0;
        nextBefore = saved?['next_before'] as String?;
        _accountCacheReady = true;
      }
      // Mutations are persisted before they can be sent. Failed requests stay queued.
      for (final operation in List<Json>.from(_pending)) {
        try {
          await api.request('/v1/account/inbox/${operation['action']}',
              body: object(operation['body']));
        } on SyncFailure catch (failure) {
          final terminalMessageState = operation['action'] != 'settings' &&
              (failure.code == 'not_found' ||
                  operation['action'] == 'presented' &&
                      failure.code == 'notification_inactive');
          if (!terminalMessageState) rethrow;
        }
        await _serialize(() async {
          if (_generation != generation) return;
          _pending.removeWhere((p) => p['key'] == operation['key']);
          await _write(scope, _remoteData());
        });
        if (_generation != generation) return;
      }
      final before = loadMore ? nextBefore : null;
      final result = await api.request(
          '/v1/account/inbox?limit=50${before == null ? '' : '&before=${Uri.encodeQueryComponent(before)}'}');
      if (_generation != generation) return;
      if (result['notifications'] is! List || result['unread_count'] is! num) {
        throw const SyncFailure('invalid_sync_response');
      }
      final incoming = _decode(result['notifications']);
      await _serialize(() async {
        if (_generation != generation) return;
        final merged = {
          for (final m in _remote) m.id: m,
          for (final m in incoming) m.id: m
        };
        for (final operation in _pending) {
          final body = object(operation['body']);
          for (final id in merged.keys.toList()) {
            if (body['all'] == true || body['id'] == id) {
              merged[id] = merged[id]!.changed(
                  operation['action'] as String, operation['at'] as int);
            }
          }
        }
        var remote = merged.values.toList()
          ..sort((a, b) =>
              b.number('created_at').compareTo(a.number('created_at')));
        var unread = (result['unread_count'] as num).toInt();
        final pendingReads = <String>{};
        for (final operation in _pending
            .where((p) => p['action'] == 'read' || p['action'] == 'dismiss')) {
          final body = object(operation['body']);
          if (body['all'] == true) {
            unread = 0;
            break;
          }
          final id = body['id'] as String?;
          if (id != null && incoming.any((m) => m.id == id && !m.read)) {
            pendingReads.add(id);
          }
        }
        unread = (unread - pendingReads.length).clamp(0, 1 << 30);
        // Honour the server's bounded account history without pruning private reminders.
        if (result['retention_days'] case final num days) {
          final cutoff = _seconds - days.toInt() * 86400;
          final announcementDays =
              (result['announcement_retention_days_after_expiry'] as num?)
                      ?.toInt() ??
                  days.toInt();
          remote = remote
              .where((m) => m.kind == 'announcement'
                  ? m.activeAt(_seconds) ||
                      m.number('expires_at') > 0 &&
                          m.number('expires_at') + announcementDays * 86400 >=
                              _seconds ||
                      m.number('created_at') >= cutoff
                  : m.number('created_at') >= cutoff)
              .toList();
          final limit = (result['history_limit'] as num?)?.toInt() ?? 1000;
          var retained = 0;
          remote = remote
              .where((m) =>
                  m.kind == 'announcement' && m.activeAt(_seconds) ||
                  retained++ < limit)
              .toList();
        }
        if (unread == 0) {
          remote = remote
              .map((m) => m.read ? m : m.changed('read', _seconds))
              .toList();
        }
        nextBefore = result['next_before'] as String?;
        await _write(scope, _remoteData(messages: remote, unread: unread));
        if (_generation != generation) return;
        _remote = remote;
        _serverUnread = unread;
        error = _localReady ? null : 'inbox_storage_failed';
      });
    } on SyncFailure catch (failure) {
      if (_generation == generation) {
        error = failure.code == 'offline'
            ? 'inbox_offline'
            : 'inbox_refresh_failed';
      }
    } catch (_) {
      if (_generation == generation) error = 'inbox_storage_failed';
    } finally {
      if (_generation == generation) {
        loading = false;
        _publish();
      }
    }
  }

  Future<void> recordReminders(List<Json> values) => _serialize(() async {
        if (values.isEmpty) return;
        if (!_localReady) {
          throw StateError('Encrypted notification history unavailable');
        }
        final byId = {for (final m in _personal) m.id: m};
        for (final value in values) {
          final id = value['id'];
          if (id is! String ||
              value['title'] is! String ||
              value['body'] is! String) {
            continue;
          }
          final previous = byId[id];
          byId[id] = InboxMessage({
            ...value,
            if (previous != null) 'read_at': previous.number('read_at')
          }, local: true);
        }
        final personal = byId.values.toList()
          ..sort((a, b) =>
              b.number('created_at').compareTo(a.number('created_at')));
        try {
          await _write(cache.localNotificationScope,
              {'messages': personal.map((m) => m.data).toList()});
          _personal = personal;
          _publish();
        } catch (_) {
          error = 'inbox_storage_failed';
          _publish();
          rethrow;
        }
      });

  Future<void> loadBudgetSettings() async {
    if (_scope == null || _api == null || budgetBusy) return;
    final generation = _generation, scope = _scope!, api = _api!;
    budgetBusy = true;
    budgetError = null;
    _publish();
    try {
      await refresh();
      if (_generation != generation) return;
      if (budgetPending) {
        budgetError = error ?? 'inbox_offline';
        return;
      }
      final result = _decodeBudgetSettings(
          await api.request('/v1/account/inbox/settings'));
      await _serialize(() async {
        if (_generation != generation || budgetPending) return;
        await _write(scope, _remoteData(budget: result));
        if (_generation == generation) _budgetSettings = result;
      });
    } on SyncFailure catch (failure) {
      if (_generation == generation) {
        budgetError = failure.code == 'offline'
            ? 'inbox_offline'
            : 'inbox_refresh_failed';
      }
    } catch (_) {
      if (_generation == generation) budgetError = 'inbox_storage_failed';
    } finally {
      if (_generation == generation) {
        budgetBusy = false;
        _publish();
      }
    }
  }

  Future<void> saveBudgetSettings(
      {required bool enabled,
      required List<int> thresholds,
      required String timezone}) {
    final generation = _generation;
    return _serialize(() async {
      if (_scope == null || generation != _generation || !_accountCacheReady) {
        return;
      }
      final settings = _decodeBudgetSettings({
        'budget_enabled': enabled,
        'budget_thresholds': thresholds,
        'timezone': timezone
      });
      final operation = {
        'key': const Uuid().v4(),
        'action': 'settings',
        'body': settings,
        'at': _seconds
      };
      final pending = [
        ..._pending.where((p) => p['action'] != 'settings'),
        operation
      ];
      budgetBusy = true;
      budgetError = null;
      _publish();
      try {
        await _write(_scope!, _remoteData(pending: pending, budget: settings));
        if (_generation != generation) return;
        _pending = pending;
        _budgetSettings = settings;
        unawaited(_syncQueued());
      } catch (_) {
        if (_generation == generation) budgetError = 'inbox_storage_failed';
      } finally {
        if (_generation == generation) {
          budgetBusy = false;
          _publish();
        }
      }
    });
  }

  Future<void> _syncQueued() async {
    final generation = _generation, active = _refreshing;
    if (active != null) {
      await active;
      if (error != null) return;
    }
    if (!_disposed && generation == _generation && _pending.isNotEmpty) {
      await refresh();
    }
  }

  Future<void> _serialize(Future<void> Function() action) {
    final next = _mutations.catchError((Object _) {}).then((_) => action());
    _mutations = next;
    return next;
  }

  Future<void> markRead(InboxMessage message) => _change(message, 'read');
  Future<void> markPresented(InboxMessage message) =>
      _change(message, 'presented');
  Future<void> dismiss(InboxMessage message) => _change(message, 'dismiss');
  Future<void> _change(InboxMessage message, String action) {
    final generation = _generation;
    return _serialize(() async {
      if (!message.local && generation != _generation) return;
      final source = message.local ? _personal : _remote;
      final current = source.where((m) => m.id == message.id).firstOrNull;
      if (current == null ||
          action == 'read' && current.read ||
          action == 'presented' && current.number('presented_at') > 0) {
        return;
      }
      final at = _seconds;
      final updated = source
          .map((m) => m.id == message.id ? m.changed(action, at) : m)
          .toList();
      final operation = {
        'key': '${message.id}:$action',
        'action': action,
        'body': {'id': message.id},
        'at': at
      };
      final pending = [
        ..._pending.where((p) => p['key'] != operation['key']),
        operation
      ];
      final unread = action != 'presented' && !current.read
          ? (_serverUnread - 1).clamp(0, 1 << 30)
          : _serverUnread;
      try {
        await _write(
            message.local ? cache.localNotificationScope : _scope!,
            message.local
                ? {'messages': updated.map((m) => m.data).toList()}
                : _remoteData(
                    messages: updated, pending: pending, unread: unread));
        if (message.local) {
          _personal = updated;
        } else if (generation == _generation) {
          _remote = updated;
          _pending = pending;
          _serverUnread = unread;
        } else {
          return;
        }
        _publish();
      } catch (_) {
        error = 'inbox_storage_failed';
        _publish();
        return;
      }
      if (!message.local) unawaited(_syncQueued());
    });
  }

  Future<void> markAllRead() {
    final generation = _generation;
    return _serialize(() async {
      final at = _seconds;
      if (!_localReady) {
        error = 'inbox_storage_failed';
        _publish();
        return;
      }
      final personal = _personal.map((m) => m.changed('read', at)).toList();
      try {
        await _write(cache.localNotificationScope,
            {'messages': personal.map((m) => m.data).toList()});
        _personal = personal;
        if (_scope != null && generation == _generation && _accountCacheReady) {
          final remote = _remote.map((m) => m.changed('read', at)).toList();
          final pending = [
            ..._pending.where((p) => p['key'] != 'all:read'),
            {
              'key': 'all:read',
              'action': 'read',
              'body': {'all': true},
              'at': at
            }
          ];
          await _write(_scope!,
              _remoteData(messages: remote, pending: pending, unread: 0));
          if (generation != _generation) return;
          _remote = remote;
          _pending = pending;
          _serverUnread = 0;
          unawaited(_syncQueued());
        }
        _publish();
      } catch (_) {
        error = 'inbox_storage_failed';
        _publish();
      }
    });
  }

  @override
  void dispose() {
    _disposed = true;
    _generation++;
    super.dispose();
  }
}
