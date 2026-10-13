import 'dart:convert';

typedef Json = Map<String, dynamic>;
Json object(Object? value) => Map<String, dynamic>.from(value as Map);
Json clone(Json value) => object(jsonDecode(jsonEncode(value)));

class SyncFailure implements Exception {
  const SyncFailure(this.code, [this.status = 0]);
  final String code;
  final int status;
}

abstract interface class SyncTransport {
  Future<Json> request(String path, {Json? body});
}

abstract interface class SyncStore {
  Future<Json?> metadata(String scope, String key);
  Future<void> saveMetadata(String scope, String key, Json value);
  Future<void> enqueue(String scope, String workspace, Json operation);
  Future<List<Json>> pending(String scope, String workspace);
  Future<List<Json>> issues(String scope, String workspace);
  Future<List<Json>> records(String scope, String workspace);
  Future<int> cursor(String scope, String workspace);
  Future<void> acknowledge(String scope, String workspace, List<Json> results);
  Future<void> receive(String scope, String workspace, Json page);
  Future<void> resolve(
    String scope,
    String workspace,
    String operationId,
    Json? replacement,
  );
  Future<void> forgetAccess(String scope, String workspace);
}
