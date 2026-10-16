import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/sync/api.dart';
import 'package:lifeos/sync/contracts.dart';

void main() {
  test('expired concurrent requests share one rotation and persist before replay', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final client = FamilyApi('http://127.0.0.1:${server.port}')
      ..token = 'old'
      ..refreshToken = 'r' * 43
      ..userId = 'same-user';
    addTearDown(() async { client.close(); await server.close(force: true); });
    var rotations = 0;
    var persisted = false;
    client.onRotated = (value) async { persisted = true; };
    server.listen((request) async {
      var reply = <String, dynamic>{'ok': true};
      if (request.uri.path == '/v1/auth/refresh') {
        rotations++;
        final body = jsonDecode(await utf8.decoder.bind(request).join());
        expect(body['refresh_token'], 'r' * 43);
        await Future<void>.delayed(const Duration(milliseconds: 20));
        reply = {'user_id': 'same-user', 'token': 'a' * 43, 'refresh_token': 'n' * 43};
      } else if (request.headers.value(HttpHeaders.authorizationHeader) != 'Bearer ${'a' * 43}') {
        if (request.uri.path == '/v1/spaces') {
          await Future<void>.delayed(const Duration(milliseconds: 80));
        }
        request.response.statusCode = 401;
        reply = {'error': 'unauthorized'};
      } else {
        expect(persisted, isTrue);
      }
      request.response.headers.contentType = ContentType.json;
      request.response.write(jsonEncode(reply));
      await request.response.close();
    });
    final result = await Future.wait([client.request('/v1/me'), client.request('/v1/spaces')]);
    expect(result.every((r) => r['ok'] == true), isTrue);
    expect(rotations, 1);
    expect(client.refreshToken, 'n' * 43);
  });

  test('rotation cannot silently replace the signed-in account', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final client = FamilyApi('http://127.0.0.1:${server.port}')
      ..token = 'old'
      ..refreshToken = 'r' * 43
      ..userId = 'expected';
    addTearDown(() async { client.close(); await server.close(force: true); });
    server.listen((request) async {
      request.response.headers.contentType = ContentType.json;
      if (request.uri.path == '/v1/auth/refresh') {
        request.response.write(jsonEncode({'user_id': 'another-account', 'token': 'a' * 43, 'refresh_token': 'n' * 43}));
      } else {
        request.response.statusCode = 401;
        request.response.write('{"error":"unauthorized"}');
      }
      await request.response.close();
    });
    await expectLater(client.request('/v1/me'), throwsA(isA<SyncFailure>().having((e) => e.code, 'code', 'identity_mismatch')));
    expect(client.token, 'old');
  });
}
