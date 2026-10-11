import 'package:intl/intl.dart';

import '../domain/models.dart';

// Presentation only: keep integer minor units, never convert money to double.
String formatMoney(Currency currency, int minor, {required String locale}) {
  final symbols = NumberFormat.decimalPattern(locale).symbols;
  final text = minor.abs().toString().padLeft(currency.digits + 1, '0');
  final split = text.length - currency.digits;
  final whole = text.substring(0, split).replaceAllMapped(
    RegExp(r'(\d)(?=(\d{3})+$)'), (match) => '${match[1]}${symbols.GROUP_SEP}');
  final fraction = text.substring(split);
  final amount = currency.digits > 0 && RegExp(r'[1-9]').hasMatch(fraction)
    ? '$whole${symbols.DECIMAL_SEP}$fraction' : whole;
  final formatter = NumberFormat.simpleCurrency(
    locale: locale, name: currency.code, decimalDigits: 0);
  final template = formatter.format(minor < 0 ? -1 : 0);
  return template.replaceFirst(minor < 0 ? '1' : '0', amount)
    .replaceAll(' ', ' ').replaceAll(' ', ' ');
}
