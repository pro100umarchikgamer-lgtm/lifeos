import '../sync/contracts.dart';

final _referralCode = RegExp(r'^[A-Za-z0-9_-]{43}$');
final _shortName = RegExp(r"^\p{L}[\p{L}'’‘-]*(?: \p{L}\.)?$", unicode: true);

Json _fields(Object? raw, Set<String> keys) {
  if (raw is! Map ||
      raw.length != keys.length ||
      raw.keys.any((key) => key is! String || !keys.contains(key))) {
    throw const SyncFailure('invalid_sync_response');
  }
  return Map<String, dynamic>.from(raw);
}

Uri? _inviteUri(String value) {
  final uri = Uri.tryParse(value);
  if (uri == null ||
      uri.scheme != 'https' ||
      uri.host != 'getuladim.space' ||
      uri.port != 443 ||
      uri.userInfo.isNotEmpty ||
      uri.path != '/app' ||
      uri.hasFragment ||
      uri.queryParametersAll.length != 1) {
    return null;
  }
  final codes = uri.queryParametersAll['ref'];
  if (codes == null ||
      codes.length != 1 ||
      !_referralCode.hasMatch(codes.single)) {
    return null;
  }
  return uri;
}

String referralCodeFromInput(String input) {
  final value = input.trim();
  if (_referralCode.hasMatch(value)) return value;
  final uri = _inviteUri(value);
  if (uri == null) throw const SyncFailure('referral_invalid');
  return uri.queryParameters['ref']!;
}

String referralDisplayName(Object? raw) {
  final name = _fields(raw, {'display_name'})['display_name'];
  if (name is! String || name.runes.length > 35 || !_shortName.hasMatch(name)) {
    throw const SyncFailure('invalid_sync_response');
  }
  return name;
}

class ReferralInvite {
  const ReferralInvite._(this.code, this.url);
  final String code;
  final Uri url;

  factory ReferralInvite.fromJson(Object? raw) {
    final value = _fields(raw, {'code', 'url'});
    final code = value['code'], url = value['url'];
    final uri = url is String ? _inviteUri(url) : null;
    if (code is! String ||
        !_referralCode.hasMatch(code) ||
        uri == null ||
        uri.queryParameters['ref'] != code) {
      throw const SyncFailure('invalid_sync_response');
    }
    return ReferralInvite._(code, uri);
  }
}

/// Deliberately has no customer ID, email, profile URL, activity or purchase data.
class ReferralSummary {
  const ReferralSummary._(
      this.confirmedCount, this.invite, this.people, this.nextOffset);
  final int confirmedCount;
  final ReferralInvite? invite;
  final List<String> people;
  final int? nextOffset;

  factory ReferralSummary.fromJson(Object? raw, {int offset = 0}) {
    final value =
        _fields(raw, {'confirmed_count', 'invite', 'people', 'next_offset'});
    final count = value['confirmed_count'],
        people = value['people'],
        next = value['next_offset'];
    if (count is! int ||
        count < 0 ||
        people is! List ||
        people.length > 50 ||
        people.length > count ||
        next != null && (next is! int || next <= offset || next > 100000)) {
      throw const SyncFailure('invalid_sync_response');
    }
    return ReferralSummary._(
        count,
        value['invite'] == null
            ? null
            : ReferralInvite.fromJson(value['invite']),
        List.unmodifiable(people.map(referralDisplayName)),
        next as int?);
  }
}
