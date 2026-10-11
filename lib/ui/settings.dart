import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:timezone/timezone.dart' as tz;
import '../app_controller.dart';
import '../domain/action_engine.dart';
import '../domain/models.dart';
import '../services/backup_service.dart';
import 'design.dart';

class PersonalSettings extends StatefulWidget {
  const PersonalSettings({super.key, required this.controller});
  final AppController controller;
  @override
  State<PersonalSettings> createState() => _PersonalSettingsState();
}
class _PersonalSettingsState extends State<PersonalSettings> {
  AppController get c => widget.controller;
  bool busy = false;
  void message(String key) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(c.pack.t(key)))); }
  Future<void> preference(String key, String value) async {
    try { await c.preference(key, value); } catch (e) { message(e is DomainFailure ? e.key : 'change_failed'); }
  }
  Widget select(String key, String value, Map<String, String> choices, {String? label}) => Padding(
    padding: const EdgeInsets.only(bottom: 12), child: DropdownButtonFormField<String>(key: ValueKey('${key}_$value'), initialValue: value, isExpanded: true,
      decoration: InputDecoration(labelText: c.pack.t(label ?? key)), items: [for (final entry in choices.entries) DropdownMenuItem(value: entry.key, child: Text(entry.value, overflow: TextOverflow.ellipsis))],
      onChanged: busy ? null : (v) { if (v != null) preference(key, v); }));
  Future<void> native(String method) async {
    try { await c.native.request(method); await c.refresh(); } catch (_) { message('native_unavailable'); }
  }
  Future<String?> password({required bool create}) async {
    final first = TextEditingController(), second = TextEditingController();
    String? error;
    final result = await showDialog<String>(context: context, barrierDismissible: false, builder: (_) => StatefulBuilder(builder: (context,set) => AlertDialog(
      title: Text(c.pack.t('backup_password')), content: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, children: [
        Text(c.pack.t(create ? 'backup_password_help' : 'restore_password_help')),
        const SizedBox(height: 12), TextField(controller: first, obscureText: true, enableSuggestions: false, autocorrect: false,
          decoration: InputDecoration(labelText: c.pack.t('backup_password'))),
        if (create) ...[const SizedBox(height: 12), TextField(controller: second, obscureText: true, enableSuggestions: false, autocorrect: false,
          decoration: InputDecoration(labelText: c.pack.t('repeat_password')))],
        if (error != null) Text(c.pack.t(error!), style: TextStyle(color: Theme.of(context).colorScheme.error)),
      ])), actions: [TextButton(onPressed: () => Navigator.pop(context), child: Text(c.pack.t('cancel'))),
        FilledButton(onPressed: () {
          if (first.text.length < 12) { set(() => error = 'backup_password_short'); return; }
          if (create && first.text != second.text) { set(() => error = 'password_mismatch'); return; }
          Navigator.pop(context, first.text);
        }, child: Text(c.pack.t('continue_action')))])));
    // Controllers are released after the closing animation no longer uses the fields.
    await Future<void>.delayed(const Duration(milliseconds: 250));
    first.dispose(); second.dispose();
    return result;
  }
  Future<void> backup(bool restore) async {
    if (busy || c.store is! PersonalStore) return;
    final store = c.store as PersonalStore;
    setState(() => busy = true);
    try {
      if (!restore) {
        final secret = await password(create: true); if (secret == null) return;
        final bytes = await compute(encryptBackupWorker, {'snapshot': await store.exportSnapshot(), 'password': secret});
        if (await c.native.saveBackup(bytes)) message('backup_saved');
      } else {
        final bytes = await c.native.readBackup(); if (bytes == null) return;
        final secret = await password(create: false); if (secret == null) return;
        final snapshot = await compute(decryptBackupWorker, {'bytes': bytes, 'password': secret});
        final tables = snapshot['tables'];
        if (tables is! Map) throw const DomainFailure('backup_invalid');
        int count(String table) => (tables[table] is List) ? (tables[table] as List).where((r) => r is Map && r['deleted_at'] == null).length : 0;
        if (!mounted) return;
        final confirmed = await showDialog<bool>(context: context, builder: (context) => AlertDialog(
          title: Text(c.pack.t('restore_backup')), content: Text('${c.pack.t('restore_warning')}\n\n${c.pack.t('finances')}: ${count('transactions')}\n${c.pack.t('my_tasks')}: ${count('tasks')}\n${c.pack.t('recent_notes')}: ${count('notes')}'),
          actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: Text(c.pack.t('cancel'))),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(c.pack.t('restore_backup')))]));
        if (confirmed != true) return;
        await store.restoreSnapshot(snapshot);
        await c.load(); message('restore_success');
      }
    } catch (e) { message(e is DomainFailure ? e.key : 'backup_failed'); }
    finally { if (mounted) setState(() => busy = false); }
  }
  Future<void> zone() async {
    String query = '';
    final selected = await showDialog<String>(context: context, builder: (_) => StatefulBuilder(builder: (context, set) {
      final zones = tz.timeZoneDatabase.locations.keys.where((z) => z.toLowerCase().contains(query.toLowerCase())).toList()..sort();
      return AlertDialog(title: Text(c.pack.t('timezone')), content: SizedBox(width: 360, height: 400, child: Column(children: [
        TextField(decoration: InputDecoration(labelText: c.pack.t('search')), onChanged: (v) => set(() => query = v)),
        Expanded(child: ListView(children: [ListTile(title: Text(c.pack.t('device_timezone')), onTap: () => Navigator.pop(context, 'device')),
          for (final z in zones) ListTile(title: Text(z), onTap: () => Navigator.pop(context, z))])),
      ])), actions: [TextButton(onPressed: () => Navigator.pop(context), child: Text(c.pack.t('cancel')))]);
    }));
    if (selected != null) await preference('timezone', selected);
  }
  @override
  Widget build(BuildContext context) => ListenableBuilder(listenable: c, builder: (context, _) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
    LifeCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(c.pack.t('local_profile'), style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
      const SizedBox(height: 8), Text(c.pack.t('local_privacy')),
    ])), const SizedBox(height: 12),
    LifeCard(child: Column(children: [
      select('theme', c.theme, {for (final v in ['system','light','dark']) v: c.pack.t(v)}),
      select('language', c.pack.tag, {for (final p in c.catalog.packs.values) p.tag: p.name}),
      select('currency', c.currency, {for (final code in {'USD','EUR','RUB','KZT','UZS','UAH','GBP','GEL','AZN','AMD','TJS','KGS',c.currency}) code: code}),
      select('region', c.region, {for (final code in {'ru','en','de','fr','es','it','pt','kk','uz','uk','ka','az','hy','tg','ky',c.region}) code: code.toUpperCase()}),
      select('week_start', '${c.weekStart}', {'1': c.pack.t('monday'), '7': c.pack.t('sunday')}),
      ListTile(contentPadding: EdgeInsets.zero, title: Text(c.pack.t('timezone')), subtitle: Text(c.timezone == 'device' ? '${c.pack.t('device_timezone')} · ${c.deviceZone}' : c.timezone),
        trailing: const Icon(Icons.chevron_right), onTap: busy ? null : zone),
    ])), const SizedBox(height: 12),
    LifeCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(children: [Expanded(child: Text(c.pack.t('notifications'), style: Theme.of(context).textTheme.titleMedium)), IconButton(tooltip: c.pack.t('refresh'), onPressed: busy ? null : () async { try { await c.refresh(); } catch (_) { message('read_failed'); } }, icon: const Icon(Icons.refresh))]), const SizedBox(height: 8),
      Text(c.pack.t(c.notificationStatus['supported'] == true ? c.notificationStatus['enabled'] == true ? 'notifications_enabled' : 'notifications_disabled' : 'native_unavailable')),
      Text(c.pack.t(c.notificationStatus['exact'] == true ? 'exact_allowed' : 'exact_unavailable')),
      if (c.notificationStatus['channels'] case final Map channels)
        for (final mode in ReminderMode.values) Text('${c.pack.t('mode_${mode.name}')}: ${c.pack.t(channels[mode.name] is Map && (channels[mode.name] as Map)['importance'] != 0 && (channels[mode.name] as Map)['sound'] == true ? 'audible_enabled' : 'audible_restricted')}'),
      const SizedBox(height: 8), Text(c.pack.t('alarm_limits'), style: Theme.of(context).textTheme.bodySmall),
      if (c.schedulingError != null) Text(c.pack.t(c.schedulingError!), style: TextStyle(color: Theme.of(context).colorScheme.error)),
      const SizedBox(height: 12),
      select('snooze_minutes', c.preferences['snooze_minutes'] ?? '10', {for (final v in ['5','10','15','30']) v: '$v ${c.pack.t('minutes')}'}),
      select('notification_content', c.preferences['notification_content'] ?? 'hide', {'hide': c.pack.t('content_hide'), 'show': c.pack.t('content_show')}),
      Wrap(spacing: 8, children: [
        OutlinedButton(onPressed: busy || !c.native.supported ? null : () => native('requestNotifications'), child: Text(c.pack.t('notification_permission'))),
        OutlinedButton(onPressed: busy || !c.native.supported ? null : () => native('requestExactAlarms'), child: Text(c.pack.t('exact_permission'))),
        TextButton(onPressed: busy || !c.native.supported ? null : () => native('notificationSettings'), child: Text(c.pack.t('system_settings'))),
      ]),
      FilledButton.icon(onPressed: busy || !c.native.supported ? null : () async {
        try { await c.native.testNotification({'title': 'LifeOS', 'message': c.pack.t('test_message'), 'doneLabel': c.pack.t('complete'), 'dismissLabel': c.pack.t('dismiss'), 'snoozeLabel': c.pack.t('snooze')}); }
        catch (_) { message('native_unavailable'); }
      }, icon: const Icon(Icons.notifications_outlined), label: Text(c.pack.t('test_notification'))),
    ])), const SizedBox(height: 12),
    LifeCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text(c.pack.t('data_privacy'), style: Theme.of(context).textTheme.titleMedium), const SizedBox(height: 8), Text(c.pack.t('backup_privacy')),
      const SizedBox(height: 12), OutlinedButton.icon(onPressed: busy || !c.native.supported || c.store is! PersonalStore ? null : () => backup(false), icon: const Icon(Icons.lock_outline), label: Text(c.pack.t('create_backup'))),
      OutlinedButton.icon(onPressed: busy || !c.native.supported || c.store is! PersonalStore ? null : () => backup(true), icon: const Icon(Icons.restore), label: Text(c.pack.t('restore_backup'))),
      if (busy) const Padding(padding: EdgeInsets.all(12), child: LinearProgressIndicator()),
    ])),
  ]));
}
