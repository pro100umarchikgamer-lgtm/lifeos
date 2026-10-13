import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../domain/models.dart';
import 'record_detail.dart';
import 'family.dart';
import 'personal_modules.dart';

class GlobalSearchPage extends StatefulWidget {
  const GlobalSearchPage({
    super.key,
    required this.controller,
    required this.family,
  });
  final AppController controller;
  final bool family;
  @override
  State<GlobalSearchPage> createState() => _GlobalSearchPageState();
}

class _GlobalSearchPageState extends State<GlobalSearchPage> {
  String query = '', filter = 'all';
  final input = TextEditingController();
  @override
  void dispose() {
    input.dispose();
    super.dispose();
  }

  AppController get c => widget.controller;
  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.family ? c.family! : c,
    builder: (context, _) => results(context),
  );

  Widget results(BuildContext context) {
    final needle = query.trim().toLowerCase();
    final own = c.records.where(
      (r) =>
          (filter == 'all' || r.kind.name == filter) &&
          (r.text.toLowerCase().contains(needle) ||
              r.date?.contains(needle) == true),
    );
    final modules = [
      for (final table in personalModules)
        for (final row in c.offline[table] ?? <Map<String, Object?>>[])
          if (filter == 'all' &&
              ['name', 'label', 'goal', 'text'].any(
                (key) =>
                    (row[key] as String? ?? '').toLowerCase().contains(needle),
              ))
            (table, row),
    ];
    final shared =
        c.family?.records
            .where(
              (r) =>
                  (filter == 'all' || r['kind'] == filter) &&
                  ['body', 'title', 'name', 'label', 'date'].any(
                    (key) => (r['data'][key] as String? ?? '')
                        .toLowerCase()
                        .contains(needle),
                  ),
            )
            .toList() ??
        [];
    return Scaffold(
      appBar: AppBar(title: Text(c.pack.t('search'))),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: TextField(
                key: const Key('global_search_input'),
                controller: input,
                autofocus: true,
                decoration: InputDecoration(
                  labelText: c.pack.t('search_hint'),
                  prefixIcon: const Icon(Icons.search),
                  suffixIcon: query.isEmpty
                      ? null
                      : IconButton(
                          tooltip: c.pack.t('clear'),
                          icon: const Icon(Icons.close),
                          onPressed: () {
                            input.clear();
                            setState(() => query = '');
                          },
                        ),
                ),
                onChanged: (v) => setState(() => query = v),
              ),
            ),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  for (final key
                      in widget.family
                          ? ['all', 'transaction', 'task', 'note', 'shopping']
                          : ['all', 'expense', 'income', 'task', 'note'])
                    Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: FilterChip(
                        label: Text(
                          c.pack.t(
                            key == 'all'
                                ? 'ux_all'
                                : widget.family
                                ? 'family_kind_$key'
                                : key,
                          ),
                        ),
                        selected: filter == key,
                        onSelected: (_) => setState(() => filter = key),
                      ),
                    ),
                ],
              ),
            ),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (needle.isEmpty)
                    Text(c.pack.t('search_hint'))
                  else if (widget.family) ...[
                    for (final r in shared)
                      ListTile(
                        leading: Icon(
                          r['visibility'] == 'private'
                              ? Icons.lock_outline
                              : Icons.people_outline,
                        ),
                        title: Text(
                          (r['data']['body'] ??
                                  r['data']['title'] ??
                                  r['data']['name'] ??
                                  r['data']['label'] ??
                                  c.pack.t('family_kind_${r['kind']}'))
                              .toString(),
                          maxLines: 2,
                        ),
                        onTap: () => Navigator.push<void>(
                          context,
                          MaterialPageRoute(
                            builder: (_) => FamilyRecordEditor(
                              controller: c.family!,
                              pack: c.pack,
                              record: r,
                            ),
                          ),
                        ),
                      ),
                    if (shared.isEmpty) Text(c.pack.t('search_empty')),
                  ] else ...[
                    for (final r in own)
                      ListTile(
                        leading: Icon(
                          r.kind == EntryKind.note
                              ? Icons.notes_outlined
                              : r.kind == EntryKind.task
                              ? Icons.check_circle_outline
                              : Icons.payments_outlined,
                        ),
                        title: Text(
                          r.text.isEmpty ? c.pack.t(r.kind.name) : r.text,
                          maxLines: 2,
                        ),
                        subtitle: Text(c.pack.t(r.kind.name)),
                        onTap: () => Navigator.push<void>(
                          context,
                          MaterialPageRoute(
                            builder: (_) =>
                                RecordDetail(controller: c, id: r.id),
                          ),
                        ),
                      ),
                    for (final match in modules)
                      ListTile(
                        leading: const Icon(Icons.grid_view_outlined),
                        title: Text(
                          (match.$2['name'] ??
                                  match.$2['label'] ??
                                  match.$2['text'] ??
                                  c.pack.t('module_${match.$1.name}'))
                              .toString(),
                          maxLines: 2,
                        ),
                        subtitle: Text(c.pack.t('module_${match.$1.name}')),
                        onTap: () => Navigator.push<void>(
                          context,
                          MaterialPageRoute(
                            builder: (_) => PersonalModulesPage(
                              controller: c,
                              table: match.$1,
                            ),
                          ),
                        ),
                      ),
                    if (filter == 'all')
                      for (final table in personalModules)
                        if (c.pack
                            .t('module_${table.name}')
                            .toLowerCase()
                            .contains(needle))
                          ListTile(
                            leading: const Icon(Icons.grid_view_outlined),
                            title: Text(c.pack.t('module_${table.name}')),
                            onTap: () => Navigator.push<void>(
                              context,
                              MaterialPageRoute(
                                builder: (_) => PersonalModulesPage(
                                  controller: c,
                                  table: table,
                                ),
                              ),
                            ),
                          ),
                    if (own.isEmpty &&
                        modules.isEmpty &&
                        !personalModules.any(
                          (t) =>
                              filter == 'all' &&
                              c.pack
                                  .t('module_${t.name}')
                                  .toLowerCase()
                                  .contains(needle),
                        ))
                      Text(c.pack.t('search_empty')),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
