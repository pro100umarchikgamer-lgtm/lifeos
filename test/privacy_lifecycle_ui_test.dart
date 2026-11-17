import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/ui/privacy_lifecycle.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/sync/controller.dart';
import 'package:lifeos/sync/contracts.dart';
import 'support/sync_memory.dart';
import 'lifecycle_authorizer_test.dart' show FreshGoogleBridge;

Json status(
        {bool mfa = false,
        List<Json> families = const [],
        bool staff = false}) =>
    {
      'has_password': false,
      'google_linked': true,
      'mfa_required': mfa,
      'ownership_transfer_required': families,
      'incoming_transfers': [],
      'staff_offboarding_required': staff,
      'request': null,
      'cancel_available': false,
      'grace_seconds': 86400,
    };
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late PackCatalog catalog;
  setUpAll(() async => catalog = await PackCatalog.load());
  testWidgets(
      'Google-only deletion requires typed confirmation and a fresh MFA code',
      (tester) async {
    final c = FamilyController(MemorySyncStore())
      ..account = {'user_id': 'alice', 'email': 'alice@example.test'};
    addTearDown(c.dispose);
    var current = status(mfa: true), proofs = 0;
    final mutations = <(String, Json)>[];
    Future<Json> request(String path, {Json? body}) async {
      if (path.endsWith('/reauth/start')) {
        return {
          'client_id': 'client',
          'nonce': 'nonce-${++proofs}',
          'challenge': 'c-$proofs'
        };
      }
      if (path.endsWith('/google/finish')) {
        return {'reauth_token': 'proof-$proofs'};
      }
      if (body != null) {
        mutations.add((path, body));
        current = {
          ...current,
          'request': {'state': 'pending', 'due_at': 1900000000},
          'cancel_available': true
        };
      }
      return clone(current);
    }

    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: ListView(children: [
      AccountPrivacyLifecycle(
          controller: c,
          pack: catalog.packs['en']!,
          request: request,
          initialData: current,
          native: FreshGoogleBridge(),
          onSupport: () {})
    ]))));
    await tester.tap(find.byKey(const Key('privacy_delete')));
    await tester.pumpAndSettle();
    expect(
        tester
            .widget<FilledButton>(
                find.byKey(const Key('privacy_confirm_action')))
            .onPressed,
        isNull);
    await tester.enterText(
        find.byKey(const Key('privacy_confirmation_input')), 'DELETE');
    await tester.pump();
    await tester.tap(find.byKey(const Key('privacy_confirm_action')));
    await tester.pumpAndSettle();
    expect(find.text(catalog.packs['en']!.t('family_password')), findsNothing);
    await tester.enterText(find.byType(TextField), '123456');
    await tester.pump();
    await tester
        .tap(find.text(catalog.packs['en']!.t('privacy_confirm_action')));
    await tester.pumpAndSettle();
    expect(mutations.single.$1, '/v1/account/lifecycle/deletion');
    expect(mutations.single.$2, {
      'confirmation': 'DELETE',
      'reauth_token': 'proof-1',
      'code': '123456'
    });
    expect(find.byKey(const Key('privacy_cancel_deletion')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  testWidgets(
      'sole-parent closure discloses all-member impact and uses a separate fresh proof',
      (tester) async {
    final c = FamilyController(MemorySyncStore())
      ..account = {'user_id': 'alice', 'email': 'alice@example.test'};
    addTearDown(c.dispose);
    var current = status(families: [
          {
            'id': 'family',
            'name': 'Our family',
            'workspace_revision': 3,
            'eligible_parent_id': null,
            'close_family_available': true
          }
        ]),
        proofs = 0;
    final mutations = <(String, Json)>[];
    Future<Json> request(String path, {Json? body}) async {
      if (path.endsWith('/reauth/start')) {
        return {
          'client_id': 'client',
          'nonce': 'n-${++proofs}',
          'challenge': 'c-$proofs'
        };
      }
      if (path.endsWith('/google/finish')) {
        return {'reauth_token': 'proof-$proofs'};
      }
      if (body != null) {
        mutations.add((path, body));
        if (path.endsWith('/close-family')) {
          current = status();
        } else {
          current = {
            ...current,
            'request': {'state': 'pending', 'due_at': 1900000000}
          };
        }
      }
      return clone(current);
    }

    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: ListView(children: [
      AccountPrivacyLifecycle(
          controller: c,
          pack: catalog.packs['en']!,
          request: request,
          initialData: current,
          native: FreshGoogleBridge(),
          onSupport: () {})
    ]))));
    expect(
        tester
            .widget<OutlinedButton>(find.byKey(const Key('privacy_delete')))
            .onPressed,
        isNull);
    await tester
        .ensureVisible(find.byKey(const Key('privacy_close_family_family')));
    await tester.tap(find.byKey(const Key('privacy_close_family_family')));
    await tester.pumpAndSettle();
    expect(find.textContaining('every member'), findsOneWidget);
    await tester.enterText(
        find.byKey(const Key('privacy_confirmation_input')), 'CLOSE FAMILY');
    await tester.pump();
    await tester.tap(find.byKey(const Key('privacy_confirm_action')));
    await tester.pumpAndSettle();
    expect(mutations.first.$2, {
      'workspace_id': 'family',
      'revision': 3,
      'confirmation': 'CLOSE FAMILY',
      'reauth_token': 'proof-1'
    });
    await tester.ensureVisible(find.byKey(const Key('privacy_delete')));
    await tester.tap(find.byKey(const Key('privacy_delete')));
    await tester.pumpAndSettle();
    await tester.enterText(
        find.byKey(const Key('privacy_confirmation_input')), 'DELETE');
    await tester.pump();
    await tester.tap(find.byKey(const Key('privacy_confirm_action')));
    await tester.pumpAndSettle();
    expect(mutations.last.$2['reauth_token'], 'proof-2');
    expect(proofs, 2);
    expect(tester.takeException(), isNull);
  });
  testWidgets(
      'staff offboarding has a clear support action and cannot silently delete staff access',
      (tester) async {
    final c = FamilyController(MemorySyncStore())
      ..account = {'user_id': 'alice'};
    addTearDown(c.dispose);
    var support = false;
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: ListView(children: [
      AccountPrivacyLifecycle(
          controller: c,
          pack: catalog.packs['en']!,
          request: (path, {body}) async => status(staff: true),
          initialData: status(staff: true),
          onSupport: () => support = true)
    ]))));
    expect(
        tester
            .widget<OutlinedButton>(find.byKey(const Key('privacy_delete')))
            .onPressed,
        isNull);
    await tester.tap(find.byKey(const Key('privacy_staff_support')));
    await tester.pumpAndSettle();
    expect(support, isTrue);
    expect(find.byType(TextField), findsNothing);
    expect(tester.takeException(), isNull);
  });
  testWidgets(
      'ownership transfer names the recipient and waits for their separate acceptance',
      (tester) async {
    final c = FamilyController(MemorySyncStore())
      ..account = {'user_id': 'alice'};
    addTearDown(c.dispose);
    var current = status(families: [
      {
        'id': 'family',
        'name': 'Family',
        'workspace_revision': 2,
        'eligible_parent_id': 'bob',
        'eligible_parent_label': 'bob@example.test',
        'close_family_available': true
      }
    ]);
    final sent = <(String, Json)>[];
    Future<Json> request(String path, {Json? body}) async {
      if (path.endsWith('/reauth/start')) {
        return {
          'client_id': 'client',
          'nonce': 'nonce',
          'challenge': 'challenge'
        };
      }
      if (path.endsWith('/google/finish')) {
        return {'reauth_token': 'fresh-proof'};
      }
      if (body != null) {
        sent.add((path, body));
        current = {
          ...current,
          'ownership_transfer_required': [
            {
              ...current['ownership_transfer_required'][0],
              'pending_until': 1900000000
            }
          ]
        };
      }
      return clone(current);
    }

    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: ListView(children: [
      AccountPrivacyLifecycle(
          controller: c,
          pack: catalog.packs['en']!,
          request: request,
          initialData: current,
          native: FreshGoogleBridge(),
          onSupport: () {})
    ]))));
    await tester
        .ensureVisible(find.byKey(const Key('privacy_transfer_family')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('privacy_transfer_family')));
    await tester.pumpAndSettle();
    expect(find.textContaining('bob@example.test'), findsOneWidget);
    expect(find.textContaining('accept separately'), findsOneWidget);
    await tester.tap(find.byKey(const Key('privacy_confirm_action')));
    await tester.pumpAndSettle();
    expect(sent.single.$1, '/v1/account/lifecycle/transfer');
    expect(sent.single.$2, {
      'workspace_id': 'family',
      'user_id': 'bob',
      'reauth_token': 'fresh-proof'
    });
    expect(sent.any((call) => call.$1.endsWith('/accept-transfer')), isFalse);
    expect(find.textContaining('Waiting for the recipient'), findsOneWidget);
    expect(
        tester
            .widget<OutlinedButton>(find.byKey(const Key('privacy_delete')))
            .onPressed,
        isNull);
  });
  testWidgets(
      'cloud erasing status keeps local copies and offers no false cancellation',
      (tester) async {
    final c = FamilyController(MemorySyncStore())
      ..account = {'user_id': 'alice'};
    addTearDown(c.dispose);
    final current = {
      ...status(),
      'request': {'state': 'erasing', 'due_at': 1},
      'cancel_available': false
    };
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: ListView(children: [
      AccountPrivacyLifecycle(
          controller: c,
          pack: catalog.packs['en']!,
          request: (path, {body}) async => current,
          initialData: current,
          onSupport: () {})
    ]))));
    expect(find.text(catalog.packs['en']!.t('privacy_cloud_erasing')),
        findsOneWidget);
    expect(find.byKey(const Key('privacy_delete')), findsNothing);
    expect(find.byKey(const Key('privacy_cancel_deletion')), findsNothing);
  });
  testWidgets(
      'incoming ownership needs recipient confirmation before accepting',
      (tester) async {
    final c = FamilyController(MemorySyncStore())..account = {'user_id': 'bob'};
    addTearDown(c.dispose);
    var current = {
      ...status(),
      'incoming_transfers': [
        {'id': 'invitation', 'workspace_id': 'family', 'name': 'Family'}
      ]
    };
    final sent = <(String, Json)>[];
    Future<Json> request(String path, {Json? body}) async {
      if (path.endsWith('/reauth/start')) {
        return {
          'client_id': 'client',
          'nonce': 'nonce',
          'challenge': 'challenge'
        };
      }
      if (path.endsWith('/google/finish')) {
        return {'reauth_token': 'recipient-proof'};
      }
      if (body != null) {
        sent.add((path, body));
        current = status();
      }
      return clone(current);
    }

    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: ListView(children: [
      AccountPrivacyLifecycle(
          controller: c,
          pack: catalog.packs['en']!,
          request: request,
          initialData: current,
          native: FreshGoogleBridge(),
          onSupport: () {})
    ]))));
    await tester
        .tap(find.byKey(const Key('privacy_accept_transfer_invitation')));
    await tester.pumpAndSettle();
    expect(sent, isEmpty);
    expect(find.textContaining('separate consent'), findsOneWidget);
    await tester.tap(find.byKey(const Key('privacy_confirm_action')));
    await tester.pumpAndSettle();
    expect(sent.single.$1, '/v1/account/lifecycle/accept-transfer');
    expect(sent.single.$2,
        {'transfer_id': 'invitation', 'reauth_token': 'recipient-proof'});
  });
}
