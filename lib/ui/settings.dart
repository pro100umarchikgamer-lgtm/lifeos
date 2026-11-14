import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' as background;
import 'package:timezone/timezone.dart' as tz;

import '../app_controller.dart';
import '../domain/action_engine.dart';
import '../domain/models.dart';
import '../domain/public_links.dart';
import '../services/backup_service.dart';
import '../platform/native_bridge.dart';
import 'design.dart';
import 'settings_surfaces.dart';
import 'appearance_editor.dart';
import 'selection.dart';
import 'preference_choices.dart';
import 'personal_modules.dart';
import 'help_center.dart';

class PersonalSettings extends StatefulWidget {
  const PersonalSettings({super.key, required this.controller, this.section});
  final int? section;
  final AppController controller;
  @override
  State<PersonalSettings> createState() => _PersonalSettingsState();
}

class _PersonalSettingsState extends State<PersonalSettings> {
  AppController get c => widget.controller;
  bool busy = false;
  final backupStatus = ValueNotifier<String>('backup_steps');
  final backupBusy = ValueNotifier<bool>(false);
  final notificationBusy = ValueNotifier<bool>(false);
  @override
  void dispose() {
    backupStatus.dispose();
    backupBusy.dispose();
    notificationBusy.dispose();
    super.dispose();
  }

