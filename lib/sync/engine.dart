import 'dart:convert';

import 'contracts.dart';

class SyncEngine {
  SyncEngine(this.store, this.api, this.scope, this.workspace);
  final SyncStore store;
  final SyncTransport api;
  final String scope, workspace;
  Future<void>? _running;
  Future<void> synchronize() =>
      _running ??= _synchronize().whenComplete(() => _running = null);
  Future<void> _synchronize() async {
    try {
      // Push before pull: a lost reply is replayed with the original operation UUID.
      while (true) {
        final waiting = await store.pending(scope, workspace);
        final operations = <Json>[];
        var bytes = 512;
        for (final operation in waiting) {
          final size = utf8.encode(jsonEncode(operation)).length + 1;
          if (operations.isNotEmpty && bytes + size > 1500000) break;
          operations.add(operation);
          bytes += size;
        }
        if (operations.isEmpty) break;
        final response = await api.request(
          '/v1/sync/push',
          body: {'workspace_id': workspace, 'operations': operations},
        );
        final results = (response['results'] as List).map(object).toList();
        final expected = operations.map((o) => o['id']).toSet();
        if (results.length != operations.length ||
            results.map((r) => r['id']).toSet().length != expected.length ||
            !results.every((r) => expected.contains(r['id']))) {
          throw const SyncFailure('invalid_sync_response');
        }
        await store.acknowledge(scope, workspace, results);
      }
      while (true) {
        final cursor = await store.cursor(scope, workspace);
        final epoch =
            (await store.metadata(scope, 'epoch:$workspace'))?['value']
                as String? ??
            '';
        final response = await api.request(
          '/v1/sync/pull?workspace=${Uri.encodeQueryComponent(workspace)}&cursor=$cursor&protocol=2&epoch=${Uri.encodeQueryComponent(epoch)}',
        );
        if (response['cursor'] is! int ||
            response['cursor'] < 0 ||
            response['cursor'] < cursor && response['reset'] != true ||
            response['more'] is! bool ||
            response['more'] == true &&
                response['cursor'] == cursor &&
                response['reset'] != true ||
            response['protocol'] == 2 &&
                (response['epoch'] is! String || response['reset'] is! bool)) {
          throw const SyncFailure('invalid_sync_response');
        }
        await store.receive(scope, workspace, response);
        if (response['more'] != true) break;
      }
    } on SyncFailure catch (error) {
      if (error.code == 'workspace_forbidden' ||
          error.code == 'profile_forbidden') {
        await store.forgetAccess(scope, workspace);
      }
      rethrow;
    }
  }
}
