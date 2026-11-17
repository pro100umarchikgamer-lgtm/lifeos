import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../domain/models.dart';
import '../localization/language_pack.dart';
import '../sync/contracts.dart';
import 'money_format.dart';
import 'settings_surfaces.dart';

String referenceMoney(LanguagePack pack, Object? amount, String? currency) {
  if (amount is! int) return pack.t('read_failed');
  if (currency != null) {
    try {
      return formatMoney(Currency.fromCode(currency), BigInt.from(amount),
          locale: pack.locale.languageCode);
    } on DomainFailure {
      // Keep the exact integer visible if a live currency cannot be decoded.
    } on FormatException {
      /* Preserve the exact recorded integer if metadata is unavailable. */
    }
  }
  return '${pack.t('privacy_currency_unavailable')} $amount';
}

class FamilyTransferReferencePage extends StatelessWidget {
  const FamilyTransferReferencePage(
      {super.key,
      required this.pack,
      required this.record,
      required this.fromCurrency,
      required this.toCurrency});
  final LanguagePack pack;
  final Json record;
  final String? fromCurrency, toCurrency;
  @override
  Widget build(BuildContext context) {
    final data = object(record['data']);
    final parsed = DateTime.tryParse(data['date'] as String? ?? '');
    return Scaffold(
      appBar: settingsAppBar(context, pack.t('family_kind_transfer')),
      body: SafeArea(
          child: ListView(padding: settingsPagePadding(context), children: [
        Text(pack.t('privacy_reference_transfer'),
            style:
                Theme.of(context).textTheme.bodyLarge?.copyWith(height: 1.5)),
        const SizedBox(height: 24),
        SettingsGroup(children: [
          SettingsRow(
              title: pack.t('amount'),
              subtitle: referenceMoney(pack, data['sent_minor'], fromCurrency),
              icon: Icons.call_made_rounded),
          SettingsRow(
              title: pack.t('family_received'),
              subtitle:
                  referenceMoney(pack, data['received_minor'], toCurrency),
              icon: Icons.call_received_rounded),
          SettingsRow(
              title: pack.t('family_date'),
              subtitle: parsed == null
                  ? (data['date'] as String? ?? '')
                  : DateFormat.yMMMd(pack.locale.languageCode).format(parsed),
              icon: Icons.calendar_today_outlined),
        ]),
      ])),
    );
  }
}
