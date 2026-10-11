import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:uuid/uuid.dart';
import '../app_controller.dart';
import '../domain/models.dart';

class CalendarGrid extends StatelessWidget {
  const CalendarGrid({super.key, required this.month, required this.selected, required this.onDay,
    required this.onMonth, this.weekStart = 1, this.marked = const {}, this.range});
  final DateTime month, selected;
  final ValueChanged<DateTime> onDay, onMonth;
  final int weekStart;
  final Set<String> marked;
  final DateTimeRange? range;
  @override
  Widget build(BuildContext context) {
    final first = DateTime(month.year, month.month);
    final offset = (first.weekday - weekStart + 7) % 7;
    final days = DateTime(month.year, month.month + 1, 0).day;
    final labels = DateFormat.E(Localizations.localeOf(context).toLanguageTag());
    final color = Theme.of(context).colorScheme.primary;
    return Column(children: [
      Row(children: [
        IconButton(tooltip: MaterialLocalizations.of(context).previousMonthTooltip,
          onPressed: month.year == 1900 && month.month == 1 ? null : () => onMonth(DateTime(month.year, month.month - 1)), icon: const Icon(Icons.chevron_left)),
        Expanded(child: TextButton(onPressed: () async {
          final date = await showDatePicker(context:context,initialDate: month,firstDate:DateTime(1900),lastDate:DateTime(2200,12,31));
          if (date != null) onMonth(DateTime(date.year,date.month));
        }, child: Text(MaterialLocalizations.of(context).formatMonthYear(month),textAlign:TextAlign.center,style:const TextStyle(fontWeight:FontWeight.w800)))),
        IconButton(tooltip: MaterialLocalizations.of(context).nextMonthTooltip,
          onPressed: month.year == 2200 && month.month == 12 ? null : () => onMonth(DateTime(month.year, month.month + 1)), icon: const Icon(Icons.chevron_right)),
      ]),
      Row(children: [for (var i = 0; i < 7; i++) Expanded(child: Text(labels.format(DateTime(2026, 10, 5 + (weekStart - 1 + i) % 7)),
        textAlign: TextAlign.center, style: Theme.of(context).textTheme.labelSmall))]),
      const SizedBox(height: 6),
      for (var row = 0; row < (offset + days + 6) ~/ 7; row++) Row(children: [
        for (var col = 0; col < 7; col++) Expanded(child: Builder(builder: (context) {
          final day = row * 7 + col - offset + 1;
          if (day < 1 || day > days) return const SizedBox(height: 48);
          final date = DateTime(month.year, month.month, day);
          final active = dateOnly(date) == dateOnly(selected);
          final inside = range != null && !date.isBefore(range!.start) && !date.isAfter(range!.end);
          return Semantics(selected: active, label: MaterialLocalizations.of(context).formatFullDate(date),
            child: InkWell(key: Key('day_${dateOnly(date)}'), borderRadius: BorderRadius.circular(12), onTap: () => onDay(date),
              child: Container(height: 48, margin: const EdgeInsets.all(1), decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(12), color: active ? color : inside ? color.withValues(alpha: .12) : null),
                child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                  Text('$day', style: TextStyle(color: active ? Colors.white : null, fontWeight: active ? FontWeight.bold : null)),
                  SizedBox(height: 5, child: marked.contains(dateOnly(date)) ? Icon(Icons.circle, size: 4, color: active ? Colors.white : color) : null),
                ]))));
        })),
      ]),
    ]);
  }
}

Future<DateTimeRange?> selectFinancialPeriod(BuildContext context, AppController c, DateTimeRange current) =>
  showDialog<DateTimeRange>(context: context, builder: (_) => _PeriodDialog(c: c, current: current));
