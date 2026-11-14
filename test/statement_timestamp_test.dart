import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/domain/statement_import.dart';
import 'package:lifeos/domain/statement_detection.dart';

void main() {
  test('timestamp bank export prefers operation date over posting date', () {
    final table = StatementTable.checked([
      [
        'transaction_id',
        'transaction_datetime',
        'posting_datetime',
        'amount',
        'currency',
        'card_amount',
        'description'
      ],
      [
        'sample',
        '2026-11-10 19:00:00',
        '2026-11-11 03:56:00',
        '-50.00',
        'RUB',
        '-500.00',
        'Purchase'
      ],
    ]);
    final found = StatementDetection.detect(table, 'USD');
    expect(found, isNotNull);
    expect(found!.mapping.date, 1);
    final item = found.mapping.normalize(table.rows[1]);
    expect(item.date, '2026-11-10');
    expect(item.amountMinor, 5000);
    expect(item.currency, 'RUB');
    expect(item.label, 'Purchase');
    expect(item.kind, EntryKind.expense);
  });
}
