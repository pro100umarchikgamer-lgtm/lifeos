import 'package:flutter/material.dart';
import 'package:timezone/timezone.dart' as tz;
import '../domain/timezones.dart';
import '../app_controller.dart';
import '../domain/models.dart';
import '../domain/calendar_engine.dart';
import '../domain/family_finance.dart';
import '../sync/contracts.dart';
import '../sync/record_projection.dart';
import 'settings_surfaces.dart';
import 'design.dart';
import 'selection.dart';
import 'calendar.dart';
import 'family.dart';
import 'cloud_record_detail.dart';
import 'money_format.dart';
import 'family_financial_reference.dart';

/// Destination presenters share only the currently authorized cloud mirror.
class FamilyDashboard extends StatefulWidget {
  const FamilyDashboard(
      {super.key,
      required this.controller,
      this.tab = 0,
      this.visibleKinds,
      this.initialDay,
      this.onWorkspaceSelected});
  final AppController controller;
  final int tab;
  final Set<String>? visibleKinds;
  final DateTime? initialDay;
  final Future<bool> Function(String)? onWorkspaceSelected;
  @override
  State<FamilyDashboard> createState() => _FamilyDashboardState();
}

class _FamilyDashboardState extends State<FamilyDashboard> {
  String query = '', status = 'all', financeSection = 'accounts';
  late DateTime day =
      widget.initialDay ?? DateTime(c.now.year, c.now.month, c.now.day);
  late DateTime month = DateTime(day.year, day.month);
  AppController get c => widget.controller;
  String t(String key) => c.pack.t(key);
  List<Json> get rows => c.family!.records.where(isActiveSyncRecord).toList();
  String get destination => widget.visibleKinds?.length == 1
      ? widget.visibleKinds!.single
      : widget.visibleKinds != null
          ? (widget.visibleKinds!.length > 5 ? 'all' : 'finance')
          : switch (widget.tab) {
              1 => 'task',
              2 => 'finance',
              3 => 'all',
              _ => 'today'
            };
  Future<void> manage() => Navigator.push<void>(
      context,
      MaterialPageRoute(
          builder: (_) => FamilyPage(
              controller: c.family!,
              pack: c.pack,
              region: c.region,
              clock: () => c.now,
              onWorkspaceSelected:
                  widget.onWorkspaceSelected ?? c.selectCloudWorkspace)));
  Future<void> add([String? kind, String? flow]) => Navigator.push<void>(
      context,
      MaterialPageRoute(
          builder: (_) => FamilyRecordEditor(
              controller: c.family!,
              pack: c.pack,
              initialFlow: flow,
              initialKind: kind ??
                  (widget.visibleKinds?.length == 1
                      ? widget.visibleKinds!.single
                      : null))));
  Future<void> open(Json row) =>
      openCloudRecord(context, c.family!, c.pack, row['id'] as String,
          region: c.region, clock: () => c.now);

  String detail(Json r) {
    final d = object(r['data']);
    return switch (r['kind']) {
      'account' => formatMoney(Currency.fromCode(d['currency'] as String),
          const FamilyFinance().accountBalance(r, rows),
          locale: c.region),
      'budget' =>
        '${t('remaining')}: ${formatMoney(Currency.fromCode(d['currency'] as String), const FamilyFinance().budgetRemaining(r, rows, c.now), locale: c.region)}',
      'transaction' =>
        '${d['kind'] == 'income' ? '+' : '−'} ${referenceMoney(c.pack, d['amount_minor'], d['currency'] as String)} · ${d['date']}',
      'transfer' =>
        '${referenceMoney(c.pack, d['sent_minor'], c.family!.accountCurrency(d['from_id'] as String))} → ${referenceMoney(c.pack, d['received_minor'], c.family!.accountCurrency(d['to_id'] as String))}',
      'request' =>
        '${referenceMoney(c.pack, d['amount_minor'], d['currency'] as String)} · ${t(d['state'] == 'fulfilled' ? 'complete' : 'family_review_pending')}',
      'task' =>
        t(cloudTaskCompleted(r, c.family!) ? 'completed' : 'open_tasks'),
      'event' =>
        (d['schedule']['localStart'] as String).replaceFirst('T', ' · '),
      'shopping' =>
        '${(d['items'] as List).where((i) => object(i)['completed'] == true).length}/${(d['items'] as List).length}',
      _ => t('family_kind_${r['kind']}'),
    };
  }

