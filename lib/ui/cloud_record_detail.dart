import 'package:flutter/material.dart';
import '../domain/family_finance.dart';
import '../domain/models.dart';
import '../localization/language_pack.dart';
import '../sync/contracts.dart';
import '../sync/controller.dart';
import '../sync/record_projection.dart';
import 'design.dart';
import 'family.dart';
import 'family_financial_reference.dart';
import 'money_format.dart';
import 'settings_surfaces.dart';

String? cloudSpaceKind(FamilyController controller) =>
    controller.spaces
        .where((s) => s['id'] == controller.workspace)
        .firstOrNull?['kind'] as String? ??
    controller.roster?['space']?['kind'] as String?;

bool cloudTaskCompleted(Json row, FamilyController controller) {
  if (controller.roster?['space']?['role'] == 'child') {
    final id = controller.roster?['space']?['profile_id'];
    final marks = (row['progress'] as List? ?? []).map(object);
    return marks
            .where((m) => m['profile_id'] == id)
            .firstOrNull?['completed'] ==
        1;
  }
  return row['data']['completed'] == 1;
}

String cloudCategoryLabel(LanguagePack pack, String category) =>
    pack.t(switch (category) {
      'transport' => 'purpose_transport',
      'shopping' => 'checklist_shopping',
      'transfers' => 'module_transfers',
      'other' => 'purpose_other',
      'food' ||
      'housing' ||
      'health' ||
      'leisure' ||
      'education' =>
        'cloud_category_$category',
      _ => 'insight_uncategorized',
    });

String cloudRecordTitle(Json row, LanguagePack pack) => (row['data']['title'] ??
        row['data']['name'] ??
        row['data']['label'] ??
        row['data']['body'] ??
        pack.t('family_kind_${row['kind']}'))
    .toString();

IconData cloudRecordIcon(String kind) => switch (kind) {
      'account' => Icons.account_balance_wallet_outlined,
      'budget' => Icons.savings_outlined,
      'task' => Icons.check_circle_outline,
      'event' => Icons.event_outlined,
      'shopping' => Icons.shopping_bag_outlined,
      'note' => Icons.description_outlined,
      _ => Icons.receipt_long_outlined,
    };

Future<void> openCloudRecord(BuildContext context, FamilyController controller,
        LanguagePack pack, String id,
        {String? region, DateTime Function()? clock}) =>
    Navigator.push<void>(
        context,
        MaterialPageRoute(
            builder: (_) => CloudRecordDetail(
                controller: controller,
                pack: pack,
                id: id,
                region: region,
                clock: clock)));

/// Reads only the current authorized mirror; a route never owns a record snapshot.
class CloudRecordDetail extends StatefulWidget {
  const CloudRecordDetail(
      {super.key,
      required this.controller,
      required this.pack,
      required this.id,
      this.region,
      this.clock});
  final FamilyController controller;
  final LanguagePack pack;
  final String id;
  final String? region;
  final DateTime Function()? clock;
  @override
  State<CloudRecordDetail> createState() => _CloudRecordDetailState();
}

class _CloudRecordDetailState extends State<CloudRecordDetail> {
  late final AccountPrincipal principal = f.capturePrincipal();
  late final String? workspace = f.workspace;
  FamilyController get f => widget.controller;
  String t(String key) => widget.pack.t(key);
  Json? get record => f.isCurrentPrincipal(principal) &&
          f.workspace == workspace &&
          f.roster != null &&
          !{'workspace_forbidden', 'profile_forbidden'}.contains(f.error)
      ? f.records
          .where((r) => r['id'] == widget.id && isActiveSyncRecord(r))
          .firstOrNull
      : null;

  String money(Object? minor, String? code) => minor is int && code != null
      ? formatMoney(Currency.fromCode(code), minor,
          locale: widget.region ?? widget.pack.tag)
      : t('privacy_currency_unavailable');
  String accountName(Object? id) =>
      f.records
          .where((r) =>
              r['id'] == id && r['kind'] == 'account' && isActiveSyncRecord(r))
          .firstOrNull?['data']?['name'] as String? ??
      t('family_none');

