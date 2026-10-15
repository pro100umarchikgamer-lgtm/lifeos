import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/domain/financial_period.dart';
import 'package:lifeos/domain/financial_insights.dart';

void main() {
  Record money(
    String id,
    EntryKind kind,
    String date,
    int amount, {
    String currency = 'RUB',
  }) => Record(
    id: id,
    kind: kind,
    text: '',
    createdAt: DateTime(2026),
    amountMinor: amount,
    currency: Currency.fromCode(currency),
    date: date,
  );
  test('inclusive calendar period and per-currency totals recalculate from current records', () {
    final period = FinancialPeriod(
      DateTime(2026, 9, 30),
      DateTime(2026, 10, 2),
    );
    final rows = [
      money('i', EntryKind.income, '2026-09-30', 10001),
      money('e', EntryKind.expense, '2026-10-02', 101),
      money('other', EntryKind.income, '2026-10-01', 99999, currency: 'USD'),
      money('outside', EntryKind.expense, '2026-10-03', 888),
    ];
    expect(period.records(rows, currency: 'RUB').map((r) => r.id), ['i', 'e']);
    expect(
      period.total(rows, EntryKind.income, 'RUB') -
          period.total(rows, EntryKind.expense, 'RUB'),
      BigInt.from(9900),
    );
    rows[1] = money('e', EntryKind.expense, '2026-10-02', 1000);
    expect(period.total(rows, EntryKind.expense, 'RUB'), BigInt.from(1000));
    rows.removeAt(1);
    expect(period.total(rows, EntryKind.expense, 'RUB'), BigInt.zero);
  });
  test(
    'large valid transaction sums never overflow signed 64-bit integers',
    () {
      final period = FinancialPeriod(
        DateTime(2026, 1, 1),
        DateTime(2026, 12, 31),
      );
      final rows = List.generate(
        10000,
        (i) => money('$i', EntryKind.income, '2026-10-11', 999999999999999),
      );
      expect(
        period.total(rows, EntryKind.income, 'RUB'),
        BigInt.parse('9999999999999990000'),
      );
    },
  );
  test('insights preserve exact amounts across grains, splits, currencies and transfers', () {
    final rows = [
      money('i', EntryKind.income, '2026-09-30', 10001),
      money('e', EntryKind.expense, '2026-10-02', 101),
      money('usd', EntryKind.expense, '2026-10-02', 99999, currency: 'USD'),
    ];
    final data = FinancialInsights(
      rows,
      FinancialPeriod(DateTime(2026, 9, 30), DateTime(2026, 10, 2)),
      'RUB',
      [
        {'id': 'a', 'currency': 'RUB', 'opening_minor': 5000},
        {'id': 'b', 'currency': 'RUB', 'opening_minor': 1000},
        {'id': 'c', 'currency': 'USD', 'opening_minor': 999999},
      ],
      [
        {
          'from_account_id': 'a',
          'to_account_id': 'b',
          'sent_minor': 900,
          'received_minor': 900,
        },
      ],
      [
        {'transaction_id': 'e', 'category_id': 'food', 'amount_minor': 100},
        {'transaction_id': 'e', 'category_id': 'home', 'amount_minor': 1},
      ],
    );
    expect(data.balance, BigInt.from(6000));
    expect(data.income, BigInt.from(10001));
    expect(data.expense, BigInt.from(101));
    expect(data.categories, {'food': BigInt.from(100), 'home': BigInt.one});
    expect(data.categoryRecords('food').map((r) => r.id), ['e']);
    for (final grain in ChartGrain.values) {
      final buckets = data.buckets(grain);
      expect(
        buckets.fold(BigInt.zero, (sum, b) => sum + b.income),
        data.income,
      );
      expect(
        buckets.fold(BigInt.zero, (sum, b) => sum + b.expense),
        data.expense,
      );
    }
    expect(data.buckets(ChartGrain.week).first.date, DateTime.utc(2026, 9, 28));
    expect(data.buckets(ChartGrain.month).map((b) => b.date), [
      DateTime.utc(2026, 9),
      DateTime.utc(2026, 10),
    ]);
    final large = FinancialInsights(
      List.generate(
        10000,
        (i) => money('$i', EntryKind.expense, '2026-10-02', 999999999999999),
      ),
      data.period,
      'RUB',
      [],
      [],
      [],
    );
    expect(large.expense, BigInt.parse('9999999999999990000'));
    expect(large.categories[''], large.expense);
    final empty = FinancialInsights([], data.period, 'RUB', [], [], []);
    expect(empty.categories, isEmpty);
    expect(empty.balance, BigInt.zero);
    expect(empty.buckets(ChartGrain.day).length, 3);
  });
}
