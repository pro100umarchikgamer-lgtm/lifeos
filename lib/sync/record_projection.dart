import 'contracts.dart';

bool isImmutableSyncTombstone(Json row) =>
    row['deleted'] == 1 &&
    (row['privacy_erased'] == true || row['structural_reference'] == true);
bool isActiveSyncRecord(Json row) =>
    (row['deleted'] ?? 0) == 0 &&
    row['structural_reference'] != true &&
    row['privacy_erased'] != true;

/// Erasure references contain no owner payload, names, audiences or amounts.
Json projectSyncRecord(Json raw) {
  if (!isImmutableSyncTombstone(raw)) {
    if (raw['structural_reference'] == true || raw['privacy_erased'] == true) {
      throw const SyncFailure('invalid_sync_response');
    }
    return clone(raw);
  }
  if (raw['id'] is! String ||
      raw['workspace_id'] is! String ||
      raw['kind'] is! String ||
      raw['revision'] is! int ||
      raw['revision'] < 1 ||
      raw['data'] is! Map ||
      (raw['data'] as Map).isNotEmpty) {
    throw const SyncFailure('invalid_sync_response');
  }
  final structural = raw['structural_reference'] == true;
  if (structural &&
      (raw['kind'] != 'account' ||
          raw['reference_currency'] is! String ||
          !RegExp(r'^[A-Z]{3}$')
              .hasMatch(raw['reference_currency'] as String))) {
    throw const SyncFailure('invalid_sync_response');
  }
  return {
    'id': raw['id'],
    'workspace_id': raw['workspace_id'],
    'kind': raw['kind'],
    'revision': raw['revision'],
    'deleted': 1,
    'editable': false,
    'data': <String, dynamic>{},
    if (raw['privacy_erased'] == true) 'privacy_erased': true,
    if (structural) ...{
      'structural_reference': true,
      'reference_currency': raw['reference_currency']
    },
  };
}

bool queuedOperationReferencesErasure(Json operation, Set<String> erased) {
  final data = operation['data'];
  return data is Map &&
          ['account_id', 'from_id', 'to_id', 'movement_id']
              .any((key) => erased.contains(data[key])) ||
      erased.contains(operation['movement_id']);
}
