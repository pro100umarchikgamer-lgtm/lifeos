import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../app_controller.dart';
import '../domain/models.dart';
import '../domain/financial_period.dart';
import '../localization/language_pack.dart';
import 'design.dart';
import 'quick_add.dart';
import 'money_format.dart';
import 'calendar.dart';
import 'calendar_panel.dart';
import 'record_detail.dart';
import 'settings.dart';

class LifeOSApp extends StatelessWidget {
  const LifeOSApp({super.key, required this.controller, this.builder});
  final AppController controller;
  final TransitionBuilder? builder;
  @override
  Widget build(BuildContext context) => ListenableBuilder(listenable: controller.presentation, builder: (context, _) {
    return MaterialApp(
      title: 'LifeOS', debugShowCheckedModeBanner: false, builder: builder,
      themeAnimationDuration: WidgetsBinding.instance.platformDispatcher.accessibilityFeatures.disableAnimations ? Duration.zero : const Duration(milliseconds: 180),
      locale: Locale(controller.region), supportedLocales: {for (final p in controller.catalog.packs.values) p.locale, Locale(controller.region)}.toList(),
      localizationsDelegates: const [MaterialFallbackDelegate(), WidgetsFallbackDelegate(), CupertinoFallbackDelegate()],
      theme: lifeTheme(Brightness.light, appearance: controller.appearance, wallpaperSeed: controller.wallpaperSeed == null ? null : Color(controller.wallpaperSeed!)),
      darkTheme: lifeTheme(Brightness.dark, appearance: controller.appearance, wallpaperSeed: controller.wallpaperSeed == null ? null : Color(controller.wallpaperSeed!)),
      themeMode: switch (controller.theme) {'light' => ThemeMode.light, 'dark' => ThemeMode.dark, _ => ThemeMode.system},
      home: HomeShell(controller: controller),
    );
  });
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key, required this.controller});
  final AppController controller;
  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> with WidgetsBindingObserver {
  int _tab = 0;
  bool _profileOpen = false;
  bool _notesOpen = false;
  DateTimeRange _period = DateTimeRange(start: DateTime(DateTime.now().year, DateTime.now().month),
    end: DateTime(DateTime.now().year, DateTime.now().month + 1, 0));
  FinancialPeriod get financialPeriod => FinancialPeriod(_period.start, _period.end);
  String get summaryCurrency {
    final codes = financialPeriod.records(c.records).map((r) => r.currency!.code).toSet().toList()..sort();
    return codes.contains(_summaryCurrency) ? _summaryCurrency! : codes.contains(c.currency) ? c.currency : codes.firstOrNull ?? c.currency;
  }
  @override
  void initState() { super.initState(); WidgetsBinding.instance.addObserver(this); c.addListener(_dataChanged); WidgetsBinding.instance.addPostFrameCallback((_) => _resume()); }
  @override
  void dispose() { c.removeListener(_dataChanged); WidgetsBinding.instance.removeObserver(this); super.dispose(); }
  void _dataChanged() { if (mounted) setState(() {}); }
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) { if (state == AppLifecycleState.resumed) _resume(); }
  Future<void> _resume() async {
    if (!c.native.supported) return;
    try {
      await c.refresh(forceReminders: true);
      final id = await c.native.launchTarget();
      if (!mounted || id == null) return;
      final entry = c.calendar.where((e) => e.id == id).firstOrNull;
      if (entry == null) return;
      final source = entry.taskId ?? entry.noteId;
      if (source != null) { _showRecord(source); }
      else { await showModalBottomSheet<void>(context: context, useSafeArea: true, isScrollControlled: true,
        builder: (_) => EventEditor(controller: c, date: DateTime.parse(entry.schedule.localStart), entry: entry)); }
    } catch (_) { _message('read_failed'); }
  }
  String? _summaryCurrency;
  AppController get c => widget.controller;
  static const _tabs = ['today', 'plans', 'finances', 'modules'];
  static const _icons = [Icons.home_rounded, Icons.format_list_bulleted_rounded, Icons.bar_chart_rounded, Icons.grid_view_rounded];

  void _message(String key) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(c.pack.t(key))));
  }

  Future<void> _add(EntryKind kind) async {
    final saved = await showEntryEditor(context, c, kind);
    if (saved == true) {
      try { await c.refresh(); _message('saved'); } catch (_) { _message('read_failed'); }
    }
  }

  void _chooseAdd() { showModalBottomSheet<void>(context: context,
    backgroundColor: Theme.of(context).colorScheme.surface,
    shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
    builder: (sheetContext) => SafeArea(child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(c.pack.t('quick_add'), style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
        const SizedBox(height: 16),
        for (final kind in EntryKind.values) ListTile(
          leading: Icon(_kindIcon(kind), color: _kindColors(kind).foreground),
          title: Text(c.pack.t(kind.name)),
          onTap: () { Navigator.pop(sheetContext); _add(kind); },
        ),
      ]),
    ))); }

  Future<void> _complete(Record record, bool value) async {
    if (c.pendingTasks.contains(record.id)) return;
    setState(() => c.pendingTasks.add(record.id));
    var saved = false;
    try {
      final linked = c.scheduleFor(record);
      if (value && linked != null && linked.schedule.repeat != RepeatRule.none) {
        final now = DateTime.now();
        final candidates = c.calendarEngine.between(linked, now.subtract(const Duration(days: 370)), now.add(const Duration(days: 370)), c.deviceZone)
          .where((o) => !c.occurrences.any((s) => s.entryId == linked.id && s.revision == linked.revision && s.epoch == o.at.millisecondsSinceEpoch)).toList();
        final due = candidates.where((o) => !o.at.isAfter(now)).lastOrNull ?? candidates.firstOrNull;
        if (due == null) throw const DomainFailure('occurrence_missing');
        await c.engine.execute(SetOccurrence(const Uuid().v4(), linked.id, due.at.millisecondsSinceEpoch, OccurrenceStatus.completed, expectedRevision: linked.revision));
      } else {
        await c.engine.execute(CompleteTask(const Uuid().v4(), record.id, value, expectedRevision: record.revision));
      }
      saved = true;
      await c.refresh();
    } catch (_) { _message(saved ? 'read_failed' : 'change_failed'); }
    finally { if (mounted) setState(() => c.pendingTasks.remove(record.id)); }
  }

  void _navigate(int tab) => setState(() { _tab = tab; _profileOpen = false; _notesOpen = false; });

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final wide = width >= 720;
    final items = <Widget>[

        _header(),
        const SizedBox(height: 18),
        if (_profileOpen) ..._profile()
        else if (_tab == 0) ..._home()
        else if (_tab == 1) ...[
          CalendarPanel(controller: c), const SizedBox(height: 18), ..._entries(EntryKind.task),
        ]
        else if (_tab == 2) ..._finance()
        else if (_notesOpen) ..._entries(EntryKind.note)
        else ..._modules(),
    ];
    final content = ListView.builder(key: Key(_profileOpen ? 'profile_page' : _tabs[_tab]),
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      padding: EdgeInsets.fromLTRB(width < 350 ? 14 : 18, 8, width < 350 ? 14 : 18, 26),
      itemCount: items.length, itemBuilder: (_, index) => items[index]);
    return PopScope(canPop: _tab == 0 && !_profileOpen && !_notesOpen, onPopInvokedWithResult: (didPop, _) { if (!didPop) _navigate(0); }, child: Scaffold(
      body: SafeArea(child: Row(children: [
        if (wide) NavigationRail(selectedIndex: _tab, onDestinationSelected: _navigate,
          labelType: NavigationRailLabelType.all,
          backgroundColor: Theme.of(context).colorScheme.surface,
          destinations: [for (var i = 0; i < _tabs.length; i++)
            NavigationRailDestination(icon: Icon(_icons[i]), label: Text(c.pack.t(_tabs[i])))]),
        Expanded(child: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 560), child: AnimatedSwitcher(duration: MediaQuery.disableAnimationsOf(context) ? Duration.zero : const Duration(milliseconds: 180), child: content)))),
      ])),
      bottomNavigationBar: wide ? null : _bottomBar(),
      floatingActionButtonLocation: FloatingActionButtonLocation.endFloat,
      floatingActionButton: wide ? _addButton() : null,
    ));
  }

  Widget _header() => Row(children: [
    Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      GestureDetector(onTap: () => _navigate(0), child: Text.rich(TextSpan(children: [
        TextSpan(text: 'Life', style: TextStyle(color: Theme.of(context).colorScheme.onSurface)),
        TextSpan(text: 'OS', style: TextStyle(color: Theme.of(context).colorScheme.primary)),
      ]), style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w800, letterSpacing: -.8))),
      Text(c.pack.t('personal_space'), style: Theme.of(context).textTheme.bodySmall?.copyWith(color: LifePalette.muted)),
    ])),
    IconButton(tooltip: c.pack.t('search'), onPressed: _showSearch, icon: const Icon(Icons.search_rounded)),
    const SizedBox(width: 3),
    IconButton(key: const Key('profile_button'), tooltip: c.pack.t('profile'), onPressed: () => setState(() => _profileOpen = true),
      icon: CircleAvatar(radius: 19, backgroundColor: Theme.of(context).colorScheme.primaryContainer,
        child: Icon(Icons.person_rounded, size: 23, color: Theme.of(context).colorScheme.primary))),
  ]);

  Widget _addButton() => Container(
    width: 58, height: 58,
    decoration: BoxDecoration(shape: BoxShape.circle, boxShadow: [
      BoxShadow(color: LifePalette.darkGreen.withValues(alpha: .16),
        blurRadius: 10, offset: const Offset(0, 3)),
    ]),
    child: FloatingActionButton(key: const Key('add_button'), onPressed: _chooseAdd,
      backgroundColor: Theme.of(context).colorScheme.primary, foregroundColor: Theme.of(context).colorScheme.onPrimary,
      shape: const CircleBorder(side: BorderSide.none),
      elevation: 0, focusElevation: 0, hoverElevation: 0, highlightElevation: 0,
      child: const Icon(Icons.add, size: 32)),
  );

  Widget _bottomBar() {
    final surface = Theme.of(context).colorScheme.surface;
    final inactive = Theme.of(context).colorScheme.onSurfaceVariant;
    return BottomAppBar(height: 76, padding: EdgeInsets.zero, color: surface,

      child: Row(children: [
        for (var i = 0; i < 2; i++) Expanded(child: _navItem(i, inactive)),
        SizedBox(width: 64, child: Center(child: _addButton())),
        for (var i = 2; i < 4; i++) Expanded(child: _navItem(i, inactive)),
      ]));
  }

  Widget _navItem(int i, Color inactive) {
    final active = !_profileOpen && _tab == i;
    final color = active ? Theme.of(context).colorScheme.primary : inactive;
    return InkWell(key: Key('nav_${_tabs[i]}'), onTap: () => _navigate(i),
      child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
        Icon(_icons[i], size: 22, color: color),
        const SizedBox(height: 3),
        Text(c.pack.t(_tabs[i]), maxLines: 1, overflow: TextOverflow.ellipsis,
          style: TextStyle(color: color, fontSize: 10, fontWeight: active ? FontWeight.w700 : FontWeight.w500)),
      ]));
  }

  List<Widget> _home() {
    final now = c.now;
    final tasks = c.records.where((r) => r.kind == EntryKind.task && !r.completed).take(3).toList();
    final notes = c.records.where((r) => r.kind == EntryKind.note).take(2).toList();
    return [
      if (c.records.isEmpty) ..._emptyHome() else ...[
        Text(c.pack.t(now.hour < 12 ? 'good_morning' : now.hour < 18 ? 'good_afternoon' : 'good_evening'),
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
        Text(MaterialLocalizations.of(context).formatMediumDate(now),
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: LifePalette.muted)),
        const SizedBox(height: 14),
        _financeSummary(),
        const SizedBox(height: 12),
        _quickActions(),
        const SizedBox(height: 12),
        _tasksCard(tasks),
        const SizedBox(height: 12),
        _notesCard(notes),
      ],
    ];
  }

  List<Widget> _emptyHome() => [
    LifeCard(padding: EdgeInsets.zero, child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const WelcomeLandscape(),
      Padding(padding: const EdgeInsets.fromLTRB(18, 16, 18, 18), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(c.pack.t('welcome_title'), style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
        const SizedBox(height: 7),
        Text(c.pack.t('welcome_body'), style: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.35, color: LifePalette.muted)),
        const SizedBox(height: 15),
        SizedBox(width: double.infinity, child: FilledButton.icon(onPressed: _chooseAdd,
          icon: const Icon(Icons.add), label: Text(c.pack.t('add_first_record')))),
      ])),
    ])),
    const SizedBox(height: 12),
    LifeCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _sectionTitle('start_examples'),
      const SizedBox(height: 10),
      _actionGrid(detailed: true),
    ])),
    const SizedBox(height: 12),
    LifeCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _sectionTitle('your_space'),
      const SizedBox(height: 10),
      Row(children: [Expanded(child: _feature(Icons.bar_chart, 'feature_finance', 'feature_finance_hint', LifePalette.green)),
        const SizedBox(width: 8), Expanded(child: _feature(Icons.check_box, 'feature_tasks', 'feature_tasks_hint', LifePalette.blue))]),
      const SizedBox(height: 8),
      Row(children: [Expanded(child: _feature(Icons.notes, 'feature_notes', 'feature_notes_hint', LifePalette.orange)),
        const SizedBox(width: 8), Expanded(child: _feature(Icons.shield_outlined, 'feature_private', 'feature_private_hint', LifePalette.green))]),
    ])),
  ];

  Widget _feature(IconData icon, String title, String detail, Color color) => Container(
    padding: const EdgeInsets.all(9),
    decoration: BoxDecoration(color: color.withValues(alpha: Theme.of(context).brightness == Brightness.dark ? .16 : .07),
      borderRadius: BorderRadius.circular(12)),
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Icon(icon, color: color, size: 19), const SizedBox(width: 6),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(c.pack.t(title), maxLines: 2, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700)),
        Text(c.pack.t(detail), maxLines: 2, style: const TextStyle(fontSize: 9, color: LifePalette.muted)),
      ])),
    ]));

  Widget _financeSummary() {
    final periodRecords = financialPeriod.records(c.records);
    final currencies = periodRecords.map((r) => r.currency!.code).toSet().toList()..sort();
    final selected = summaryCurrency;
    final records = financialPeriod.records(c.records, currency: selected);
    final income = financialPeriod.total(c.records, EntryKind.income, selected);
    final expense = financialPeriod.total(c.records, EntryKind.expense, selected);
    final incomeCount = records.where((r) => r.kind == EntryKind.income).length;
    final expenseCount = records.where((r) => r.kind == EntryKind.expense).length;
    final duration = DateTime.utc(_period.end.year,_period.end.month,_period.end.day)
      .difference(DateTime.utc(_period.start.year,_period.start.month,_period.start.day)).inDays + 1;
    final days = duration < 31 ? duration : 31;
    final dailyIncome = List<BigInt>.filled(days, BigInt.zero), dailyExpense = List<BigInt>.filled(days, BigInt.zero);
    for (final r in records) {
      final date = DateTime.parse(r.date!);
      final offset = DateTime.utc(date.year,date.month,date.day).difference(DateTime.utc(_period.start.year,_period.start.month,_period.start.day)).inDays;
      final bucket = offset * days ~/ duration;
      if (r.kind == EntryKind.income) dailyIncome[bucket] += BigInt.from(r.amountMinor!);
      if (r.kind == EntryKind.expense) dailyExpense[bucket] += BigInt.from(r.amountMinor!);
    }
    final wholeMonth = _period.start.day == 1 && _period.end == DateTime(_period.start.year,_period.start.month + 1,0);
    final currency = Currency.fromCode(selected);
    return LifeCard(child: Column(children: [
      Wrap(alignment: WrapAlignment.spaceBetween, spacing: 8, runSpacing: 8, children: [
        InkWell(key: const Key('financial_period'), onTap: () async {
          final selected = await selectFinancialPeriod(context, c, _period);
          if (selected != null && mounted) setState(() => _period = selected);
        }, child: _chip(wholeMonth ? MaterialLocalizations.of(context).formatMonthYear(_period.start)
          : '${MaterialLocalizations.of(context).formatShortDate(_period.start)} — ${MaterialLocalizations.of(context).formatShortDate(_period.end)}')),
        PopupMenuButton<String>(tooltip: c.pack.t('currency'), onSelected: (v) => setState(() => _summaryCurrency = v),
          itemBuilder: (context) => [for (final code in currencies.isEmpty ? [selected] : currencies) PopupMenuItem(value: code, child: Text(code))],
          child: _chip(selected)),
      ]),
      const SizedBox(height: 15),
      if (_tab == 2) ...[
        _financeTotal('income', formatMoney(currency, income, locale: c.region), c.pack.count('record_count', incomeCount), LifePalette.green),
        const Divider(height: 24),
        _financeTotal('expense', formatMoney(currency, expense, locale: c.region), c.pack.count('record_count', expenseCount), LifePalette.red),
        const Divider(height: 24),
        _financeTotal('difference', formatMoney(currency, income - expense, locale: c.region), '', (income - expense).isNegative ? LifePalette.red : LifePalette.green),
      ] else Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(child: _metric('income', formatMoney(currency, income, locale: c.region), c.pack.count('record_count', incomeCount), LifePalette.green)),
        Container(width: 1, height: 48, color: Theme.of(context).dividerColor),
        Expanded(child: _metric('expense', formatMoney(currency, expense, locale: c.region), c.pack.count('record_count', expenseCount), LifePalette.red)),
        Container(width: 1, height: 48, color: Theme.of(context).dividerColor),
        Expanded(child: _metric('difference', formatMoney(currency, income - expense, locale: c.region), '', (income - expense).isNegative ? LifePalette.red : LifePalette.green)),
      ]),
      const SizedBox(height: 12),
      DailyBarChart(income: dailyIncome, expense: dailyExpense),
      const SizedBox(height: 4),
      if (wholeMonth) Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [for (final day in [1,8,15,22,duration]) Text('$day',style: const TextStyle(fontSize: 10,color: LifePalette.muted))])
      else Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text(MaterialLocalizations.of(context).formatShortDate(_period.start), style: const TextStyle(fontSize: 10, color: LifePalette.muted)),
        Text(MaterialLocalizations.of(context).formatShortDate(_period.end), style: const TextStyle(fontSize: 10, color: LifePalette.muted)),
      ]),
    ]));
  }

  Widget _financeTotal(String label, String amount, String count, Color color) => Column(
    crossAxisAlignment: CrossAxisAlignment.start, children: [
      Wrap(spacing: 12, children: [Text(c.pack.t(label), style: Theme.of(context).textTheme.titleMedium),
        if (count.isNotEmpty) Text(count, style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant))]),
      const SizedBox(height: 4), Text(amount, style: Theme.of(context).textTheme.headlineSmall?.copyWith(color: color, fontWeight: FontWeight.w700)),
    ]);

  Widget _chip(String label) => Container(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
    decoration: BoxDecoration(border: Border.all(color: Theme.of(context).colorScheme.outlineVariant), borderRadius: BorderRadius.circular((Theme.of(context).extension<LifeSurfaces>()?.radius ?? 20) * .7)),
    child: Row(mainAxisSize: MainAxisSize.min, children: [Text(label, style: TextStyle(fontSize: _tab == 0 ? 11 : 14, fontWeight: FontWeight.w600)),
      const SizedBox(width: 3), const Icon(Icons.keyboard_arrow_down, size: 14)]));

  Widget _metric(String key, String amount, String count, Color color) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 5),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(c.pack.t(key), style: const TextStyle(fontSize: 10)),
      const SizedBox(height: 3),
      FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.centerLeft,
        child: Text(amount, style: TextStyle(color: color, fontSize: 14, fontWeight: FontWeight.w800))),
      if (count.isNotEmpty) Text(count, maxLines: 1, overflow: TextOverflow.ellipsis,
        style: const TextStyle(fontSize: 9, color: LifePalette.muted)),
    ]));

  Widget _quickActions() => LifeCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    _sectionTitle('quick_add'), const SizedBox(height: 10), _actionGrid(detailed: false),
  ]));

  Widget _actionGrid({required bool detailed}) => LayoutBuilder(builder: (context, constraints) {
    if (!detailed) { return Row(children: [for (final kind in EntryKind.values) Expanded(child: Padding(
      padding: const EdgeInsets.symmetric(horizontal: 3), child: _actionTile(kind, detailed: false)))]); }
    return Column(children: [
      Row(children: [Expanded(child: _actionTile(EntryKind.expense, detailed: true)), const SizedBox(width: 8), Expanded(child: _actionTile(EntryKind.income, detailed: true))]),
      const SizedBox(height: 8),
      Row(children: [Expanded(child: _actionTile(EntryKind.task, detailed: true)), const SizedBox(width: 8), Expanded(child: _actionTile(EntryKind.note, detailed: true))]),
    ]);
  });

  Widget _actionTile(EntryKind kind, {required bool detailed}) {
    final colors = _kindColors(kind);
    final background = Theme.of(context).brightness == Brightness.dark
      ? Color.alphaBlend(colors.foreground.withValues(alpha: .13), Theme.of(context).colorScheme.surface)
      : colors.background;
    return Material(color: background, borderRadius: BorderRadius.circular((Theme.of(context).extension<LifeSurfaces>()?.radius ?? 20) * .65),
      child: InkWell(key: Key('quick_${kind.name}'), onTap: () => _add(kind), borderRadius: BorderRadius.circular((Theme.of(context).extension<LifeSurfaces>()?.radius ?? 20) * .65),
        child: Padding(padding: EdgeInsets.all(detailed ? 9 : 7), child: detailed
          ? Row(children: [
              CircleAvatar(radius: 17, backgroundColor: colors.foreground.withValues(alpha: .12),
                child: Icon(_kindIcon(kind), color: colors.foreground, size: 19)),
              const SizedBox(width: 6),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(c.pack.t('create_${kind.name}'), maxLines: 2, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700)),
                Text(c.pack.t('example_${kind.name}'), maxLines: 1, overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 9, color: LifePalette.muted)),
              ])),
            ])
          : Column(children: [
              Icon(_kindIcon(kind), color: colors.foreground, size: 23),
              const SizedBox(height: 7),
              Text(c.pack.t(kind.name), maxLines: 1, overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w600)),
            ]))));
  }

  Widget _tasksCard(List<Record> tasks) => LifeCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    _sectionTitle('my_tasks', action: 'all_tasks', onTap: () => _navigate(1)),
    const SizedBox(height: 6),
    if (tasks.isEmpty) _cardEmpty('empty_tasks', EntryKind.task),
    for (final task in tasks) _taskRow(task),
  ]));

  Widget _notesCard(List<Record> notes) => LifeCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    _sectionTitle('recent_notes', action: 'all_notes', onTap: () => _entriesPage(EntryKind.note)),
    const SizedBox(height: 6),
    if (notes.isEmpty) _cardEmpty('empty_notes', EntryKind.note),
    for (final note in notes) _noteRow(note),
  ]));

  Widget _sectionTitle(String key, {String? action, VoidCallback? onTap}) => Row(children: [
    Expanded(child: Text(c.pack.t(key), style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800))),
    if (action != null) InkWell(onTap: onTap, child: Row(children: [
      Text(c.pack.t(action), style: TextStyle(fontSize: 11, color: Theme.of(context).colorScheme.primary)),
      Icon(Icons.chevron_right, size: 15, color: Theme.of(context).colorScheme.primary),
    ])),
  ]);

  Widget _cardEmpty(String key, EntryKind kind) => Padding(padding: const EdgeInsets.symmetric(vertical: 7),
    child: Row(children: [Expanded(child: Text(c.pack.t(key), style: const TextStyle(fontSize: 12, color: LifePalette.muted))),
      IconButton(tooltip: c.pack.t('create_${kind.name}'), onPressed: () => _add(kind), icon: const Icon(Icons.add_circle_outline))]));

  Widget _taskRow(Record task) => Container(
    constraints: const BoxConstraints(minHeight: 48),
    decoration: BoxDecoration(border: Border(bottom: BorderSide(color: Theme.of(context).dividerColor.withValues(alpha: .35)))),
    child: Row(children: [
      SizedBox(width: 35, child: Checkbox(key: Key('task_${task.id}'), value: task.completed, visualDensity: VisualDensity.compact,
        onChanged: c.pendingTasks.contains(task.id) ? null : (value) => _complete(task, value!))),
      const SizedBox(width: 5),
      Expanded(child: InkWell(onTap: () => _showRecord(task.id), child: Padding(padding: const EdgeInsets.symmetric(vertical: 10),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(task.text, maxLines: 2, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: _tab == 0 ? 13 : 16, decoration: task.completed ? TextDecoration.lineThrough : null)),
          if (c.scheduleFor(task) case final CalendarEntry entry) Text(entry.schedule.localStart.replaceFirst('T',' '), style: TextStyle(fontSize: _tab == 0 ? 10 : 13, color: Theme.of(context).colorScheme.onSurfaceVariant)),
        ])))),
    ]));

  Widget _noteRow(Record note) => InkWell(onTap: () => _showNote(note),
    child: Padding(padding: const EdgeInsets.symmetric(vertical: 7), child: Row(children: [
      const CircleAvatar(radius: 17, backgroundColor: LifePalette.mint,
        child: Icon(Icons.description_outlined, color: LifePalette.green, size: 18)),
      const SizedBox(width: 9),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(_firstLine(note.text), maxLines: 1, overflow: TextOverflow.ellipsis,
          style: TextStyle(fontSize: _tab == 0 ? 12 : 16, fontWeight: FontWeight.w700)),
        if (note.text.contains('\n')) Text(note.text.substring(note.text.indexOf('\n') + 1).trim(),
          maxLines: 2, overflow: TextOverflow.ellipsis,
          style: TextStyle(fontSize: _tab == 0 ? 11 : 14, color: Theme.of(context).colorScheme.onSurfaceVariant)),
      ])),
      const SizedBox(width: 5),
      Text(MaterialLocalizations.of(context).formatShortDate(note.createdAt.toLocal()),
        style: const TextStyle(fontSize: 10, color: LifePalette.muted)),
    ])));

  String _firstLine(String value) => value.split('\n').first;

  void _showRecord(String id) { Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => RecordDetail(controller: c, id: id))); }
  void _showNote(Record note) => _showRecord(note.id);

  List<Widget> _entries(EntryKind kind) {
    final records = c.records.where((r) => r.kind == kind).toList();
    final open = records.where((r) => !r.completed).toList();
    final completed = records.where((r) => r.completed).toList();
    return [
      _pageTitle(kind == EntryKind.task ? 'my_tasks' : 'recent_notes'),
      const SizedBox(height: 14),
      if (records.isEmpty) LifeCard(child: _cardEmpty(kind == EntryKind.task ? 'empty_tasks' : 'empty_notes', kind)),
      if (kind == EntryKind.task && open.isNotEmpty) ...[
        _sectionTitle('open_tasks'), const SizedBox(height: 8),
        for (final record in open) Padding(padding: const EdgeInsets.only(bottom: 8), child: LifeCard(child: _taskRow(record))),
      ],
      if (kind == EntryKind.task && completed.isNotEmpty) ...[
        const SizedBox(height: 12), _sectionTitle('completed_tasks'), const SizedBox(height: 8),
        for (final record in completed) Padding(padding: const EdgeInsets.only(bottom: 8), child: LifeCard(child: _taskRow(record))),
      ],
      if (kind == EntryKind.note) for (final record in records)
        Padding(padding: const EdgeInsets.only(bottom: 8), child: LifeCard(child: _noteRow(record))),
      const SizedBox(height: 14),
      FilledButton.icon(onPressed: () => _add(kind), icon: const Icon(Icons.add), label: Text(c.pack.t('create_${kind.name}'))),
    ];
  }

  List<Widget> _finance() {
    final records = financialPeriod.records(c.records, currency: summaryCurrency)..sort((a,b) => b.date!.compareTo(a.date!));
    return [
      _pageTitle('finances'),
      const SizedBox(height: 14),
      _financeSummary(),
      const SizedBox(height: 12),
      LifeCard(child: Row(children: [
        Expanded(child: _actionTile(EntryKind.expense, detailed: true)),
        const SizedBox(width: 8),
        Expanded(child: _actionTile(EntryKind.income, detailed: true)),
      ])),
      const SizedBox(height: 12),
      Text(c.pack.t('no_account_hint'), style: Theme.of(context).textTheme.bodySmall?.copyWith(color: LifePalette.muted)),
      const SizedBox(height: 12),
      if (records.isEmpty) LifeCard(child: Text(c.pack.t('empty_money'))),
      for (final record in records) Padding(padding: const EdgeInsets.only(bottom: 8), child: InkWell(onTap: () => _showRecord(record.id), child: LifeCard(child: Row(children: [
        CircleAvatar(backgroundColor: _kindColors(record.kind).background,
          child: Icon(_kindIcon(record.kind), color: _kindColors(record.kind).foreground)),
        const SizedBox(width: 10),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(record.text.isEmpty ? c.pack.t(record.kind.name) : record.text, maxLines: 2, overflow: TextOverflow.ellipsis),
          Text(record.date == null ? '' : MaterialLocalizations.of(context).formatMediumDate(DateTime.parse(record.date!)), style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 13)),
        ])),
        Flexible(child: Text(formatMoney(record.currency!, record.amountMinor!, locale: c.region), textAlign: TextAlign.right,
          style: TextStyle(color: _kindColors(record.kind).foreground, fontWeight: FontWeight.w700))),
      ])))),
    ];
  }

  List<Widget> _modules() => [
    _pageTitle('modules'), const SizedBox(height: 14),
    LifeCard(child: Material(type: MaterialType.transparency, child: ListTile(contentPadding: EdgeInsets.zero,
      leading: const CircleAvatar(backgroundColor: LifePalette.cream,
        child: Icon(Icons.description_outlined, color: LifePalette.orange)),
      title: Text(c.pack.t('recent_notes')), subtitle: Text(c.pack.t('notes_module_hint')),
      trailing: const Icon(Icons.chevron_right), onTap: () => _entriesPage(EntryKind.note)))),
  ];

  void _entriesPage(EntryKind kind) => setState(() {
    _profileOpen = false;
    _tab = kind == EntryKind.note ? 3 : 1;
    _notesOpen = kind == EntryKind.note;
  });

  List<Widget> _profile() => [_pageTitle('profile'), const SizedBox(height: 14), PersonalSettings(controller: c)];

  Widget _pageTitle(String key) => Text(c.pack.t(key),
    style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800));

  void _showSearch() {
    showSearch<void>(context: context, delegate: _RecordSearch(c));
  }

  KindColors _kindColors(EntryKind kind) => switch (kind) {
    EntryKind.expense => const KindColors(LifePalette.red, LifePalette.rose),
    EntryKind.income => const KindColors(LifePalette.green, LifePalette.mint),
    EntryKind.task => const KindColors(LifePalette.blue, LifePalette.ice),
    EntryKind.note => const KindColors(LifePalette.orange, LifePalette.cream),
  };

  IconData _kindIcon(EntryKind kind) => switch (kind) {
    EntryKind.expense => Icons.remove_circle_rounded,
    EntryKind.income => Icons.add_circle_rounded,
    EntryKind.task => Icons.check_box_rounded,
    EntryKind.note => Icons.notes_rounded,
  };
}

