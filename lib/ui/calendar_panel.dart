import 'module_calendar_route.dart';
import 'package:flutter/material.dart';
import 'package:timezone/timezone.dart' as tz;
import 'package:uuid/uuid.dart';
import '../app_controller.dart';
import '../domain/models.dart';
import 'calendar.dart';
import 'design.dart';
import 'record_detail.dart';

class CalendarPanel extends StatefulWidget {
  const CalendarPanel({super.key, required this.controller});
  final AppController controller;
  @override
  State<CalendarPanel> createState() => _CalendarPanelState();
}
class _CalendarPanelState extends State<CalendarPanel> {
  DateTime day = DateTime(DateTime.now().year, DateTime.now().month, DateTime.now().day);
  late DateTime month = DateTime(day.year, day.month);
  bool busy = false;
  List<CalendarEntry>? _calendarSource;
  String? _monthKey;
  List<CalendarOccurrence> _monthOccurrences = [];
  Map<(String, int, int), OccurrenceState> _states = {};
  Set<String> _completed = {};
  AppController get c => widget.controller;
  Future<void> editor([CalendarEntry? entry]) async {
    await showModalBottomSheet<void>(context: context, isScrollControlled: true, useSafeArea: true,
      isDismissible: false, enableDrag: false, builder: (_) => EventEditor(controller: c, date: day, entry: entry));
  }
  void open(CalendarEntry entry) {
    final module=calendarModule(c,entry.id);if(module!=null){openModuleCalendar(context,c,module);return;}
    final linked = entry.taskId ?? entry.noteId;
    if (linked == null) { editor(entry); }
    else { Navigator.push(context, MaterialPageRoute<void>(builder: (_) => RecordDetail(controller: c, id: linked))); }
  }
  Future<void> state(CalendarOccurrence occurrence, OccurrenceStatus value) async {
    setState(() => busy = true);
    try {
      await c.execute(SetOccurrence(const Uuid().v4(), occurrence.entry.id, occurrence.at.millisecondsSinceEpoch, value,
        expectedRevision: occurrence.entry.revision,
        snoozedUntil: value == OccurrenceStatus.snoozed ? DateTime.now().add(Duration(minutes: int.tryParse(c.preferences['snooze_minutes'] ?? '') ?? 10)).millisecondsSinceEpoch : null));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(c.pack.t(e is DomainFailure ? e.key : 'change_failed'))));
    } finally { if (mounted) setState(() => busy = false); }
  }
  @override
  Widget build(BuildContext context) => ListenableBuilder(listenable: c, builder: (context, _) {
    final location = tz.getLocation(c.timezone == 'device' ? c.deviceZone : c.timezone);
    final from = tz.TZDateTime(location, month.year, month.month);
    final to = tz.TZDateTime(location, month.year, month.month + 1);
    final key = '${month.year}-${month.month}-${location.name}-${c.deviceZone}';
    if (_calendarSource != c.calendar || _monthKey != key) {
      _monthOccurrences = [for (final e in c.calendar) ...c.calendarEngine.between(e, from, to, c.deviceZone)]..sort((a,b) => a.at.compareTo(b.at));
      _calendarSource = c.calendar; _monthKey = key;
    }
    _states = {for (final s in c.occurrences) (s.entryId, s.revision, s.epoch): s};
    _completed = c.records.where((r) => r.completed).map((r) => r.id).toSet();
    final all = _monthOccurrences;
    final selected = all.where((o) => dateOnly(tz.TZDateTime.from(o.at, location)) == dateOnly(day)).toList();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      LifeCard(child: CalendarGrid(month: month, selected: day, weekStart: c.weekStart,
        marked: all.map((o) => dateOnly(tz.TZDateTime.from(o.at, location))).toSet(),
        onMonth: (v) => setState(() { month = v; day = v; }), onDay: (v) => setState(() => day = v))),
      const SizedBox(height: 12),
      LifeCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [Expanded(child: Text(MaterialLocalizations.of(context).formatMediumDate(day), style: const TextStyle(fontWeight: FontWeight.w800))),
          IconButton(tooltip: c.pack.t('create_event'), onPressed: () => editor(), icon: const Icon(Icons.add))]),
        if (selected.isEmpty) Padding(padding: const EdgeInsets.symmetric(vertical: 12), child: Text(c.pack.t('empty_day'))),
        for (final o in selected) _agenda(o, location),
      ])),
    ]);
  });
  Widget _agenda(CalendarOccurrence o, tz.Location location) {
    final saved = _states[(o.entry.id, o.entry.revision, o.at.millisecondsSinceEpoch)];
    final done = saved?.status == OccurrenceStatus.completed || saved?.status == OccurrenceStatus.dismissed || _completed.contains(o.entry.taskId);
    final at = tz.TZDateTime.from(o.at, location);
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      ListTile(contentPadding: EdgeInsets.zero, leading: Icon(o.entry.taskId != null ? Icons.check_box_outlined : o.entry.noteId != null ? Icons.notes : Icons.event,
        color: done ? Theme.of(context).colorScheme.onSurfaceVariant : o.entry.taskId != null ? LifePalette.blue : o.entry.noteId != null ? LifePalette.orange : Theme.of(context).colorScheme.primary), title: Text(o.entry.title, maxLines: 2, overflow: TextOverflow.ellipsis,
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, decoration: done ? TextDecoration.lineThrough : null)),
        subtitle: Text('${c.pack.t(o.entry.taskId != null ? 'task' : o.entry.noteId != null ? 'note' : 'event')} · ${o.entry.schedule.allDay ? c.pack.t('all_day') : MaterialLocalizations.of(context).formatTimeOfDay(TimeOfDay.fromDateTime(at))}'),
        onTap: () => open(o.entry)),
      if (saved?.snoozedUntil != null) Text('${c.pack.t('snooze')}: ${DateTime.fromMillisecondsSinceEpoch(saved!.snoozedUntil!).toLocal()}'),
      Wrap(spacing: 4, children: [
        if (!done) TextButton.icon(onPressed: busy ? null : () => state(o, OccurrenceStatus.completed), icon: const Icon(Icons.check, size: 18), label: Text(c.pack.t('complete'))),
        if (!done && o.entry.schedule.reminder) TextButton(onPressed: busy || o.at.isAfter(DateTime.now()) ? null : () => state(o, OccurrenceStatus.snoozed), child: Text(c.pack.t('snooze'))),
        if (!done) TextButton(onPressed: busy ? null : () => state(o, OccurrenceStatus.dismissed), child: Text(c.pack.t('dismiss'))),
        if (o.entry.taskId == null && o.entry.noteId == null && calendarModule(c,o.entry.id)==null) TextButton(onPressed: busy ? null : () async {
          final confirm = await showDialog<bool>(context: context, builder: (_) => AlertDialog(title: Text(c.pack.t('delete')), content: Text(c.pack.t('delete_series')),
            actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: Text(c.pack.t('cancel'))), FilledButton(onPressed: () => Navigator.pop(context, true), child: Text(c.pack.t('delete')))]));
          if (confirm != true) return;
          try { await c.execute(DeleteCalendar(const Uuid().v4(), o.entry.id, o.entry.revision)); }
          catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(c.pack.t(e is DomainFailure ? e.key : 'change_failed')))); }
        }, child: Text(c.pack.t('delete'))),
      ]),
      const Divider(),
    ]);
  }
}
