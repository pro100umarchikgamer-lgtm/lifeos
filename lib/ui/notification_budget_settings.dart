import 'package:flutter/material.dart';
import '../app_controller.dart';
import '../domain/timezones.dart';
import 'selection.dart';
import 'settings_surfaces.dart';

class NotificationBudgetSettingsPage extends StatefulWidget {
  const NotificationBudgetSettingsPage({super.key, required this.controller});
  final AppController controller;
  @override
  State<NotificationBudgetSettingsPage> createState() =>
      _NotificationBudgetSettingsPageState();
}

class _NotificationBudgetSettingsPageState
    extends State<NotificationBudgetSettingsPage> {
  AppController get c => widget.controller;
  late final String? _scope;
  static List<int> _steps(int step) => [
        ...List.generate(100 ~/ step, (i) => (i + 1) * step),
        if (100 % step != 0) 100
      ];
  @override
  void initState() {
    super.initState();
    _scope = c.inbox.accountScope;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _scope == c.inbox.accountScope) {
        c.inbox.loadBudgetSettings();
      }
    });
  }

  Future<void> _save({bool? enabled, List<int>? thresholds}) =>
      c.inbox.saveBudgetSettings(
        enabled: enabled ?? c.inbox.budgetEnabled,
        thresholds: thresholds ?? c.inbox.budgetThresholds,
        timezone:
            calendarLocation(c.timezone == 'device' ? c.deviceZone : c.timezone)
                .name,
      );
  @override
  Widget build(BuildContext context) => ListenableBuilder(
      listenable: c.inbox,
      builder: (context, _) {
        final center = c.inbox;
        final thresholds = center.budgetThresholds;
        final presets = {
          'standard': [50, 80, 100],
          for (final step in [5, 10, 15]) '$step': _steps(step)
        };
        final selected = presets.entries
                .where((e) => e.value.join(',') == thresholds.join(','))
                .firstOrNull
                ?.key ??
            'custom';
        return Scaffold(
          appBar: settingsAppBar(context, c.pack.t('inbox_budget_title')),
          body: SafeArea(
              child: ListView(padding: settingsPagePadding(context), children: [
            Text(c.pack.t('inbox_budget_scope'),
                style: Theme.of(context)
                    .textTheme
                    .bodyMedium
                    ?.copyWith(height: 1.5)),
            const SizedBox(height: 20),
            if (!center.hasAccount || _scope != center.accountScope)
              Text(c.pack.t('inbox_local_only'))
            else ...[
              SettingsGroup(children: [
                SwitchListTile.adaptive(
                  key: const Key('budget_reminders_enabled'),
                  title: Text(c.pack.t('inbox_budget_enabled')),
                  value: center.budgetEnabled,
                  onChanged: center.budgetBusy
                      ? null
                      : (value) => _save(enabled: value),
                )
              ]),
              const SizedBox(height: 20),
              LifeSelect<String>(
                key: const Key('budget_reminder_thresholds'),
                label: c.pack.t('inbox_budget_thresholds'),
                value: selected,
                choices: {
                  'standard': '50%, 80%, 100%',
                  for (final step in [5, 10, 15])
                    '$step': c.pack
                        .t('inbox_budget_every')
                        .replaceAll('{step}', '$step'),
                  if (selected == 'custom')
                    'custom': c.pack.t('inbox_budget_custom').replaceAll(
                        '{values}', thresholds.map((v) => '$v%').join(', ')),
                },
                onChanged: center.budgetBusy
                    ? null
                    : (value) {
                        if (presets[value] != null) {
                          _save(thresholds: presets[value]);
                        }
                      },
              ),
              if (center.budgetBusy)
                const Padding(
                    padding: EdgeInsets.symmetric(vertical: 20),
                    child: LinearProgressIndicator()),
              if (center.budgetError != null || center.error != null)
                Padding(
                  padding: const EdgeInsets.only(top: 20),
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(c.pack.t(center.budgetError ?? center.error!)),
                        TextButton.icon(
                            onPressed: center.budgetBusy
                                ? null
                                : center.loadBudgetSettings,
                            icon: const Icon(Icons.refresh_rounded),
                            label: Text(c.pack.t('retry'))),
                      ]),
                ),
            ],
          ])),
        );
      });
}