class _RecordSearch extends SearchDelegate<void> {
  _RecordSearch(this.controller);
  final AppController controller;
  @override
  String get searchFieldLabel => controller.pack.t('search');
  @override
  List<Widget> buildActions(BuildContext context) => [IconButton(onPressed: () => query = '', icon: const Icon(Icons.clear))];
  @override
  Widget buildLeading(BuildContext context) => IconButton(onPressed: () => close(context, null), icon: const Icon(Icons.arrow_back));
  @override
  Widget buildResults(BuildContext context) => buildSuggestions(context);
  @override
  Widget buildSuggestions(BuildContext context) {
    final records = query.trim().isEmpty ? <Record>[] : controller.records.where((r) =>
      r.text.toLowerCase().contains(query.trim().toLowerCase())).toList();
    return ListView(children: [
      if (query.trim().isEmpty) ListTile(title: Text(controller.pack.t('search_hint'))),
      if (query.trim().isNotEmpty && records.isEmpty) ListTile(title: Text(controller.pack.t('search_empty'))),
      for (final record in records) ListTile(
        title: Text(record.text.isEmpty ? controller.pack.t(record.kind.name) : record.text, maxLines: 2),
        subtitle: Text(controller.pack.t(record.kind.name)),
        onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => RecordDetail(controller: controller, id: record.id))),
      ),
    ]);
  }
}
