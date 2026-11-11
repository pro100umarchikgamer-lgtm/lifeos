import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/sync/api.dart';
import 'package:lifeos/sync/contracts.dart';

void main() {
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
