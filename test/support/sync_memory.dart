import 'package:lifeos/sync/contracts.dart';

// A deterministic stand-in for the SQLCipher adapter, used only by protocol tests.
class MemorySyncStore implements SyncStore {
  final Map<String, Json> outbox = {}, mirror = {}, meta = {};
  final Map<String, int> cursors = {};
  String key(String s, String w) => '$s|$w';
  @override
  Future<Json?> metadata(String s, String k) async => meta['$s|$k'];
  @override
  Future<void> saveMetadata(String s, String k, Json v) async {
    meta['$s|$k'] = clone(v);
  }

  @override
  Future<void> enqueue(String s, String w, Json op) async {
    final k = '${key(s, w)}|${op['id']}';
    if (outbox.containsKey(k)) return;
    outbox[k] = {
      'scope': s,
      'workspace': w,
      'operation': clone(op),
      'state': 'pending',
    };
  }

  List<Json> scoped(String s, String w) => outbox.values
      .where((r) => r['scope'] == s && r['workspace'] == w)
      .toList();
  @override
  Future<List<Json>> pending(String s, String w) async => scoped(s, w)
      .where((r) => r['state'] == 'pending')
      .take(100)
      .map((r) => clone(object(r['operation'])))
      .toList();
  @override
  Future<List<Json>> issues(String s, String w) async => scoped(s, w)
      .where((r) => r['state'] != 'pending')
      .map(
        (r) => {
          'operation': clone(object(r['operation'])),
          'result': clone(object(r['result'])),
        },
      )
      .toList();
  @override
  Future<List<Json>> records(String s, String w) async => mirror.values
      .where((r) => r['scope'] == s && r['workspace'] == w)
      .map((r) => clone(object(r['record'])))
      .toList();
  @override
  Future<int> cursor(String s, String w) async => cursors[key(s, w)] ?? 0;
  @override
  Future<void> acknowledge(String s, String w, List<Json> results) async {
    for (final result in results) {
      final k = '${key(s, w)}|${result['id']}';
      if (result['status'] == 'accepted') {
        outbox.remove(k);
      } else {
        outbox[k]!['state'] = result['status'];
        outbox[k]!['result'] = clone(result);
      }
    }
  }

  @override
  Future<void> receive(String s, String w, Json page) async {
    final incremental = page['protocol'] == 2;
    final visible = incremental ? null : (page['visible_ids'] as List).toSet();
    mirror.removeWhere(
      (_, v) =>
          v['scope'] == s &&
          v['workspace'] == w &&
          (incremental
              ? page['reset'] == true
              : !visible!.contains(v['record']['id'])),
    );
    for (final raw in page['records'] as List) {
      final r = object(raw);
      if (r['deleted'] == 0 && (incremental || visible!.contains(r['id']))) {
        mirror['${key(s, w)}|${r['id']}'] = {
          'scope': s,
          'workspace': w,
          'record': clone(r),
        };
      } else if (r['deleted'] == 1) {
        mirror.remove('${key(s, w)}|${r['id']}');
      }
    }
    cursors[key(s, w)] = page['cursor'] as int;
    if (incremental)
      await saveMetadata(s, 'epoch:$w', {'value': page['epoch']});
  }

  @override
  Future<void> resolve(String s, String w, String id, Json? replacement) async {
    if (replacement != null) await enqueue(s, w, replacement);
    outbox.remove('${key(s, w)}|$id');
  }

  @override
  Future<void> forgetAccess(String s, String w) async {
    mirror.removeWhere((_, r) => r['scope'] == s && r['workspace'] == w);
    cursors.remove(key(s, w));
    for (final row in scoped(s, w)) {
      row['state'] = 'rejected';
      row['result'] = {'status': 'rejected', 'error': 'workspace_forbidden'};
    }
  }
}
