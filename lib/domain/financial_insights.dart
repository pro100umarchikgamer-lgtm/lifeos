import 'models.dart';
import 'financial_period.dart';
import 'finance_engine.dart';

enum ChartGrain { day, week, month }

class CashBucket {
  CashBucket(this.date);
  final DateTime date;
  BigInt income = BigInt.zero, expense = BigInt.zero;
}

/// Analytics never converts currencies or includes transfers as consumption.
/// Plotting ratios are separate from the exact integer ledger and labels.
class FinancialInsights {
  FinancialInsights(
    this.source,
    this.period,
    this.currency,
    this.accounts,
    this.transfers,
    this.splits,
  );
  final List<Record> source;
  final FinancialPeriod period;
  final String currency;
  final List<Map<String, Object?>> accounts, transfers, splits;
  List<Record> get records => period.records(source, currency: currency);
  BigInt get income => period.total(source, EntryKind.income, currency);
  BigInt get expense => period.total(source, EntryKind.expense, currency);

  /// Actual balances of accounts; unassigned ledger records are not bank funds.
  BigInt get balance => accounts
      .where((a) => a['currency'] == currency && a['deleted_at'] == null)
      .fold(
        BigInt.zero,
        (sum, a) =>
            sum + const FinanceEngine().accountBalance(a, source, transfers),
      );
  bool get hasAccounts =>
      accounts.any((a) => a['currency'] == currency && a['deleted_at'] == null);
  List<CashBucket> buckets(ChartGrain grain) {
    DateTime key(DateTime d) => switch (grain) {
      ChartGrain.day => DateTime.utc(d.year, d.month, d.day),
      ChartGrain.week => DateTime.utc(d.year, d.month, d.day - (d.weekday - 1)),
      ChartGrain.month => DateTime.utc(d.year, d.month),
    };
    final result = <DateTime, CashBucket>{};
    var cursor = key(period.start);
    final end = key(period.end);
    while (!cursor.isAfter(end)) {
      result[cursor] = CashBucket(cursor);
      cursor = grain == ChartGrain.month
          ? DateTime.utc(cursor.year, cursor.month + 1)
          : cursor.add(Duration(days: grain == ChartGrain.week ? 7 : 1));
    }
    for (final r in records) {
      final b = result[key(DateTime.parse(r.date!))]!;
      if (r.kind == EntryKind.income) b.income += BigInt.from(r.amountMinor!);
      if (r.kind == EntryKind.expense) b.expense += BigInt.from(r.amountMinor!);
    }
    return result.values.toList();
  }

  Map<String, BigInt> get categories {
    final result = <String, BigInt>{};
    final grouped = <String, List<Map<String, Object?>>>{};
    for (final part in splits) {
      grouped.putIfAbsent(part['transaction_id'] as String, () => []).add(part);
    }
    void add(String? id, BigInt amount) {
      final key = id ?? '';
      result[key] = (result[key] ?? BigInt.zero) + amount;
    }

    for (final r in records.where((r) => r.kind == EntryKind.expense)) {
      final parts = grouped[r.id];
      if (parts == null || parts.isEmpty) {
        add(r.categoryId, BigInt.from(r.amountMinor!));
      } else {
        for (final part in parts) {
          add(
            part['category_id'] as String?,
            BigInt.from(part['amount_minor'] as int),
          );
        }
      }
    }
    return result;
  }

  List<Record> categoryRecords(String id) => records
      .where(
        (r) =>
            r.kind == EntryKind.expense &&
            (splits.any((s) => s['transaction_id'] == r.id)
                ? splits.any(
                    (s) =>
                        s['transaction_id'] == r.id &&
                        (s['category_id'] ?? '') == id,
                  )
                : (r.categoryId ?? '') == id),
      )
      .toList();
}
