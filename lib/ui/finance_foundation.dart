import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../app_controller.dart';
import '../domain/models.dart';
import '../domain/finance_engine.dart';
import 'design.dart';
import 'entry_sheet.dart';
import 'selection.dart';
import 'preference_choices.dart';
import 'calendar.dart';
import 'money_format.dart';
import 'wealth.dart';
import 'statement_import.dart';

int signedMinor(String raw, String code) {
  final text = raw.trim(), currency = Currency.fromCode(code);
  if (RegExp(r'^[-+]?0(?:[.,]0+)?$').hasMatch(text)) return 0;
  return text.startsWith('-')
      ? -currency.parse(text.substring(1))
      : currency.parse(text.startsWith('+') ? text.substring(1) : text);
}

String minorText(int minor, String code) {
  final c = Currency.fromCode(code),
      text = minor.abs().toString().padLeft(c.digits + 1, '0');
  return '${minor < 0 ? '-' : ''}${c.digits == 0 ? text : '${text.substring(0, text.length - c.digits)}.${text.substring(text.length - c.digits)}'}';
}

class FinanceFoundation extends StatefulWidget {
  const FinanceFoundation({super.key, required this.controller});
  final AppController controller;
  @override
  State<FinanceFoundation> createState() => _FinanceFoundationState();
}

