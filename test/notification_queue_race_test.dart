import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/notifications/notification_center.dart';
import 'package:lifeos/sync/contracts.dart';
import 'notification_center_test.dart' show InboxCache, InboxApi, message;

class DelayedInboxCache extends InboxCache {
  Completer<void>? gate;
  @override
  Future<void> writeNotificationCache(String scope, Json value) async {
    final held = gate;
    gate = null;
    if (held != null) await held.future;
    await super.writeNotificationCache(scope, value);
  }
}

class FailedMutationApi extends InboxApi {
  SyncFailure? failure;
  int failedMutations = 0;
  @override
  Future<Json> request(String path, {Json? body}) async {
    if (body != null && failure != null) {
      failedMutations++;
      throw failure!;
    }
    return super.request(path, body: body);
  }
}

void main() {
  for (final action in ['read', 'presented']) {
    test('delayed GET cannot overwrite an unfinished durable $action',
        () async {
      final cache = DelayedInboxCache();
      final api = InboxApi()
        ..messages = [message('a', presentation: 'fullscreen')];
      final c = NotificationCenter(cache: cache);
      await c.initialize();
      await c.attachAccount('https://a.test|alice', api);
      final reply = api.delayed = Completer<Json>();
      final refreshing = c.refresh();
      await Future<void>.delayed(Duration.zero);
      final gate = cache.gate = Completer<void>();
      final marking = action == 'read'
          ? c.markRead(c.messages.single)
          : c.markPresented(c.messages.single);
      await Future<void>.delayed(Duration.zero);
      // The original GET succeeds, then connectivity disappears before the queued POST.
      api.offline = true;
      reply.complete({
        'notifications': [message('a', presentation: 'fullscreen')],
        'unread_count': 1
      });
      await Future<void>.delayed(Duration.zero);
      gate.complete();
      await marking;
      await refreshing;
      final saved = cache.data['https://a.test|alice']!;
      expect(saved['pending'], isNotEmpty);
      expect(
          (saved['messages'] as List)
              .single[action == 'read' ? 'read_at' : 'presented_at'],
          greaterThan(0));
      if (action == 'read') {
        expect(c.messages.single.read, isTrue);
      } else {
        expect(c.nextAnnouncement, isNull);
      }
      c.dispose();
      final restored = NotificationCenter(cache: cache);
      await restored.initialize();
      await restored.attachAccount('https://a.test|alice', api);
      if (action == 'read') {
        expect(restored.messages.single.read, isTrue);
      } else {
        expect(restored.nextAnnouncement, isNull);
      }
      restored.dispose();
    });
  }
  test('read all invoked by Alice never targets Bob after waiting for storage',
      () async {
    final cache = DelayedInboxCache();
    final alice = InboxApi(), bob = InboxApi()..messages = [message('bob')];
    final c = NotificationCenter(cache: cache);
    await c.initialize();
    await c.attachAccount('https://a.test|alice', alice);
    final gate = cache.gate = Completer<void>();
    final recording = c.recordReminders([message('personal')]);
    await Future<void>.delayed(Duration.zero);
    final marking = c.markAllRead();
    final changing = c.attachAccount('https://a.test|bob', bob);
    await Future<void>.delayed(Duration.zero);
    gate.complete();
    await recording;
    await marking;
    await changing;
    await Future<void>.delayed(Duration.zero);
    expect(bob.calls.where((call) => call.$1.endsWith('/read')), isEmpty);
    c.dispose();
  });
  for (final caseValue in [
    ('read', 'not_found', 404),
    ('dismiss', 'not_found', 404),
    ('presented', 'not_found', 404),
    ('presented', 'notification_inactive', 409)
  ]) {
    test(
        '${caseValue.$1} ${caseValue.$2}/${caseValue.$3} is terminal and permits inbox GET',
        () async {
      final cache = InboxCache();
      await cache.writeNotificationCache('https://a.test|alice', {
        'messages': [],
        'pending': [
          {
            'key': 'old',
            'action': caseValue.$1,
            'body': {'id': 'expired'},
            'at': 1
          }
        ],
        'unread_count': 0
      });
      final api = FailedMutationApi()
        ..failure = SyncFailure(caseValue.$2, caseValue.$3);
      final c = NotificationCenter(cache: cache);
      await c.initialize();
      await c.attachAccount('https://a.test|alice', api);
      await c.retry();
      expect(api.failedMutations, 1);
      expect(api.calls.where((call) => call.$2 == null), isNotEmpty);
      expect(cache.data['https://a.test|alice']!['pending'], isEmpty);
      expect(c.error, isNull);
      c.dispose();
    });
  }
  test('rate-limited state stays durable and retries later', () async {
    final cache = InboxCache();
    await cache.writeNotificationCache('https://a.test|alice', {
      'messages': [],
      'pending': [
        {
          'key': 'read',
          'action': 'read',
          'body': {'id': 'a'},
          'at': 1
        }
      ],
      'unread_count': 0
    });
    final api = FailedMutationApi()
      ..failure = const SyncFailure('rate_limited', 429);
    final c = NotificationCenter(cache: cache);
    await c.initialize();
    await c.attachAccount('https://a.test|alice', api);
    expect(cache.data['https://a.test|alice']!['pending'], isNotEmpty);
    expect(c.error, 'inbox_refresh_failed');
    api.failure = null;
    await c.retry();
    expect(cache.data['https://a.test|alice']!['pending'], isEmpty);
    expect(api.calls.where((call) => call.$1.endsWith('/read')), isNotEmpty);
    expect(c.error, isNull);
    c.dispose();
  });
}
