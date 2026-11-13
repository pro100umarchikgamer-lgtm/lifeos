import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/notifications/notification_center.dart';
import 'package:lifeos/sync/contracts.dart';

class InboxCache implements NotificationCache {
  final data = <String, Json>{};
  bool failWrites = false, failReads = false;
  @override
  String get localNotificationScope => 'personal:device';
  @override
  Future<Json?> readNotificationCache(String scope) async {
    if (failReads) throw StateError('unavailable');
    return data[scope] == null ? null : clone(data[scope]!);
  }

  @override
  Future<void> writeNotificationCache(String scope, Json value) async {
    if (failWrites) throw StateError('disk');
    data[scope] = clone(value);
  }
}

Json message(String id, {String presentation = 'inbox', int readAt = 0}) => {
      'id': id,
      'kind': 'announcement',
      'title': 'A helpful update',
      'body': 'Full details stay available in your history.',
      'presentation': presentation,
      'created_at': 1700000000,
      'starts_at': 0,
      'expires_at': 0,
      'read_at': readAt,
      'dismissed_at': 0,
      'presented_at': 0,
      'active': true,
    };

class InboxApi implements SyncTransport {
  List<Json> messages = [message('a')];
  final calls = <(String, Json?)>[];
  bool offline = false;
  Completer<Json>? delayed;
  @override
  Future<Json> request(String path, {Json? body}) async {
    calls.add((path, body));
    if (offline) throw const SyncFailure('offline');
    if (body == null) {
      if (delayed != null) return delayed!.future;
      return {
        'notifications': messages,
        'unread_count': messages.where((m) => m['read_at'] == 0).length,
        'next_before': null
      };
    }
    for (final m in messages) {
      if (m['id'] == body['id'] || body['all'] == true) {
        if (path.endsWith('/read') || path.endsWith('/dismiss')) {
          m['read_at'] = 1700000020;
        }
        if (path.endsWith('/presented') || path.endsWith('/dismiss')) {
          m['presented_at'] = 1700000020;
        }
        if (path.endsWith('/dismiss')) m['dismissed_at'] = 1700000020;
      }
    }
    return {'updated': true};
  }
}

void main() {
  test('actual personal reminders persist privately offline and deduplicate',
      () async {
    final cache = InboxCache();
    final c = NotificationCenter(cache: cache);
    await c.initialize();
    final reminder = {
      'id': 'reminder:task:1:123',
      'entry_id': 'task',
      'title': 'Medicine',
      'body': 'Reminder',
      'created_at': 1700000000,
      'status': 'delivered'
    };
    await c.recordReminders([reminder, reminder]);
    expect(c.messages.length, 1);
    expect(c.unreadCount, 1);
    await c.markRead(c.messages.single);
    final restored = NotificationCenter(cache: cache);
    await restored.initialize();
    expect(restored.messages.single.title, 'Medicine');
    expect(restored.unreadCount, 0);
    await restored.attachAccount('https://a.test|alice', InboxApi());
    await restored.attachAccount(null, null);
    expect(restored.messages.single.local, isTrue);
    c.dispose();
    restored.dispose();
  });

  test('offline account read queues durably and retries without losing history',
      () async {
    final cache = InboxCache();
    final api = InboxApi();
    final c = NotificationCenter(cache: cache);
    await c.initialize();
    await c.attachAccount('https://a.test|alice', api);
    api.offline = true;
    await c.markRead(c.messages.single);
    expect(c.unreadCount, 0);
    await c.refresh();
    expect(c.error, isNotNull);
    c.dispose();
    final restored = NotificationCenter(cache: cache);
    await restored.initialize();
    await restored.attachAccount('https://a.test|alice', api);
    expect(restored.messages.single.read, isTrue);
    api.offline = false;
    await restored.refresh();
    expect(api.messages.single['read_at'], isNot(0));
    expect(restored.messages.single.title, 'A helpful update');
    expect(restored.error, isNull);
    restored.dispose();
  });

  test('logout hides account history immediately and ignores a late response',
      () async {
    final api = InboxApi()..delayed = Completer<Json>();
    final c = NotificationCenter(cache: InboxCache());
    await c.initialize();
    final attaching = c.attachAccount('https://a.test|alice', api);
    await Future<void>.delayed(Duration.zero);
    await c.attachAccount(null, null);
    api.delayed!.complete({
      'notifications': [message('alice')],
      'unread_count': 1
    });
    await attaching;
    expect(c.hasAccount, isFalse);
    expect(c.messages, isEmpty);
    c.dispose();
  });

  test('presented announcements do not repeat after restart or dismiss',
      () async {
    final cache = InboxCache();
    final api = InboxApi()
      ..messages = [message('a', presentation: 'fullscreen')];
    final c = NotificationCenter(cache: cache);
    await c.initialize();
    await c.attachAccount('https://a.test|alice', api);
    expect(c.nextAnnouncement?.id, 'a');
    api.offline = true;
    await c.markPresented(c.nextAnnouncement!);
    expect(c.nextAnnouncement, isNull);
    c.dispose();
    final restored = NotificationCenter(cache: cache);
    await restored.initialize();
    await restored.attachAccount('https://a.test|alice', api);
    expect(restored.nextAnnouncement, isNull);
    expect(restored.messages, hasLength(1));
    restored.dispose();
  });

  test(
      'failed local persistence does not claim a message read or acknowledge remotely',
      () async {
    final cache = InboxCache();
    final api = InboxApi();
    final c = NotificationCenter(cache: cache);
    await c.initialize();
    await c.attachAccount('https://a.test|alice', api);
    cache.failWrites = true;
    await c.markRead(c.messages.single);
    expect(c.messages.single.read, isFalse);
    expect(api.calls.where((call) => call.$1.endsWith('/read')), isEmpty);
    expect(c.error, 'inbox_storage_failed');
    c.dispose();
  });
  test('a delayed refresh cannot restore an unread badge after local read',
      () async {
    final api = InboxApi();
    final c = NotificationCenter(cache: InboxCache());
    await c.initialize();
    await c.attachAccount('https://a.test|alice', api);
    api.delayed = Completer<Json>();
    final refreshing = c.refresh();
    await Future<void>.delayed(Duration.zero);
    await c.markRead(c.messages.single);
    api.delayed!.complete({
      'notifications': [message('a')],
      'unread_count': 1
    });
    await refreshing;
    expect(c.messages.single.read, isTrue);
    expect(c.unreadCount, 0);
    api.delayed = null;
    await c.refresh();
    c.dispose();
  });
  test('an unreadable encrypted history is never replaced by new reminders',
      () async {
    final cache = InboxCache()..failReads = true;
    cache.data[cache.localNotificationScope] = {
      'messages': [message('preserved')]
    };
    final c = NotificationCenter(cache: cache);
    await c.initialize();
    await expectLater(c.recordReminders([message('new')]), throwsStateError);
    expect(cache.data[cache.localNotificationScope]!['messages'][0]['id'],
        'preserved');
    c.dispose();
  });
}
