import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../app_controller.dart';
import '../domain/models.dart';
import '../localization/language_pack.dart';
import 'quick_add.dart';

class LifeOSApp extends StatelessWidget {
  const LifeOSApp({super.key, required this.controller});
  final AppController controller;
  @override
  Widget build(BuildContext context) => ListenableBuilder(listenable: controller, builder: (context, _) {
    final pack = controller.pack;
    ThemeData theme(Brightness brightness) => ThemeData(useMaterial3: true, brightness: brightness,
      colorSchemeSeed: const Color(0xff346b59),
      inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder()),
      filledButtonTheme: FilledButtonThemeData(style: FilledButton.styleFrom(minimumSize: const Size(48, 52))));
    return MaterialApp(title: 'LifeOS', debugShowCheckedModeBanner: false,
      locale: pack.locale, supportedLocales: controller.catalog.packs.values.map((p) => p.locale).toList(),
      localizationsDelegates: const [MaterialFallbackDelegate(), WidgetsFallbackDelegate()],
      theme: theme(Brightness.light), darkTheme: theme(Brightness.dark),
      themeMode: switch (controller.theme) {'light' => ThemeMode.light, 'dark' => ThemeMode.dark, _ => ThemeMode.system},
      home: HomeShell(controller: controller));
  });
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key, required this.controller});
  final AppController controller;
  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _tab = 0;
  AppController get c => widget.controller;
  static const _tabs = ['home', 'plans', 'finances', 'modules', 'profile'];
  static const _icons = [Icons.space_dashboard_outlined, Icons.event_note_outlined, Icons.account_balance_wallet_outlined, Icons.grid_view_outlined, Icons.person_outline];
  void _message(String key) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(c.pack.t(key))));
  }
  Future<void> _add(EntryKind kind) async {
    final saved = await showModalBottomSheet<bool>(context: context, isScrollControlled: true,
      useSafeArea: true, isDismissible: false, enableDrag: false,
      builder: (context) => QuickAdd(controller: c, kind: kind));
    if (saved == true) {
      try { await c.refresh(); _message('saved'); } catch (_) { _message('read_failed'); }
    }
  }
  Future<void> _complete(Record record, bool value) async {
    if (c.pendingTasks.contains(record.id)) return;
    setState(() => c.pendingTasks.add(record.id));
    var saved = false;
    try {
      await c.engine.execute(CompleteTask(const Uuid().v4(), record.id, value));
      saved = true;
      await c.refresh();
    } catch (_) { _message(saved ? 'read_failed' : 'change_failed'); }
    finally { if (mounted) setState(() => c.pendingTasks.remove(record.id)); }
  }
  Future<void> _preference(String key, String value) async {
    try { await c.preference(key, value); } catch (_) { _message('change_failed'); }
  }

  @override
  Widget build(BuildContext context) {
    final pack = c.pack;
    final wide = MediaQuery.sizeOf(context).width >= 720;
    final content = ListView(padding: const EdgeInsets.all(20), children: [
      if (_tab == 0) ..._home(),
      if (_tab == 1) ..._entries(EntryKind.task),
      if (_tab == 2) ..._finance(),
      if (_tab == 3) ..._entries(EntryKind.note),
      if (_tab == 4) ..._profile(),
    ]);
    return Scaffold(appBar: AppBar(title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(_tab == 0 ? 'LifeOS' : pack.t(_tabs[_tab])),
      Text(pack.t('personal_space'), style: Theme.of(context).textTheme.labelMedium),
    ])),
      body: SafeArea(child: Row(children: [
        if (wide) NavigationRail(selectedIndex: _tab, onDestinationSelected: (v) => setState(() => _tab = v),
          labelType: NavigationRailLabelType.all, destinations: [for (var i = 0; i < _tabs.length; i++)
            NavigationRailDestination(icon: Icon(_icons[i]), label: Text(pack.t(_tabs[i])))]),
        Expanded(child: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 900), child: content))),
      ])),
      bottomNavigationBar: wide ? null : NavigationBar(selectedIndex: _tab,
        onDestinationSelected: (v) => setState(() => _tab = v), destinations: [for (var i = 0; i < _tabs.length; i++)
          NavigationDestination(icon: Icon(_icons[i]), label: pack.t(_tabs[i]))]),
    );
  }

  List<Widget> _home() => [
    Text(c.pack.t('today'), style: Theme.of(context).textTheme.headlineMedium),
    const SizedBox(height: 6), Text(c.pack.t('offline_ready')),
    const SizedBox(height: 24),
    Wrap(spacing: 10, runSpacing: 10, children: [for (final kind in EntryKind.values)
      FilledButton.tonalIcon(key: Key('quick_${kind.name}'), onPressed: () => _add(kind),
        icon: Icon(_kindIcon(kind)), label: Text(c.pack.t(kind.name)))]),
    const SizedBox(height: 28),
    Text(c.pack.t('recent'), style: Theme.of(context).textTheme.titleLarge),
    const SizedBox(height: 12),
    if (c.records.isEmpty) _empty('empty_home'),
    for (final record in c.records.take(12)) _record(record),
  ];

  List<Widget> _entries(EntryKind kind) {
    final records = c.records.where((r) => r.kind == kind).toList();
    return [FilledButton.icon(onPressed: () => _add(kind), icon: const Icon(Icons.add), label: Text(c.pack.t(kind.name))),
      const SizedBox(height: 20), if (records.isEmpty) _empty(kind == EntryKind.task ? 'empty_tasks' : 'empty_notes'),
      for (final record in records) _record(record)];
  }

  List<Widget> _finance() {
    final records = c.records.where((r) => r.amountMinor != null).toList();
    final totals = <String, List<int>>{};
    for (final record in records) {
      final bucket = totals.putIfAbsent(record.currency!.code, () => [0, 0]);
      bucket[record.kind == EntryKind.expense ? 0 : 1] += record.amountMinor!;
    }
    return [Wrap(spacing: 12, runSpacing: 12, children: [for (final kind in [EntryKind.expense, EntryKind.income])
      FilledButton.tonalIcon(onPressed: () => _add(kind), icon: const Icon(Icons.add), label: Text(c.pack.t(kind.name)))]),
      const SizedBox(height: 20), Text(c.pack.t('recorded_totals'), style: Theme.of(context).textTheme.titleLarge),
      for (final entry in totals.entries) Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(
        crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${c.pack.t('expense')}: ${Currency.fromCode(entry.key).format(entry.value[0])}'),
          const SizedBox(height: 8), Text('${c.pack.t('income')}: ${Currency.fromCode(entry.key).format(entry.value[1])}'),
        ]))),
      const SizedBox(height: 12), Text(c.pack.t('no_account_hint'), style: Theme.of(context).textTheme.bodySmall),
      const SizedBox(height: 16), if (records.isEmpty) _empty('empty_money'),
      for (final record in records) _record(record)];
  }

  List<Widget> _profile() => [
    Text(c.pack.t('local_profile'), style: Theme.of(context).textTheme.titleLarge),
    const SizedBox(height: 8), Text(c.pack.t('local_privacy')),
    const SizedBox(height: 24),
    DropdownButtonFormField<String>(initialValue: c.pack.tag, isExpanded: true,
      decoration: InputDecoration(labelText: c.pack.t('language')),
      items: [for (final pack in c.catalog.packs.values) DropdownMenuItem(value: pack.tag, child: Text(pack.name))],
      onChanged: (value) { if (value != null) _preference('language', value); }),
    const SizedBox(height: 16),
    DropdownButtonFormField<String>(initialValue: c.currency, isExpanded: true,
      decoration: InputDecoration(labelText: c.pack.t('currency')),
      items: [for (final code in {'USD', 'EUR', 'RUB', 'KZT', 'UZS', 'UAH', 'GBP', 'GEL', 'AZN', 'AMD', 'TJS', 'KGS', c.currency})
        DropdownMenuItem(value: code, child: Text(code))],
      onChanged: (value) { if (value != null) _preference('currency', value); }),
    const SizedBox(height: 16),
    DropdownButtonFormField<String>(initialValue: c.theme, decoration: InputDecoration(labelText: c.pack.t('theme')),
      items: [for (final mode in ['system', 'light', 'dark']) DropdownMenuItem(value: mode, child: Text(c.pack.t(mode)))],
      onChanged: (value) { if (value != null) _preference('theme', value); }),
  ];

  Widget _empty(String key) => Padding(padding: const EdgeInsets.symmetric(vertical: 32),
    child: Text(c.pack.t(key), textAlign: TextAlign.center));

  Widget _record(Record record) => Card(child: ListTile(
    onTap: record.kind == EntryKind.note ? () => showDialog<void>(context: context,
      builder: (context) => AlertDialog(title: Text(c.pack.t('note')),
        content: SingleChildScrollView(child: SelectableText(record.text)),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: Text(c.pack.t('close')))])) : null,
    leading: record.kind == EntryKind.task ? Checkbox(value: record.completed,
      onChanged: c.pendingTasks.contains(record.id) ? null : (v) => _complete(record, v!)) : Icon(_kindIcon(record.kind)),
    title: Text(record.text.isEmpty ? c.pack.t(record.kind.name) : record.text, maxLines: 3, overflow: TextOverflow.ellipsis,
      style: record.completed ? const TextStyle(decoration: TextDecoration.lineThrough) : null),
    subtitle: record.currency != null ? Text('${record.currency!.format(record.amountMinor!)} · ${record.date}') : null,
  ));

  IconData _kindIcon(EntryKind kind) => switch (kind) {
    EntryKind.expense => Icons.remove_circle_outline, EntryKind.income => Icons.add_circle_outline,
    EntryKind.task => Icons.check_circle_outline, EntryKind.note => Icons.edit_note,
  };
}
