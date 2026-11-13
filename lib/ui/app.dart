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
  bool _calendarOpen = false;
  bool _modulesOpen = false;
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
    return _summaryCurrency ??
        (codes.contains(c.currency)
            ? c.currency
            : codes.firstOrNull ?? c.currency);
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
  static const _tabs = [
    'today',
    'nav_tasks',
    'nav_calendar',
    'nav_notes',
    'finances',
    'profile'
  ];
  static const _icons = [
    Icons.space_dashboard_outlined,
    Icons.checklist_rounded,
    Icons.calendar_today_outlined,
    Icons.notes_outlined,
    Icons.account_balance_wallet_outlined,
    Icons.person_outline_rounded,
  ];
  int get _destination => _profileOpen || _modulesOpen
      ? 5
      : _calendarOpen
          ? 2
          : _notesOpen
              ? 3
              : _tab == 2
                  ? 4
                  : _tab == 1
                      ? 1
                      : 0;

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
    FocusScope.of(context).unfocus();
    showModalBottomSheet<void>(
      context: context,
      useSafeArea: true,
      showDragHandle: true,
      isScrollControlled: true,
      sheetAnimationStyle: MediaQuery.disableAnimationsOf(context)
          ? AnimationStyle.noAnimation
          : null,
      builder: (sheetContext) => SafeArea(
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxWidth: 560,
            maxHeight: MediaQuery.sizeOf(sheetContext).height * .65,
          ),
          child: SingleChildScrollView(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(8, 0, 8, 16),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(12, 0, 4, 8),
                  child: Row(children: [
                    Expanded(
                        child: Text(c.pack.t('quick_add'),
                            style: Theme.of(context).textTheme.titleMedium)),
                    IconButton(
                      tooltip:
                          MaterialLocalizations.of(context).closeButtonTooltip,
                      onPressed: () => Navigator.pop(sheetContext),
                      icon: const Icon(Icons.close_rounded),
                    ),
                  ]),
                ),
                for (final kind in EntryKind.values.where((kind) =>
                    !familyMode ||
                    c.family!.roster?['space']?['role'] != 'child' ||
                    kind != EntryKind.income &&
                        c.family!.creatableKinds.contains(
                            kind == EntryKind.expense
                                ? 'transaction'
                                : kind.name)))
                  ListTile(
                    key: Key('quick_${kind.name}'),
                    leading: Icon(switch (kind) {
                      EntryKind.expense => Icons.remove_circle_outline,
                      EntryKind.income => Icons.add_circle_outline,
                      EntryKind.task => Icons.check_circle_outline,
                      EntryKind.note => Icons.notes_outlined,
                    }),
                    title: Text(c.pack.t(kind.name)),
                    trailing: const Icon(Icons.chevron_right_rounded, size: 20),
                    onTap: () {
                      Navigator.pop(sheetContext);
                      _add(kind);
                    },
                  ),
              ]),
            ),
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

  // Existing dashboard links use the legacy tab indices.
  void _navigate(int tab) {
    LifeNoticeScope.of(context).clear();
    setState(() {
      _tab = tab;
      _profileOpen = false;
      _notesOpen = false;
      _calendarOpen = false;
      _modulesOpen = false;
    });
  }

  void _selectDestination(int index) {
    LifeNoticeScope.of(context).clear();
    setState(() {
      _profileOpen = index == 5;
      _calendarOpen = index == 2;
      _notesOpen = index == 3;
      _modulesOpen = false;
      _tab = switch (index) { 1 || 2 => 1, 4 => 2, 3 => 3, _ => 0 };
    });
  }

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final wide = width >= 720;
    final wideHome = wide && _destination == 0 && !familyMode;
    final items = <Widget>[
      if (_modulesOpen) ...[
        Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: () => _selectDestination(5),
              icon: const Icon(Icons.arrow_back_rounded, size: 18),
              label: Text(c.pack.t('profile')),
            )),
        if (familyMode)
          FamilyDashboard(controller: c, visibleKinds: const {
            'note', 'task', 'account', 'transaction', 'transfer', 'budget',
            'event', 'shopping', 'request',
          })
        else
          ..._modules(),
      ] else if (_profileOpen) ...[
        ..._profile(),
        const SizedBox(height: 16),
        LifeCard(
            padding: EdgeInsets.zero,
            child: ListTile(
              key: const Key('nav_modules'),
              leading: const Icon(Icons.grid_view_outlined),
              title: Text(c.pack.t('all_sections')),
              trailing: const Icon(Icons.chevron_right_rounded, size: 20),
              onTap: () => setState(() {
                _modulesOpen = true;
                _profileOpen = false;
              }),
            )),
      ] else if (familyMode)
        FamilyDashboard(controller: c, tab: _tab, visibleKinds: switch (_destination) {
          1 => const {'task'},
          2 => const {'event'},
          3 => const {'note'},
          4 => const {'account', 'transaction', 'transfer', 'budget', 'request'},
          _ => null,
        })
      else if (_calendarOpen)
        CalendarPanel(controller: c)
      else if (_notesOpen)
        ..._entries(EntryKind.note)
      else if (_tab == 0)
        ..._home()
      else if (_tab == 1)
        ..._entries(EntryKind.task)
      else if (_tab == 2)
        ..._finance()
      else
        ..._modules(),
    ];
    final content = ListView.builder(
      key: Key(_modulesOpen
          ? 'modules_page'
          : _profileOpen
              ? 'profile_page'
              : '${_tabs[_destination].replaceFirst('nav_', '')}_page'),
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      padding:
          EdgeInsets.fromLTRB(wideHome ? 24 : 16, 20, wideHome ? 24 : 16, 28),
      itemCount: items.length,
      itemBuilder: (_, index) => items[index],
    );
    return PopScope(
      canPop: _destination == 0,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) {
          if (_modulesOpen) {
            _selectDestination(5);
          } else {
            _navigate(0);
          }
        }
      },
      child: Scaffold(
        body: SafeArea(
          child: Row(children: [
            if (wide) _sideNavigation(width >= 1080),
            Expanded(
                child: Column(children: [
              Padding(
                  padding: const EdgeInsets.fromLTRB(16, 4, 12, 8),
                  child: _header()),
              Divider(
                  height: 1,
                  color: Theme.of(context).colorScheme.outlineVariant),
              Expanded(
                  child: Center(
                      child: ConstrainedBox(
                constraints: BoxConstraints(
                    maxWidth: wideHome
                        ? 1120
                        : wide
                            ? 800
                            : 560),
                child: AnimatedSwitcher(
                  duration: MediaQuery.disableAnimationsOf(context)
                      ? Duration.zero
                      : const Duration(milliseconds: 160),
                  child: content,
                ),
              ))),
            ])),
          ]),
        ),
        bottomNavigationBar: wide ? null : _bottomBar(),
      ),
    );
  }

  Widget _sideNavigation(bool extended) => Container(
        decoration: BoxDecoration(
            border: Border(
                right: BorderSide(
                    color: Theme.of(context).colorScheme.outlineVariant))),
        child: NavigationRail(
          minWidth: 88,
          minExtendedWidth: 192,
          extended: extended,
          selectedIndex: _destination,
          onDestinationSelected: _selectDestination,
          labelType: extended
              ? NavigationRailLabelType.none
              : NavigationRailLabelType.all,
          backgroundColor: Theme.of(context).scaffoldBackgroundColor,
          leading: Padding(
            padding: const EdgeInsets.fromLTRB(8, 16, 8, 24),
            child: Text('ULADIM',
                style: Theme.of(context)
                    .textTheme
                    .labelLarge
                    ?.copyWith(fontWeight: FontWeight.w700, letterSpacing: .5)),
          ),
          destinations: [
            for (var i = 0; i < _tabs.length; i++)
              NavigationRailDestination(
                  icon: Icon(_icons[i], size: 22),
                  label: Text(c.pack.t(_tabs[i]))),
          ],
        ),
      );

  Widget _header() {
    final colors = Theme.of(context).colorScheme;
    final name = familyMode
        ? (c.family!.spaces.where((s) => s['id'] == c.family!.workspace)
            .firstOrNull?['name'] as String? ?? c.pack.t('family_account'))
        : c.pack.t(MediaQuery.sizeOf(context).width < 600
            ? 'workspace_personal_short' : 'personal_space');
    final workspace = TextButton(
      key: const Key('workspace_switcher'),
      onPressed: _workspace,
      style: TextButton.styleFrom(
        alignment: Alignment.centerLeft, foregroundColor: colors.onSurface,
        padding: const EdgeInsets.symmetric(horizontal: 8)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(familyMode ? Icons.people_outline : Icons.person_outline,
          size: 20, color: colors.primary),
        const SizedBox(width: 8),
        Flexible(child: Text(name, maxLines: 1, overflow: TextOverflow.ellipsis,
          style: Theme.of(context).textTheme.labelLarge)),
        const SizedBox(width: 4),
        Icon(Icons.expand_more_rounded, size: 18, color: colors.onSurfaceVariant),
      ]),
    );
    final compact = MediaQuery.textScalerOf(context).scale(1) <= 1.3 ||
        MediaQuery.sizeOf(context).width >= 600;
    return Column(mainAxisSize: MainAxisSize.min, children: [
      Row(children: [
        Expanded(child: workspace),
        IconButton(key: const Key('search_button'), tooltip: c.pack.t('search'),
          onPressed: _showSearch, icon: const Icon(Icons.search_rounded)),
        if (_destination == 0 && compact) ...[
          const SizedBox(width: 4), _addButton(),
        ],
      ]),
      if (_destination == 0 && !compact)
        Align(alignment: Alignment.centerRight, child: _addButton()),
    ]);
  }

  Widget _addButton() => FilledButton.icon(
        key: const Key('add_button'),
        onPressed: _chooseAdd,
        style: FilledButton.styleFrom(
          minimumSize: const Size(44, 44),
          padding: const EdgeInsets.symmetric(horizontal: 12),
        ),
        icon: const Icon(Icons.add_rounded, size: 20),
        label: Text(c.pack.t('add')),
      );

  Widget _bottomBar() {
    final colors = Theme.of(context).colorScheme;
    final width = MediaQuery.sizeOf(context).width;
    final scaler = MediaQuery.textScalerOf(context);
    double requiredWidth = 48;
    double labelHeight = 16;
    for (final key in _tabs) {
      final p = TextPainter(
        text: TextSpan(
            text: c.pack.t(key),
            style: Theme.of(context).textTheme.labelMedium),
        textDirection: Directionality.of(context),
        textScaler: scaler,
      )..layout();
      if (p.width + 12 > requiredWidth) requiredWidth = p.width + 12;
      if (p.height > labelHeight) labelHeight = p.height;
      p.dispose();
    }
    final enlarged = scaler.scale(1) > 1.2;
    final itemWidth = enlarged && requiredWidth > width / 6
        ? requiredWidth : width / 6;
    final height = (labelHeight + 42).clamp(64.0, 112.0);
    final children = <Widget>[
      for (var i = 0; i < _tabs.length; i++)
        SizedBox(width: itemWidth, height: height, child: _navItem(i)),
    ];
    return DecoratedBox(
      decoration: BoxDecoration(
          color: colors.surface,
          border: Border(top: BorderSide(color: colors.outlineVariant))),
      child: SafeArea(
          top: false,
          child: SizedBox(
            height: height,
            child: itemWidth * 6 > width + 1
                ? SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(children: children))
                : Row(children: children),
          )),
    );
  }

  Widget _navItem(int index) {
    final active = _destination == index;
    final colors = Theme.of(context).colorScheme;
    final color = active ? colors.primary : colors.onSurfaceVariant;
    return Semantics(
      selected: active,
      button: true,
      child: InkWell(
        key: Key('nav_${_tabs[index].replaceFirst('nav_', '')}'),
        onTap: () => _selectDestination(index),
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          AnimatedContainer(
            duration: MediaQuery.disableAnimationsOf(context)
                ? Duration.zero
                : const Duration(milliseconds: 160),
            width: 44,
            height: 28,
            decoration: BoxDecoration(
                color: active ? colors.primaryContainer : Colors.transparent,
                borderRadius: BorderRadius.circular(10)),
            child: Icon(_icons[index], size: 21, color: color),
          ),
          const SizedBox(height: 4),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 3),
            child: FittedBox(fit: BoxFit.scaleDown, child: Text(c.pack.t(_tabs[index]),
                maxLines: 1,
                style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: color,
                    fontWeight: active ? FontWeight.w700 : FontWeight.w500))),
          ),
        ]),
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
      if (c.civilDate(at) == c.civilDate(now)) {
        return 1;
      }
      return 3;
    }

    tasks.removeWhere((task) => _taskDone(task) && dates[task.id] == null);
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
    final visible = config.where((r) => r['visible'] == 1).toList();
    content.add(LayoutBuilder(builder: (context, bounds) {
      // Keep the saved sequence and visibility while using tablet space.
      final columns = bounds.maxWidth >= 680 &&
              MediaQuery.textScalerOf(context).scale(1) <= 1.3
          ? 2
          : 1;
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (var start = 0; start < visible.length; start += columns) ...[
            if (start > 0) const SizedBox(height: 14),
            if (columns == 1)
              card(visible[start])
            else
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(child: card(visible[start])),
                  const SizedBox(width: 18),
                  Expanded(
                      child: start + 1 < visible.length
                          ? card(visible[start + 1])
                          : const SizedBox.shrink()),
                ],
              ),
          ],
        ],
      );
    }));
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
              : MediaQuery.textScalerOf(context).scale(1) > 1.3 ? 1 : 2;
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
      const titleStyle = TextStyle(fontSize: 15, fontWeight: FontWeight.w600);
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
    )) {
      return c.calendarEngine.next(entry, c.now, c.deviceZone, c.occurrences) ==
              null
          ? 'completed'
          : 'task_upcoming';
    }
    if (due.at.isBefore(c.now)) return 'task_overdue';
    return c.civilDate(due.at) == c.civilDate(c.now)
        ? 'today'
        : 'task_upcoming';
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
                      decoration: _taskDone(task)
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
    final open = records.where((r) => !_taskDone(r)).toList();
    final completed = records.where(_taskDone).toList();
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
                      key: Key('finance_amount_${record.id}'),
                      textAlign: TextAlign.right,
                      style: TextStyle(
                        color: lifeAccent(context, _kindColors(record.kind).foreground),
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
      _calendarOpen = false;
      _modulesOpen = false;
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
        ?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -.5),
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
