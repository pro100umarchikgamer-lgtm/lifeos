import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../app_controller.dart';
import '../domain/models.dart';
import 'design.dart';
import 'calendar.dart';
import 'entry_sheet.dart';
import 'selection.dart';
import 'preference_choices.dart';

Future<bool?> showEntryEditor(
  BuildContext context,
  AppController controller,
  EntryKind kind, {
  Record? record,
}) {
  if (kind == EntryKind.note) {
    return Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) =>
            QuickAdd(controller: controller, kind: kind, record: record),
      ),
    );
  }
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    sheetAnimationStyle: MediaQuery.disableAnimationsOf(context)
        ? AnimationStyle.noAnimation
        : null,
    isDismissible: false,
    enableDrag: false,
    builder: (_) =>
        QuickAdd(controller: controller, kind: kind, record: record),
  );
}

class QuickAdd extends StatefulWidget {
  const QuickAdd({
    super.key,
    required this.controller,
    required this.kind,
    this.record,
  });
  final AppController controller;
  final EntryKind kind;
  final Record? record;
  @override
  State<QuickAdd> createState() => _QuickAddState();
}

class _QuickAddState extends State<QuickAdd> {
  final _amount = TextEditingController();
  final _text = TextEditingController();
  final _descriptionFocus = FocusNode();
  late String _account, _category;
  late final TextEditingController _currency;
  final _operation = const Uuid().v4();
  late DateTime _date;
  bool _saving = false;
  bool _advanced = false;
  String? _error;
  ScheduleSpec? _schedule;
  int _scheduleRevision = 0;
  bool get _money =>
      widget.kind == EntryKind.expense || widget.kind == EntryKind.income;
  @override
  void initState() {
    super.initState();
    _date = widget.controller.now;
    final record = widget.record;
    _account = record?.accountId ?? '';
    _category = record?.categoryId ?? '';
    _amount.addListener(_changed);
    _text.addListener(_changed);
    _currency = TextEditingController(
      text: record?.currency?.code ?? widget.controller.currency,
    );
    if (record != null) {
      _text.text = record.text;
      _date = record.date == null
          ? widget.controller.now
          : DateTime.parse(record.date!);
      if (record.currency != null) {
        final digits = record.currency!.digits;
        final minor = record.amountMinor!.toString().padLeft(digits + 1, '0');
        _amount.text = digits == 0
            ? minor
            : '${minor.substring(0, minor.length - digits)}.${minor.substring(minor.length - digits)}';
      }
      final linked = widget.controller.scheduleFor(record);
      _schedule = linked?.schedule;
      _scheduleRevision = linked?.revision ?? 0;
      _advanced = _schedule != null;
    }
  }

  void _changed() {
    if (mounted) setState(() {});
  }

  bool get _valid {
    if (!_money) return _text.text.trim().isNotEmpty;
    try {
      Currency.fromCode(_currency.text).parse(_amount.text);
      return true;
    } on DomainFailure {
      return false;
    }
  }

