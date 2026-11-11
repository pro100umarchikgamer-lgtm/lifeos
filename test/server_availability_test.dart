import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/sync/api.dart';
import 'package:lifeos/sync/contracts.dart';
import 'package:lifeos/sync/controller.dart';

import 'support/sync_memory.dart';

class _RetryingSyncApi extends FamilyApi {
  _RetryingSyncApi() : super('https://api.example.test');

  final attempts = <String>[];
  final committed = <String, Json>{};

  @override
  Future<Json> request(String path, {Json? body}) async {
    if (path == '/v1/me') return {'user_id': 'user', 'verified': true};
    if (path == '/v1/spaces') {
      return {
        'spaces': [
          {'id': 'workspace'}
        ]
      };
    }
    if (path.startsWith('/v1/roster?')) return {};
    if (path == '/v1/sync/push') {
      final operation = object((body!['operations'] as List).single);
      final id = operation['id'] as String;
      attempts.add(id);
      final record = committed.putIfAbsent(
          id,
          () => {
                'id': operation['record_id'],
                'deleted': 0,
              });
      // The server commits the write, but the first response never arrives.
      if (attempts.length == 1) {
        throw const SyncFailure('service_unavailable', 503);
      }
      return {
        'results': [
          {'id': id, 'status': 'accepted', 'record': record},
        ]
      };
    }
    if (path.startsWith('/v1/sync/pull?')) {
      return {
        'protocol': 2,
        'epoch': 'epoch',
        'reset': true,
        'records': committed.values.toList(),
        'cursor': 1,
        'more': false,
      };
    }
    throw StateError('Unexpected path $path');
  }
}

void main() {
  test('a locally saved record survives 503 and retries with the same ID',
      () async {
    final api = _RetryingSyncApi();
    final controller = FamilyController(MemorySyncStore())
      ..api = api
      ..account = {'user_id': 'user', 'verified': true}
      ..workspace = 'workspace'
      ..roster = {};
    addTearDown(controller.dispose);
    final operation = {
      'id': 'operation',
      'record_id': 'record',
      'action': 'record.put',
    };
    expect(await controller.enqueue(operation), isTrue);
    expect(controller.error, 'service_unavailable');
    expect(controller.pending, [operation]);
    expect(
        await controller.enqueue({...operation, 'id': 'duplicate'}), isFalse);
    expect(controller.error, 'record_pending');
    await controller.refresh();
    expect(controller.error, isNull);
    expect(controller.pending, isEmpty);
    expect(controller.records.single['id'], 'record');
    expect(api.attempts, ['operation', 'operation']);
    expect(api.committed, hasLength(1));
  });

  test('503 is classified before waiting for its response body', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final api = FamilyApi('http://127.0.0.1:${server.port}')
      ..token = 'retained-session';
    addTearDown(() async {
      api.close();
      await server.close(force: true);
    });
    server.listen((r) async {
      r.response.statusCode = 503;
      r.response.write('maintenance');
      await r.response.flush(); // Headers arrive but the body remains open.
    });
    await expectLater(
        api
            .request('/v1/auth/google/config')
            .timeout(const Duration(seconds: 2)),
        throwsA(isA<SyncFailure>()
            .having((e) => e.code, 'code', 'service_unavailable')
            .having((e) => e.status, 'status', 503)));
    expect(api.token, 'retained-session');
  });
  for (final body in [
    '<html>Service unavailable</html>',
    '{"error":"maintenance"}',
    ''
  ]) {
    test('503 preserves status and reports temporary unavailability: $body',
        () async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      final api = FamilyApi('http://127.0.0.1:${server.port}')
        ..token = 'retained-session';
      addTearDown(() async {
        api.close();
        await server.close(force: true);
      });
      server.listen((r) async {
        r.response.statusCode = 503;
        r.response.write(body);
        await r.response.close();
      });
      await expectLater(
          api.request('/v1/auth/google/config'),
          throwsA(isA<SyncFailure>()
              .having((e) => e.code, 'code', 'service_unavailable')
              .having((e) => e.status, 'status', 503)));
      expect(api.token, 'retained-session');
    });
  }
}