  Widget heading(String title, {Widget? trailing}) => Padding(
      padding: const EdgeInsets.only(top: 24, bottom: 12),
      child: Row(children: [
        Expanded(
            child: Text(title, style: Theme.of(context).textTheme.titleMedium)),
        if (trailing != null) trailing
      ]));
  Widget recordCard(Json r, {String? subtitle}) => Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: LifeCard(
          padding: EdgeInsets.zero,
          child: ListTile(
              leading: Icon(cloudRecordIcon(r['kind'] as String),
                  color: Theme.of(context).colorScheme.primary),
              title: Text(cloudRecordTitle(r, c.pack),
                  maxLines: 2, overflow: TextOverflow.ellipsis),
              subtitle: Text(subtitle ?? detail(r)),
              trailing: const Icon(Icons.chevron_right_rounded, size: 20),
              onTap: () => open(r))));
  Widget empty(String key) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 24),
      child: Text(t(key), style: Theme.of(context).textTheme.bodyLarge));

  Future<void> module(String title,
          {Set<String>? kinds, int tab = 0, DateTime? initialDay}) =>
      Navigator.push<void>(
          context,
          MaterialPageRoute(
              builder: (_) => Scaffold(
                  appBar: AppBar(title: Text(t(title))),
                  body: SafeArea(
                      child: ListView(
                          padding: settingsPagePadding(context),
                          children: [
                        FamilyDashboard(
                            controller: c,
                            tab: tab,
                            visibleKinds: kinds,
                            initialDay: initialDay,
                            onWorkspaceSelected: widget.onWorkspaceSelected)
                      ])))));

  Future<void> openBalance() {
    final accounts = rows.where((r) => r['kind'] == 'account').toList();
    return accounts.length == 1
        ? open(accounts.single)
        : module('module_accounts', kinds: {'account'});
  }

  Widget amounts(Map<String, BigInt> totals, {bool prominent = false}) =>
      Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        for (final entry in totals.entries)
          Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(entry.key,
                        style: Theme.of(context).textTheme.labelMedium),
                    const SizedBox(height: 2),
                    Text(
                        formatMoney(Currency.fromCode(entry.key), entry.value,
                            locale: c.region),
                        style: prominent
                            ? Theme.of(context).textTheme.headlineSmall
                            : Theme.of(context).textTheme.titleLarge),
                  ])),
      ]);

  List<Widget> summaries({bool actionable = true}) {
    final accounts = rows.where((r) => r['kind'] == 'account').toList();
    final totals = <String, BigInt>{};
    for (final account in accounts) {
      final currency = account['data']['currency'] as String;
      totals[currency] = (totals[currency] ?? BigInt.zero) +
          const FamilyFinance().accountBalance(account, rows);
    }
    if (totals.isEmpty) return [];
    return [
      LifeCard(
          padding: EdgeInsets.zero,
          child: InkWell(
              key: const Key('cloud_current_balance'),
              onTap: actionable ? openBalance : null,
              child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Row(children: [
                          Icon(Icons.account_balance_wallet_outlined,
                              color: Theme.of(context).colorScheme.primary),
                          const SizedBox(width: 10),
                          Expanded(
                              child: Text(t('current_balance'),
                                  style:
                                      Theme.of(context).textTheme.titleMedium)),
                          if (actionable)
                            const Icon(Icons.chevron_right_rounded),
                        ]),
                        amounts(totals, prominent: true),
                      ])))),
      const SizedBox(height: 12)
    ];
  }

  tz.Location get viewZone =>
      calendarLocation(c.timezone == 'device' ? c.deviceZone : c.timezone);
  DateTime viewTime(DateTime instant) => tz.TZDateTime.from(instant, viewZone);

  List<(Json, CalendarOccurrence)> occurrences(DateTime from, DateTime until) {
    // Calendar dates belong to the selected view zone, not the host OS zone.
    final start = tz.TZDateTime(viewZone, from.year, from.month, from.day);
    final end = tz.TZDateTime(viewZone, until.year, until.month, until.day);
    final result = <(Json, CalendarOccurrence)>[];
    for (final row in rows.where((r) => r['kind'] == 'event')) {
      final data = object(row['data']), schedule = object(data['schedule']);
      // Local reminder fields are display defaults only, never persisted or scheduled.
      final spec = ScheduleSpec.fromJson({
        'timezone': c.timezone,
        'allDay': false,
        'repeat': 'none',
        'interval': 1,
        'until': null,
        ...schedule,
        'reminder': false,
        'mode': 'standard'
      });
      final entry = CalendarEntry(
          id: row['id'] as String,
          title: data['title'] as String,
          schedule: spec,
          revision: row['revision'] as int? ?? 1);
      for (final occurrence in const CalendarEngine()
          .between(entry, start, end, c.deviceZone, limit: 500)) {
        result.add((row, occurrence));
      }
    }
    result.sort((a, b) => a.$2.at.compareTo(b.$2.at));
    return result;
  }

  List<Widget> tasks() {
    final filtered = rows
        .where((r) =>
            r['kind'] == 'task' &&
            cloudRecordTitle(r, c.pack)
                .toLowerCase()
                .contains(query.toLowerCase()) &&
            (status == 'all' ||
                cloudTaskCompleted(r, c.family!) == (status == 'done')))
        .toList();
    return [
      TextField(
          key: const Key('cloud_task_search'),
          decoration: InputDecoration(
              labelText: t('search'), prefixIcon: const Icon(Icons.search)),
          onChanged: (v) => setState(() => query = v)),
      const SizedBox(height: 12),
      LifeSelect<String>(
          label: t('status'),
          value: status,
          choices: {
            'all': t('ux_all'),
            'open': t('open_tasks'),
            'done': t('completed')
          },
          onChanged: (v) => setState(() => status = v)),
      for (final done in [false, true]) ...[
        if (filtered.any((r) => cloudTaskCompleted(r, c.family!) == done)) ...[
          heading(t(done ? 'completed' : 'open_tasks')),
          for (final row in filtered
              .where((r) => cloudTaskCompleted(r, c.family!) == done))
            recordCard(row),
        ]
      ],
      if (filtered.isEmpty) empty('offline_empty'),
    ];
  }

  List<Widget> notes() {
    final notes = rows
        .where((r) =>
            r['kind'] == 'note' &&
            r['data']['body']
                .toString()
                .toLowerCase()
                .contains(query.toLowerCase()))
        .toList();
    return [
      TextField(
          key: const Key('cloud_note_search'),
          decoration: InputDecoration(
              labelText: t('search'), prefixIcon: const Icon(Icons.search)),
          onChanged: (v) => setState(() => query = v)),
      const SizedBox(height: 20),
      for (final note in notes)
        Padding(
            padding: const EdgeInsets.only(bottom: 14),
            child: LifeCard(
                padding: EdgeInsets.zero,
                child: InkWell(
                    onTap: () => open(note),
                    child: Padding(
                        padding: const EdgeInsets.all(20),
                        child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(Icons.notes_rounded,
                                  color: Theme.of(context).colorScheme.primary),
                              const SizedBox(height: 14),
                              Text(note['data']['body'].toString(),
                                  maxLines: 6,
                                  overflow: TextOverflow.ellipsis,
                                  style: Theme.of(context)
                                      .textTheme
                                      .bodyLarge
                                      ?.copyWith(height: 1.6)),
                            ]))))),
      if (notes.isEmpty) empty('empty_notes'),
    ];
  }

  List<Widget> calendar() {
    final events = occurrences(DateTime(month.year, month.month),
        DateTime(month.year, month.month + 1));
    final selected =
        events.where((e) => c.civilDate(e.$2.at) == dateOnly(day)).toList();
    return [
      LifeCard(
          child: CalendarGrid(
              month: month,
              selected: day,
              weekStart: c.weekStart,
              marked: events.map((e) => c.civilDate(e.$2.at)).toSet(),
              onMonth: (v) => setState(() {
                    month = v;
                    day = v;
                  }),
              onDay: (v) => setState(() => day = v))),
      heading(MaterialLocalizations.of(context).formatFullDate(day)),
      for (final event in selected)
        recordCard(event.$1,
            subtitle: event.$2.entry.schedule.allDay
                ? t('all_day')
                : MaterialLocalizations.of(context).formatTimeOfDay(
                    TimeOfDay.fromDateTime(viewTime(event.$2.at)))),
      if (selected.isEmpty) empty('offline_empty'),
    ];
  }

  List<Widget> finances() {
    final groups = {
      'accounts': 'module_accounts',
      'operations': 'cloud_operations',
      'budgets': 'module_budgets'
    };
    final kinds = switch (financeSection) {
      'accounts' => {'account'},
      'budgets' => {'budget'},
      _ => {'transaction', 'transfer', 'request'}
    };
    final records = rows
        .where((r) =>
            kinds.contains(r['kind']) &&
            (query.isEmpty ||
                cloudRecordTitle(r, c.pack)
                    .toLowerCase()
                    .contains(query.toLowerCase())))
        .toList()
      ..sort((a, b) => (b['data']['date'] as String? ?? '')
          .compareTo(a['data']['date'] as String? ?? ''));
    return [
      ...summaries(),
      Wrap(spacing: 8, runSpacing: 8, children: [
        for (final group in groups.entries)
          ChoiceChip(
              label: Text(t(group.value)),
              selected: financeSection == group.key,
              onSelected: (_) => setState(() {
                    financeSection = group.key;
                    query = '';
                  })),
      ]),
      const SizedBox(height: 20),
      TextField(
          key: ValueKey('cloud_finance_search_$financeSection'),
          decoration: InputDecoration(
              labelText: t('search'), prefixIcon: const Icon(Icons.search)),
          onChanged: (v) => setState(() => query = v)),
      const SizedBox(height: 16),
      if (records.isEmpty) empty('offline_empty'),
      for (final row in records) recordCard(row),
    ];
  }

  List<Widget> today() {
    final allTasks = rows.where((r) => r['kind'] == 'task').toList();
    final tasks =
        allTasks.where((r) => !cloudTaskCompleted(r, c.family!)).toList();
    final completed = allTasks.length - tasks.length;
    final now = c.now;
    final currentDay = DateTime(now.year, now.month, now.day);
    final upcoming =
        occurrences(currentDay, DateTime(now.year, now.month, now.day + 7));
    final notes = rows.where((r) => r['kind'] == 'note').toList();
    final allowed = c.family!.creatableKinds;
    final monthStart = dateOnly(DateTime(now.year, now.month));
    final monthEnd = dateOnly(DateTime(now.year, now.month + 1));
    final expenses = <String, BigInt>{};
    final operations = rows
        .where(
            (r) => ['transaction', 'transfer', 'request'].contains(r['kind']))
        .toList()
      ..sort((a, b) => (b['data']['date'] as String? ?? '')
          .compareTo(a['data']['date'] as String? ?? ''));
    for (final row in rows.where((r) => r['kind'] == 'transaction')) {
      final data = object(row['data']), date = data['date'] as String? ?? '';
      if (data['kind'] != 'expense' ||
          date.compareTo(monthStart) < 0 ||
          date.compareTo(monthEnd) >= 0) {
        continue;
      }
      final code = data['currency'] as String;
      expenses[code] = (expenses[code] ?? BigInt.zero) +
          BigInt.from(data['amount_minor'] as int);
    }
    Widget cardHeader(String title, IconData icon,
            {String? action, VoidCallback? onTap}) =>
        Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(children: [
            Icon(icon, color: Theme.of(context).colorScheme.primary),
            const SizedBox(width: 10),
            Expanded(
                child: Text(t(title),
                    style: Theme.of(context).textTheme.titleMedium)),
          ]),
          if (action != null)
            Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                    onPressed: onTap,
                    iconAlignment: IconAlignment.end,
                    icon: const Icon(Icons.chevron_right_rounded, size: 18),
                    label: Text(t(action)))),
        ]);
    Widget preview(Json record, {String? subtitle}) => ListTile(
        contentPadding: EdgeInsets.zero,
        leading: Icon(cloudRecordIcon(record['kind'] as String)),
        title: Text(cloudRecordTitle(record, c.pack),
            maxLines: 2, overflow: TextOverflow.ellipsis),
        subtitle: Text(subtitle ?? detail(record)),
        trailing: const Icon(Icons.chevron_right_rounded, size: 18),
        onTap: () => open(record));
    final financeCards = <Widget>[
      LifeCard(
          key: const Key('cloud_today_expenses'),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            cardHeader('today_month_expenses', Icons.bar_chart_rounded,
                action: 'finances', onTap: () => module('finances', tab: 2)),
            Text(MaterialLocalizations.of(context).formatMonthYear(now),
                style: Theme.of(context).textTheme.bodySmall),
            if (expenses.isEmpty) ...[
              const SizedBox(height: 14),
              Text(t('today_no_month_expenses')),
            ] else
              amounts(expenses),
          ])),
      ...summaries(actionable: true).where((widget) => widget is! SizedBox),
    ];
    return [
      Text(MaterialLocalizations.of(context).formatFullDate(now),
          style: Theme.of(context).textTheme.bodyMedium),
      if (allowed.isNotEmpty) ...[
        const SizedBox(height: 16),
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (final (kind, flow, label, icon) in [
            ('task', '', 'create_task', Icons.add_task_rounded),
            (
              'transaction',
              'expense',
              'create_expense',
              Icons.remove_circle_outline
            ),
            (
              'transaction',
              'income',
              'create_income',
              Icons.add_circle_outline
            ),
            ('note', '', 'create_note', Icons.edit_note_rounded),
          ])
            if (allowed.contains(kind) &&
                !(flow == 'income' &&
                    c.family!.roster?['space']?['role'] == 'child'))
              Tooltip(
                  message: t(label),
                  child: FilledButton.tonalIcon(
                      key: Key('cloud_quick_${flow.isEmpty ? kind : flow}'),
                      onPressed: c.family!.busy
                          ? null
                          : () => add(kind, flow.isEmpty ? null : flow),
                      icon: Icon(icon, size: 20),
                      label: Text(t(flow.isEmpty ? kind : flow)))),
        ]),
      ],
      const SizedBox(height: 20),
      LifeCard(
          key: const Key('cloud_today_tasks'),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            cardHeader('open_tasks', Icons.checklist_rounded,
                action: 'all_tasks',
                onTap: () => module('nav_tasks', kinds: {'task'})),
            Text('${tasks.length}',
                style: Theme.of(context).textTheme.headlineSmall),
            if (allTasks.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text('${t('completed')}: $completed / ${allTasks.length}',
                  style: Theme.of(context).textTheme.bodySmall),
              const SizedBox(height: 6),
              LinearProgressIndicator(
                  value: completed / allTasks.length,
                  semanticsLabel:
                      '${t('completed')}: $completed / ${allTasks.length}',
                  borderRadius: BorderRadius.circular(8),
                  minHeight: 6),
            ],
            if (tasks.isEmpty) ...[
              const SizedBox(height: 16),
              Text(t('today_no_open_tasks')),
            ],
            for (final row in tasks.take(3)) preview(row),
          ])),
      const SizedBox(height: 14),
      LayoutBuilder(builder: (context, bounds) {
        final columns = bounds.maxWidth >= 680 &&
            MediaQuery.textScalerOf(context).scale(1) <= 1.3;
        return columns && financeCards.length == 2
            ? Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Expanded(child: financeCards[0]),
                const SizedBox(width: 14),
                Expanded(child: financeCards[1]),
              ])
            : Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                for (var i = 0; i < financeCards.length; i++) ...[
                  if (i > 0) const SizedBox(height: 14),
                  financeCards[i],
                ]
              ]);
      }),
      const SizedBox(height: 14),
      LifeCard(
          key: const Key('cloud_today_calendar'),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            cardHeader('today_next_seven_days', Icons.event_outlined,
                action: 'nav_calendar',
                onTap: () => module('nav_calendar', kinds: {'event'})),
            SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(children: [
                  for (var index = 0; index < 7; index++)
                    Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: ActionChip(
                            backgroundColor: index == 0
                                ? Theme.of(context).colorScheme.primaryContainer
                                : null,
                            label: Text(MaterialLocalizations.of(context)
                                .formatShortMonthDay(DateTime(currentDay.year,
                                    currentDay.month, currentDay.day + index))),
                            onPressed: () => module('nav_calendar',
                                kinds: {'event'},
                                initialDay: DateTime(currentDay.year,
                                    currentDay.month, currentDay.day + index))))
                ])),
            const SizedBox(height: 10),
            if (upcoming.isEmpty) Text(t('today_no_upcoming_events')),
            for (final occurrence in upcoming.take(3))
              preview(occurrence.$1,
                  subtitle:
                      '${MaterialLocalizations.of(context).formatMediumDate(viewTime(occurrence.$2.at))} · ${occurrence.$2.entry.schedule.allDay ? t('all_day') : MaterialLocalizations.of(context).formatTimeOfDay(TimeOfDay.fromDateTime(viewTime(occurrence.$2.at)))}'),
          ])),
      const SizedBox(height: 14),
      LifeCard(
          key: const Key('cloud_today_notes'),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            cardHeader('recent_notes', Icons.notes_rounded,
                action: 'all_notes',
                onTap: () => module('nav_notes', kinds: {'note'})),
            if (notes.isEmpty) Text(t('empty_notes')),
            for (final row in notes.take(2)) preview(row),
          ])),
      if (operations.isNotEmpty) ...[
        const SizedBox(height: 14),
        LifeCard(
            child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
              cardHeader('cloud_operations', Icons.receipt_long_outlined,
                  action: 'finances', onTap: () => module('finances', tab: 2)),
              for (final row in operations.take(3)) preview(row),
            ])),
      ],
    ];
  }

  List<Widget> allSections() => [
        for (final kind in [
          'note',
          'task',
          'event',
          'account',
          'transaction',
          'transfer',
          'budget',
          'shopping',
          'request'
        ])
          if ((widget.visibleKinds == null ||
                  widget.visibleKinds!.contains(kind)) &&
              rows.any((r) => r['kind'] == kind)) ...[
            heading(t('family_kind_$kind')),
            for (final row in rows.where((r) => r['kind'] == kind))
              recordCard(row),
          ],
        if (rows.isEmpty) empty('offline_empty')
      ];

  @override
  Widget build(BuildContext context) => ListenableBuilder(
      listenable: c.family!,
      builder: (context, _) {
        final f = c.family!, dest = destination;
        final title = t(switch (dest) {
          'today' => 'today',
          'all' => 'all_sections',
          'finance' => 'finances',
          'task' => 'nav_tasks',
          'note' => 'nav_notes',
          'event' => 'nav_calendar',
          'account' => 'module_accounts',
          _ => 'all_sections'
        });
        final allowed = f.creatableKinds
            .intersection(widget.visibleKinds ?? f.creatableKinds);
        final createKind = widget.visibleKinds?.length == 1
            ? widget.visibleKinds!.single
            : dest == 'finance'
                ? switch (financeSection) {
                    'accounts' =>
                      allowed.contains('account') ? 'account' : null,
                    'budgets' => allowed.contains('budget') ? 'budget' : null,
                    _ => 'transaction'
                  }
                : null;
        return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(children: [
                Expanded(
                    child: Text(title,
                        style: Theme.of(context).textTheme.headlineSmall)),
                IconButton(
                    tooltip: t('family_sync'),
                    onPressed: f.busy ? null : () => f.refresh(),
                    icon: const Icon(Icons.sync))
              ]),
              const SizedBox(height: 6),
              Text(
                  t(cloudSpaceKind(f) == 'personal'
                      ? 'workspace_account_personal'
                      : 'account_spaces'),
                  style: Theme.of(context).textTheme.bodySmall),
              const SizedBox(height: 16),
              if (f.busy) const LinearProgressIndicator(),
              if (f.error != null)
                Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Text(t('family_error_${f.error}'))),
              if (f.pending.isNotEmpty || f.issues.isNotEmpty) ...[
                SettingsGroup(children: [
                  SettingsRow(
                      icon: Icons.cloud_upload_outlined,
                      title:
                          '${t('family_pending')}: ${f.pending.length} · ${t('family_conflict')}: ${f.issues.length}',
                      onTap: manage)
                ]),
                const SizedBox(height: 16)
              ],
              if (allowed.isNotEmpty && dest != 'today') ...[
                Align(
                    alignment: Alignment.centerLeft,
                    child: FilledButton.icon(
                        key: const Key('cloud_add_record'),
                        onPressed: f.busy ? null : () => add(createKind),
                        icon: const Icon(Icons.add),
                        label: Text(createKind != null
                            ? '${t('add')} · ${t('family_kind_$createKind')}'
                            : t('add')))),
                const SizedBox(height: 20)
              ],
              ...switch (dest) {
                'today' => today(),
                'task' => tasks(),
                'note' => notes(),
                'event' => calendar(),
                'finance' => finances(),
                _ => allSections()
              },
            ]);
      });
}