  Map<String, String> _choices(OfflineTable table) => {
    '': widget.controller.pack.t('unassigned'),
    for (final row in widget.controller.offline[table] ?? [])
      if ((row['archived'] != 1 ||
              row['id'] ==
                  (table == OfflineTable.accounts ? _account : _category)) &&
          (table != OfflineTable.accounts || row['currency'] == _currency.text))
        row['id'] as String: row['name'] as String,
  };
  @override
  void dispose() {
    _amount.dispose();
    _text.dispose();
    _currency.dispose();
    _descriptionFocus.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving || !_valid) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final record = widget.record;
      final AppAction action;
      if (record == null) {
        action = switch (widget.kind) {
          EntryKind.expense || EntryKind.income => CreateMoney(
            _operation,
            kind: widget.kind,
            amount: _amount.text,
            currencyCode: _currency.text,
            date: _date,
            label: _text.text,
            accountId: _account.isEmpty ? null : _account,
            categoryId: _category.isEmpty ? null : _category,
          ),
          EntryKind.task => CreateTask(
            _operation,
            _text.text,
            schedule: _schedule,
          ),
          EntryKind.note => CreateNote(
            _operation,
            _text.text,
            schedule: _schedule,
          ),
        };
      } else {
        action = switch (widget.kind) {
          EntryKind.expense || EntryKind.income => EditMoney(
            _operation,
            record.id,
            record.kind,
            record.revision,
            amount: _amount.text,
            currencyCode: _currency.text,
            date: _date,
            label: _text.text,
            updateDetails: true,
            accountId: _account.isEmpty ? null : _account,
            categoryId: _category.isEmpty ? null : _category,
          ),
          EntryKind.task => EditTask(
            _operation,
            record.id,
            record.revision,
            _text.text,
            schedule: _schedule,
            updateSchedule: true,
            expectedScheduleRevision: _scheduleRevision,
          ),
          EntryKind.note => EditNote(
            _operation,
            record.id,
            record.revision,
            _text.text,
            schedule: _schedule,
            updateSchedule: true,
            expectedScheduleRevision: _scheduleRevision,
          ),
        };
      }
      await widget.controller.execute(action);
      if (mounted) Navigator.pop(context, true);
    } catch (error) {
      if (mounted) {
        setState(() {
          _saving = false;
          _error = error is DomainFailure ? error.key : 'save_failed';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final pack = widget.controller.pack;
    final accent = switch (widget.kind) {
      EntryKind.expense => LifePalette.red,
      EntryKind.income => LifePalette.green,
      EntryKind.task => LifePalette.blue,
      EntryKind.note => LifePalette.orange,
    };
    final icon = switch (widget.kind) {
      EntryKind.expense => Icons.remove_circle_rounded,
      EntryKind.income => Icons.add_circle_rounded,
      EntryKind.task => Icons.check_box_rounded,
      EntryKind.note => Icons.notes_rounded,
    };
    if (widget.kind == EntryKind.note) {
      return PopScope(
        canPop: !_saving,
        child: Scaffold(
          appBar: AppBar(
            title: Text(pack.t(widget.record == null ? 'create_note' : 'edit')),
            actions: [
              TextButton(
                key: const Key('save'),
                onPressed: _saving || !_valid ? null : _save,
                child: Text(pack.t(_saving ? 'saving' : 'save')),
              ),
            ],
          ),
          body: SafeArea(
            child: Column(
              children: [
                Expanded(
                  child: TextField(
                    key: const Key('entry_text'),
                    controller: _text,
                    autofocus: true,
                    enabled: !_saving,
                    expands: true,
                    minLines: null,
                    maxLines: null,
                    keyboardType: TextInputType.multiline,
                    textCapitalization: TextCapitalization.sentences,
                    style: Theme.of(context).textTheme.bodyLarge
                        ?.copyWith(height: 1.6),
                    decoration: InputDecoration(
                      hintText: pack.t('note_text'),
                      filled: false,
                      border: InputBorder.none,
                      enabledBorder: InputBorder.none,
                      focusedBorder: InputBorder.none,
                      contentPadding: const EdgeInsets.all(24),
                    ),
                  ),
                ),
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: Text(
                      pack.t(_error!),
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ),
                TextButton.icon(
                  onPressed: _saving
                      ? null
                      : () async {
                          FocusScope.of(context).unfocus();
                          await showModalBottomSheet<void>(
                            context: context,
                            isScrollControlled: true,
                            useSafeArea: true,
                            builder: (_) => StatefulBuilder(
                              builder: (context, update) =>
                                  SingleChildScrollView(
                                    padding: const EdgeInsets.all(20),
                                    child: ScheduleEditor(
                                      controller: widget.controller,
                                      value: _schedule,
                                      onChanged: (v) {
                                        setState(() => _schedule = v);
                                        update(() {});
                                      },
                                    ),
                                  ),
                            ),
                          );
                        },
                  icon: Icon(
                    _schedule?.reminder == true
                        ? Icons.notifications_active_outlined
                        : Icons.event_outlined,
                  ),
                  label: Text(
                    pack.t(
                      _schedule == null ? 'add_reminder' : 'scheduled_date',
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    }
    return EntrySheet(
      saving: _saving,
      saveLabel: pack.t(_saving ? 'saving' : 'save'),
      onSave: _save,
      canSave: _valid,
      header: Row(
        children: [
          CircleAvatar(
            backgroundColor: lifeAccent(context, accent).withValues(alpha: .12),
            child: Icon(icon, color: lifeAccent(context, accent)),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              pack.t(
                widget.record == null ? 'create_${widget.kind.name}' : 'edit',
              ),
              style: Theme.of(context).textTheme.titleLarge
                  ?.copyWith(fontWeight: FontWeight.w800),
            ),
          ),
          IconButton(
            tooltip: pack.t('cancel'),
            onPressed: _saving ? null : () => Navigator.pop(context),
            icon: const Icon(Icons.close),
          ),
        ],
      ),
      children: [
        if (_money) ...[
          TextField(
            key: const Key('amount'),
            controller: _amount,
            autofocus: true,
            enabled: !_saving,
            style: Theme.of(context).textTheme.headlineMedium
                ?.copyWith(fontWeight: FontWeight.w700),
            textInputAction: TextInputAction.next,
            onSubmitted: (_) => _descriptionFocus.requestFocus(),
            scrollPadding: const EdgeInsets.all(24),
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(
              labelText: pack.t('amount'),
              suffixText: _currency.text.toUpperCase(),
            ),
          ),
          const SizedBox(height: 12),
          LifeSelect<String>(
            key: const Key('entry_currency'),
            label: pack.t('currency'),
            value: _currency.text,
            choices: currencyChoices(pack, current: _currency.text),
            dialog: true,
            searchLabel: pack.t('search'),
            onChanged: _saving
                ? null
                : (v) => setState(() {
                    _currency.text = v;
                    if (!_choices(OfflineTable.accounts)
                        .containsKey(_account)) {
                      _account = '';
                    }
                  }),
          ),
          const SizedBox(height: 12),
        ],
        TextField(
          key: const Key('entry_text'),
          controller: _text,
          autofocus: !_money,
          enabled: !_saving,
          focusNode: _descriptionFocus,
          textInputAction: TextInputAction.done,
          onSubmitted: (_) {
            if (_valid) _save();
          },
          minLines: 1,
          maxLines: 2,
          style: Theme.of(context).textTheme.bodyLarge,
          textCapitalization: TextCapitalization.sentences,
          decoration: InputDecoration(
            labelText: pack.t(
              _money
                  ? 'label_optional'
                  : widget.kind == EntryKind.task
                  ? 'task_title'
                  : 'note_text',
            ),
          ),
        ),
        if (_money) ...[
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 4,
            children: [
              for (final purpose
                  in widget.kind == EntryKind.income
                      ? ['salary', 'gift', 'other']
                      : ['food', 'transport', 'home', 'other'])
                ActionChip(
                  label: Text(pack.t('purpose_$purpose')),
                  onPressed: () {
                    final label = pack.t('purpose_$purpose');
                    _text.value = TextEditingValue(
                      text: label,
                      selection: TextSelection.collapsed(offset: label.length),
                    );
                  },
                ),
            ],
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: _saving
                ? null
                : () async {
                    final selected = await showDatePicker(
                      context: context,
                      initialDate: _date,
                      firstDate: DateTime(1900),
                      lastDate: DateTime(2200, 12, 31),
                      helpText: pack.t('date'),
                      cancelText: pack.t('cancel'),
                      confirmText: pack.t('save'),
                    );
                    if (selected != null && mounted) {
                      setState(() => _date = selected);
                    }
                  },
            icon: const Icon(Icons.calendar_today_outlined),
            label: Text(
              MaterialLocalizations.of(context).formatMediumDate(_date),
            ),
          ),

          const SizedBox(height: 12),
          TextButton.icon(
            onPressed: _saving
                ? null
                : () => setState(() => _advanced = !_advanced),
            icon: Icon(_advanced ? Icons.expand_less : Icons.expand_more),
            label: Text(pack.t('details')),
          ),
          if (_advanced) ...[
            LifeSelect<String>(
              label: pack.t('account'),
              value: _account,
              choices: _choices(OfflineTable.accounts),
              searchLabel: pack.t('search'),
              dialog: true,
              onChanged: _saving ? null : (v) => setState(() => _account = v),
            ),
            const SizedBox(height: 12),
            LifeSelect<String>(
              label: pack.t('category'),
              value: _category,
              choices: _choices(OfflineTable.categories),
              searchLabel: pack.t('search'),
              dialog: true,
              onChanged: _saving ? null : (v) => setState(() => _category = v),
            ),
          ],
        ],
        if (!_money) ...[
          const SizedBox(height: 12),
          AbsorbPointer(
            absorbing: _saving,
            child: ScheduleEditor(
              controller: widget.controller,
              value: _schedule,
              onChanged: (v) => setState(() => _schedule = v),
            ),
          ),
        ],
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Text(
              pack.t(_error!),
              style: TextStyle(color: Theme.of(context).colorScheme.error),
              semanticsLabel: pack.t(_error!),
            ),
          ),
      ],
    );
  }
}
