/// Checks new secrets only; existing login passwords bypass this policy.
/// Returns the same public error codes as backend.service.validate_password.
String? newPasswordIssue(String password) {
  final length = password.runes.length;
  if (length < 8 || length > 256) return 'password_length';
  final value = password.toLowerCase().trim();
  final letters = _letter.allMatches(value).map((m) => m.group(0)!).toSet();
  if (letters.isEmpty ||
      (!_digit.hasMatch(value) &&
          !(password.trim().runes.length >= 16 && letters.length >= 3))) {
    return 'password_weak';
  }
  final plain = value.runes
      .map(String.fromCharCode)
      .where((char) => _letter.hasMatch(char) || _digit.hasMatch(char))
      .join();
  final stem = plain.replaceFirst(_digitSuffix, '');
  final runs = _runs.allMatches(plain).map((m) => m.group(0)!);
  if (value.runes.toSet().length < 3 ||
      _common.contains(plain) ||
      _common.contains(stem) ||
      _repeated(value) ||
      _repeated(plain) ||
      (stem != plain && _repeated(stem)) ||
      runs.every(_simpleRun)) {
    return 'password_weak';
  }
  return null;
}

final _letter = RegExp(r'\p{L}', unicode: true);
final _digit = RegExp(r'\p{Nd}', unicode: true);
final _digitSuffix = RegExp(r'\p{Nd}+$', unicode: true);
final _runs = RegExp(r'\p{L}+|\p{Nd}+', unicode: true);
const _common = {
  'password', 'password1', 'password123', 'qwerty', 'qwerty1', 'qwerty123',
  'letmein', 'welcome', 'welcome1', '1234567', '12345678', '123456789',
  'пароль', 'пароль123', 'uladim', 'uladim123', 'lifeos', 'lifeos123',
  'abcdefg', 'abcdefgh', 'qwertyuiop', 'iloveyou', 'welcome123', 'letmein1',
  'admin', 'admin123', 'test', 'test123', 'testing', '123456a', 'sunshine',
  'football', 'monkey', 'monkey123', 'dragon', 'dragon123', 'princess', 'a1b2c3d4',
};

bool _repeated(String value) {
  final chars = value.runes.toList();
  for (var width = 1; width <= chars.length ~/ 2; width++) {
    if (chars.length % width != 0) continue;
    var matches = true;
    for (var i = width; i < chars.length; i++) {
      if (chars[i] != chars[i % width]) {
        matches = false;
        break;
      }
    }
    if (matches) return true;
  }
  return false;
}

bool _simpleRun(String value) {
  final chars = value.runes.toList();
  if (chars.length < 2) return false;
  if (chars.every((char) => char == chars.first)) return true;
  final step = chars[1] - chars[0];
  if (step.abs() == 1 &&
      List.generate(chars.length - 1,
              (i) => chars[i + 1] - chars[i] == step)
          .every((matches) => matches)) {
    return true;
  }
  return ['qwertyuiop', 'asdfghjkl', 'zxcvbnm'].any(
      (row) => row.contains(value) || row.split('').reversed.join().contains(value));
}
