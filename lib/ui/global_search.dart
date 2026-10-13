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
  AppController get c => widget.controller;
  @override
  Widget build(BuildContext context) {
    final needle = query.trim().toLowerCase();
    final own = c.records.where(
      (r) =>
          (filter == 'all' || r.kind.name == filter) &&
          (r.text.toLowerCase().contains(needle) ||
              r.date?.contains(needle) == true),
    );
    final shared =
        c.family?.records
            .where(
              (r) =>
                  (filter == 'all' || r['kind'] == filter) &&
                  r['data'].toString().toLowerCase().contains(needle),
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
                autofocus: true,
                decoration: InputDecoration(
                  labelText: c.pack.t('search_hint'),
                  prefixIcon: const Icon(Icons.search),
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
