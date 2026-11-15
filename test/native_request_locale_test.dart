import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/sync/api.dart';
import 'package:lifeos/sync/controller.dart';
import 'package:timezone/data/latest.dart' as timezone;

import 'controller_test.dart' show CountingStore, FakeNative;
import 'support/sync_memory.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  // These tests exercise real loopback transport, not the widget binding's 400 stub.
  HttpOverrides.global = null;
  timezone.initializeTimeZones();

  test(
      'per-client language follows UI changes without leaking to another client',
      () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final endpoint = 'http://127.0.0.1:${server.port}';
    var selected = 'fr';
    final first = FamilyApi(endpoint, locale: () => selected);
    final second = FamilyApi(endpoint, locale: () => 'en');
    final observed = <String?>[];
    addTearDown(() async {
      first.close();
      second.close();
      await server.close(force: true);
    });
    server.listen((request) async {
      observed.add(request.headers.value(HttpHeaders.acceptLanguageHeader));
      request.response.headers.contentType = ContentType.json;
      request.response.write('{"ok":true}');
      await request.response.close();
    });
    await first.request('/v1/auth/recovery',
        body: {'email': 'synthetic@example.test'});
    await second.request('/v1/me');
    selected = 'pt';
    await first.request('/v1/me');
    selected = 'en\r\nX-Test: invalid';
    await first.request('/v1/me');
    expect(observed, ['fr', 'en', 'pt', 'ru']);
  });

  test('AppController language preference reaches fresh recovery API instances',
      () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final endpoint = 'http://127.0.0.1:${server.port}';
    final observed = <String?>[];
    server.listen((request) async {
      observed.add(request.headers.value(HttpHeaders.acceptLanguageHeader));
      request.response.headers.contentType = ContentType.json;
      request.response.write('{"ok":true}');
      await request.response.close();
    });
    final catalog = await PackCatalog.load();
    final first =
        AppController(CountingStore(), catalog, 'en', platform: FakeNative());
    final second =
        AppController(CountingStore(), catalog, 'fr', platform: FakeNative());
    first.family = FamilyController(MemorySyncStore());
    second.family = FamilyController(MemorySyncStore());
    addTearDown(() async {
      first.dispose();
      second.dispose();
      await server.close(force: true);
    });
    await first.family!.recover(endpoint, 'synthetic@example.test');
    await first.preference('language', 'pt');
    await first.family!.recover(endpoint, 'synthetic@example.test');
    await second.family!.recover(endpoint, 'synthetic@example.test');
    expect(observed, ['en', 'pt', 'fr']);
  });
}
