import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/account/lifecycle_authorizer.dart';
import 'package:lifeos/platform/native_bridge.dart';
import 'package:lifeos/sync/contracts.dart';

class FreshGoogleBridge extends NativeBridge {
  final calls = <(String, String)>[];
  bool cancelled = false;
  void Function()? onGoogle;
  @override
  Future<String> googleSignIn(String clientId, String nonce) async {
    calls.add((clientId, nonce));
    onGoogle?.call();
    if (cancelled) throw PlatformException(code: 'google_cancelled');
    return 'fresh-id-token';
  }
}

void main() {
  test('Google-only deletion proof keeps MFA and never asks for a password',
      () async {
    final calls = <(String, Json?)>[];
    final bridge = FreshGoogleBridge();
    final authorizer = LifecycleAuthorizer(
        native: bridge,
        request: (path, {body}) async {
          calls.add((path, body));
          if (path.endsWith('/start')) {
            return {
              'client_id': 'client',
              'nonce': 'fresh-nonce',
              'challenge': 'challenge'
            };
          }
          return {'reauth_token': 'one-use-proof', 'expires_in': 300};
        });
    final prompted = <bool>[];
    final result = await authorizer.authenticate(
        {'has_password': false, 'google_linked': true, 'mfa_required': true},
        prompt: (mfa) async {
      prompted.add(mfa);
      return '123456';
    });
    expect(prompted, [true]);
    expect(bridge.calls, [('client', 'fresh-nonce')]);
    expect(calls.map((c) => c.$1),
        ['/v1/auth/google/reauth/start', '/v1/auth/google/finish']);
    expect(calls.last.$2,
        {'challenge': 'challenge', 'id_token': 'fresh-id-token'});
    expect(result, {'reauth_token': 'one-use-proof', 'code': '123456'});
  });
  test('each sensitive action gets a new Google proof', () async {
    var challenges = 0;
    final authorizer = LifecycleAuthorizer(
        native: FreshGoogleBridge(),
        request: (path, {body}) async {
          if (path.endsWith('/start')) {
            return {
              'client_id': 'client',
              'nonce': 'nonce-${++challenges}',
              'challenge': 'challenge-$challenges'
            };
          }
          return {'reauth_token': 'proof-$challenges'};
        });
    final status = {
      'has_password': false,
      'google_linked': true,
      'mfa_required': false
    };
    expect(await authorizer.authenticate(status, prompt: (_) async => null),
        {'reauth_token': 'proof-1'});
    expect(await authorizer.authenticate(status, prompt: (_) async => null),
        {'reauth_token': 'proof-2'});
  });
  test('password path still requires MFA and sends no Google request',
      () async {
    final authorizer = LifecycleAuthorizer(
        native: FreshGoogleBridge(),
        request: (path, {body}) async =>
            throw StateError('unexpected request'));
    final result = await authorizer.authenticate(
        {'has_password': true, 'google_linked': false, 'mfa_required': true},
        prompt: (mfa) async => mfa ? '654321' : 'existing-password');
    expect(result, {'password': 'existing-password', 'code': '654321'});
  });
  test('cancelling Google or MFA returns no mutation credential', () async {
    final bridge = FreshGoogleBridge()..cancelled = true;
    final authorizer = LifecycleAuthorizer(
        native: bridge,
        request: (path, {body}) async => {
              'client_id': 'client',
              'nonce': 'nonce',
              'challenge': 'challenge'
            });
    expect(
        await authorizer.authenticate({
          'has_password': false,
          'google_linked': true,
          'mfa_required': false
        }, prompt: (_) async => null),
        isNull);
    expect(
        await authorizer.authenticate({
          'has_password': true,
          'google_linked': false,
          'mfa_required': true
        }, prompt: (mfa) async => mfa ? null : 'password'),
        isNull);
  });
  test(
      'account change during Google confirmation cannot authorize another account',
      () async {
    var current = true;
    final calls = <String>[];
    final bridge = FreshGoogleBridge()..onGoogle = () => current = false;
    final authorizer = LifecycleAuthorizer(
        native: bridge,
        validSession: () => current,
        request: (path, {body}) async {
          calls.add(path);
          return {
            'client_id': 'client',
            'nonce': 'nonce',
            'challenge': 'challenge'
          };
        });
    await expectLater(
        authorizer.authenticate({
          'has_password': false,
          'google_linked': true,
          'mfa_required': false
        }, prompt: (_) async => null),
        throwsA(isA<SyncFailure>()
            .having((e) => e.code, 'code', 'identity_mismatch')));
    expect(calls, ['/v1/auth/google/reauth/start']);
  });
}
