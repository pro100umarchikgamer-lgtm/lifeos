import 'dart:async';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/platform/native_bridge.dart';
import 'package:lifeos/sync/api.dart';
import 'package:lifeos/sync/contracts.dart';
import 'package:lifeos/sync/controller.dart';
import 'package:lifeos/ui/app.dart';
import 'package:lifeos/ui/referrals.dart';
import 'package:lifeos/ui/design.dart';
import 'package:timezone/data/latest.dart' as timezone;

import 'support/sync_memory.dart';
import 'widget_test.dart' show UIStore, openNativeProfile;

const referralCode = 'abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG';
const referralLink = 'https://getuladim.space/app?ref=$referralCode';
Json referralSummary({String? name = 'Умар U.', int? next}) => {
      'confirmed_count': name == null ? 0 : 1,
      'invite': {'code': referralCode, 'url': referralLink},
      'people': [
        if (name != null) {'display_name': name}
      ],
      'next_offset': next,
    };

class ReferralApi extends FamilyApi {
  ReferralApi(this.respond) : super('https://api.example.test');
  final Future<Json> Function(String, Json?) respond;
  @override
  Future<Json> request(String path, {Json? body}) => respond(path, body);
}

FamilyController referralController(
    Future<Json> Function(String, Json?) respond) {
  final c = FamilyController(MemorySyncStore());
  c.api = ReferralApi(respond);
  c.account = {
    'user_id': 'current-user',
    'email': 'private@example.test',
    'verified': true,
  };
  return c;
}

Matcher failureCode(String code) =>
    isA<SyncFailure>().having((error) => error.code, 'code', code);

class ReferralAndroidBridge extends NativeBridge {
  @override
  bool get supported => true;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  timezone.initializeTimeZones();
  late PackCatalog catalog;
  setUpAll(() async => catalog = await PackCatalog.load());
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  test('own summary exposes only the count, public invite and short labels',
      () async {
    final c = referralController((path, body) async {
      expect(path, '/v1/referrals?offset=0');
      expect(body, isNull);
      return referralSummary();
    });
    addTearDown(c.dispose);
    final dynamic value = await (c as dynamic).referralSummary();
    expect(value.confirmedCount, 1);
    expect(value.people, ['Умар U.']);
    expect(value.invite?.url.toString(), referralLink);
    expect(await c.secure.readAll(), isEmpty);
    expect((c.store as MemorySyncStore).meta, isEmpty);
    expect((c.store as MemorySyncStore).outbox, isEmpty);
  });

  test('unverified customer is rejected before a referral request', () async {
    var sent = 0;
    final c = referralController((path, body) async {
      sent++;
      return referralSummary();
    });
    addTearDown(c.dispose);
    c.account!['verified'] = false;
    await expectLater(() => (c as dynamic).referralSummary(),
        throwsA(failureCode('verify_email')));
    expect(sent, 0);
  });

  test('an account switch discards the previous in-flight summary', () async {
    final response = Completer<Json>();
    final c = referralController((path, body) => response.future);
    addTearDown(c.dispose);
    final Future<dynamic> pending = (c as dynamic).referralSummary();
    c.account = {'user_id': 'different-user', 'verified': true};
    response.complete(referralSummary());
    await expectLater(pending, throwsA(failureCode('identity_mismatch')));
  });

  test(
      'customer mutations contain only explicit code or voluntary alias fields',
      () async {
    final requests = <Map<String, Object?>>[];
    final c = referralController((path, body) async {
      requests.add({'path': path, 'body': body});
      if (path.endsWith('/code')) return referralSummary(name: null);
      if (path.endsWith('/claim')) return {'status': 'confirmed'};
      return {'display_name': 'Участник'};
    });
    addTearDown(c.dispose);
    await (c as dynamic).createReferralCode();
    await (c as dynamic).claimReferral(referralCode);
    await (c as dynamic).saveReferralAlias('', '');
    expect(requests, [
      {'path': '/v1/referrals/code', 'body': <String, Object?>{}},
      {
        'path': '/v1/referrals/claim',
        'body': {'code': referralCode}
      },
      {
        'path': '/v1/referrals/alias',
        'body': {'first_name': '', 'surname_initial': ''},
      },
    ]);
    expect(await c.secure.readAll(), isEmpty);
  });

