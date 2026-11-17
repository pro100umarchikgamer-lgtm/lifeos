import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../app_controller.dart';
import '../domain/models.dart';
import 'settings_surfaces.dart';

const dashboardWidgets = [
  'financial',
  'tasks',
  'notes',
  'projects',
  'habits',
  'shopping'
];
Map<String, Object?> dashboardChoice(AppController c, String key) =>
    c.offline[OfflineTable.dashboard]
        ?.where((r) => r['widget'] == key)
        .firstOrNull ??
    {
      'widget': key,
      'visible': dashboardWidgets.indexOf(key) < 3 ? 1 : 0,
      'expanded': 1,
      'position': dashboardWidgets.indexOf(key) * 10 + 10
    };

class DashboardEditor extends StatefulWidget {
  const DashboardEditor({super.key, required this.controller});
  final AppController controller;
  @override
  State<DashboardEditor> createState() => _DashboardEditorState();
}

class _DashboardEditorState extends State<DashboardEditor> {
  AppController get c => widget.controller;
  bool busy = false;
  Future<void> save(Map<String, Object?> row,
      {bool? visible, bool? expanded, int? position}) async {
    if (busy) return;
    setState(() => busy = true);
    try {
      await c.execute(SaveDashboard(
          const Uuid().v4(),
          row['id'] as String? ?? const Uuid().v4(),
          row['revision'] as int? ?? 0,
          widget: row['widget'] as String,
          position: position ?? row['position'] as int,
          visible: visible ?? row['visible'] == 1,
          expanded: expanded ?? row['expanded'] == 1));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content:
                Text(c.pack.t(e is DomainFailure ? e.key : 'change_failed'))));
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
      listenable: c,
      builder: (context, _) {
        final rows = [for (final w in dashboardWidgets) dashboardChoice(c, w)]
          ..sort((a, b) {
            final v = (a['position'] as int).compareTo(b['position'] as int);
            return v == 0
                ? (a['widget'] as String).compareTo(b['widget'] as String)
                : v;
          });
        return Scaffold(
            appBar: settingsAppBar(context, c.pack.t('dashboard_customize')),
            body: SafeArea(
                child:
                    ListView(padding: settingsPagePadding(context), children: [
              SettingsGroup(children: [
                for (var index = 0; index < rows.length; index++)
                  ExpansionTile(
                    tilePadding:
                        const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                    childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                    title: Text(c.pack.t('widget_${rows[index]['widget']}')),
                    leading: Switch.adaptive(
                        value: rows[index]['visible'] == 1,
                        onChanged:
                            busy ? null : (v) => save(rows[index], visible: v)),
                    children: [
                      SwitchListTile.adaptive(
                          contentPadding: EdgeInsets.zero,
                          title: Text(c.pack.t('expanded_view')),
                          value: rows[index]['expanded'] == 1,
                          onChanged: busy
                              ? null
                              : (v) => save(rows[index], expanded: v)),
                      Wrap(spacing: 8, children: [
                        TextButton.icon(
                            onPressed: busy ||
                                    index == 0 ||
                                    rows[index - 1]['position'] == 0
                                ? null
                                : () => save(rows[index],
                                    position:
                                        (rows[index - 1]['position'] as int) -
                                            1),
                            icon: const Icon(Icons.arrow_upward, size: 18),
                            label: Text(c.pack.t('move_up'))),
                        TextButton.icon(
                            onPressed: busy ||
                                    index == rows.length - 1 ||
                                    rows[index + 1]['position'] == 100
                                ? null
                                : () => save(rows[index],
                                    position:
                                        (rows[index + 1]['position'] as int) +
                                            1),
                            icon: const Icon(Icons.arrow_downward, size: 18),
                            label: Text(c.pack.t('move_down'))),
                      ]),
                    ],
                  ),
              ]),
            ])));
      });
}
