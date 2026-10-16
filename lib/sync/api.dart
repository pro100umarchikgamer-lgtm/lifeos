import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'contracts.dart';

class FamilyApi implements SyncTransport {
  FamilyApi(String endpoint) : base = Uri.parse(endpoint) {
    if (base.host.isEmpty ||
        base.userInfo.isNotEmpty ||
        base.hasQuery ||
        base.hasFragment ||
        (base.path.isNotEmpty && base.path != '/') ||
        (base.scheme != 'https' &&
            !(base.scheme == 'http' &&
                [
                  '127.0.0.1',
                  'localhost',
                  '10.0.2.2',
                  '::1',
                ].contains(base.host)))) {
      throw const SyncFailure('invalid_endpoint');
    }
  }
  final Uri base;
  String? token, refreshToken, userId;
  Future<void> Function(Json)? onRotated;
  Future<void>? _rotation;

  final HttpClient _client = HttpClient()
    ..connectionTimeout = const Duration(seconds: 15);
  @override
  Future<Json> request(String path, {Json? body}) async {
    final attemptedToken = token;
    try {
      return await _send(path, body: body);
    } on SyncFailure catch (error) {
      if (error.code != 'unauthorized' || refreshToken == null || token == null ||
          path == '/v1/auth/refresh') rethrow;
      if (token != attemptedToken) return _send(path, body: body);
      final rotation = _rotation ??= _rotate();
      try {
        await rotation;
      } finally {
        if (identical(_rotation, rotation)) _rotation = null;
      }
      // Mutations keep their original operation ID; a retry cannot duplicate data.
      return _send(path, body: body);
    }
  }

  Future<void> _rotate() async {
    final result = await _send('/v1/auth/refresh', body: {
      'refresh_token': refreshToken,
    });
    if (result['user_id'] != userId || result['token'] is! String ||
        result['refresh_token'] is! String ||
        (result['token'] as String).length != 43 ||
        (result['refresh_token'] as String).length != 43) {
      throw const SyncFailure('identity_mismatch');
    }
    // Persist the complete credential pair atomically before publishing it.
    await onRotated?.call(result);
    token = result['token'] as String;
    refreshToken = result['refresh_token'] as String;
  }

  Future<Json> _send(String path, {Json? body}) async {
    try {
      final bytes = body == null ? null : utf8.encode(jsonEncode(body));
      if (bytes != null && bytes.length > 2 * 1024 * 1024) {
        throw const SyncFailure('body_limit');
      }
      final req = await _client
          .openUrl(body == null ? 'GET' : 'POST', base.resolve(path))
          .timeout(const Duration(seconds: 15));
      req.followRedirects = false;
      if (token != null) {
        req.headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
      }
      if (bytes != null) {
        req.headers.contentType = ContentType.json;
        req.contentLength = bytes.length;
        req.add(bytes);
      }
      final response = await req.close().timeout(const Duration(seconds: 20));
      final content = <int>[];
      await for (final chunk in response.timeout(const Duration(seconds: 20))) {
        content.addAll(chunk);
        if (content.length > 8 * 1024 * 1024) {
          throw const SyncFailure('response_limit');
        }
      }
      final value = object(jsonDecode(utf8.decode(content)));
      if (response.statusCode != 200) {
        throw SyncFailure(
          value['error'] as String? ?? 'server_error',
          response.statusCode,
        );
      }
      return value;
    } on SocketException {
      throw const SyncFailure('offline');
    } on TimeoutException {
      throw const SyncFailure('offline');
    } on HandshakeException {
      throw const SyncFailure('tls_error');
    } on FormatException {
      throw const SyncFailure('invalid_sync_response');
    }
  }

  void close() => _client.close(force: true);
}