  test('richer customer rows and unsafe invite destinations are rejected',
      () async {
    for (final response in [
      {
        ...referralSummary(),
        'people': [
          {'display_name': 'Умар U.', 'email': 'private@example.test'},
        ],
      },
      {
        ...referralSummary(),
        'invite': {
          'code': referralCode,
          'url': 'https://other.example/app?ref=$referralCode',
        },
      },
    ]) {
      final c = referralController((path, body) async => response);
      await expectLater(() => (c as dynamic).referralSummary(),
          throwsA(failureCode('invalid_sync_response')));
      c.dispose();
    }
  });

  test('pagination is a bounded number without a customer selector', () async {
    var sent = 0;
    final c = referralController((path, body) async {
      sent++;
      expect(path, '/v1/referrals?offset=50');
      return referralSummary();
    });
    addTearDown(c.dispose);
    await (c as dynamic).referralSummary(offset: 50);
    await expectLater(() => (c as dynamic).referralSummary(offset: -1),
        throwsA(failureCode('invalid_cursor')));
    await expectLater(() => (c as dynamic).referralSummary(offset: 100001),
        throwsA(failureCode('invalid_cursor')));
    expect(sent, 1);
  });

  testWidgets('profile entry opens the native invitation screen',
      (tester) async {
    final app = AppController(UIStore(), catalog, 'en');
    await app.load();
    app.family = referralController((path, body) async =>
        path.endsWith('/alias')
            ? {'display_name': 'Участник'}
            : referralSummary());
    addTearDown(app.dispose);
    await tester.pumpWidget(LifeOSApp(controller: app));
    await tester.pumpAndSettle();
    await openNativeProfile(tester);
    final entry = find.byKey(const Key('native_referrals_entry'));
    expect(entry, findsOneWidget);
    await tester.ensureVisible(entry);
    await tester.tap(entry);
    await tester.pumpAndSettle();
    expect(find.text('Умар U.'), findsOneWidget);
    expect(find.text('private@example.test'), findsNothing);
  });

  testWidgets(
      'loading has no fabricated count and a real zero shows empty state',
      (tester) async {
    final pending = Completer<Json>();
    final c = referralController((path, body) => path.endsWith('/alias')
        ? Future.value({'display_name': 'Участник'})
        : pending.future);
    addTearDown(c.dispose);
    final pack = catalog.packs['en']!;
    await tester.pumpWidget(
        MaterialApp(home: ReferralsPage(controller: c, pack: pack)));
    await tester.pump();
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
    expect(find.byKey(const Key('referral_count')), findsNothing);
    pending.complete({
      'confirmed_count': 0,
      'invite': null,
      'people': [],
      'next_offset': null
    });
    await tester.pumpAndSettle();
    expect(find.text('0'), findsOneWidget);
    expect(find.text(referralText(pack, 'empty')), findsOneWidget);
    expect(find.text(referralText(pack, 'create')), findsOneWidget);
    expect(find.byKey(const Key('referral_link')), findsNothing);
  });

  testWidgets(
      'offline summary offers retry without showing stale customer data',
      (tester) async {
    var offline = true;
    final c = referralController((path, body) async {
      if (path.endsWith('/alias')) return {'display_name': 'Участник'};
      if (offline) throw const SyncFailure('offline');
      return referralSummary();
    });
    addTearDown(c.dispose);
    final pack = catalog.packs['en']!;
    await tester.pumpWidget(
        MaterialApp(home: ReferralsPage(controller: c, pack: pack)));
    await tester.pumpAndSettle();
    expect(find.text(referralText(pack, 'load_error')), findsOneWidget);
    expect(find.byKey(const Key('referral_count')), findsNothing);
    offline = false;
    await tester.tap(find.text(referralText(pack, 'retry')));
    await tester.pumpAndSettle();
    expect(find.text('Умар U.'), findsOneWidget);
    expect(find.text('private@example.test'), findsNothing);
    expect(
        find.ancestor(of: find.text('Умар U.'), matching: find.byType(InkWell)),
        findsNothing);
  });

