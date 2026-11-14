import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../app_controller.dart';
import '../domain/models.dart';
import 'design.dart';
import 'money_format.dart';
import 'quick_add.dart';
import 'money_details.dart';
import 'notices.dart';
import 'personal_modules.dart';

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
    final changed =
        await showEntryEditor(context, c, record.kind, record: record);
    if (changed == true) {
      await c.refresh();
    }
  }

  Future<void> remove(Record record) async {
    final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
                title: Text(c.pack.t('delete')),
                content: Text(c.pack.t('delete_confirm')),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(context, false),
                      child: Text(c.pack.t('cancel'))),
                  FilledButton(
                      onPressed: () => Navigator.pop(context, true),
                      child: Text(c.pack.t('delete')))
                ]));
    if (confirmed != true || !mounted) return;
    setState(() => busy = true);
    try {
      await c.execute(DeleteRecord(
          const Uuid().v4(), record.id, record.kind, record.revision));
      if (!mounted) return;
      final notices = LifeNoticeScope.of(context);
      FocusScope.of(context).unfocus();
      Navigator.pop(context);
      notices.show(c.pack.t('deleted'),
          undoLabel: c.pack.t('undo'),
          undo: () => c.execute(UndoRecordChange(
              const Uuid().v4(), record.id, record.kind, record.revision + 1)),
          errorLabel: (e) =>
              c.pack.t(e is DomainFailure ? e.key : 'change_failed'));
    } catch (e) {
      if (mounted) {
        setState(() => busy = false);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content:
                Text(c.pack.t(e is DomainFailure ? e.key : 'change_failed'))));
      }
    }
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: c,
        builder: (context, _) {
          final record = c.records.where((r) => r.id == widget.id).firstOrNull;
          final theme = Theme.of(context), colors = theme.colorScheme;
          return Scaffold(
            appBar: AppBar(
                title: Text(c.pack.t(record?.kind.name ?? 'record_missing'))),
            bottomNavigationBar: record == null
                ? null
                : SafeArea(
                    top: false,
                    child: Container(
                      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
                      decoration: BoxDecoration(
                          color: colors.surface,
                          border: Border(
                              top: BorderSide(color: colors.outlineVariant))),
                      child: Center(
                          heightFactor: 1,
                          child: ConstrainedBox(
                            constraints: const BoxConstraints(maxWidth: 560),
                            child: SizedBox(
                                width: double.infinity,
                                child: FilledButton.icon(
                                  key: const Key('edit_record'),
                                  onPressed: busy ? null : () => edit(record),
                                  icon:
                                      const Icon(Icons.edit_outlined, size: 20),
                                  label: Text(c.pack.t('edit')),
                                )),
                          )),
                    ),
                  ),
            body: record == null
                ? Center(child: Text(c.pack.t('record_missing')))
                : SafeArea(
                    child: Center(
                        child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 640),
                    child: ListView(
                      padding: const EdgeInsets.fromLTRB(16, 20, 16, 28),
                      children: [
                        if (record.amountMinor != null) ...[
                          Text(
                              formatMoney(record.currency!, record.amountMinor!,
                                  locale: c.region),
                              style: theme.textTheme.headlineMedium?.copyWith(
                                  color: lifeAccent(
                                      context,
                                      record.kind == EntryKind.income
                                          ? LifePalette.green
                                          : LifePalette.red))),
                          const SizedBox(height: 20),
                        ],
                        LifeCard(
                            child: SelectableText(
                          record.text.isEmpty
                              ? c.pack.t(record.kind.name)
                              : record.text,
                          style:
                              theme.textTheme.bodyLarge?.copyWith(height: 1.6),
                        )),
                        const SizedBox(height: 20),
                        Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(Icons.calendar_today_outlined,
                                  size: 18, color: colors.onSurfaceVariant),
                              const SizedBox(width: 10),
                              Expanded(
                                  child: Text(
                                      record.date ??
                                          MaterialLocalizations.of(context)
                                              .formatMediumDate(
                                                  record.createdAt.toLocal()),
                                      style: theme.textTheme.bodyMedium
                                          ?.copyWith(
                                              color: colors.onSurfaceVariant))),
                            ]),
                        if (c.scheduleFor(record)
                            case final CalendarEntry linked) ...[
                          const SizedBox(height: 16),
                          LifeCard(
                              child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                Row(children: [
                                  Icon(Icons.schedule_outlined,
                                      size: 20, color: colors.primary),
                                  const SizedBox(width: 10),
                                  Expanded(
                                      child: Text(linked.schedule.localStart
                                          .replaceFirst('T', ' '))),
                                ]),
                                const SizedBox(height: 8),
                                Text(
                                    c.pack.t(
                                        'repeat_${linked.schedule.repeat.name}'),
                                    style: theme.textTheme.bodySmall?.copyWith(
                                        color: colors.onSurfaceVariant)),
                                if (linked.schedule.reminder)
                                  Text(
                                      c.pack.t(
                                          'mode_${linked.schedule.mode.name}'),
                                      style: theme.textTheme.bodySmall
                                          ?.copyWith(
                                              color: colors.onSurfaceVariant)),
                              ])),
                        ],
                        if (record.amountMinor != null) ...[
                          const SizedBox(height: 20),
                          LifeCard(
                              padding: EdgeInsets.zero,
                              child: ListTile(
                                leading: const Icon(
                                    Icons.account_balance_wallet_outlined),
                                title: Text(c.pack.t('account_and_splits')),
                                trailing: const Icon(
                                    Icons.chevron_right_rounded,
                                    size: 20),
                                onTap: busy
                                    ? null
                                    : () => showModalBottomSheet<void>(
                                        context: context,
                                        isScrollControlled: true,
                                        useSafeArea: true,
                                        builder: (_) => MoneyDetails(
                                            controller: c, record: record)),
                              )),
                        ],
                        if (record.kind == EntryKind.note) ...[
                          const SizedBox(height: 20),
                          LifeCard(
                              padding: EdgeInsets.zero,
                              child: Column(children: [
                                for (final table in [
                                  OfflineTable.noteMetadata,
                                  OfflineTable.recordLinks,
                                  OfflineTable.checklists
                                ])
                                  ListTile(
                                    leading: Icon(switch (table) {
                                      OfflineTable.noteMetadata =>
                                        Icons.label_outline_rounded,
                                      OfflineTable.checklists =>
                                        Icons.checklist_rounded,
                                      _ => Icons.link_rounded,
                                    }),
                                    title:
                                        Text(c.pack.t('module_${table.name}')),
                                    trailing: const Icon(
                                        Icons.chevron_right_rounded,
                                        size: 20),
                                    onTap: () => Navigator.push<void>(
                                        context,
                                        MaterialPageRoute(
                                            builder: (_) => PersonalModulesPage(
                                                controller: c,
                                                table: table,
                                                noteId: record.id))),
                                  ),
                              ])),
                        ],
                        const SizedBox(height: 24),
                        if (record.revision > 1)
                          TextButton.icon(
                            onPressed: busy
                                ? null
                                : () async {
                                    setState(() => busy = true);
                                    try {
                                      await c.execute(UndoRecordChange(
                                          const Uuid().v4(),
                                          record.id,
                                          record.kind,
                                          record.revision));
                                    } catch (e) {
                                      if (context.mounted) {
                                        ScaffoldMessenger.of(context)
                                            .showSnackBar(SnackBar(
                                                content: Text(c.pack.t(
                                                    e is DomainFailure
                                                        ? e.key
                                                        : 'change_failed'))));
                                      }
                                    } finally {
                                      if (mounted) setState(() => busy = false);
                                    }
                                  },
                            icon: const Icon(Icons.undo_rounded, size: 20),
                            label: Text(c.pack.t('undo_last_change')),
                          ),
                        TextButton.icon(
                          key: const Key('delete_record'),
                          onPressed: busy ? null : () => remove(record),
                          style: TextButton.styleFrom(
                              foregroundColor: colors.error),
                          icon: const Icon(Icons.delete_outline_rounded,
                              size: 20),
                          label: Text(c.pack.t('delete')),
                        ),
                      ],
                    ),
                  ))),
          );
        },
      );
}
