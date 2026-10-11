import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/domain/financial_period.dart';
void main() {
  Record money(String id, EntryKind kind, String date, int amount, {String currency = 'RUB'}) => Record(id: id, kind: kind, text: '',
    createdAt: DateTime(2026), amountMinor: amount, currency: Currency.fromCode(currency), date: date);
  test('inclusive calendar period and per-currency totals recalculate from current records', () {
    final period = FinancialPeriod(DateTime(2026,9,30),DateTime(2026,10,2));
    final rows = [money('i',EntryKind.income,'2026-09-30',10001),money('e',EntryKind.expense,'2026-10-02',101),
      money('other',EntryKind.income,'2026-10-01',99999,currency: 'USD'),money('outside',EntryKind.expense,'2026-10-03',888)];
    expect(period.records(rows,currency: 'RUB').map((r) => r.id), ['i','e']);
    expect(period.total(rows,EntryKind.income,'RUB') - period.total(rows,EntryKind.expense,'RUB'), BigInt.from(9900));
    rows[1] = money('e',EntryKind.expense,'2026-10-02',1000);
    expect(period.total(rows,EntryKind.expense,'RUB'), BigInt.from(1000));
    rows.removeAt(1);
    expect(period.total(rows,EntryKind.expense,'RUB'), BigInt.zero);
  });
  test('large valid transaction sums never overflow signed 64-bit integers', () {
    final period = FinancialPeriod(DateTime(2026,1,1),DateTime(2026,12,31));
    final rows = List.generate(10000,(i) => money('$i',EntryKind.income,'2026-10-11',999999999999999));
    expect(period.total(rows,EntryKind.income,'RUB'),BigInt.parse('9999999999999990000'));
  });
}
