import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/services/backup_service.dart';
import 'package:lifeos/domain/models.dart';
void main() {
  test('portable authenticated encryption round trips, randomizes, rejects tampering and wrong password', () async {
    final service = BackupService();
    final snapshot = <String,Object?>{'schemaVersion': 3, 'tables': {'notes': [{'body': 'Секретная заметка'}]}};
    const password = 'test long password 2026';
    final first = await service.encrypt(snapshot, password);
    final second = await service.encrypt(snapshot, password);
    expect(first, isNot(orderedEquals(second)));
    expect(utf8.decode(first), isNot(contains('Секретная заметка')));
    expect(await service.decrypt(first, password), snapshot);
    await expectLater(service.decrypt(first, 'a different password'), throwsA(isA<DomainFailure>()));
    final envelope = jsonDecode(utf8.decode(first)) as Map<String,dynamic>;
    final ciphertext = base64Decode(envelope['ciphertext'] as String); ciphertext[0] ^= 1;
    envelope['ciphertext'] = base64Encode(ciphertext);
    await expectLater(service.decrypt(Uint8List.fromList(utf8.encode(jsonEncode(envelope))), password), throwsA(isA<DomainFailure>()));
    envelope['iterations'] = 999999999;
    await expectLater(service.decrypt(Uint8List.fromList(utf8.encode(jsonEncode(envelope))), password), throwsA(isA<DomainFailure>()));
    await expectLater(service.encrypt(snapshot, 'short'), throwsA(isA<DomainFailure>()));
  }, timeout: const Timeout(Duration(minutes: 2)));
}