class _PeriodDialog extends StatefulWidget {
  const _PeriodDialog({required this.c, required this.current});
  final AppController c;
  final DateTimeRange current;
  @override
  State<_PeriodDialog> createState() => _PeriodDialogState();
}
class _PeriodDialogState extends State<_PeriodDialog> {
  late DateTime month = DateTime(widget.current.start.year, widget.current.start.month);
  late DateTime start = widget.current.start;
  late DateTime end = widget.current.end;
  bool custom = false, pickingEnd = false;
  @override
  Widget build(BuildContext context) => AlertDialog(title: Text(widget.c.pack.t('period')),
    content: SizedBox(width: 390, child: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, children: [
      SegmentedButton<bool>(showSelectedIcon: false, segments: [ButtonSegment(value: false, label: Text(widget.c.pack.t('month'))),
        ButtonSegment(value: true, label: Text(widget.c.pack.t('date_range')))], selected: {custom},
        onSelectionChanged: (v) => setState(() { custom = v.single; pickingEnd = false; })),
      if (custom) Padding(padding: const EdgeInsets.symmetric(vertical: 12), child: Text('${dateOnly(start)} — ${dateOnly(end)}')),
      CalendarGrid(month: month, selected: pickingEnd ? start : end, weekStart: widget.c.weekStart,
        range: custom ? DateTimeRange(start: start, end: end) : null,
        onMonth: (v) => setState(() => month = v), onDay: (v) => setState(() {
          if (!custom) { month = DateTime(v.year, v.month); return; }
          if (!pickingEnd) { start = v; end = v; pickingEnd = true; }
          else { if (v.isBefore(start)) { end = start; start = v; } else { end = v; } pickingEnd = false; }
        })),
      TextButton(onPressed: () => setState(() { final now = DateTime.now(); month = DateTime(now.year, now.month); custom = false; pickingEnd = false; }), child: Text(widget.c.pack.t('current_month'))),
    ]))), actions: [TextButton(onPressed: () => Navigator.pop(context), child: Text(widget.c.pack.t('cancel'))),
      FilledButton(onPressed: () => Navigator.pop(context, custom ? DateTimeRange(start: start, end: end)
        : DateTimeRange(start: month, end: DateTime(month.year, month.month + 1, 0))), child: Text(widget.c.pack.t('save')))]);
}

class ScheduleEditor extends StatelessWidget {
  const ScheduleEditor({super.key, required this.controller, required this.value, required this.onChanged, this.optional = true});
  final AppController controller;
  final ScheduleSpec? value;
  final ValueChanged<ScheduleSpec?> onChanged;
  final bool optional;
  ScheduleSpec _copy({DateTime? date, RepeatRule? repeat, int? interval, bool? reminder, bool? allDay, ReminderMode? mode,
      String? until, bool clearUntil = false}) {
    final base = value ?? ScheduleSpec(localStart: '${dateOnly(DateTime.now())}T09:00:00', timezone: controller.timezone);
    final start = date ?? DateTime.parse(base.localStart);
    return ScheduleSpec(localStart: '${dateOnly(start)}T${start.hour.toString().padLeft(2,'0')}:${start.minute.toString().padLeft(2,'0')}:00',
      timezone: base.timezone, repeat: repeat ?? base.repeat, interval: interval ?? base.interval,
      reminder: reminder ?? base.reminder, allDay: allDay ?? base.allDay, mode: mode ?? base.mode,
      until: clearUntil ? null : until ?? base.until);
  }
  @override
  Widget build(BuildContext context) {
    final p = controller.pack;
    final start = value == null ? DateTime.now() : DateTime.parse(value!.localStart);
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      if (optional) SwitchListTile.adaptive(contentPadding: EdgeInsets.zero, title: Text(p.t('scheduled_date')),
        value: value != null, onChanged: (v) => onChanged(v ? _copy() : null)),
      if (value != null) ...[
        Wrap(spacing: 8, children: [
          OutlinedButton.icon(icon: const Icon(Icons.calendar_today_outlined), label: Text(MaterialLocalizations.of(context).formatMediumDate(start)),
            onPressed: () async {
              final date = await showDatePicker(context: context, initialDate: start, firstDate: DateTime(1900), lastDate: DateTime(2200,12,31));
              if (date != null) onChanged(_copy(date: DateTime(date.year,date.month,date.day,start.hour,start.minute), clearUntil: value?.until != null && value!.until!.compareTo(dateOnly(date)) < 0));
            }),
          if (!value!.allDay || value!.reminder) OutlinedButton.icon(icon: const Icon(Icons.schedule), label: Text(MaterialLocalizations.of(context).formatTimeOfDay(TimeOfDay.fromDateTime(start))),
            onPressed: () async {
              final time = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(start));
              if (time != null) onChanged(_copy(date: DateTime(start.year,start.month,start.day,time.hour,time.minute)));
            }),
        ]),
        SwitchListTile.adaptive(contentPadding: EdgeInsets.zero, title: Text(p.t('all_day')), value: value!.allDay, onChanged: (v) => onChanged(_copy(allDay: v))),
        DropdownButtonFormField<RepeatRule>(key: ValueKey('repeat_${value!.repeat}'), initialValue: value!.repeat, isExpanded: true,
          decoration: InputDecoration(labelText: p.t('repeat')), items: [for (final r in RepeatRule.values) DropdownMenuItem(value: r, child: Text(p.t('repeat_${r.name}')))],
          onChanged: (v) { if (v != null) onChanged(_copy(repeat: v, clearUntil: v == RepeatRule.none)); }),
        if (value!.repeat != RepeatRule.none) ...[
          const SizedBox(height: 12),
          DropdownButtonFormField<int>(key: ValueKey('interval_${value!.interval}'), initialValue: value!.interval, isExpanded: true,
            decoration: InputDecoration(labelText: p.t('repeat_interval')), items: [for (final i in {1,2,3,4,6,12,value!.interval}) DropdownMenuItem(value: i, child: Text('$i'))],
            onChanged: (v) { if (v != null) onChanged(_copy(interval: v)); }),
          Row(children: [Expanded(child: TextButton(onPressed: () async {
            final end = await showDatePicker(context: context, initialDate: value!.until == null ? start : DateTime.parse(value!.until!), firstDate: DateTime(start.year,start.month,start.day), lastDate: DateTime(2200,12,31));
            if (end != null) onChanged(_copy(until: dateOnly(end)));
          }, child: Text('${p.t('repeat_until')}: ${value!.until ?? p.t('no_limit')}'))),
            if (value!.until != null) IconButton(tooltip: p.t('clear'), onPressed: () => onChanged(_copy(clearUntil: true)), icon: const Icon(Icons.close))]),
        ],
        SwitchListTile.adaptive(contentPadding: EdgeInsets.zero, title: Text(p.t('reminder')), value: value!.reminder, onChanged: (v) => onChanged(_copy(reminder: v))),
        if (value!.reminder) ...[
          DropdownButtonFormField<ReminderMode>(key: ValueKey('mode_${value!.mode}'), initialValue: value!.mode, isExpanded: true,
            decoration: InputDecoration(labelText: p.t('reminder_mode')), items: [for (final m in ReminderMode.values) DropdownMenuItem(value: m, child: Text(p.t('mode_${m.name}')))],
            onChanged: (v) { if (v != null) onChanged(_copy(mode: v)); }),
          const SizedBox(height: 8), Text(p.t('alarm_limits'), style: Theme.of(context).textTheme.bodySmall),
        ],
        Padding(padding: const EdgeInsets.only(top: 8), child: Text('${p.t('timezone')}: ${value!.timezone == 'device' ? p.t('device_timezone') : value!.timezone}', style: Theme.of(context).textTheme.bodySmall)),
      ],
    ]);
  }
}

