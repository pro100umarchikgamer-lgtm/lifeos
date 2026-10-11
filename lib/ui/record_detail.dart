import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../app_controller.dart';
import '../domain/models.dart';
import 'design.dart';
import 'money_format.dart';
import 'quick_add.dart';

class RecordDetail extends StatefulWidget {
  const RecordDetail({super.key, required this.controller, required this.id});
  final AppController controller;
  final String id;
  @override
  State<RecordDetail> createState() => _RecordDetailState();
}
class _RecordDetailState extends State<RecordDetail> {
  bool busy = false;
  AppController get c => widget.controller;
  Future<void> edit(Record record) async {
    final changed = await showModalBottomSheet<bool>(context: context, isScrollControlled: true, useSafeArea: true,
      isDismissible: false, enableDrag: false, builder: (_) => QuickAdd(controller: c, kind: record.kind, record: record));
    if (changed == true) { await c.refresh(); }
  }
  Future<void> remove(Record record) async {
    final confirmed = await showDialog<bool>(context: context, builder: (context) => AlertDialog(
      title: Text(c.pack.t('delete')), content: Text(c.pack.t('delete_confirm')),
      actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: Text(c.pack.t('cancel'))),
        FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(c.pack.t('delete')))]));
    if (confirmed != true || !mounted) return;
    setState(() => busy = true);
    try {
      await c.execute(DeleteRecord(const Uuid().v4(), record.id, record.kind, record.revision));
      if (!mounted) return;
      final messenger = ScaffoldMessenger.of(context);
      Navigator.pop(context);
      messenger.showSnackBar(SnackBar(content: Text(c.pack.t('deleted')), duration: const Duration(seconds: 10),
        action: SnackBarAction(label: c.pack.t('undo'), onPressed: () async {
          try { await c.execute(UndoRecordChange(const Uuid().v4(), record.id, record.kind, record.revision + 1)); }
          catch (e) { messenger.showSnackBar(SnackBar(content: Text(c.pack.t(e is DomainFailure ? e.key : 'change_failed')))); }
        })));
    } catch (e) {
      if (mounted) { setState(() => busy = false); ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(c.pack.t(e is DomainFailure ? e.key : 'change_failed')))); }
    }
  }
  @override
  Widget build(BuildContext context) => ListenableBuilder(listenable: c, builder: (context, _) {
    final record = c.records.where((r) => r.id == widget.id).firstOrNull;
    return Scaffold(appBar: AppBar(title: Text(c.pack.t(record?.kind.name ?? 'record_missing'))),
      body: record == null ? Center(child: Text(c.pack.t('record_missing'))) : SafeArea(child: Center(
        child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 560), child: ListView(padding: const EdgeInsets.all(18), children: [
          if (record.amountMinor != null) Text(formatMoney(record.currency!, record.amountMinor!, locale: c.region),
            style: Theme.of(context).textTheme.headlineMedium?.copyWith(color: record.kind == EntryKind.income ? LifePalette.green : LifePalette.red)),
          if (record.amountMinor != null) const SizedBox(height: 12),
          LifeCard(child: SelectableText(record.text.isEmpty ? c.pack.t(record.kind.name) : record.text,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(height: 1.5))),
          const SizedBox(height: 12),
          Text(record.date ?? MaterialLocalizations.of(context).formatMediumDate(record.createdAt.toLocal())),
          if (c.scheduleFor(record) case final CalendarEntry linked) ...[
            const SizedBox(height: 12), LifeCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(linked.schedule.localStart.replaceFirst('T', ' ')),
              Text(c.pack.t('repeat_${linked.schedule.repeat.name}')),
              if (linked.schedule.reminder) Text(c.pack.t('mode_${linked.schedule.mode.name}')),
            ])),
          ],
          const SizedBox(height: 20), FilledButton.icon(key: const Key('edit_record'), onPressed: busy ? null : () => edit(record), icon: const Icon(Icons.edit_outlined), label: Text(c.pack.t('edit'))),
          const SizedBox(height: 8), OutlinedButton.icon(key: const Key('delete_record'), onPressed: busy ? null : () => remove(record), icon: const Icon(Icons.delete_outline), label: Text(c.pack.t('delete'))),
          if (record.revision > 1) TextButton.icon(onPressed: busy ? null : () async {
            setState(() => busy = true);
            try { await c.execute(UndoRecordChange(const Uuid().v4(), record.id, record.kind, record.revision)); }
            catch (e) { if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(c.pack.t(e is DomainFailure ? e.key : 'change_failed')))); }
            finally { if (mounted) setState(() => busy = false); }
          }, icon: const Icon(Icons.undo), label: Text(c.pack.t('undo_last_change'))),
        ])))));
  });
}
