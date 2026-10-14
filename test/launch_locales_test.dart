import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/intl.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/preference_choices.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late PackCatalog catalog;
  setUpAll(() async {
    catalog = await PackCatalog.load();
  });
  test('every launch pack has exactly the versioned schema and formats', () {
    final launch =
        jsonDecode(File('tool/launch_locales.json').readAsStringSync()) as Map;
    expect(catalog.packs.keys.toSet(), launch.keys.toSet());
    for (final pack in catalog.packs.values) {
      expect(
        pack.strings.keys.toSet(),
        catalog.packs['en']!.strings.keys.toSet(),
      );
      for (final count in [0, 1, 2, 5, 11, 21, 100]) {
        expect(pack.count('record_count', count), contains('$count'));
        expect(pack.count('record_count', count), isNot(contains('{count}')));
      }
      expect(
        NumberFormat.decimalPattern(pack.locale.languageCode).format(12345.67),
        isNotEmpty,
      );
      expect(
        DateFormat.yMMMMd(pack.locale.toString())
            .format(DateTime(2026, 10, 14)),
        isNotEmpty,
      );
      expect(currencyChoices(pack)['RUB'], contains(pack.t('currency_RUB')));
    }
    expect(formatChoices(catalog, 'tg').length, 15);
    expect(catalog.resolve('uz_Cyrl').tag, 'uz-Cyrl');
    expect(catalog.resolve('uz_Cyrl_UZ').tag, 'uz-Cyrl');
    expect(catalog.resolve('uz-Latn-UZ').tag, 'uz-Latn');
    expect(catalog.resolve('UZ_latn_uz').tag, 'uz-Latn');
    expect(catalog.resolve('uz-UZ').tag, 'uz-Latn');
    expect(catalog.resolve('uz').tag, 'uz-Latn');
    expect(catalog.resolve('unknown').tag, 'en');
    expect(catalog.packs['ru']!.count('record_count', 21), '21 запись');
    expect(catalog.packs['uk']!.count('record_count', 5), '5 записів');
  });
  test(
    'Tajik and Uzbek Cyrillic have their own calendar and dialog text',
    () async {
      for (final tag in ['tg', 'uz-Cyrl']) {
        final pack = catalog.packs[tag]!;
        final material = await const MaterialFallbackDelegate().load(
          pack.locale,
        );
        expect(material.cancelButtonLabel, isNot('Cancel'));
        expect(material.selectYearSemanticsLabel, isNot('Select year'));
        expect(
          material.formatMonthYear(DateTime(2026, 10)),
          contains('октябр'),
        );
        expect(
          material.formatCompactDate(DateTime(2026, 10, 14)),
          contains('2026'),
        );
      }
      final russian = await const MaterialFallbackDelegate(formatLocale: 'en')
          .load(const Locale('ru'));
      expect(russian.cancelButtonLabel, 'Отмена');
      expect(russian.formatCompactDate(DateTime(2026, 10, 14)), '10/14/2026');
    },
  );
}