  void message(String key) {
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(c.pack.t(key))));
    }
  }

  Future<void> legalLink(String path) async {
    try {
      await c.native.openExternalLink(publicSitePage(path));
    } catch (_) {
      message('inbox_link_failed');
    }
  }

  Future<void> preference(String key, String value) async {
    try {
      await c.preference(key, value);
    } catch (e) {
      message(e is DomainFailure ? e.key : 'change_failed');
    }
  }

  Widget select(
    String key,
    String value,
    Map<String, String> choices, {
    String? label,
  }) =>
      Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: LifeSelect<String>(
          key: ValueKey('${key}_$value'),
          value: value,
          label: c.pack.t(label ?? key),
          choices: choices,
          queryChoices: key == 'currency'
              ? (query) => currencyQueryChoice(c.pack, query)
              : null,
          dialog: key == 'currency' || key == 'region' || key == 'language',
          searchLabel: key == 'language' ||
                  key == 'currency' ||
                  key == 'region' ||
                  choices.length > 10
              ? c.pack.t('search_options')
              : null,
          onChanged: busy ? null : (v) => preference(key, v),
        ),
      );
  Future<void> native(String method) async {
    try {
      await c.native.request(method);
      await c.refresh(forceReminders: true);
    } catch (_) {
      message('native_unavailable');
    }
  }

  Future<void> testNotification() async {
    if (busy || notificationBusy.value) return;
    notificationBusy.value = true;
    try {
      final result = await c.native.testNotification({
        'title': 'ULADIM',
        'message': c.pack.t('test_message'),
      });
      await c.refresh(forceReminders: true);
      message(switch (result.status) {
        NotificationTestStatus.posted => 'test_notification_posted',
        NotificationTestStatus.blocked => result.channelBlocked
            ? 'notification_channel_blocked'
            : 'notifications_disabled',
        NotificationTestStatus.unconfirmed => 'test_notification_not_posted',
      });
    } catch (_) {
      message('native_unavailable');
    } finally {
      if (mounted) notificationBusy.value = false;
    }
  }

  String notificationChannelDetails(Map? channel) {
    final importance = channel?['importance'] as int? ?? 0;
    final priority = switch (importance) {
      >= 4 => 'notification_priority_high',
      3 => 'notification_priority_standard',
      > 0 => 'notification_priority_silent',
      _ => 'notification_channel_blocked',
    };
    final audible = c.notificationStatus['enabled'] == true &&
        importance >= 3 &&
        channel?['sound'] == true;
    return '${c.pack.t(priority)}\n${c.pack.t(audible ? 'audible_enabled' : 'audible_restricted')}';
  }

  Future<String?> password({required bool create}) async {
    final first = TextEditingController(), second = TextEditingController();
    String? error;
    final result = await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (_) => StatefulBuilder(
        builder: (context, set) => AlertDialog(
          title: Text(c.pack.t('backup_password')),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  c.pack.t(
                    create ? 'backup_password_help' : 'restore_password_help',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: first,
                  obscureText: true,
                  enableSuggestions: false,
                  autocorrect: false,
                  decoration: InputDecoration(
                    labelText: c.pack.t('backup_password'),
                  ),
                ),
                if (create) ...[
                  const SizedBox(height: 12),
                  TextField(
                    controller: second,
                    obscureText: true,
                    enableSuggestions: false,
                    autocorrect: false,
                    decoration: InputDecoration(
                      labelText: c.pack.t('repeat_password'),
                    ),
                  ),
                ],
                if (error != null)
                  Text(
                    c.pack.t(error!),
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: Text(c.pack.t('cancel')),
            ),
            FilledButton(
              onPressed: () {
                if (first.text.length < 12) {
                  set(() => error = 'backup_password_short');
                  return;
                }
                if (create && first.text != second.text) {
                  set(() => error = 'password_mismatch');
                  return;
                }
                Navigator.pop(context, first.text);
              },
              child: Text(c.pack.t('continue_action')),
            ),
          ],
        ),
      ),
    );
    // Controllers are released after the closing animation no longer uses the fields.
    await Future<void>.delayed(const Duration(milliseconds: 250));
    first.dispose();
    second.dispose();
    return result;
  }

  Future<void> backup(bool restore) async {
    if (busy || c.store is! PersonalStore) return;
    final store = c.store as PersonalStore;
    setState(() => busy = true);
    backupBusy.value = true;
    backupStatus.value = 'backup_step_password';
    try {
      if (!restore) {
        backupStatus.value = 'backup_step_password';
        final secret = await password(create: true);
        if (secret == null) {
          backupStatus.value = 'backup_cancelled';
          return;
        }
        backupStatus.value = 'backup_step_encrypt';
        final bytes = await background.compute(encryptBackupWorker, {
          'snapshot': await store.exportSnapshot(),
          'password': secret,
        });
        backupStatus.value = 'backup_step_file';
        if (await c.native.saveBackup(bytes)) {
          backupStatus.value = 'backup_saved';
          message('backup_saved');
        } else {
          backupStatus.value = 'backup_cancelled';
        }
      } else {
        backupStatus.value = 'backup_step_file';
        final bytes = await c.native.readBackup();
        if (bytes == null) {
          backupStatus.value = 'backup_cancelled';
          return;
        }
        final secret = await password(create: false);
        if (secret == null) {
          backupStatus.value = 'backup_cancelled';
          return;
        }
        backupStatus.value = 'backup_step_verify';
        final snapshot = await background.compute(decryptBackupWorker, {
          'bytes': bytes,
          'password': secret,
        });
        final tables = snapshot['tables'];
        if (tables is! Map) throw const DomainFailure('backup_invalid');
        int count(String table) => (tables[table] is List)
            ? (tables[table] as List)
                .where((r) => r is Map && r['deleted_at'] == null)
                .length
            : 0;
        if (!mounted) return;
        backupStatus.value = 'backup_step_confirm';
        final confirmed = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: Text(c.pack.t('restore_backup')),
            content: Text(
              '${c.pack.t('restore_warning')}\n\n${c.pack.t('finances')}: ${count('transactions')}\n${c.pack.t('my_tasks')}: ${count('tasks')}\n${c.pack.t('recent_notes')}: ${count('notes')}',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: Text(c.pack.t('cancel')),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: Text(c.pack.t('restore_backup')),
              ),
            ],
          ),
        );
        if (confirmed != true) {
          backupStatus.value = 'backup_cancelled';
          return;
        }
        await store.restoreSnapshot(snapshot);
        await c.load();
        backupStatus.value = 'restore_success';
        message('restore_success');
      }
    } catch (e) {
      backupStatus.value = e is DomainFailure ? e.key : 'backup_failed';
      message(backupStatus.value);
    } finally {
      if (mounted) {
        setState(() => busy = false);
        backupBusy.value = false;
      }
    }
  }

  Future<void> notificationDetails() => Navigator.push<void>(
        context,
        MaterialPageRoute(
          builder: (_) => Scaffold(
            appBar: AppBar(title: Text(c.pack.t('permissions_diagnostics'))),
            body: SafeArea(
              child: ListenableBuilder(
                listenable: Listenable.merge([c, notificationBusy]),
                builder: (context, _) => ListView(
                  padding: const EdgeInsets.all(20),
                  children: [
                    LifeCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text(
                            c.pack.t('notification_permission'),
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          const SizedBox(height: 8),
                          Text(
                            c.pack.t(
                              !c.native.supported
                                  ? 'native_unavailable'
                                  : c.notificationStatus['enabled'] == true
                                      ? 'notifications_enabled'
                                      : 'notifications_disabled',
                            ),
                          ),
                          const SizedBox(height: 12),
                          OutlinedButton.icon(
                            onPressed: busy || !c.native.supported
                                ? null
                                : () => native('requestNotifications'),
                            icon:
                                const Icon(Icons.notifications_active_outlined),
                            label: Text(c.pack.t('notification_permission')),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                    LifeCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text(
                            c.pack.t('exact_permission'),
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          const SizedBox(height: 8),
                          Text(
                            c.pack.t(
                              !c.native.supported
                                  ? 'native_unavailable'
                                  : c.notificationStatus['exact'] == true
                                      ? 'exact_allowed'
                                      : 'exact_unavailable',
                            ),
                          ),
                          const SizedBox(height: 12),
                          OutlinedButton.icon(
                            onPressed: busy || !c.native.supported
                                ? null
                                : () => native('requestExactAlarms'),
                            icon: const Icon(Icons.alarm_on_outlined),
                            label: Text(c.pack.t('exact_permission')),
                          ),
                        ],
                      ),
                    ),
                    if (c.notificationStatus['channels']
                        case final Map channels) ...[
                      const SizedBox(height: 12),
                      LifeCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Text(
                              c.pack.t('reminder_modes'),
                              style: Theme.of(context).textTheme.titleMedium,
                            ),
                            for (final mode in ReminderMode.values)
                              ListTile(
                                contentPadding: EdgeInsets.zero,
                                title: Text(c.pack.t('mode_${mode.name}')),
                                subtitle: Text(
                                  notificationChannelDetails(
                                      channels[mode.name] as Map?),
                                ),
                                leading: Icon(
                                  mode == ReminderMode.alarm
                                      ? Icons.alarm
                                      : Icons.notifications_outlined,
                                ),
                              ),
                          ],
                        ),
                      ),
                    ],
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      onPressed:
                          busy || notificationBusy.value || !c.native.supported
                              ? null
                              : () => native('notificationSettings'),
                      icon: const Icon(Icons.settings_outlined),
                      label: Text(c.pack.t('system_settings')),
                    ),
                    const SizedBox(height: 12),
                    FilledButton.icon(
                      onPressed:
                          busy || notificationBusy.value || !c.native.supported
                              ? null
                              : testNotification,
                      icon: const Icon(Icons.send_outlined),
                      label: Text(c.pack.t('test_notification')),
                    ),
                    const SizedBox(height: 12),
                    ExpansionTile(
                      tilePadding: EdgeInsets.zero,
                      title: Text(c.pack.t('os_limitations')),
                      children: [
                        Padding(
                          padding: const EdgeInsets.only(bottom: 16),
                          child: Text(c.pack.t('alarm_limits')),
                        ),
                      ],
                    ),
                    if (c.schedulingError != null)
                      Text(
                        c.pack.t(c.schedulingError!),
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
  Future<void> backupGuide() async {
    await Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => ListenableBuilder(
          listenable: Listenable.merge([backupStatus, backupBusy]),
          builder: (context, _) => PopScope(
            canPop: !busy,
            child: Scaffold(
              appBar: AppBar(title: Text(c.pack.t('data_privacy'))),
              body: SafeArea(
                child: ListView(
                  padding: const EdgeInsets.all(20),
                  children: [
                    const Icon(Icons.lock_outline, size: 48),
                    const SizedBox(height: 16),
                    Text(
                      c.pack.t('backup_steps'),
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 12),
                    Text(c.pack.t('backup_privacy')),
                    const SizedBox(height: 20),
                    LifeCard(child: Text(c.pack.t(backupStatus.value))),
                    const SizedBox(height: 20),
                    FilledButton.icon(
                      onPressed: busy ? null : () => backup(false),
                      icon: const Icon(Icons.save_alt),
                      label: Text(c.pack.t('create_backup')),
                    ),
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      onPressed: busy ? null : () => backup(true),
                      icon: const Icon(Icons.restore),
                      label: Text(c.pack.t('restore_backup')),
                    ),
                    if (busy)
                      const Padding(
                        padding: EdgeInsets.all(16),
                        child: LinearProgressIndicator(),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: Listenable.merge([c, notificationBusy]),
        builder: (context, _) {
          final sections = <Widget>[
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              select('language', c.pack.tag,
                  {for (final p in c.catalog.packs.values) p.tag: p.name}),
              select('currency', c.currency,
                  currencyChoices(c.pack, current: c.currency)),
              select('region', c.region, formatChoices(c.catalog, c.region)),
              const SizedBox(height: 12),
              Text(c.pack.t('calendar_preferences'),
                  style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 16),
              select('week_start', '${c.weekStart}',
                  {'1': c.pack.t('monday'), '7': c.pack.t('sunday')}),
              const SizedBox(height: 12),
              LifeSelect<String>(
                key: const Key('timezone_select'),
                label: c.pack.t('timezone'),
                value: c.timezone,
                choices: {
                  'device': '${c.pack.t('device_timezone')} · ${c.deviceZone}',
                  for (final name
                      in tz.timeZoneDatabase.locations.keys.toList()..sort())
                    name: name,
                },
                searchLabel: c.pack.t('search_options'),
                dialog: true,
                onChanged:
                    busy ? null : (value) => preference('timezone', value),
              ),
            ]),
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              SettingsGroup(children: [
                SettingsRow(
                    icon: Icons.notifications_outlined,
                    title: c.pack.t(c.notificationStatus['supported'] == true
                        ? c.notificationStatus['enabled'] == true
                            ? 'notifications_enabled'
                            : 'notifications_disabled'
                        : 'native_unavailable'),
                    trailing: IconButton(
                        tooltip: c.pack.t('refresh'),
                        icon: const Icon(Icons.refresh),
                        onPressed: busy
                            ? null
                            : () async {
                                try {
                                  await c.refresh(forceReminders: true);
                                } catch (_) {
                                  message('read_failed');
                                }
                              })),
                SettingsRow(
                    icon: Icons.tune_outlined,
                    title: c.pack.t('notification_details'),
                    onTap: busy ? null : notificationDetails),
              ]),
              const SizedBox(height: 20),
              FilledButton.icon(
                  key: const Key('test_notification'),
                  onPressed:
                      busy || notificationBusy.value || !c.native.supported
                          ? null
                          : testNotification,
                  icon: const Icon(Icons.notifications_active_outlined),
                  label: Text(c.pack.t('test_notification'))),
              const SizedBox(height: 12),
              ExpansionTile(
                  title: Text(c.pack.t('details')),
                  tilePadding: EdgeInsets.zero,
                  children: [
                    select('snooze_minutes',
                        c.preferences['snooze_minutes'] ?? '10', {
                      for (final v in ['5', '10', '15', '30'])
                        v: '$v ${c.pack.t('minutes')}',
                    }),
                    select('notification_content',
                        c.preferences['notification_content'] ?? 'hide', {
                      'hide': c.pack.t('content_hide'),
                      'show': c.pack.t('content_show'),
                    }),
                  ]),
            ]),
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Text(c.pack.t('local_privacy')),
              const SizedBox(height: 12),
              Text(c.pack.t('backup_privacy')),
              const SizedBox(height: 24),
              SettingsGroup(children: [
                SettingsRow(
                    key: const Key('help_center'),
                    title: helpCenterTitle(c.pack.tag),
                    icon: Icons.help_outline_rounded,
                    onTap: () => Navigator.push<void>(
                        context,
                        MaterialPageRoute(
                            builder: (_) => HelpCenterScreen(
                                languageTag: c.pack.tag,
                                onOpenLink: c.native.openExternalLink)))),
                SettingsRow(
                    key: const Key('legal_privacy'),
                    title: c.pack.t('legal_privacy'),
                    icon: Icons.privacy_tip_outlined,
                    trailing: const Icon(Icons.open_in_new_rounded, size: 20),
                    onTap: () => legalLink('/privacy')),
                SettingsRow(
                    key: const Key('legal_terms'),
                    title: c.pack.t('legal_terms'),
                    icon: Icons.description_outlined,
                    trailing: const Icon(Icons.open_in_new_rounded, size: 20),
                    onTap: () => legalLink('/terms')),
                SettingsRow(
                    title: c.pack.t('backup_manage'),
                    icon: Icons.lock_outline,
                    onTap:
                        busy || !c.native.supported || c.store is! PersonalStore
                            ? null
                            : backupGuide),
                SettingsRow(
                    title: c.pack.t('module_profiles'),
                    icon: Icons.person_outline,
                    onTap: () => Navigator.push<void>(
                        context,
                        MaterialPageRoute(
                            builder: (_) => PersonalModulesPage(
                                controller: c, table: OfflineTable.profiles)))),
              ]),
            ]),
          ];
          if (widget.section != null) return sections[widget.section!];
          void open(int index, String title) {
            Navigator.push<void>(
                context,
                MaterialPageRoute(
                    builder: (_) => Scaffold(
                          appBar: settingsAppBar(context, c.pack.t(title)),
                          body: SafeArea(
                              child: ListView(
                                  key: Key('settings_section_$index'),
                                  padding: settingsPagePadding(context),
                                  children: [
                                PersonalSettings(controller: c, section: index)
                              ])),
                        )));
          }

          return SettingsGroup(children: [
            SettingsRow(
                icon: Icons.palette_outlined,
                title: c.pack.t('appearance'),
                onTap: () => Navigator.push<void>(
                    context,
                    MaterialPageRoute(
                        builder: (_) => AppearanceEditor(controller: c)))),
            SettingsRow(
                key: const Key('settings_0'),
                icon: Icons.language_outlined,
                title: c.pack.t('language_region'),
                onTap: () => open(0, 'language_region')),
            SettingsRow(
                key: const Key('settings_1'),
                icon: Icons.notifications_outlined,
                title: c.pack.t('notifications'),
                onTap: () => open(1, 'notifications')),
            SettingsRow(
                key: const Key('settings_2'),
                icon: Icons.lock_outline,
                title: c.pack.t('data_privacy'),
                onTap: () => open(2, 'data_privacy')),
          ]);
        },
      );
}
