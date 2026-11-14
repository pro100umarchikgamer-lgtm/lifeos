import '../domain/timezones.dart';
import 'module_calendar_route.dart';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
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
  late DateTime day;
  late DateTime month;
  bool monthExpanded = true;
  @override
  void initState() {
    super.initState();
    final now = widget.controller.now;
    day = DateTime(now.year, now.month, now.day);
    month = DateTime(day.year, day.month);
  }

  bool busy = false;
  List<CalendarEntry>? _calendarSource;
  String? _monthKey;
  List<CalendarOccurrence> _monthOccurrences = [];
  Map<(String, int, int), OccurrenceState> _states = {};
  Set<String> _completed = {};
  AppController get c => widget.controller;
  Future<void> editor([CalendarEntry? entry]) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      isDismissible: false,
      enableDrag: false,
      builder: (_) => EventEditor(controller: c, date: day, entry: entry),
    );
  }

  void open(CalendarEntry entry) {
    final module = calendarModule(c, entry.id);
    if (module != null) {
      openModuleCalendar(context, c, module);
      return;
    }
    final linked = entry.taskId ?? entry.noteId;
    if (linked == null) {
      editor(entry);
    } else {
      Navigator.push(
        context,
        MaterialPageRoute<void>(
          builder: (_) => RecordDetail(controller: c, id: linked),
        ),
      );
    }
  }

  Future<void> state(
    CalendarOccurrence occurrence,
    OccurrenceStatus value,
  ) async {
    setState(() => busy = true);
    try {
      await c.execute(
        SetOccurrence(
          const Uuid().v4(),
          occurrence.entry.id,
          occurrence.at.millisecondsSinceEpoch,
          value,
          expectedRevision: occurrence.entry.revision,
          snoozedUntil: value == OccurrenceStatus.snoozed
              ? DateTime.now()
                  .add(
                    Duration(
                      minutes: int.tryParse(
                            c.preferences['snooze_minutes'] ?? '',
                          ) ??
                          10,
                    ),
                  )
                  .millisecondsSinceEpoch
              : null,
        ),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              c.pack.t(e is DomainFailure ? e.key : 'change_failed'),
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: c,
        builder: (context, _) {
          final location = calendarLocation(
            c.timezone == 'device' ? c.deviceZone : c.timezone,
          );
          final weekStart = DateTime(day.year, day.month,
              day.day - (day.weekday - c.weekStart + 7) % 7);
          final monthStart = DateTime(month.year, month.month);
          final weekEnd =
              DateTime(weekStart.year, weekStart.month, weekStart.day + 7);
          final monthEnd = DateTime(month.year, month.month + 1);
          final rangeStart =
              weekStart.isBefore(monthStart) ? weekStart : monthStart;
          final rangeEnd = weekEnd.isAfter(monthEnd) ? weekEnd : monthEnd;
          final from = tz.TZDateTime(
            location,
            rangeStart.year,
            rangeStart.month,
            rangeStart.day,
          );
          final to = tz.TZDateTime(
            location,
            rangeEnd.year,
            rangeEnd.month,
            rangeEnd.day,
          );
          final key =
              '${dateOnly(rangeStart)}-${dateOnly(rangeEnd)}-${location.name}-${c.deviceZone}';
          if (_calendarSource != c.calendar || _monthKey != key) {
            _monthOccurrences = [
              for (final e in c.calendar)
                ...c.calendarEngine.between(e, from, to, c.deviceZone),
            ]..sort((a, b) => a.at.compareTo(b.at));
            _calendarSource = c.calendar;
            _monthKey = key;
          }
          _states = {
            for (final s in c.occurrences) (s.entryId, s.revision, s.epoch): s,
          };
          _completed =
              c.records.where((r) => r.completed).map((r) => r.id).toSet();
          final all = _monthOccurrences;
          final selected = all
              .where(
                (o) =>
                    dateOnly(tz.TZDateTime.from(o.at, location)) ==
                    dateOnly(day),
              )
              .toList();
          final marked = all
              .map((o) => dateOnly(tz.TZDateTime.from(o.at, location)))
              .toSet();
          final local = MaterialLocalizations.of(context);
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Wrap(
                alignment: WrapAlignment.spaceBetween,
                crossAxisAlignment: WrapCrossAlignment.center,
                spacing: 12,
                children: [
                  Text(
                    c.pack.t('nav_calendar'),
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  TextButton(
                    onPressed: () => setState(() {
                      final now = c.now;
                      day = DateTime(now.year, now.month, now.day);
                      month = DateTime(day.year, day.month);
                    }),
                    child: Text(c.pack.t('today')),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              LifeCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      children: [
                        IconButton(
                          tooltip: monthExpanded
                              ? local.previousMonthTooltip
                              : c.pack.t('calendar_previous_week'),
                          onPressed: day.year <= 1900 && day.month == 1
                              ? null
                              : () => setState(() {
                                    day = monthExpanded
                                        ? DateTime(month.year, month.month - 1)
                                        : DateTime(
                                            day.year, day.month, day.day - 7);
                                    month = DateTime(day.year, day.month);
                                  }),
                          icon: const Icon(Icons.chevron_left),
                        ),
                        Expanded(
                          child: TextButton.icon(
                            key: const Key('calendar_month_toggle'),
                            onPressed: () =>
                                setState(() => monthExpanded = !monthExpanded),
                            icon: Icon(
                              monthExpanded
                                  ? Icons.view_agenda_outlined
                                  : Icons.calendar_month_outlined,
                              size: 18,
                            ),
                            label: Text(
                              local.formatMonthYear(month),
                              textAlign: TextAlign.center,
                            ),
                          ),
                        ),
                        IconButton(
                          tooltip: monthExpanded
                              ? local.nextMonthTooltip
                              : c.pack.t('calendar_next_week'),
                          onPressed: day.year >= 2200 && day.month == 12
                              ? null
                              : () => setState(() {
                                    day = monthExpanded
                                        ? DateTime(month.year, month.month + 1)
                                        : DateTime(
                                            day.year, day.month, day.day + 7);
                                    month = DateTime(day.year, day.month);
                                  }),
                          icon: const Icon(Icons.chevron_right),
                        ),
                      ],
                    ),
                    if (monthExpanded)
                      CalendarGrid(
                        month: month,
                        selected: day,
                        weekStart: c.weekStart,
                        marked: marked,
                        showMonthHeader: false,
                        onMonth: (v) => setState(() {
                          month = v;
                          day = v;
                        }),
                        onDay: (v) => setState(() {
                          day = v;
                        }),
                      )
                    else
                      Row(
                        children: [
                          for (var index = 0; index < 7; index++)
                            Expanded(
                              child: _weekDay(
                                DateTime(weekStart.year, weekStart.month,
                                    weekStart.day + index),
                                marked,
                              ),
                            ),
                        ],
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              Wrap(
                alignment: WrapAlignment.spaceBetween,
                crossAxisAlignment: WrapCrossAlignment.center,
                spacing: 8,
                children: [
                  Text(
                    local.formatMediumDate(day),
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  TextButton.icon(
                    onPressed: () => editor(),
                    icon: const Icon(Icons.add, size: 18),
                    label: Text(c.pack.t('create_event')),
                  ),
                ],
              ),
              if (selected.isEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  child: Text(
                    c.pack.t('empty_day'),
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                )
              else
                LifeCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      for (var index = 0; index < selected.length; index++) ...[
                        if (index > 0) const Divider(height: 24),
                        _agenda(selected[index], location),
                      ],
                    ],
                  ),
                ),
            ],
          );
        },
      );

  Widget _weekDay(DateTime date, Set<String> marked) {
    final active = dateOnly(date) == dateOnly(day);
    final colors = Theme.of(context).colorScheme;
    final local = MaterialLocalizations.of(context);
    final weekday = DateFormat.E(c.pack.locale.toLanguageTag()).format(date);
    return Semantics(
      selected: active,
      button: true,
      label: local.formatFullDate(date),
      child: InkWell(
        key: Key('week_day_${dateOnly(date)}'),
        borderRadius: BorderRadius.circular(12),
        onTap: () => setState(() {
          day = date;
          month = DateTime(date.year, date.month);
        }),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(
            color: active ? colors.primary : null,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            children: [
              Text(
                weekday,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color:
                          active ? colors.onPrimary : colors.onSurfaceVariant,
                    ),
              ),
              const SizedBox(height: 6),
              Text(
                '${date.day}',
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  color: active ? colors.onPrimary : colors.onSurface,
                ),
              ),
              const SizedBox(height: 4),
              SizedBox(
                height: 4,
                child: marked.contains(dateOnly(date))
                    ? Icon(
                        Icons.circle,
                        size: 4,
                        color: active ? colors.onPrimary : colors.primary,
                      )
                    : null,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _agenda(CalendarOccurrence o, tz.Location location) {
    final saved =
        _states[(o.entry.id, o.entry.revision, o.at.millisecondsSinceEpoch)];
    final done = saved?.status == OccurrenceStatus.completed ||
        saved?.status == OccurrenceStatus.dismissed ||
        _completed.contains(o.entry.taskId);
    final at = tz.TZDateTime.from(o.at, location);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: Icon(
            o.entry.taskId != null
                ? Icons.check_box_outlined
                : o.entry.noteId != null
                    ? Icons.notes
                    : Icons.event,
            color: done
                ? Theme.of(context).colorScheme.onSurfaceVariant
                : o.entry.taskId != null
                    ? LifePalette.blue
                    : o.entry.noteId != null
                        ? LifePalette.orange
                        : Theme.of(context).colorScheme.primary,
          ),
          title: Text(
            o.entry.title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              decoration: done ? TextDecoration.lineThrough : null,
            ),
          ),
          subtitle: Text(
            '${c.pack.t(o.entry.taskId != null ? 'task' : o.entry.noteId != null ? 'note' : 'event')} · ${o.entry.schedule.allDay ? c.pack.t('all_day') : MaterialLocalizations.of(context).formatTimeOfDay(TimeOfDay.fromDateTime(at))}',
          ),
          onTap: () => open(o.entry),
        ),
        if (saved?.snoozedUntil != null)
          Text(
            '${c.pack.t('snooze')}: ${DateTime.fromMillisecondsSinceEpoch(saved!.snoozedUntil!).toLocal()}',
          ),
        if (!done ||
            o.entry.taskId == null &&
                o.entry.noteId == null &&
                calendarModule(c, o.entry.id) == null)
          Wrap(
            spacing: 4,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              if (!done)
                TextButton.icon(
                  onPressed:
                      busy ? null : () => state(o, OccurrenceStatus.completed),
                  icon: const Icon(Icons.check, size: 18),
                  label: Text(c.pack.t('complete')),
                ),
              PopupMenuButton<String>(
                enabled: !busy,
                tooltip: c.pack.t('advanced_options'),
                onSelected: (action) async {
                  if (action == 'snooze') {
                    await state(o, OccurrenceStatus.snoozed);
                    return;
                  }
                  if (action == 'dismiss') {
                    await state(o, OccurrenceStatus.dismissed);
                    return;
                  }
                  final confirm = await showDialog<bool>(
                    context: context,
                    builder: (_) => AlertDialog(
                      title: Text(c.pack.t('delete')),
                      content: Text(c.pack.t('delete_series')),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.pop(context, false),
                          child: Text(c.pack.t('cancel')),
                        ),
                        FilledButton(
                          onPressed: () => Navigator.pop(context, true),
                          child: Text(c.pack.t('delete')),
                        ),
                      ],
                    ),
                  );
                  if (confirm != true) return;
                  try {
                    await c.execute(
                      DeleteCalendar(
                        const Uuid().v4(),
                        o.entry.id,
                        o.entry.revision,
                      ),
                    );
                  } catch (e) {
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(
                            c.pack.t(
                              e is DomainFailure ? e.key : 'change_failed',
                            ),
                          ),
                        ),
                      );
                    }
                  }
                },
                itemBuilder: (_) => [
                  if (!done &&
                      o.entry.schedule.reminder &&
                      !o.at.isAfter(c.now))
                    PopupMenuItem(
                      value: 'snooze',
                      child: Text(c.pack.t('snooze')),
                    ),
                  if (!done)
                    PopupMenuItem(
                      value: 'dismiss',
                      child: Text(c.pack.t('dismiss')),
                    ),
                  if (o.entry.taskId == null &&
                      o.entry.noteId == null &&
                      calendarModule(c, o.entry.id) == null)
                    PopupMenuItem(
                      value: 'delete',
                      child: Text(c.pack.t('delete')),
                    ),
                ],
                icon: const Icon(Icons.more_horiz),
              ),
            ],
          ),
      ],
    );
  }
}