  testWidgets('copy and Android share export only the public invite URL',
      (tester) async {
    String? copied, shared;
    tester.binding.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (call) async {
      if (call.method == 'Clipboard.setData') {
        copied = (call.arguments as Map)['text'] as String;
      }
      return null;
    });
    tester.binding.defaultBinaryMessenger
        .setMockMethodCallHandler(NativeBridge.channel, (call) async {
      expect(call.method, 'shareText');
      shared = call.arguments as String;
      return null;
    });
    addTearDown(() {
      tester.binding.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, null);
      tester.binding.defaultBinaryMessenger
          .setMockMethodCallHandler(NativeBridge.channel, null);
    });
    final c = referralController((path, body) async => path.endsWith('/alias')
        ? {'display_name': 'Участник'}
        : referralSummary());
    addTearDown(c.dispose);
    final pack = catalog.packs['en']!;
    await tester.pumpWidget(MaterialApp(
        home: ReferralsPage(
            controller: c, pack: pack, native: ReferralAndroidBridge())));
    await tester.pumpAndSettle();
    await tester.tap(find.text(referralText(pack, 'copy')));
    await tester.pumpAndSettle();
    expect(copied, referralLink);
    await tester.tap(find.text(referralText(pack, 'share')));
    await tester.pumpAndSettle();
    expect(shared, referralLink);
    await expectLater(
        () => ReferralAndroidBridge().shareReferralLink(
            Uri.parse('https://other.example/app?ref=$referralCode')),
        throwsA(isA<PlatformException>()));
  });

  testWidgets('an in-flight explicit claim never follows an account switch',
      (tester) async {
    final pending = Completer<Json>();
    final calls = <String>[];
    final c = referralController((path, body) async {
      calls.add(path);
      if (path.endsWith('/claim')) return pending.future;
      return path.endsWith('/alias')
          ? {'display_name': 'Участник'}
          : referralSummary();
    });
    addTearDown(c.dispose);
    final pack = catalog.packs['en']!;
    await tester.pumpWidget(
        MaterialApp(home: ReferralsPage(controller: c, pack: pack)));
    await tester.pumpAndSettle();
    final expand = find.text(referralText(pack, 'claim_title'));
    await tester.scrollUntilVisible(expand, 240,
        scrollable: find.byType(Scrollable).first);
    await tester.pumpAndSettle();
    await tester.tap(expand);
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).last, referralLink);
    final accept = find.text(referralText(pack, 'claim_action'));
    await tester.ensureVisible(accept);
    await tester.pumpAndSettle();
    await tester.tap(accept);
    await tester.pump();
    expect(calls.where((path) => path.endsWith('/claim')).length, 1);
    c.account = {'user_id': 'different-user', 'verified': true};
    c.publish();
    await tester.pump();
    pending.complete({'status': 'confirmed'});
    await tester.pumpAndSettle();
    expect(find.text('Умар U.'), findsNothing);
    expect(find.text(referralText(pack, 'identity_changed')), findsOneWidget);
    expect(find.text(referralText(pack, 'claim_done')), findsNothing);
    expect(calls.length, 3);
    expect(await c.secure.readAll(), isEmpty);
  });

  testWidgets('voluntary Unicode alias remains usable at 320 dark large text',
      (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(320, 844);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    Json? saved;
    final c = referralController((path, body) async {
      if (path.endsWith('/alias')) {
        if (body != null) {
          saved = body;
          return {'display_name': 'Умар 𐐀.'};
        }
        return {'display_name': 'Участник'};
      }
      return referralSummary();
    });
    addTearDown(c.dispose);
    final pack = catalog.packs['en']!;
    await tester.pumpWidget(MaterialApp(
        theme: lifeTheme(Brightness.dark),
        builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context)
                .copyWith(textScaler: const TextScaler.linear(1.4)),
            child: child!),
        home: ReferralsPage(controller: c, pack: pack)));
    await tester.pumpAndSettle();
    final expand = find.text(referralText(pack, 'alias_title'));
    await tester.scrollUntilVisible(expand, 240,
        scrollable: find.byType(Scrollable).first);
    await tester.pumpAndSettle();
    await tester.tap(expand);
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).at(0), 'Умар');
    await tester.enterText(find.byType(TextField).at(1), '𐐀');
    final save = find.text(referralText(pack, 'show_name'));
    await tester.ensureVisible(save);
    await tester.pumpAndSettle();
    await tester.tap(save);
    await tester.pumpAndSettle();
    expect(saved, {'first_name': 'Умар', 'surname_initial': '𐐀'});
    expect(find.text(referralText(pack, 'name_saved')), findsOneWidget);
    expect(
        tester
            .getSize(
                find.ancestor(of: save, matching: find.byType(FilledButton)))
            .height,
        greaterThanOrEqualTo(48));
    expect(tester.takeException(), isNull);
  });
}
