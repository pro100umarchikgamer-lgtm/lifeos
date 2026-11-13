import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../domain/models.dart';
import 'design.dart';
import 'record_detail.dart';
import 'family.dart';
import 'personal_modules.dart';
import 'selection.dart';

class GlobalSearchPage extends StatefulWidget {
  const GlobalSearchPage(
      {super.key, required this.controller, required this.family});
  final AppController controller;
  final bool family;
  @override
  State<GlobalSearchPage> createState() => _GlobalSearchPageState();
}

class _GlobalSearchPageState extends State<GlobalSearchPage> {
  String query = '', filter = 'all';
  final input = TextEditingController();
  AppController get c => widget.controller;
  @override
  void dispose() {
    input.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: widget.family ? c.family! : c,
        builder: (context, _) => results(context),
      );

  Widget results(BuildContext context) {
    final needle = query.trim().toLowerCase();
    final own = c.records.where((r) =>
        (filter == 'all' || r.kind.name == filter) &&
        (r.text.toLowerCase().contains(needle) ||
            r.date?.contains(needle) == true));
    final modules = [
      for (final table in personalModules)
        for (final row in c.offline[table] ?? <Map<String, Object?>>[])
          if (filter == 'all' &&
              ['name', 'label', 'goal', 'text'].any((key) =>
                  (row[key] as String? ?? '').toLowerCase().contains(needle)))
            (table, row),
    ];
    final shared = c.family?.records
            .where((r) =>
                (filter == 'all' || r['kind'] == filter) &&
                ['body', 'title', 'name', 'label', 'date'].any((key) =>
                    (r['data'][key] as String? ?? '')
                        .toLowerCase()
                        .contains(needle)))
            .toList() ??
        [];
    final filters = <String, String>{
      for (final key in widget.family
          ? ['all', 'transaction', 'task', 'note', 'shopping']
          : ['all', 'expense', 'income', 'task', 'note'])
        key: c.pack.t(key == 'all'
            ? 'ux_all'
            : widget.family
                ? 'family_kind_$key'
                : key),
    };
    final matches = <Widget>[];
    if (needle.isNotEmpty) {
      if (widget.family) {
        for (final r in shared) {
          matches.add(_result(
            icon: r['visibility'] == 'private'
                ? Icons.lock_outline
                : Icons.people_outline,
            title: (r['data']['body'] ??
                    r['data']['title'] ??
                    r['data']['name'] ??
                    r['data']['label'] ??
                    c.pack.t('family_kind_${r['kind']}'))
                .toString(),
            subtitle: c.pack.t('family_kind_${r['kind']}'),
            onTap: () => Navigator.push<void>(
                context,
                MaterialPageRoute(
                    builder: (_) => FamilyRecordEditor(
                        controller: c.family!, pack: c.pack, record: r))),
          ));
        }
      } else {
        for (final r in own) {
          matches.add(_result(
            icon: switch (r.kind) {
              EntryKind.note => Icons.notes_outlined,
              EntryKind.task => Icons.check_circle_outline,
              _ => Icons.payments_outlined,
            },
            title: r.text.isEmpty ? c.pack.t(r.kind.name) : r.text,
            subtitle: c.pack.t(r.kind.name),
            onTap: () => Navigator.push<void>(
                context,
                MaterialPageRoute(
                    builder: (_) => RecordDetail(controller: c, id: r.id))),
          ));
        }
        for (final match in modules) {
          matches.add(_result(
            icon: Icons.grid_view_outlined,
            title: (match.$2['name'] ??
                    match.$2['label'] ??
                    match.$2['text'] ??
                    c.pack.t('module_${match.$1.name}'))
                .toString(),
            subtitle: c.pack.t('module_${match.$1.name}'),
            onTap: () => Navigator.push<void>(
                context,
                MaterialPageRoute(
                    builder: (_) =>
                        PersonalModulesPage(controller: c, table: match.$1))),
          ));
        }
        if (filter == 'all') {
          for (final table in personalModules) {
            if (c.pack
                .t('module_${table.name}')
                .toLowerCase()
                .contains(needle)) {
              matches.add(_result(
                icon: Icons.grid_view_outlined,
                title: c.pack.t('module_${table.name}'),
                onTap: () => Navigator.push<void>(
                    context,
                    MaterialPageRoute(
                        builder: (_) =>
                            PersonalModulesPage(controller: c, table: table))),
              ));
            }
          }
        }
      }
    }
    return Scaffold(
      appBar: AppBar(title: Text(c.pack.t('search'))),
      body: SafeArea(
          child: Center(
              child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 720),
        child: Column(children: [
          Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
              child: TextField(
                key: const Key('global_search_input'),
                controller: input,
                autofocus: true,
                textInputAction: TextInputAction.search,
                decoration: InputDecoration(
                  labelText: c.pack.t('search_hint'),
                  prefixIcon: const Icon(Icons.search_rounded),
                  suffixIcon: query.isEmpty
                      ? null
                      : IconButton(
                          tooltip: c.pack.t('clear'),
                          icon: const Icon(Icons.close_rounded),
                          onPressed: () {
                            input.clear();
                            setState(() => query = '');
                          },
                        ),
                ),
                onChanged: (v) => setState(() => query = v),
              )),
          Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              child: LifeSelect<String>(
                label: c.pack.t('kind'),
                value: filter,
                choices: filters,
                showLabel: false,
                onChanged: (v) => setState(() => filter = v),
              )),
          Expanded(
              child: needle.isEmpty || matches.isEmpty
                  ? Align(
                      alignment: Alignment.topCenter,
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(32, 32, 32, 24),
                        child: Text(
                            c.pack.t(needle.isEmpty
                                ? 'search_hint'
                                : 'search_empty'),
                            textAlign: TextAlign.center,
                            style: Theme.of(context)
                                .textTheme
                                .bodyMedium
                                ?.copyWith(
                                    color: Theme.of(context)
                                        .colorScheme
                                        .onSurfaceVariant)),
                      ))
                  : ListView(
                      keyboardDismissBehavior:
                          ScrollViewKeyboardDismissBehavior.onDrag,
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                      children: [
                        LifeCard(
                            padding: EdgeInsets.zero,
                            child: Column(children: [
                              for (var i = 0; i < matches.length; i++) ...[
                                if (i > 0)
                                  const Divider(
                                      height: 1, indent: 52, endIndent: 16),
                                matches[i],
                              ],
                            ]))
                      ],
                    )),
        ]),
      ))),
    );
  }

  Widget _result(
          {required IconData icon,
          required String title,
          String? subtitle,
          required VoidCallback onTap}) =>
      ListTile(
        leading: Icon(icon, size: 22),
        title: Text(title, maxLines: 2, overflow: TextOverflow.ellipsis),
        subtitle: subtitle == null ? null : Text(subtitle),
        trailing: const Icon(Icons.chevron_right_rounded, size: 20),
        onTap: onTap,
      );
}