class _FinanceFoundationState extends State<FinanceFoundation> {
  AppController get c => widget.controller;
  OfflineTable table = OfflineTable.accounts;
  static const destinations = [
    OfflineTable.accounts,
    OfflineTable.transfers,
    OfflineTable.plannedPayments,
    OfflineTable.budgets,
    OfflineTable.categories,
    OfflineTable.importBatches,
  ];
  bool busy = false;
  Future<void> edit([Map<String, Object?>? row]) async {
    if (table == OfflineTable.importBatches) return;
    await Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => Scaffold(
          resizeToAvoidBottomInset: false,
          body: SafeArea(
            child: FinanceEditor(controller: c, table: table, row: row),
          ),
        ),
      ),
    );
  }

  Future<void> change(AppAction action) async {
    if (busy) return;
    setState(() => busy = true);
    try {
      await c.execute(action);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              c.pack.t(e is DomainFailure ? e.key : 'change_failed'),
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  String summary(Map<String, Object?> row) {
    if (table == OfflineTable.importBatches) {
      return '${row["row_count"]} · ${MaterialLocalizations.of(context).formatMediumDate(DateTime.parse(row["created_at"] as String))}';
    }
    const f = FinanceEngine();
    if (table == OfflineTable.accounts) {
      return formatMoney(
        Currency.fromCode(row['currency'] as String),
        f.accountBalance(
          row,
          c.records,
          c.offline[OfflineTable.transfers] ?? [],
        ),
        locale: c.region,
      );
    }
    if (table == OfflineTable.transfers) {
      String account(String id) =>
          (c.offline[OfflineTable.accounts] ?? [])
                  .where((a) => a['id'] == id)
                  .firstOrNull?['name']
              as String? ??
          id;
      return '${account(row['from_account_id'] as String)} → ${account(row['to_account_id'] as String)}';
    }
    if (table == OfflineTable.budgets) {
      return '${c.pack.t('remaining')}: ${formatMoney(Currency.fromCode(row['currency'] as String), f.budgetRemaining(row, c.now, c.records, c.allocations, c.offline[OfflineTable.categories] ?? []), locale: c.region)}';
    }
    if (table == OfflineTable.plannedPayments) {
      return '${c.pack.t('not_actual')}: ${formatMoney(Currency.fromCode(row['currency'] as String), row['amount_minor'] as int, locale: c.region)}';
    }
    return c.pack.t(row['archived'] == 1 ? 'archived' : 'category');
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: c,
    builder: (context, _) {
      final rows = c.offline[table] ?? [];
      return Scaffold(
        appBar: AppBar(title: Text(c.pack.t('financial_foundation'))),
        body: SafeArea(
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                child: LifeSelect<OfflineTable>(
                  label: c.pack.t('finances'),
                  showLabel: false,
                  dialog: true,
                  value: table,
                  choices: {
                    for (final t in destinations)
                      t: c.pack.t('module_${t.name}'),
                  },
                  onChanged: (v) => setState(() => table = v),
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
                child: Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  children: [
                    TextButton.icon(
                      onPressed: () => Navigator.push<void>(
                        context,
                        MaterialPageRoute(
                          builder: (_) => StatementImportPage(controller: c),
                        ),
                      ),
                      icon: const Icon(Icons.file_open_outlined),
                      label: Text(c.pack.t('import_file')),
                    ),
                    TextButton.icon(
                      onPressed: () => Navigator.push<void>(
                        context,
                        MaterialPageRoute(
                          builder: (_) => WealthPage(controller: c),
                        ),
                      ),
                      icon: const Icon(Icons.savings_outlined),
                      label: Text(c.pack.t('wealth')),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: ListView.builder(
                  padding: EdgeInsets.fromLTRB(
                    16,
                    16,
                    16,
                    rows.isEmpty ? 16 : 104,
                  ),
                  itemCount: rows.isEmpty ? 1 : rows.length,
                  itemBuilder: (context, index) {
                    if (rows.isEmpty) {
                      return LifeCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Text(
                              c.pack.t('module_${table.name}'),
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                            const SizedBox(height: 12),
                            const SizedBox(height: 8),
                            Icon(
                              table == OfflineTable.accounts
                                  ? Icons.account_balance_wallet_outlined
                                  : Icons.receipt_long_outlined,
                              size: 36,
                              color: Theme.of(context).colorScheme.primary,
                            ),
                            const SizedBox(height: 12),
                            Text(c.pack.t('ux_empty_${table.name}')),
                            const SizedBox(height: 16),
                            if (table != OfflineTable.importBatches)
                              FilledButton.icon(
                                onPressed: busy ? null : () => edit(),
                                icon: const Icon(Icons.add),
                                label: Text(c.pack.t('add')),
                              ),
                          ],
                        ),
                      );
                    }
                    final row = rows[index];
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: LifeCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            ListTile(
                              contentPadding: EdgeInsets.zero,
                              title: Text(
                                row['name'] as String? ??
                                    row['label'] as String? ??
                                    c.pack.t('module_${table.name}'),
                              ),
                              leading: Icon(
                                table == OfflineTable.accounts
                                    ? Icons.account_balance_wallet_outlined
                                    : table == OfflineTable.budgets
                                    ? Icons.pie_chart_outline
                                    : Icons.receipt_long_outlined,
                              ),
                              subtitle: table == OfflineTable.accounts
                                  ? Text(c.pack.t('account_${row['kind']}'))
                                  : Text(summary(row)),
                              trailing: const Icon(Icons.edit_outlined),
                              onTap: table == OfflineTable.importBatches
                                  ? null
                                  : () => edit(row),
                            ),
                            if (table == OfflineTable.accounts) ...[
                              Text(
                                summary(row),
                                style: Theme.of(context).textTheme.headlineSmall
                                    ?.copyWith(fontWeight: FontWeight.w700),
                              ),
                              const SizedBox(height: 8),
                            ],
                            if (table == OfflineTable.importBatches)
                              TextButton.icon(
                                onPressed: busy
                                    ? null
                                    : () async {
                                        final yes = await showDialog<bool>(
                                          context: context,
                                          builder: (context) => AlertDialog(
                                            title: Text(
                                              c.pack.t('reverse_import'),
                                            ),
                                            content: Text(
                                              c.pack.t('reverse_import_help'),
                                            ),
                                            actions: [
                                              TextButton(
                                                onPressed: () => Navigator.pop(
                                                  context,
                                                  false,
                                                ),
                                                child: Text(c.pack.t('cancel')),
                                              ),
                                              FilledButton(
                                                onPressed: () => Navigator.pop(
                                                  context,
                                                  true,
                                                ),
                                                child: Text(c.pack.t('undo')),
                                              ),
                                            ],
                                          ),
                                        );
                                        if (yes == true) {
                                          await change(
                                            ReverseImport(
                                              const Uuid().v4(),
                                              row['id'] as String,
                                              row['revision'] as int,
                                            ),
                                          );
                                        }
                                      },
                                icon: const Icon(Icons.undo),
                                label: Text(c.pack.t('reverse_import')),
                              ),
                            if (table == OfflineTable.plannedPayments)
                              TextButton.icon(
                                onPressed: busy
                                    ? null
                                    : () async {
                                        final date = await showDatePicker(
                                          context: context,
                                          initialDate: c.now,
                                          firstDate: DateTime(1900),
                                          lastDate: DateTime(2200, 12, 31),
                                        );
                                        if (date != null) {
                                          await change(
                                            ConfirmPlannedPayment(
                                              const Uuid().v4(),
                                              row['id'] as String,
                                              row['revision'] as int,
                                              dateOnly(date),
                                            ),
                                          );
                                        }
                                      },
                                icon: const Icon(Icons.check),
                                label: Text(c.pack.t('confirm_payment')),
                              ),
                            if (![
                              OfflineTable.accounts,
                              OfflineTable.categories,
                              OfflineTable.importBatches,
                            ].contains(table))
                              Wrap(
                                spacing: 8,
                                children: [
                                  TextButton(
                                    onPressed: busy
                                        ? null
                                        : () async {
                                            final yes = await showDialog<bool>(
                                              context: context,
                                              builder: (context) => AlertDialog(
                                                title: Text(c.pack.t('delete')),
                                                content: Text(
                                                  c.pack.t('delete_confirm'),
                                                ),
                                                actions: [
                                                  TextButton(
                                                    onPressed: () =>
                                                        Navigator.pop(
                                                          context,
                                                          false,
                                                        ),
                                                    child: Text(
                                                      c.pack.t('cancel'),
                                                    ),
                                                  ),
                                                  FilledButton(
                                                    onPressed: () =>
                                                        Navigator.pop(
                                                          context,
                                                          true,
                                                        ),
                                                    child: Text(
                                                      c.pack.t('delete'),
                                                    ),
                                                  ),
                                                ],
                                              ),
                                            );
                                            if (yes == true) {
                                              await change(
                                                DeleteOffline(
                                                  const Uuid().v4(),
                                                  row['id'] as String,
                                                  row['revision'] as int,
                                                  table,
                                                ),
                                              );
                                            }
                                          },
                                    child: Text(c.pack.t('delete')),
                                  ),
                                  if ((row['revision'] as int) > 1 &&
                                      table != OfflineTable.plannedPayments)
                                    TextButton(
                                      onPressed: busy
                                          ? null
                                          : () => change(
                                              UndoOffline(
                                                const Uuid().v4(),
                                                row['id'] as String,
                                                row['revision'] as int,
                                                table,
                                              ),
                                            ),
                                      child: Text(c.pack.t('undo_last_change')),
                                    ),
                                ],
                              ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
        floatingActionButton:
            rows.isEmpty || table == OfflineTable.importBatches
            ? null
            : FloatingActionButton(
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(20),
                ),
                elevation: 2,
                onPressed: busy ? null : () => edit(),
                tooltip: c.pack.t('add'),
                child: const Icon(Icons.add),
              ),
      );
    },
  );
}

class FinanceEditor extends StatefulWidget {
  const FinanceEditor({
    super.key,
    required this.controller,
    required this.table,
    this.row,
  });
  final AppController controller;
  final OfflineTable table;
  final Map<String, Object?>? row;
  @override
  State<FinanceEditor> createState() => _FinanceEditorState();
}

class _FinanceEditorState extends State<FinanceEditor> {
  AppController get c => widget.controller;
  late final id = widget.row?['id'] as String? ?? const Uuid().v4();
  final operation = const Uuid().v4();
  late final name = TextEditingController(
    text:
        widget.row?['name'] as String? ?? widget.row?['label'] as String? ?? '',
  );
  late final currency = TextEditingController(
    text: widget.row?['currency'] as String? ?? c.currency,
  );
  late final amount = TextEditingController(
    text: widget.row == null
        ? ''
        : minorText(
            (widget.row?['opening_minor'] ??
                    widget.row?['limit_minor'] ??
                    widget.row?['amount_minor'] ??
                    0)
                as int,
            widget.row?['currency'] as String? ?? c.currency,
          ),
  );
  late final received = TextEditingController();
  late String kind =
      widget.row?['kind'] as String? ??
      (widget.table == OfflineTable.accounts ? 'cash' : 'expense');
  late String period = widget.row?['period'] as String? ?? 'month',
      rollover = widget.row?['rollover'] as String? ?? 'none';
  late String account = widget.row?['account_id'] as String? ?? '',
      category = widget.row?['category_id'] as String? ?? '',
      parent = widget.row?['parent_id'] as String? ?? '';
  late String from = widget.row?['from_account_id'] as String? ?? '',
      to = widget.row?['to_account_id'] as String? ?? '';
  late bool archived = widget.row?['archived'] == 1;
  late DateTime date = DateTime.parse(
    widget.row?['occurred_on'] as String? ??
        widget.row?['start_on'] as String? ??
        dateOnly(c.now),
  );
  late DateTime end = DateTime.parse(
    widget.row?['end_on'] as String? ?? dateOnly(c.now),
  );
  late ScheduleSpec schedule =
      c.calendar
          .where((e) => e.id == widget.row?['calendar_id'])
          .firstOrNull
          ?.schedule ??
      ScheduleSpec(
        localStart: '${dateOnly(c.now)}T09:00:00',
        timezone: c.timezone,
      );
  bool saving = false;
  String? error;
  @override
  void initState() {
    super.initState();
    if (widget.table == OfflineTable.transfers && widget.row != null) {
      amount.text = minorText(
        widget.row!['sent_minor'] as int,
        accountCurrency(from),
      );
      received.text = minorText(
        widget.row!['received_minor'] as int,
        accountCurrency(to),
      );
    }
  }

  String accountCurrency(String id) =>
      (c.offline[OfflineTable.accounts] ?? [])
              .where((a) => a['id'] == id)
              .firstOrNull?['currency']
          as String? ??
      currency.text;
  @override
  void dispose() {
    name.dispose();
    currency.dispose();
    amount.dispose();
    received.dispose();
    super.dispose();
  }

  Widget input(
    TextEditingController controller,
    String key, {
    bool money = false,
  }) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: TextField(
      controller: controller,
      keyboardType: money
          ? const TextInputType.numberWithOptions(decimal: true, signed: true)
          : TextInputType.text,
      decoration: InputDecoration(labelText: c.pack.t(key)),
      style: money ? Theme.of(context).textTheme.headlineSmall : null,
    ),
  );
  Widget select(
    String key,
    String value,
    Map<String, String> choices,
    ValueChanged<String> changed,
  ) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: LifeSelect<String>(
      label: c.pack.t(key),
      value: value,
      choices: choices,
      onChanged: (v) => setState(() => changed(v)),
      searchLabel: c.pack.t('search'),
    ),
  );
  Map<String, String> choices(OfflineTable table, {bool optional = true}) => {
    if (optional) '': c.pack.t('unassigned'),
    for (final r in c.offline[table] ?? [])
      if (r['id'] != id) r['id'] as String: r['name'] as String? ?? '',
  };
  Widget pickDate(
    String key,
    DateTime value,
    ValueChanged<DateTime> changed,
  ) => OutlinedButton.icon(
    onPressed: () async {
      final d = await showDatePicker(
        context: context,
        initialDate: value,
        firstDate: DateTime(1900),
        lastDate: DateTime(2200, 12, 31),
      );
      if (d != null && mounted) setState(() => changed(d));
    },
    icon: const Icon(Icons.calendar_today),
    label: Text(
      '${c.pack.t(key)}: ${MaterialLocalizations.of(context).formatMediumDate(value)}',
    ),
  );
  Future<void> save() async {
    if (saving) return;
    setState(() {
      saving = true;
      error = null;
    });
    try {
      final rev = widget.row?['revision'] as int? ?? 0;
      final AppAction action = switch (widget.table) {
        OfflineTable.accounts => SaveAccount(
          operation,
          id,
          rev,
          name: name.text,
          currency: currency.text,
          kind: kind,
          openingMinor: amount.text.trim().isEmpty
              ? 0
              : signedMinor(amount.text, currency.text),
          archived: archived,
        ),
        OfflineTable.categories => SaveCategory(
          operation,
          id,
          rev,
          name.text,
          parentId: parent.isEmpty ? null : parent,
          archived: archived,
        ),
        OfflineTable.transfers => SaveTransfer(
          operation,
          id,
          rev,
          fromId: from,
          toId: to,
          sentMinor: Currency.fromCode(accountCurrency(from))
              .parse(amount.text),
          receivedMinor: Currency.fromCode(accountCurrency(to))
              .parse(received.text),
          date: date,
          label: name.text,
        ),
        OfflineTable.budgets => SaveBudget(
          operation,
          id,
          rev,
          name: name.text,
          currency: currency.text,
          limitMinor: signedMinor(amount.text, currency.text),
          start: period == 'month'
              ? DateTime(date.year, date.month)
              : period == 'year'
              ? DateTime(date.year)
              : date,
          end: period == 'custom' ? end : null,
          categoryId: category.isEmpty ? null : category,
          period: period,
          rollover: rollover,
        ),
        OfflineTable.plannedPayments => SavePlannedPayment(
          operation,
          id,
          rev,
          name: name.text,
          kind: EntryKind.values.byName(kind),
          currency: currency.text,
          amountMinor: Currency.fromCode(currency.text).parse(amount.text),
          schedule: schedule,
          accountId: account.isEmpty ? null : account,
          categoryId: category.isEmpty ? null : category,
        ),
        _ => throw const DomainFailure('invalid_action'),
      };
      await c.execute(action);
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) {
        setState(() {
          saving = false;
          error = e is DomainFailure ? e.key : 'save_failed';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => EntrySheet(
    saving: saving,
    saveLabel: c.pack.t(saving ? 'saving' : 'save'),
    onSave: save,
    header: Row(
      children: [
        Expanded(
          child: Text(
            c.pack.t('module_${widget.table.name}'),
            style: Theme.of(context).textTheme.titleLarge,
          ),
        ),
        IconButton(
          tooltip: c.pack.t('cancel'),
          onPressed: () => Navigator.pop(context),
          icon: const Icon(Icons.close),
        ),
      ],
    ),
    children: [
      input(name, 'name'),
      if (widget.table == OfflineTable.accounts) ...[
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: LifeSelect<String>(
            label: c.pack.t('currency'),
            value: currency.text,
            choices: currencyChoices(c.pack, current: currency.text),
            dialog: true,
            searchLabel: c.pack.t('search'),
            onChanged: (v) => setState(() => currency.text = v),
          ),
        ),
        input(amount, 'opening_balance', money: true),
        select('account_kind', kind, {
          for (final k in ['cash', 'card', 'wallet', 'deposit', 'custom'])
            k: c.pack.t('account_$k'),
        }, (v) => kind = v),
        SwitchListTile(
          title: Text(c.pack.t('archived')),
          value: archived,
          onChanged: (v) => setState(() => archived = v),
        ),
      ],
      if (widget.table == OfflineTable.categories) ...[
        select(
          'parent_category',
          parent,
          choices(OfflineTable.categories),
          (v) => parent = v,
        ),
        SwitchListTile(
          title: Text(c.pack.t('archived')),
          value: archived,
          onChanged: (v) => setState(() => archived = v),
        ),
      ],
      if (widget.table == OfflineTable.transfers) ...[
        select(
          'from_account',
          from,
          choices(OfflineTable.accounts),
          (v) => from = v,
        ),
        input(amount, 'sent_amount', money: true),
        select('to_account', to, choices(OfflineTable.accounts), (v) => to = v),
        input(received, 'received_amount', money: true),
        Text(c.pack.t('transfer_help')),
        pickDate('date', date, (v) => date = v),
      ],
      if (widget.table == OfflineTable.budgets ||
          widget.table == OfflineTable.plannedPayments) ...[
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: LifeSelect<String>(
            label: c.pack.t('currency'),
            value: currency.text,
            choices: currencyChoices(c.pack, current: currency.text),
            dialog: true,
            searchLabel: c.pack.t('search'),
            onChanged: (v) => setState(() => currency.text = v),
          ),
        ),
        input(
          amount,
          widget.table == OfflineTable.budgets ? 'budget_limit' : 'amount',
          money: true,
        ),
        select(
          'category',
          category,
          choices(OfflineTable.categories),
          (v) => category = v,
        ),
      ],
      if (widget.table == OfflineTable.budgets) ...[
        select('period', period, {
          for (final k in ['week', 'month', 'year', 'custom'])
            k: c.pack.t('period_$k'),
        }, (v) => period = v),
        pickDate('date', date, (v) => date = v),
        if (period == 'custom') pickDate('end_date', end, (v) => end = v),
        select('rollover', rollover, {
          for (final k in ['none', 'positive', 'negative', 'both'])
            k: c.pack.t('rollover_$k'),
        }, (v) => rollover = v),
      ],
      if (widget.table == OfflineTable.plannedPayments) ...[
        select('kind', kind, {
          'expense': c.pack.t('expense'),
          'income': c.pack.t('income'),
        }, (v) => kind = v),
        select(
          'account',
          account,
          choices(OfflineTable.accounts),
          (v) => account = v,
        ),
        Text(c.pack.t('not_actual')),
        ScheduleEditor(
          controller: c,
          value: schedule,
          optional: false,
          onChanged: (v) => setState(() => schedule = v!),
        ),
      ],
      if (error != null)
        Text(
          c.pack.t(error!),
          style: TextStyle(color: Theme.of(context).colorScheme.error),
        ),
    ],
  );
}
