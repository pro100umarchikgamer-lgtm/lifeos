import 'package:flutter/services.dart';
import '../platform/native_bridge.dart';
import '../sync/contracts.dart';

typedef LifecycleRequest = Future<Json> Function(String path, {Json? body});

enum LifecycleAuthMethod { password, google }

/// Produces fresh, single-action credentials. It never changes the login session
/// and never persists a password, Google ID token, proof or MFA code.
class LifecycleAuthorizer {
  LifecycleAuthorizer(
      {required this.request,
      NativeBridge? native,
      bool Function()? validSession})
      : native = native ?? NativeBridge(),
        _validSession = validSession ?? (() => true);
  final LifecycleRequest request;
  final NativeBridge native;
  final bool Function() _validSession;
  void _guard() {
    if (!_validSession()) throw const SyncFailure('identity_mismatch');
  }

  Future<Json?> authenticate(
    Json status, {
    required Future<String?> Function(bool mfa) prompt,
    Future<LifecycleAuthMethod?> Function()? choose,
  }) async {
    _guard();
    var methods = status;
    if (methods['has_password'] is! bool || methods['google_linked'] is! bool) {
      methods = {...status, ...await request('/v1/account/google')};
      _guard();
    }
    var mfa = methods['mfa_required'] == true;
    if (methods['mfa_required'] is! bool) {
      mfa = (await request('/v1/account/mfa'))['enabled'] == true;
      _guard();
    }
    final password = methods['has_password'] == true;
    final google = methods['google_linked'] == true;
    if (!password && !google) throw const SyncFailure('google_unavailable');
    final selected = password && google
        ? (choose == null ? LifecycleAuthMethod.password : await choose())
        : password
            ? LifecycleAuthMethod.password
            : LifecycleAuthMethod.google;
    _guard();
    if (selected == null) return null;
    final auth = <String, dynamic>{};
    if (selected == LifecycleAuthMethod.google) {
      if (!google) throw const SyncFailure('google_unavailable');
      final challenge = await request('/v1/auth/google/reauth/start', body: {});
      _guard();
      if (challenge['client_id'] is! String ||
          challenge['nonce'] is! String ||
          challenge['challenge'] is! String) {
        throw const SyncFailure('invalid_sync_response');
      }
      try {
        final idToken = await native.googleSignIn(
            challenge['client_id'] as String, challenge['nonce'] as String);
        _guard();
        final result = await request('/v1/auth/google/finish',
            body: {'challenge': challenge['challenge'], 'id_token': idToken});
        _guard();
        final proof = result['reauth_token'];
        if (proof is! String || proof.isEmpty || proof.length > 4096) {
          throw const SyncFailure('invalid_sync_response');
        }
        auth['reauth_token'] = proof;
      } on PlatformException catch (error) {
        if (error.code == 'google_cancelled') return null;
        throw SyncFailure(error.code);
      }
    } else {
      if (!password) throw const SyncFailure('invalid_credentials');
      final secret = await prompt(false);
      _guard();
      if (secret == null || secret.isEmpty) return null;
      auth['password'] = secret;
    }
    if (mfa) {
      final code = await prompt(true);
      _guard();
      if (code == null || code.trim().isEmpty) return null;
      auth['code'] = code.trim();
    }
    return auth;
  }
}