  Future<void> edit() async {
    final latest = record;
    if (latest == null ||
        latest['editable'] == false ||
        f.busy ||
        f.transferUsesErasedAccount(latest)) {
      return;
    }
    await Navigator.push<void>(
        context,
        MaterialPageRoute(
            builder: (_) => FamilyRecordEditor(
                controller: f, pack: widget.pack, record: latest)));
    if (mounted) setState(() {});
  }

  List<Widget> content(Json row) {
    final d = object(row['data']), kind = row['kind'] as String;
    final code = d['currency'] as String?;
    Widget fact(String label, Object? value,
            [IconData icon = Icons.info_outline]) =>
        SettingsRow(
            title: t(label), subtitle: value?.toString() ?? '—', icon: icon);
    Widget hero(String value, {String? caption}) => LifeCard(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (caption != null)
            Text(caption, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 6),
          SelectableText(value,
              style: Theme.of(context).textTheme.headlineMedium),
        ]));
    final fields = <Widget>[];
    final result = <Widget>[];
    if (kind == 'note') {
      result.add(SelectableText(d['body'] as String,
          style:
              Theme.of(context).textTheme.bodyLarge?.copyWith(height: 1.65)));
    } else if (kind == 'account') {
      result.add(hero(
          formatMoney(Currency.fromCode(code!),
              const FamilyFinance().accountBalance(row, f.records),
              locale: widget.region ?? widget.pack.tag),
          caption: t('current_balance')));
      fields.add(fact('opening_balance', money(d['opening_minor'], code)));
      fields.add(fact('currency', code));
    } else if (kind == 'transaction' || kind == 'request') {
      final sign =
          kind == 'transaction' ? (d['kind'] == 'income' ? '+ ' : '− ') : '';
      result.add(hero(sign + money(d['amount_minor'], code)));
      if (d['date'] != null) {
        fields
            .add(fact('family_date', d['date'], Icons.calendar_today_outlined));
      }
      if (d['label'] != null && d['label'] != '') {
        fields.add(fact('label_optional', d['label']));
      }
      if (kind == 'transaction') {
        fields.add(fact('family_account_select', accountName(d['account_id'])));
        if (d['category'] != null) {
          fields.add(fact('category',
              cloudCategoryLabel(widget.pack, d['category'] as String)));
        }
      } else {
        fields.add(fact(
            'status',
            t(d['state'] == 'fulfilled'
                ? 'complete'
                : 'family_review_pending')));
      }
    } else if (kind == 'transfer') {
      fields.addAll([
        fact('family_from', accountName(d['from_id'])),
        fact('amount',
            money(d['sent_minor'], f.accountCurrency(d['from_id'] as String))),
        fact('family_to', accountName(d['to_id'])),
        fact(
            'family_received',
            money(
                d['received_minor'], f.accountCurrency(d['to_id'] as String))),
        fact('family_date', d['date']),
      ]);
    } else if (kind == 'budget') {
      result.add(hero(
          formatMoney(
              Currency.fromCode(code!),
              const FamilyFinance().budgetRemaining(
                  row, f.records, widget.clock?.call() ?? DateTime.now()),
              locale: widget.region ?? widget.pack.tag),
          caption: t('remaining')));
      fields.addAll([
        fact('amount', money(d['limit_minor'], code)),
        fact('family_period', t('family_${d['period']}')),
        fact('family_start', d['start_on']),
        if (d['end_on'] != null) fact('family_end', d['end_on']),
        fact('family_rollover', t('family_roll_${d['rollover']}')),
      ]);
    } else if (kind == 'task') {
      fields.addAll([
        fact('status',
            t(cloudTaskCompleted(row, f) ? 'completed' : 'open_tasks')),
        fact('family_assignment', t('family_${d['assignment']}')),
        fact('family_review_required',
            t(d['review'] == 1 ? 'state_yes' : 'state_no'))
      ]);
    } else if (kind == 'event') {
      final schedule = object(d['schedule']);
      fields.addAll([
        fact('family_date', schedule['localStart']),
        fact('family_timezone', schedule['timezone']),
        fact('all_day',
            t(schedule['allDay'] == true ? 'state_yes' : 'state_no')),
        fact('repeat', t('repeat_${schedule['repeat']}')),
        if (schedule['repeat'] != 'none')
          fact('repeat_interval', schedule['interval']),
        if (schedule['until'] != null) fact('repeat_until', schedule['until'])
      ]);
    } else if (kind == 'shopping') {
      for (final raw in d['items'] as List? ?? []) {
        final item = object(raw);
        fields.add(SettingsRow(
            title: item['name'] as String,
            subtitle: item['quantity'] as String?,
            icon: item['completed'] == true
                ? Icons.check_circle_outline
                : Icons.radio_button_unchecked));
      }
    }
    if (fields.isNotEmpty) {
      result.addAll(
          [const SizedBox(height: 20), SettingsGroup(children: fields)]);
    }
    if (kind == 'account') {
      final related = f.records
          .where((r) =>
              isActiveSyncRecord(r) &&
              (r['kind'] == 'transaction' &&
                      r['data']['account_id'] == row['id'] ||
                  r['kind'] == 'transfer' &&
                      (r['data']['from_id'] == row['id'] ||
                          r['data']['to_id'] == row['id'])))
          .toList()
        ..sort((a, b) => (b['data']['date'] as String)
            .compareTo(a['data']['date'] as String));
      result.addAll([
        const SizedBox(height: 24),
        Text(t('cloud_operations'),
            style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 12),
        if (related.isEmpty)
          Text(t('offline_empty'))
        else
          SettingsGroup(children: [
            for (final movement in related)
              SettingsRow(
                  icon: cloudRecordIcon(movement['kind'] as String),
                  title: cloudRecordTitle(movement, widget.pack),
                  subtitle: movement['kind'] == 'transaction'
                      ? '${movement['data']['kind'] == 'income' ? '+' : '−'} ${money(movement['data']['amount_minor'], movement['data']['currency'] as String)} · ${movement['data']['date']}'
                      : '${money(movement['data']['sent_minor'], f.accountCurrency(movement['data']['from_id'] as String))} → ${money(movement['data']['received_minor'], f.accountCurrency(movement['data']['to_id'] as String))} · ${movement['data']['date']}',
                  onTap: () => openCloudRecord(
                      context, f, widget.pack, movement['id'] as String,
                      region: widget.region, clock: widget.clock)),
          ])
      ]);
    }
    return result;
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
      listenable: f,
      builder: (context, _) {
        final row = record;
        if (row != null && f.transferUsesErasedAccount(row)) {
          return FamilyTransferReferencePage(
              pack: widget.pack,
              record: row,
              fromCurrency: f.accountCurrency(row['data']['from_id'] as String),
              toCurrency: f.accountCurrency(row['data']['to_id'] as String));
        }
        return Scaffold(
          appBar: settingsAppBar(context,
              row == null ? t('details') : t('family_kind_${row['kind']}')),
          bottomNavigationBar: row == null || row['editable'] == false
              ? null
              : SafeArea(
                  child: Padding(
                      padding: settingsPagePadding(context),
                      child: FilledButton.icon(
                          key: const Key('cloud_record_edit'),
                          onPressed: f.busy ? null : edit,
                          icon: const Icon(Icons.edit_outlined),
                          label: Text(t('edit'))))),
          body: SafeArea(
              child: row == null
                  ? Center(child: Text(t('privacy_record_unavailable')))
                  : ListView(padding: settingsPagePadding(context), children: [
                      if (row['kind'] != 'note') ...[
                        SelectableText(cloudRecordTitle(row, widget.pack),
                            style: Theme.of(context).textTheme.headlineSmall),
                        const SizedBox(height: 20),
                      ],
                      ...content(row),
                    ])),
        );
      });
}
