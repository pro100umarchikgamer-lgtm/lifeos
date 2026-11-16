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
      this.onWorkspaceSelected});
  final AppController controller;
  final int tab;
  final Set<String>? visibleKinds;
  final Future<bool> Function(String)? onWorkspaceSelected;
  @override
  State<FamilyDashboard> createState() => _FamilyDashboardState();
}

class _FamilyDashboardState extends State<FamilyDashboard> {
  String query = '', status = 'all', financeSection = 'accounts';
  late DateTime day = DateTime(c.now.year, c.now.month, c.now.day);
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
  Future<void> add([String? kind]) => Navigator.push<void>(
      context,
      MaterialPageRoute(
          builder: (_) => FamilyRecordEditor(
              controller: c.family!,
              pack: c.pack,
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

  List<Widget> summaries() {
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
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(t('current_balance'),
            style: Theme.of(context).textTheme.bodySmall),
        for (final entry in totals.entries)
          Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(
                  formatMoney(Currency.fromCode(entry.key), entry.value,
                      locale: c.region),
                  style: Theme.of(context).textTheme.headlineSmall)),
      ])),
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
    final tasks = rows
        .where((r) => r['kind'] == 'task' && !cloudTaskCompleted(r, c.family!))
        .toList();
    final now = c.now;
    final currentDay = DateTime(now.year, now.month, now.day);
    final upcoming =
        occurrences(currentDay, DateTime(now.year, now.month, now.day + 7));
    final notes = rows.where((r) => r['kind'] == 'note').toList();
    return [
      ...summaries(),
      heading(t('open_tasks')),
      if (tasks.isEmpty) empty('empty_tasks'),
      for (final row in tasks.take(4)) recordCard(row),
      heading(t('nav_calendar')),
      if (upcoming.isEmpty) empty('offline_empty'),
      for (final occurrence in upcoming.take(4))
        recordCard(occurrence.$1,
            subtitle:
                '${MaterialLocalizations.of(context).formatMediumDate(viewTime(occurrence.$2.at))} · ${occurrence.$2.entry.schedule.allDay ? t('all_day') : MaterialLocalizations.of(context).formatTimeOfDay(TimeOfDay.fromDateTime(viewTime(occurrence.$2.at)))}'),
      if (notes.isNotEmpty) ...[
        heading(t('recent_notes')),
        for (final row in notes.take(2)) recordCard(row)
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
