import 'package:intl/intl.dart';

import '../domain/models.dart';

// Presentation only: keep integer minor units, never convert money to double.
String formatMoney(Currency currency, Object minor, {required String locale}) {
  final units = switch (minor) { int() => BigInt.from(minor), BigInt() => minor, _ => throw ArgumentError.value(minor, 'minor') };
  final symbols = NumberFormat.decimalPattern(locale).symbols;
  final text = units.abs().toString().padLeft(currency.digits + 1, '0');
  final split = text.length - currency.digits;
  final whole = text.substring(0, split).replaceAllMapped(
    RegExp(r'(\d)(?=(\d{3})+$)'), (match) => '${match[1]}${symbols.GROUP_SEP}');
  final fraction = text.substring(split);
  final amount = currency.digits > 0 && RegExp(r'[1-9]').hasMatch(fraction)
    ? '$whole${symbols.DECIMAL_SEP}$fraction' : whole;
  final formatter = NumberFormat.simpleCurrency(
    locale: locale, name: currency.code, decimalDigits: 0);
  final template = formatter.format(units.isNegative ? -1 : 0);
  return template.replaceFirst(units.isNegative ? '1' : '0', amount)
    .replaceAll(' ', ' ').replaceAll(' ', ' ');
}

// Convert only the bounded presentation ratio, never monetary units, to double.
String formatShare(BigInt part, BigInt total, {required String locale}) {
  final formatter = NumberFormat.percentPattern(locale)
    ..minimumFractionDigits = 1
    ..maximumFractionDigits = 1;
  final tenths = total == BigInt.zero
      ? BigInt.zero
      : part * BigInt.from(1000) ~/ total;
  return formatter.format(tenths.toInt() / 1000);
}
