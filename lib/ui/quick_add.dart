import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:uuid/uuid.dart';

import '../app_controller.dart';
import '../domain/models.dart';
import 'design.dart';

class QuickAdd extends StatefulWidget {
  const QuickAdd({super.key, required this.controller, required this.kind});
  final AppController controller;
  final EntryKind kind;
  @override
  State<QuickAdd> createState() => _QuickAddState();
}

class _QuickAddState extends State<QuickAdd> {
  final _amount = TextEditingController();
  final _text = TextEditingController();
  late final TextEditingController _currency;
  final _operation = const Uuid().v4();
  DateTime _date = DateTime.now();
  bool _saving = false;
  bool _advanced = false;
  String? _error;
  bool get _money => widget.kind == EntryKind.expense || widget.kind == EntryKind.income;
  @override
  void initState() { super.initState(); _currency = TextEditingController(text: widget.controller.currency); }
  @override
  void dispose() { _amount.dispose(); _text.dispose(); _currency.dispose(); super.dispose(); }

  Future<void> _save() async {
    if (_saving) return;
    setState(() { _saving = true; _error = null; });
    try {
      final AppAction action = switch (widget.kind) {
        EntryKind.expense || EntryKind.income => CreateMoney(_operation, kind: widget.kind,
          amount: _amount.text, currencyCode: _currency.text, date: _date, label: _text.text),
        EntryKind.task => CreateTask(_operation, _text.text),
        EntryKind.note => CreateNote(_operation, _text.text),
      };
      await widget.controller.engine.execute(action);
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
      EntryKind.expense => LifePalette.red, EntryKind.income => LifePalette.green,
      EntryKind.task => LifePalette.blue, EntryKind.note => LifePalette.orange,
    };
    final icon = switch (widget.kind) {
      EntryKind.expense => Icons.remove_circle_rounded, EntryKind.income => Icons.add_circle_rounded,
      EntryKind.task => Icons.check_box_rounded, EntryKind.note => Icons.notes_rounded,
    };
    return PopScope(canPop: !_saving, child: Padding(
      padding: EdgeInsets.fromLTRB(20, 10, 20, 22 + MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Center(child: Container(width: 36, height: 4, decoration: BoxDecoration(
          color: Theme.of(context).dividerColor, borderRadius: BorderRadius.circular(8)))),
        const SizedBox(height: 18),
        Row(children: [CircleAvatar(backgroundColor: accent.withValues(alpha: .12),
            child: Icon(icon, color: accent)), const SizedBox(width: 10),
          Expanded(child: Text(pack.t('create_${widget.kind.name}'),
            style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800))),
          IconButton(tooltip: pack.t('cancel'), onPressed: _saving ? null : () => Navigator.pop(context),
            icon: const Icon(Icons.close))]),
        const SizedBox(height: 20),
        if (_money) ...[
          TextField(key: const Key('amount'), controller: _amount, autofocus: true, enabled: !_saving,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(labelText: pack.t('amount'), suffixText: _currency.text.toUpperCase())),
          const SizedBox(height: 16),
        ],
        TextField(key: const Key('entry_text'), controller: _text, autofocus: !_money, enabled: !_saving,
          minLines: widget.kind == EntryKind.note ? 3 : 1, maxLines: widget.kind == EntryKind.note ? 8 : 2,
          textCapitalization: TextCapitalization.sentences,
          decoration: InputDecoration(labelText: pack.t(_money ? 'label_optional' : widget.kind == EntryKind.task ? 'task_title' : 'note_text'))),
        if (_money) ...[
          const SizedBox(height: 8),
          TextButton.icon(onPressed: _saving ? null : () => setState(() => _advanced = !_advanced),
            icon: Icon(_advanced ? Icons.expand_less : Icons.expand_more), label: Text(pack.t('details'))),
          if (_advanced) ...[
            TextField(controller: _currency, enabled: !_saving, maxLength: 3,
              inputFormatters: [FilteringTextInputFormatter.allow(RegExp('[a-zA-Z]'))],
              textCapitalization: TextCapitalization.characters,
              onChanged: (_) => setState(() {}), decoration: InputDecoration(labelText: pack.t('currency'))),
            OutlinedButton.icon(onPressed: _saving ? null : () async {
              final selected = await showDatePicker(context: context, initialDate: _date,
                firstDate: DateTime(1900), lastDate: DateTime(2200, 12, 31),
                helpText: pack.t('date'), cancelText: pack.t('cancel'), confirmText: pack.t('save'));
              if (selected != null && mounted) setState(() => _date = selected);
            }, icon: const Icon(Icons.calendar_today_outlined), label: Text(MaterialLocalizations.of(context).formatMediumDate(_date))),
          ],
        ],
        if (_error != null) Padding(padding: const EdgeInsets.only(top: 12),
          child: Text(pack.t(_error!), style: TextStyle(color: Theme.of(context).colorScheme.error), semanticsLabel: pack.t(_error!))),
        const SizedBox(height: 20),
        FilledButton(key: const Key('save'), onPressed: _saving ? null : _save,
          style: FilledButton.styleFrom(backgroundColor: LifePalette.green, foregroundColor: Colors.white),
          child: _saving ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)) : Text(pack.t('save'))),
      ])),
    ));
  }
}