class EventEditor extends StatefulWidget {
  const EventEditor({super.key, required this.controller, required this.date, this.entry});
  final AppController controller;
  final DateTime date;
  final CalendarEntry? entry;
  @override
  State<EventEditor> createState() => _EventEditorState();
}
class _EventEditorState extends State<EventEditor> {
  late final TextEditingController title = TextEditingController(text: widget.entry?.title ?? '');
  late ScheduleSpec schedule = widget.entry?.schedule ?? ScheduleSpec(localStart: '${dateOnly(widget.date)}T09:00:00', timezone: widget.controller.timezone);
  final operation = const Uuid().v4();
  bool saving = false;
  String? error;
  @override
  void dispose() { title.dispose(); super.dispose(); }
  Future<void> save() async {
    setState(() { saving = true; error = null; });
    try {
      await widget.controller.execute(SaveCalendar(operation, id: widget.entry?.id, expectedRevision: widget.entry?.revision,
        title: title.text, schedule: schedule));
      if (mounted) Navigator.pop(context);
    } catch (e) { if (mounted) setState(() { saving = false; error = e is DomainFailure ? e.key : 'save_failed'; }); }
  }
  @override
  Widget build(BuildContext context) => PopScope(canPop: !saving, child: Padding(
    padding: EdgeInsets.fromLTRB(20,20,20,20 + MediaQuery.viewInsetsOf(context).bottom),
    child: SingleChildScrollView(child: AbsorbPointer(absorbing: saving, child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(children: [Expanded(child: Text(widget.controller.pack.t('event'), style: Theme.of(context).textTheme.titleLarge)),
        IconButton(tooltip: widget.controller.pack.t('cancel'), onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close))]),
      const SizedBox(height: 12), TextField(controller: title, autofocus: true, decoration: InputDecoration(labelText: widget.controller.pack.t('event_title'))),
      const SizedBox(height: 12), ScheduleEditor(controller: widget.controller, value: schedule, optional: false, onChanged: (v) => setState(() => schedule = v!)),
      if (error != null) Text(widget.controller.pack.t(error!), style: TextStyle(color: Theme.of(context).colorScheme.error)),
      const SizedBox(height: 16), FilledButton(onPressed: saving ? null : save, child: Text(widget.controller.pack.t(saving ? 'saving' : 'save'))),
    ])))));
}
