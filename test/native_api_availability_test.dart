import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/sync/api.dart';
import 'package:lifeos/sync/contracts.dart';

void main() {
  for (final text in [
    'ULADIM: closed testing is being prepared.',
    '<html>Unavailable</html>'
  ]) {
    test('HTTP 503 is a service outage before JSON parsing: $text', () async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      final api = FamilyApi('http://127.0.0.1:${server.port}');
      addTearDown(() async {
        api.close();
        await server.close(force: true);
      });
      server.listen((request) async {
        request.response.statusCode = 503;
        request.response.write(text);
        await request.response.close();
      });
      await expectLater(
          api.request('/v1/auth/google/config'),
          throwsA(isA<SyncFailure>()
              .having((e) => e.code, 'code', 'service_unavailable')
              .having((e) => e.status, 'status', 503)));
    });
  }

  test('malformed success still reports a malformed API response', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final api = FamilyApi('http://127.0.0.1:${server.port}');
    addTearDown(() async {
      api.close();
      await server.close(force: true);
    });
    server.listen((request) async {
      request.response.write('not json');
      await request.response.close();
    });
    await expectLater(
        api.request('/v1/me'),
        throwsA(isA<SyncFailure>()
            .having((e) => e.code, 'code', 'invalid_sync_response')));
  });
}
