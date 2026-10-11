import 'package:timezone/timezone.dart' as tz;
import 'models.dart';
import 'calendar_engine.dart';

ScheduleSpec? storedSchedule(Map<String,Object?>? row) {
  final value=row?['__schedule'];if(value is! Map)return null;
  return ScheduleSpec(localStart:value['local_start'] as String,timezone:value['timezone'] as String,allDay:value['all_day']==1,repeat:RepeatRule.values.byName(value['repeat_rule'] as String),interval:value['repeat_interval'] as int,until:value['until_date'] as String?,reminder:value['reminder']==1,mode:ReminderMode.values.byName(value['reminder_mode'] as String));
}
/// Civil dates, never elapsed 24-hour periods. Paused habits do not accumulate misses.
int habitStreak(CalendarEntry entry,DateTime now,String deviceZone,Iterable<Map<String,Object?>> checks,{Iterable<Map<String,Object?>> pauses=const []}) {
  final zone=tz.getLocation(entry.schedule.timezone=='device'?deviceZone:entry.schedule.timezone);
  final today=tz.TZDateTime.from(now,zone),civil=DateTime.utc(today.year,today.month,today.day);
  final completed={for(final c in checks)if(c['completed']==1&&c['deleted_at']==null)c['local_date'] as String};
  if(completed.isEmpty)return 0;
  final earliest=DateTime.parse((completed.toList()..sort()).first);
  final from=tz.TZDateTime(zone,earliest.year,earliest.month,earliest.day);
  final to=tz.TZDateTime(zone,today.year,today.month,today.day+1);
  final dates=const CalendarEngine().between(entry,from,to,deviceZone,limit:civil.difference(DateTime.utc(earliest.year,earliest.month,earliest.day)).inDays.abs()+2).map((e)=>dateOnly(tz.TZDateTime.from(e.at,zone))).toSet().toList()..sort();
  var count=0;
  for(final d in dates.reversed){if(pauses.any((p)=>d.compareTo(p['start_on'] as String)>=0&&(p['end_on']==null||d.compareTo(p['end_on'] as String)<0)))continue;if(d==dateOnly(civil)&&!completed.contains(d))continue;if(!completed.contains(d))break;count++;}
  return count;
}
