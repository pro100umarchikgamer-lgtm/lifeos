import 'models.dart';

class FinancialPeriod {
  FinancialPeriod(this.start, this.end) {
    if (end.isBefore(start)) throw const DomainFailure('invalid_date');
  }
  final DateTime start, end;
  bool contains(Record record) => record.amountMinor != null && record.date != null &&
    record.date!.compareTo(dateOnly(start)) >= 0 && record.date!.compareTo(dateOnly(end)) <= 0;
  List<Record> records(List<Record> source, {String? currency}) => source.where((r) => contains(r) &&
    (currency == null || r.currency?.code == currency)).toList();
  BigInt total(List<Record> source, EntryKind kind, String currency) => records(source, currency: currency)
    .where((r) => r.kind == kind).fold(BigInt.zero, (sum, r) => sum + BigInt.from(r.amountMinor!));
}
