import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../domain/models.dart';
import '../domain/financial_period.dart';
import '../localization/language_pack.dart';
import 'design.dart';
import 'quick_add.dart';
import 'money_format.dart';
import 'financial_overview.dart';
import 'calendar.dart';
import 'calendar_panel.dart';
import 'record_detail.dart';
import 'settings.dart';
import 'finance_foundation.dart';
import 'notices.dart';
import 'selection.dart';
import 'personal_modules.dart';
import 'dashboard_editor.dart';
import 'module_calendar_route.dart';
import 'family.dart';
import 'family_dashboard.dart';
import 'global_search.dart';

class LifeOSApp extends StatefulWidget {
  const LifeOSApp({super.key, required this.controller, this.builder});
  final AppController controller;
  final TransitionBuilder? builder;
  @override
  State<LifeOSApp> createState() => _LifeOSAppState();
}

class _LifeOSAppState extends State<LifeOSApp> {
  final notices = LifeNotices();
  late final navigationObserver = NoticeNavigationObserver(notices);
  AppController get controller => widget.controller;
  @override
  void dispose() {
    notices.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: controller.presentation,
    builder: (context, _) {
      return MaterialApp(
        title: 'ULADIM',
        debugShowCheckedModeBanner: false,
        scaffoldMessengerKey: notices.messengerKey,
        navigatorObservers: [navigationObserver],
        builder: (context, child) => LifeNoticeScope(
          notices: notices,
          child: widget.builder?.call(context, child) ?? child!,
        ),
        themeAnimationDuration:
            WidgetsBinding
                .instance
                .platformDispatcher
                .accessibilityFeatures
                .disableAnimations
            ? Duration.zero
            : const Duration(milliseconds: 180),
        locale: controller.pack.locale,
        supportedLocales: {
          for (final p in controller.catalog.packs.values) p.locale,
          Locale(controller.region),
        }.toList(),
        localizationsDelegates: [
          MaterialFallbackDelegate(formatLocale: controller.region),
          const WidgetsFallbackDelegate(),
          const CupertinoFallbackDelegate(),
        ],
        theme: lifeTheme(
          Brightness.light,
          appearance: controller.appearance,
          wallpaperSeed: controller.wallpaperSeed == null
              ? null
              : Color(controller.wallpaperSeed!),
        ),
        darkTheme: lifeTheme(
          Brightness.dark,
          appearance: controller.appearance,
          wallpaperSeed: controller.wallpaperSeed == null
              ? null
              : Color(controller.wallpaperSeed!),
        ),
        themeMode: switch (controller.theme) {
          'light' => ThemeMode.light,
          'dark' => ThemeMode.dark,
          _ => ThemeMode.system,
        },
        home: HomeShell(controller: controller),
      );
    },
  );
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
  String _moduleQuery = '';
  DateTimeRange _period = DateTimeRange(
    start: DateTime(DateTime.now().year, DateTime.now().month),
    end: DateTime(DateTime.now().year, DateTime.now().month + 1, 0),
  );
  FinancialPeriod get financialPeriod =>
      FinancialPeriod(_period.start, _period.end);
  String get summaryCurrency {
    final codes =
        financialPeriod
            .records(c.records)
            .map((r) => r.currency!.code)
            .followedBy(
              (c.offline[OfflineTable.accounts] ?? []).map(
                (a) => a['currency'] as String,
              ),
            )
            .toSet()
            .toList()
          ..sort();
    return codes.contains(_summaryCurrency)
        ? _summaryCurrency!
        : codes.contains(c.currency)
        ? c.currency
        : codes.firstOrNull ?? c.currency;
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    c.addListener(_dataChanged);
    c.family?.addListener(_dataChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) => _resume());
  }

  @override
  void dispose() {
    c.family?.removeListener(_dataChanged);
    c.removeListener(_dataChanged);
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  void _dataChanged() {
    if (mounted) setState(() {});
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _resume();
  }

  Future<void> _resume() async {
    if (!c.native.supported) return;
    try {
      await c.refresh(forceReminders: true);
      final id = await c.native.launchTarget();
      if (!mounted || id == null) return;
      final entry = c.calendar.where((e) => e.id == id).firstOrNull;
      if (entry == null) return;
      final module = calendarModule(c, entry.id);
      if (module != null) {
        await openModuleCalendar(context, c, module);
        return;
      }
      final source = entry.taskId ?? entry.noteId;
      if (source != null) {
        _showRecord(source);
      } else {
        await showModalBottomSheet<void>(
          context: context,
          useSafeArea: true,
          isScrollControlled: true,
          builder: (_) => EventEditor(
            controller: c,
            date: DateTime.parse(entry.schedule.localStart),
            entry: entry,
          ),
        );
      }
    } catch (_) {
      _message('read_failed');
    }
  }

  String? _summaryCurrency;
  AppController get c => widget.controller;
  static const _tabs = ['today', 'plans', 'finances', 'modules'];
  static const _icons = [
    Icons.home_rounded,
    Icons.format_list_bulleted_rounded,
    Icons.bar_chart_rounded,
    Icons.grid_view_rounded,
  ];

  void _message(String key) {
    if (mounted) LifeNoticeScope.of(context).show(c.pack.t(key));
  }

  bool get familyMode =>
      c.preferences['active_scope'] == 'family' &&
      c.family?.verified == true &&
      c.family?.workspace != null;
  Future<void> _workspace() async {
    final f = c.family;
    await showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (ctx) => SafeArea(
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                title: Text(c.pack.t('personal_space')),
                leading: const Icon(Icons.person_outline),
                selected: !familyMode,
                onTap: () async {
                  await c.preference('active_scope', 'personal');
                  if (ctx.mounted) Navigator.pop(ctx);
                },
              ),
              if (f?.verified == true)
                for (final space in f!.spaces)
                  ListTile(
                    title: Text(space['name'] as String),
                    leading: const Icon(Icons.people_outline),
                    selected: familyMode && f.workspace == space['id'],
                    onTap: f.busy
                        ? null
                        : () async {
                            await f.select(space['id'] as String);
                            if (f.workspace == space['id']) {
                              await c.preference('active_scope', 'family');
                            }
                            if (ctx.mounted) Navigator.pop(ctx);
                          },
                  ),
              if (f != null)
                ListTile(
                  title: Text(c.pack.t('family_account')),
                  leading: const Icon(Icons.manage_accounts_outlined),
                  onTap: () {
                    Navigator.pop(ctx);
                    Navigator.push<void>(
                      context,
                      MaterialPageRoute(
                        builder: (_) => FamilyPage(controller: f, pack: c.pack),
                      ),
                    );
                  },
                ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _add(EntryKind kind) async {
    if (familyMode) {
      await Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => FamilyRecordEditor(
            controller: c.family!,
            pack: c.pack,
            initialKind: kind == EntryKind.expense || kind == EntryKind.income
                ? 'transaction'
                : kind.name,
            initialFlow: kind == EntryKind.income ? 'income' : 'expense',
          ),
        ),
      );
      return;
    }

    final saved = await showEntryEditor(context, c, kind);
    if (saved == true) {
      try {
        await c.refresh();
      } catch (_) {
        _message('read_failed');
      }
    }
  }

  void _chooseAdd() {
    showModalBottomSheet<void>(
      context: context,
      sheetAnimationStyle: MediaQuery.disableAnimationsOf(context)
          ? AnimationStyle.noAnimation
          : null,
      backgroundColor: Theme.of(context).colorScheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetContext) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                c.pack.t('quick_add'),
                style: Theme.of(context).textTheme.titleLarge
                    ?.copyWith(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 16),
              _actionGrid(detailed: false, sheetContext: sheetContext),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _complete(Record record, bool value) async {
    if (c.pendingTasks.contains(record.id)) return;
    setState(() => c.pendingTasks.add(record.id));
    var saved = false;
    try {
      await c.completeTask(record.id, value);
      saved = true;
      await c.refresh();
    } on DomainFailure catch (error) {
      _message(saved ? 'read_failed' : error.key);
    } catch (_) {
      _message(saved ? 'read_failed' : 'change_failed');
    } finally {
      if (mounted) setState(() => c.pendingTasks.remove(record.id));
    }
  }

  void _navigate(int tab) {
    LifeNoticeScope.of(context).clear();
    setState(() {
      _tab = tab;
      _profileOpen = false;
      _notesOpen = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final wide = width >= 720;
    final items = <Widget>[
      _header(),
      const SizedBox(height: 18),
      if (_profileOpen)
        ..._profile()
      else if (familyMode)
        FamilyDashboard(controller: c, tab: _tab)
      else if (_tab == 0)
        ..._home()
      else if (_tab == 1) ...[
        CalendarPanel(controller: c),
        const SizedBox(height: 18),
        ..._entries(EntryKind.task),
      ] else if (_tab == 2)
        ..._finance()
      else if (_notesOpen)
        ..._entries(EntryKind.note)
      else
        ..._modules(),
    ];
    final content = ListView.builder(
      key: Key(_profileOpen ? 'profile_page' : _tabs[_tab]),
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      padding: EdgeInsets.fromLTRB(
        width < 350 ? 14 : 18,
        8,
        width < 350 ? 14 : 18,
        26,
      ),
      itemCount: items.length,
      itemBuilder: (_, index) => items[index],
    );
    return PopScope(
      canPop: _tab == 0 && !_profileOpen && !_notesOpen,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _navigate(0);
      },
      child: Scaffold(
        body: SafeArea(
          child: Row(
            children: [
              if (wide)
                NavigationRail(
                  selectedIndex: _tab,
                  onDestinationSelected: _navigate,
                  labelType: NavigationRailLabelType.all,
                  backgroundColor: Theme.of(context).colorScheme.surface,
                  destinations: [
                    for (var i = 0; i < _tabs.length; i++)
                      NavigationRailDestination(
                        icon: Icon(_icons[i]),
                        label: Text(c.pack.t(_tabs[i])),
                      ),
                  ],
                ),
              Expanded(
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 560),
                    child: AnimatedSwitcher(
                      duration: MediaQuery.disableAnimationsOf(context)
                          ? Duration.zero
                          : const Duration(milliseconds: 180),
                      child: content,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
        bottomNavigationBar: wide ? null : _bottomBar(),
        floatingActionButtonLocation: FloatingActionButtonLocation.endFloat,
        floatingActionButton: wide ? _addButton() : null,
      ),
    );
  }

  Widget _header() => Row(
    children: [
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            GestureDetector(
              onTap: () => _navigate(0),
              child: Text.rich(
                TextSpan(
                  children: [
                    TextSpan(
                      text: 'ULA',
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.onSurface,
                      ),
                    ),
                    TextSpan(
                      text: 'DIM',
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.primary,
                      ),
                    ),
                  ],
                ),
                style: const TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -.8,
                ),
              ),
            ),
            if (c.family == null)
              Text(
                c.pack.t('personal_space'),
                style: Theme.of(context).textTheme.bodySmall,
              )
            else
              TextButton.icon(
                key: const Key('workspace_switcher'),
                onPressed: _workspace,
                icon: Icon(
                  familyMode ? Icons.people_outline : Icons.person_outline,
                  size: 16,
                ),
                label: Text(
                  familyMode
                      ? (c.family!.spaces
                                    .where(
                                      (s) => s['id'] == c.family!.workspace,
                                    )
                                    .firstOrNull?['name']
                                as String? ??
                            c.pack.t('family_account'))
                      : c.pack.t('personal_space'),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
          ],
        ),
      ),
      IconButton(
        tooltip: c.pack.t('search'),
        onPressed: _showSearch,
        icon: const Icon(Icons.search_rounded),
      ),
      const SizedBox(width: 3),
      IconButton(
        key: const Key('profile_button'),
        tooltip: c.pack.t('profile'),
        onPressed: () {
          LifeNoticeScope.of(context).clear();
          setState(() => _profileOpen = true);
        },
        icon: CircleAvatar(
          radius: 19,
          backgroundColor: Theme.of(context).colorScheme.primaryContainer,
          child: Icon(
            Icons.person_rounded,
            size: 23,
            color: Theme.of(context).colorScheme.primary,
          ),
        ),
      ),
    ],
  );

  Widget _addButton() => Container(
    width: 58,
    height: 58,
    decoration: BoxDecoration(
      shape: BoxShape.circle,
      boxShadow: [
        BoxShadow(
          color: LifePalette.darkGreen.withValues(alpha: .16),
          blurRadius: 10,
          offset: const Offset(0, 3),
        ),
      ],
    ),
    child: FloatingActionButton(
      key: const Key('add_button'),
      onPressed: _chooseAdd,
      backgroundColor: Theme.of(context).colorScheme.primary,
      foregroundColor: Theme.of(context).colorScheme.onPrimary,
      shape: const CircleBorder(side: BorderSide.none),
      elevation: 0,
      focusElevation: 0,
      hoverElevation: 0,
      highlightElevation: 0,
      child: const Icon(Icons.add, size: 32),
    ),
  );

  Widget _bottomBar() {
    final surface = Theme.of(context).colorScheme.surface;
    final inactive = Theme.of(context).colorScheme.onSurfaceVariant;
    final width = MediaQuery.sizeOf(context).width;
    final scaler = MediaQuery.textScalerOf(context);
    double labelWidth = 0;
    double labelHeight = 0;
    for (final tab in _tabs) {
      final painter = TextPainter(
        text: TextSpan(
          text: c.pack.t(tab),
          style: Theme.of(context).textTheme.labelMedium
              ?.copyWith(fontSize: 12, fontWeight: FontWeight.w700),
        ),
        textDirection: Directionality.of(context),
        textScaler: scaler,
      )..layout();
      if (painter.width > labelWidth) labelWidth = painter.width;
      if (painter.height > labelHeight) labelHeight = painter.height;
      painter.dispose();
    }
    // Give labels a whole row before they would wrap inside a single word.
    final roomy = labelWidth + 12 > (width - 64) / 4;
    final rowHeight = (labelHeight + 41).clamp(64.0, 160.0);
    if (roomy && labelWidth + 44 <= (width - 64) / 2) {
      final compactHeight = (labelHeight + 24).clamp(48.0, 140.0);
      return BottomAppBar(
        height: compactHeight * 2,
        padding: EdgeInsets.zero,
        color: surface,
        child: Row(
          children: [
            Expanded(
              child: Column(
                children: [
                  for (var row = 0; row < 2; row++)
                    SizedBox(
                      height: compactHeight,
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          for (var i = row * 2; i < row * 2 + 2; i++)
                            Expanded(
                              child: _navItem(i, inactive, horizontal: true),
                            ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
            SizedBox(width: 64, child: Center(child: _addButton())),
          ],
        ),
      );
    }
    return BottomAppBar(
      height: roomy ? rowHeight * 2 + 64 : 80,
      padding: EdgeInsets.zero,
      color: surface,
      child: roomy
          ? Column(
              children: [
                for (var row = 0; row < 2; row++)
                  SizedBox(
                    height: rowHeight,
                    child: Row(
                      children: [
                        for (var i = row * 2; i < row * 2 + 2; i++)
                          Expanded(child: _navItem(i, inactive)),
                      ],
                    ),
                  ),
                SizedBox(height: 64, child: Center(child: _addButton())),
              ],
            )
          : Row(
              children: [
                for (var i = 0; i < 2; i++)
                  Expanded(child: _navItem(i, inactive)),
                SizedBox(width: 64, child: Center(child: _addButton())),
                for (var i = 2; i < 4; i++)
                  Expanded(child: _navItem(i, inactive)),
              ],
            ),
    );
  }

  Widget _navItem(int i, Color inactive, {bool horizontal = false}) {
    final active = !_profileOpen && _tab == i;
    final color = active ? Theme.of(context).colorScheme.primary : inactive;
    final label = Text(
      c.pack.t(_tabs[i]),
      textAlign: TextAlign.center,
      style: Theme.of(context).textTheme.labelMedium?.copyWith(
        color: color,
        fontSize: 12,
        fontWeight: active ? FontWeight.w700 : FontWeight.w500,
      ),
    );
    return Semantics(
      selected: active,
      button: true,
      child: InkWell(
        key: Key('nav_${_tabs[i]}'),
        onTap: () => _navigate(i),
        child: horizontal
            ? Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8),
                child: Row(
                  children: [
                    Icon(_icons[i], size: 22, color: color),
                    const SizedBox(width: 6),
                    Expanded(child: label),
                  ],
                ),
              )
            : Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(_icons[i], size: 22, color: color),
                  const SizedBox(height: 3),
                  label,
                ],
              ),
      ),
    );
  }

  List<Record> _dailyTasks() {
    final now = c.now;
    final tasks = c.records
        .where((r) => r.kind == EntryKind.task && !r.completed)
        .toList();
    final dates = <String, DateTime?>{};
    for (final task in tasks) {
      final entry = c.scheduleFor(task);
      if (entry == null) {
        dates[task.id] = null;
        continue;
      }
      final due = c.calendarEngine.completionOccurrence(
        entry,
        now,
        c.deviceZone,
      );
      final done =
          due != null &&
          c.occurrences.any(
            (s) =>
                s.entryId == entry.id &&
                s.revision == entry.revision &&
                s.epoch == due.at.millisecondsSinceEpoch &&
                s.status == OccurrenceStatus.completed,
          );
      dates[task.id] = done
          ? c.calendarEngine.next(entry, now, c.deviceZone, c.occurrences)?.at
          : due?.at;
    }
    int priority(Record record) {
      final at = dates[record.id];
      if (at == null) {
        return 2;
      }
      if (!at.isAfter(now)) {
        return 0;
      }
      if (dateOnly(at.toLocal()) == dateOnly(now)) {
        return 1;
      }
      return 3;
    }

    tasks.sort((a, b) {
      final order = priority(a).compareTo(priority(b));
      if (order != 0) {
        return order;
      }
      final left = dates[a.id], right = dates[b.id];
      if (left != null && right != null) {
        return left.compareTo(right);
      }
      return a.createdAt.compareTo(b.createdAt);
    });
    return tasks;
  }

  List<Widget> _home() {
    final now = c.now;
    final config = [for (final key in dashboardWidgets) dashboardChoice(c, key)]
      ..sort((a, b) {
        final order = (a['position'] as int).compareTo(b['position'] as int);
        return order == 0
            ? (a['widget'] as String).compareTo(b['widget'] as String)
            : order;
      });
    final tasks = _dailyTasks();
    final notes = c.records.where((r) => r.kind == EntryKind.note);
    Widget card(Map<String, Object?> row) {
      final expanded = row['expanded'] == 1, key = row['widget'] as String;
      if (key == 'financial') return _financeSummary();
      if (key == 'tasks') {
        return _tasksCard(tasks.take(expanded ? 3 : 1).toList());
      }
      if (key == 'notes') {
        return _notesCard(notes.take(expanded ? 2 : 1).toList());
      }
      final table = switch (key) {
        'projects' => OfflineTable.projects,
        'habits' => OfflineTable.habits,
        _ => OfflineTable.checklists,
      };
      final rows = (c.offline[table] ?? []).where(
        (r) => key != 'shopping' || r['kind'] == 'shopping',
      );
      return LifeCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(c.pack.t('widget_$key')),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.push<void>(
                context,
                MaterialPageRoute(
                  builder: (_) =>
                      PersonalModulesPage(controller: c, table: table),
                ),
              ),
            ),
            for (final r in rows.take(expanded ? 3 : 1))
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Text(r['name'] as String),
              ),
            if (rows.isEmpty) Text(c.pack.t('offline_empty')),
          ],
        ),
      );
    }

    final content = <Widget>[
      _pageTitle('today'),
      const SizedBox(height: 4),
      Text(
        MaterialLocalizations.of(context).formatMediumDate(now),
        style: Theme.of(context).textTheme.bodyMedium,
      ),
      const SizedBox(height: 12),
    ];
    for (final row in config.where((r) => r['visible'] == 1)) {
      content.addAll([card(row), const SizedBox(height: 12)]);
    }
    return content;
  }

  Widget _financeSummary() => FinancialOverview(
    key: const Key('home_financial_summary'),
    controller: c,
    period: financialPeriod,
    currency: summaryCurrency,
    compact: _tab == 0,
    onCurrency: (v) => setState(() => _summaryCurrency = v),
    onPeriod: () async {
      final result = await selectFinancialPeriod(context, c, _period);
      if (result != null && mounted) setState(() => _period = result);
    },
    onRecord: (r) => _showRecord(r.id),
    onAdd: _add,
  );

  Widget _actionGrid({required bool detailed, BuildContext? sheetContext}) =>
      LayoutBuilder(
        builder: (context, constraints) {
          final columns =
              !detailed &&
                  constraints.maxWidth >= 500 &&
                  MediaQuery.textScalerOf(context).scale(1) <= 1.2
              ? 4
              : 2;
          final kinds = EntryKind.values
              .where(
                (kind) =>
                    !familyMode ||
                    c.family!.roster?['space']?['role'] != 'child' ||
                    kind != EntryKind.income &&
                        c.family!.creatableKinds.contains(
                          kind == EntryKind.expense ? 'transaction' : kind.name,
                        ),
              )
              .toList();
          return Column(
            children: [
              for (var start = 0; start < kinds.length; start += columns) ...[
                if (start > 0) const SizedBox(height: 10),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (
                      var i = start;
                      i < start + columns && i < kinds.length;
                      i++
                    ) ...[
                      if (i > start) const SizedBox(width: 10),
                      Expanded(
                        child: _actionTile(
                          kinds[i],
                          detailed: detailed,
                          onTap: sheetContext == null
                              ? null
                              : () {
                                  Navigator.pop(sheetContext);
                                  _add(kinds[i]);
                                },
                        ),
                      ),
                    ],
                  ],
                ),
              ],
            ],
          );
        },
      );

  Widget _actionTile(
    EntryKind kind, {
    required bool detailed,
    VoidCallback? onTap,
  }) {
    final colors = _kindColors(kind);
    final theme = Theme.of(context);
    final foreground = lifeAccent(context, colors.foreground);
    final background = theme.brightness == Brightness.dark
        ? Color.alphaBlend(
            foreground.withValues(alpha: .12),
            theme.colorScheme.surface,
          )
        : colors.background;
    final radius = BorderRadius.circular(
      theme.extension<LifeSurfaces>()?.radius ?? 20,
    );
    return Material(
      color: background,
      shape: RoundedRectangleBorder(
        borderRadius: radius,
        side: BorderSide(color: foreground.withValues(alpha: .12)),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        key: Key('quick_${kind.name}'),
        onTap: onTap ?? () => _add(kind),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 84),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Icon(_kindIcon(kind), color: foreground, size: 26),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        c.pack.t(kind.name),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: theme.textTheme.labelLarge?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      if (detailed) ...[
                        const SizedBox(height: 4),
                        Text(
                          c.pack.t('example_${kind.name}'),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _tasksCard(List<Record> tasks) => LifeCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle(
          'my_tasks',
          action: 'all_tasks',
          onTap: () => _navigate(1),
        ),
        const SizedBox(height: 6),
        if (tasks.isEmpty) _cardEmpty('empty_tasks', EntryKind.task),
        for (final task in tasks) _taskRow(task),
      ],
    ),
  );

  Widget _notesCard(List<Record> notes) => LifeCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle(
          'recent_notes',
          action: 'all_notes',
          onTap: () => _entriesPage(EntryKind.note),
        ),
        const SizedBox(height: 6),
        if (notes.isEmpty) _cardEmpty('empty_notes', EntryKind.note),
        for (final note in notes) _noteRow(note),
      ],
    ),
  );

  Widget _sectionTitle(
    String key, {
    String? action,
    VoidCallback? onTap,
  }) => LayoutBuilder(
    builder: (context, bounds) {
      const titleStyle = TextStyle(fontSize: 15, fontWeight: FontWeight.w800);
      final actionStyle = TextStyle(
        fontSize: 13,
        color: Theme.of(context).colorScheme.primary,
      );
      final title = Text(c.pack.t(key), style: titleStyle);
      if (action == null) return title;
      double textWidth(String text, TextStyle style) {
        final painter = TextPainter(
          text: TextSpan(
            text: text,
            style: DefaultTextStyle.of(context).style.merge(style),
          ),
          textDirection: Directionality.of(context),
          textScaler: MediaQuery.textScalerOf(context),
        )..layout();
        final width = painter.width;
        painter.dispose();
        return width;
      }

      final actionLabel = c.pack.t(action);
      final stacked =
          textWidth(c.pack.t(key), titleStyle) +
              textWidth(actionLabel, actionStyle) +
              23 >
          bounds.maxWidth;
      final actionButton = Semantics(
        button: true,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: ConstrainedBox(
            constraints: BoxConstraints(
              minHeight: 48,
              maxWidth: bounds.maxWidth,
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Flexible(child: Text(actionLabel, style: actionStyle)),
                Icon(
                  Icons.chevron_right,
                  size: 15,
                  color: Theme.of(context).colorScheme.primary,
                ),
              ],
            ),
          ),
        ),
      );
      return stacked
          ? Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                title,
                Align(alignment: Alignment.centerRight, child: actionButton),
              ],
            )
          : Row(
              children: [
                Expanded(child: title),
                const SizedBox(width: 8),
                actionButton,
              ],
            );
    },
  );

  Widget _cardEmpty(String key, EntryKind kind) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 7),
    child: Row(
      children: [
        Expanded(
          child: Text(
            c.pack.t(key),
            style: TextStyle(
              fontSize: 12,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        IconButton(
          tooltip: c.pack.t('create_${kind.name}'),
          onPressed: () => _add(kind),
          icon: const Icon(Icons.add_circle_outline),
        ),
      ],
    ),
  );

  bool _taskDone(Record task) {
    if (task.completed) return true;
    final entry = c.scheduleFor(task);
    if (entry == null || entry.schedule.repeat == RepeatRule.none) return false;
    final due = c.calendarEngine.completionOccurrence(
      entry,
      c.now,
      c.deviceZone,
    );
    return due != null &&
        c.occurrences.any(
          (s) =>
              s.entryId == entry.id &&
              s.revision == entry.revision &&
              s.epoch == due.at.millisecondsSinceEpoch &&
              s.status == OccurrenceStatus.completed,
        );
  }

  String? _taskStatus(Record task) {
    final entry = c.scheduleFor(task);
    if (entry == null || task.completed) return null;
    final due = c.calendarEngine.completionOccurrence(
      entry,
      c.now,
      c.deviceZone,
    );
    if (due == null) return null;
    if (c.occurrences.any(
      (s) =>
          s.entryId == entry.id &&
          s.revision == entry.revision &&
          s.epoch == due.at.millisecondsSinceEpoch &&
          s.status == OccurrenceStatus.completed,
    ))
      return 'task_upcoming';
    if (due.at.isBefore(c.now)) return 'task_overdue';
    return dateOnly(due.at) == dateOnly(c.now) ? 'today' : 'task_upcoming';
  }

  Widget _taskRow(Record task) => Container(
    constraints: const BoxConstraints(minHeight: 48),
    decoration: BoxDecoration(
      border: Border(
        bottom: BorderSide(
          color: Theme.of(context).dividerColor.withValues(alpha: .35),
        ),
      ),
    ),
    child: Row(
      children: [
        SizedBox(
          width: 48,
          child: Checkbox(
            key: Key('task_${task.id}'),
            value: _taskDone(task),
            visualDensity: VisualDensity.standard,
            onChanged: c.pendingTasks.contains(task.id)
                ? null
                : (value) => _complete(task, value!),
          ),
        ),
        const SizedBox(width: 5),
        Expanded(
          child: InkWell(
            onTap: () => _showRecord(task.id),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    task.text,
                    style: TextStyle(
                      fontSize: 15,
                      decoration: task.completed
                          ? TextDecoration.lineThrough
                          : null,
                    ),
                  ),
                  if (_taskStatus(task) case final String status)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(
                        c.pack.t(status),
                        style: TextStyle(
                          fontWeight: FontWeight.w600,
                          color: status == 'task_overdue'
                              ? lifeAccent(context, LifePalette.red)
                              : Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ),
                  if (c.scheduleFor(task) case final CalendarEntry entry)
                    Padding(
                      padding: const EdgeInsets.only(top: 5),
                      child: Text(
                        _scheduleLabel(entry),
                        style: TextStyle(
                          fontSize: 12,
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ],
    ),
  );

  String _scheduleLabel(CalendarEntry entry) {
    final date = DateTime.parse(entry.schedule.localStart);
    final local = MaterialLocalizations.of(context);
    return '${local.formatMediumDate(date)}${entry.schedule.allDay ? '' : ' · ${local.formatTimeOfDay(TimeOfDay.fromDateTime(date))}'}';
  }

  Widget _noteRow(Record note) => InkWell(
    onTap: () => _showNote(note),
    borderRadius: BorderRadius.circular(12),
    child: Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: 19,
            backgroundColor: Theme.of(context).colorScheme.primaryContainer,
            child: Icon(
              Icons.description_outlined,
              color: Theme.of(context).colorScheme.onPrimaryContainer,
              size: 21,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _firstLine(note.text),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (note.text.contains('\n')) ...[
                  const SizedBox(height: 5),
                  Text(
                    note.text.substring(note.text.indexOf('\n') + 1).trim(),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 14,
                      height: 1.4,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
                const SizedBox(height: 6),
                Text(
                  MaterialLocalizations.of(context)
                      .formatMediumDate(note.createdAt.toLocal()),
                  style: TextStyle(
                    fontSize: 12,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );

  String _firstLine(String value) => value.split('\n').first;

  void _showRecord(String id) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => RecordDetail(controller: c, id: id),
      ),
    );
  }

  void _showNote(Record note) => _showRecord(note.id);

  List<Widget> _entries(EntryKind kind) {
    final records = c.records.where((r) => r.kind == kind).toList();
    final open = records.where((r) => !r.completed).toList();
    final completed = records.where((r) => r.completed).toList();
    return [
      _pageTitle(kind == EntryKind.task ? 'my_tasks' : 'recent_notes'),
      const SizedBox(height: 14),
      if (records.isEmpty)
        LifeCard(
          child: _cardEmpty(
            kind == EntryKind.task ? 'empty_tasks' : 'empty_notes',
            kind,
          ),
        ),
      if (kind == EntryKind.task && open.isNotEmpty) ...[
        _sectionTitle('open_tasks'),
        const SizedBox(height: 8),
        for (final record in open)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: LifeCard(child: _taskRow(record)),
          ),
      ],
      if (kind == EntryKind.task && completed.isNotEmpty) ...[
        const SizedBox(height: 12),
        _sectionTitle('completed_tasks'),
        const SizedBox(height: 8),
        for (final record in completed)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: LifeCard(child: _taskRow(record)),
          ),
      ],
      if (kind == EntryKind.note)
        for (final record in records)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: LifeCard(child: _noteRow(record)),
          ),
      const SizedBox(height: 14),
      FilledButton.icon(
        onPressed: () => _add(kind),
        icon: const Icon(Icons.add),
        label: Text(c.pack.t('create_${kind.name}')),
      ),
    ];
  }

  List<Widget> _finance() {
    final records = financialPeriod.records(
      c.records,
      currency: summaryCurrency,
    )..sort((a, b) => b.date!.compareTo(a.date!));
    return [
      Row(
        children: [
          Expanded(child: _pageTitle('finances')),
          IconButton(
            key: const Key('finance_accounts'),
            tooltip: c.pack.t('financial_foundation'),
            icon: const Icon(Icons.account_balance_wallet_outlined),
            onPressed: () => Navigator.push<void>(
              context,
              MaterialPageRoute(
                builder: (_) => FinanceFoundation(controller: c),
              ),
            ),
          ),
        ],
      ),
      const SizedBox(height: 12),
      _financeSummary(),
      const SizedBox(height: 12),
      if (records.isEmpty) LifeCard(child: Text(c.pack.t('empty_money'))),
      for (final record in records)
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: InkWell(
            onTap: () => _showRecord(record.id),
            child: LifeCard(
              child: Row(
                children: [
                  CircleAvatar(
                    backgroundColor: _kindColors(record.kind).background,
                    child: Icon(
                      _kindIcon(record.kind),
                      color: _kindColors(record.kind).foreground,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          record.text.isEmpty
                              ? c.pack.t(record.kind.name)
                              : record.text,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        Text(
                          record.date == null
                              ? ''
                              : MaterialLocalizations.of(context)
                                    .formatMediumDate(
                                      DateTime.parse(record.date!),
                                    ),
                          style: TextStyle(
                            color: Theme.of(context)
                                .colorScheme
                                .onSurfaceVariant,
                            fontSize: 13,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Flexible(
                    child: Text(
                      formatMoney(
                        record.currency!,
                        record.amountMinor!,
                        locale: c.region,
                      ),
                      textAlign: TextAlign.right,
                      style: TextStyle(
                        color: _kindColors(record.kind).foreground,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
    ];
  }

  List<Widget> _modules() {
    final grid = c.preferences['modules_view'] != 'list';
    final modules =
        <({IconData icon, String title, String body, VoidCallback open})>[
              (
                icon: Icons.account_balance_wallet_outlined,
                title: c.pack.t('financial_foundation'),
                body: c.pack.t('ux_modules_finance'),
                open: () => Navigator.push<void>(
                  context,
                  MaterialPageRoute(
                    builder: (_) => FinanceFoundation(controller: c),
                  ),
                ),
              ),
              for (final table in personalModules)
                (
                  icon: switch (table) {
                    OfflineTable.projects => Icons.flag_outlined,
                    OfflineTable.habits => Icons.check_circle_outline,
                    OfflineTable.subjects => Icons.school_outlined,
                    OfflineTable.checklists => Icons.shopping_basket_outlined,
                    _ => Icons.favorite_outline,
                  },
                  title: c.pack.t('module_${table.name}'),
                  body: c.pack.t('ux_modules_${table.name}'),
                  open: () => Navigator.push<void>(
                    context,
                    MaterialPageRoute(
                      builder: (_) =>
                          PersonalModulesPage(controller: c, table: table),
                    ),
                  ),
                ),
              (
                icon: Icons.notes_outlined,
                title: c.pack.t('recent_notes'),
                body: c.pack.t('notes_module_hint'),
                open: () => _entriesPage(EntryKind.note),
              ),
            ]
            .where(
              (m) => '${m.title} ${m.body}'.toLowerCase().contains(
                _moduleQuery.toLowerCase(),
              ),
            )
            .toList();
    final theme = Theme.of(context);
    Widget tile(int i) {
      final m = modules[i];
      return Material(
        color: theme.colorScheme.surfaceContainerLow,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: BorderSide(color: theme.colorScheme.outlineVariant),
        ),
        child: InkWell(
          key: ValueKey('module_card_$i'),
          borderRadius: BorderRadius.circular(18),
          onTap: m.open,
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: grid
                ? Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(m.icon, color: theme.colorScheme.primary, size: 26),
                      const SizedBox(height: 10),
                      Text(
                        m.title,
                        style: theme.textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(m.body, style: theme.textTheme.bodyMedium),
                    ],
                  )
                : Row(
                    children: [
                      Icon(m.icon, color: theme.colorScheme.primary),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(m.title, style: theme.textTheme.titleMedium),
                            const SizedBox(height: 4),
                            Text(m.body, style: theme.textTheme.bodyMedium),
                          ],
                        ),
                      ),
                      const Icon(Icons.chevron_right),
                    ],
                  ),
          ),
        ),
      );
    }

    final viewToggle = IconButton(
      key: const Key('modules_view_toggle'),
      tooltip: c.pack.t(grid ? 'ux_list' : 'ux_grid'),
      onPressed: () => c.preference('modules_view', grid ? 'list' : 'grid'),
      icon: Icon(grid ? Icons.view_list_outlined : Icons.grid_view_outlined),
    );
    final largeText = MediaQuery.textScalerOf(context).scale(1) > 1.3;
    return [
      if (largeText) ...[
        _pageTitle('modules'),
        Align(alignment: Alignment.centerRight, child: viewToggle),
      ] else
        Row(
          children: [
            Expanded(child: _pageTitle('modules')),
            viewToggle,
          ],
        ),
      const SizedBox(height: 12),
      if (largeText) ...[
        Text(c.pack.t('search_modules'), style: theme.textTheme.bodyMedium),
        const SizedBox(height: 8),
      ],
      Semantics(
        label: largeText ? c.pack.t('search_modules') : null,
        child: TextField(
          decoration: InputDecoration(
            labelText: largeText ? null : c.pack.t('search_modules'),
            prefixIcon: const Icon(Icons.search),
          ),
          onChanged: (v) => setState(() => _moduleQuery = v),
        ),
      ),
      const SizedBox(height: 12),
      if (grid)
        LayoutBuilder(
          builder: (context, box) {
            final columns =
                box.maxWidth >= 280 &&
                    MediaQuery.textScalerOf(context).scale(1) <= 1.3
                ? 2
                : 1;
            final width = (box.maxWidth - 12 * (columns - 1)) / columns;
            double height = 48;
            for (final m in modules) {
              double textHeight(String text, TextStyle? style) => (TextPainter(
                text: TextSpan(text: text, style: style),
                textDirection: Directionality.of(context),
                textScaler: MediaQuery.textScalerOf(context),
              )..layout(maxWidth: width - 28)).height;
              final measured =
                  28 +
                  26 +
                  10 +
                  6 +
                  textHeight(
                    m.title,
                    theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ) +
                  textHeight(m.body, theme.textTheme.bodyMedium);
              if (measured > height) height = measured;
            }
            return Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                for (var i = 0; i < modules.length; i++)
                  SizedBox(width: width, height: height, child: tile(i)),
              ],
            );
          },
        )
      else ...[
        for (var i = 0; i < modules.length; i++)
          Padding(padding: const EdgeInsets.only(bottom: 10), child: tile(i)),
      ],
      const SizedBox(height: 12),
      TextButton.icon(
        onPressed: () => Navigator.push<void>(
          context,
          MaterialPageRoute(builder: (_) => DashboardEditor(controller: c)),
        ),
        icon: const Icon(Icons.dashboard_customize_outlined),
        label: Text(c.pack.t('dashboard_customize')),
      ),
    ];
  }

  void _entriesPage(EntryKind kind) {
    LifeNoticeScope.of(context).clear();
    setState(() {
      _profileOpen = false;
      _tab = kind == EntryKind.note ? 3 : 1;
      _notesOpen = kind == EntryKind.note;
    });
  }

  List<Widget> _profile() => [
    _pageTitle('profile'),
    const SizedBox(height: 6),
    Text(
      c.pack.t('ux3_profile_body'),
      style: Theme.of(context).textTheme.bodyMedium
          ?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
    ),
    const SizedBox(height: 14),
    if (c.family != null) ...[
      LifeCard(
        child: ListTile(
          leading: const Icon(Icons.people_outline),
          title: Text(c.pack.t('family_account')),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => Navigator.push<void>(
            context,
            MaterialPageRoute(
              builder: (_) => FamilyPage(controller: c.family!, pack: c.pack),
            ),
          ),
        ),
      ),
      const SizedBox(height: 12),
    ],
    PersonalSettings(controller: c),
  ];

  Widget _pageTitle(String key) => Text(
    c.pack.t(key),
    style: Theme.of(context).textTheme.headlineSmall
        ?.copyWith(fontWeight: FontWeight.w800),
  );

  void _showSearch() {
    Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => GlobalSearchPage(controller: c, family: familyMode),
      ),
    );
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
