import 'dart:convert';
import 'dart:math';
import 'dart:typed_data' as typed;
import 'package:cryptography/cryptography.dart';
import '../domain/models.dart';

class BackupService {
  static const maxBytes = 20 * 1024 * 1024;
  static const iterations = 210000;
  final _cipher = AesGcm.with256bits();
  final _kdf = Pbkdf2(macAlgorithm: Hmac.sha256(), iterations: iterations, bits: 256);
  typed.Uint8List _random(int length) => typed.Uint8List.fromList(List.generate(length, (_) => Random.secure().nextInt(256)));
  Future<typed.Uint8List> encrypt(Map<String, Object?> snapshot, String passphrase) async {
    if (passphrase.length < 12) throw const DomainFailure('backup_password_short');
    final salt = _random(16), nonce = _random(12);
    final key = await _kdf.deriveKey(secretKey: SecretKey(utf8.encode(passphrase)), nonce: salt);
    final plain = utf8.encode(jsonEncode(snapshot));
    if (plain.length > maxBytes) throw const DomainFailure('backup_too_large');
    final box = await _cipher.encrypt(plain, secretKey: key, nonce: nonce, aad: utf8.encode('LifeOS backup v1'));
    final bytes = typed.Uint8List.fromList(utf8.encode(jsonEncode({'format': 'LifeOS', 'version': 1,
      'iterations': iterations, 'salt': base64Encode(salt), 'nonce': base64Encode(nonce),
      'ciphertext': base64Encode(box.cipherText), 'mac': base64Encode(box.mac.bytes)})));
    if (bytes.length > maxBytes) throw const DomainFailure('backup_too_large');
    return bytes;
  }
  Future<Map<String, Object?>> decrypt(typed.Uint8List bytes, String passphrase) async {
    if (bytes.length > maxBytes) throw const DomainFailure('backup_too_large');
    try {
      final data = jsonDecode(utf8.decode(bytes)) as Map<String, dynamic>;
      if (data['format'] != 'LifeOS' || data['version'] != 1 || data['iterations'] != iterations) {
        throw const FormatException();
      }
      final salt = base64Decode(data['salt'] as String), nonce = base64Decode(data['nonce'] as String);
      final mac = base64Decode(data['mac'] as String);
      if (salt.length != 16 || nonce.length != 12 || mac.length != 16) throw const FormatException();
      final key = await _kdf.deriveKey(secretKey: SecretKey(utf8.encode(passphrase)), nonce: salt);
      final plain = await _cipher.decrypt(SecretBox(base64Decode(data['ciphertext'] as String), nonce: nonce, mac: Mac(mac)),
        secretKey: key, aad: utf8.encode('LifeOS backup v1'));
      return Map<String, Object?>.from(jsonDecode(utf8.decode(plain)) as Map);
    } catch (_) { throw const DomainFailure('backup_invalid'); }
  }
}

Future<typed.Uint8List> encryptBackupWorker(Map<String, Object?> input) => BackupService().encrypt(
  input['snapshot'] as Map<String, Object?>, input['password'] as String);
Future<Map<String, Object?>> decryptBackupWorker(Map<String, Object?> input) => BackupService().decrypt(
  input['bytes'] as typed.Uint8List, input['password'] as String);
