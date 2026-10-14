import 'package:intl/intl.dart';

import '../localization/language_pack.dart';

const primaryCurrencies = [
  'USD',
  'EUR',
  'RUB',
  'KZT',
  'UZS',
  'UAH',
  'GBP',
  'GEL',
  'AZN',
  'AMD',
  'TJS',
  'KGS',
  'JPY',
  'CHF',
  'CNY',
  'AED',
];
Map<String, String> currencyChoices(LanguagePack pack, {String? current}) => {
  for (final code in {...primaryCurrencies, if (current != null) current})
    code:
        '${pack.strings['currency_$code'] ?? code} · $code · ${NumberFormat.simpleCurrency(name: code).currencySymbol}',
};
Map<String, String> formatChoices(PackCatalog catalog, String current) => {
  for (final code in {
    ...catalog.packs.values.map((p) => p.locale.languageCode),
    current,
  })
    code:
        '${catalog.resolve(code).name}\n${NumberFormat.decimalPattern(code).format(12345.67)} · ${DateFormat.yMd(code).format(DateTime(2026, 10, 14))}',
};

// Preserve legacy/custom three-letter currencies without requiring a novice
// to type codes in the money form. Exact-code search offers the choice.
Map<String, String> currencyQueryChoice(LanguagePack pack, String query) {
  final code = query.trim().toUpperCase();
  if (!RegExp(r'^[A-Z]{3}$').hasMatch(code)) {
    return {};
  }
  if (primaryCurrencies.contains(code)) {
    return {};
  }
  final symbol = NumberFormat.simpleCurrency(name: code).currencySymbol;
  return {
    code:
        pack.strings['currency_$code'] ??
        '${pack.t('currency')}: $code${symbol == code ? '' : ' · $symbol'}',
  };
}
