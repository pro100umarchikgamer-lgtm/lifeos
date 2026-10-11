import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as data;
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/domain/offline_validation.dart';
import 'package:lifeos/domain/habit_progress.dart';
void main(){
  setUpAll(data.initializeTimeZones);
  test('habit streak counts scheduled civil days across DST',(){
    final e=CalendarEntry(id:'h',title:'Walk',schedule:const ScheduleSpec(localStart:'2026-10-23T09:00:00',timezone:'Europe/Berlin',repeat:RepeatRule.daily));
    final checks=[for(final day in [23,24,25]){'local_date':'2026-10-$day','completed':1}];
    expect(habitStreak(e,DateTime.utc(2026,10,25,12),'UTC',checks),3);
    expect(habitStreak(e,DateTime.utc(2026,10,26,7),'UTC',checks),3);
  });
  test('task cycles and disconnected duplicate schedule are rejected',(){
    expect(()=>OfflineValidation.validate(const SetTaskPlacement('o','p',0,taskId:'task',parentTaskId:'task')),throwsA(isA<DomainFailure>()));
    expect(()=>OfflineValidation.validate(const SaveStudyItem('o','s',0,subjectId:'subject',name:'Exam',taskId:'task',schedule:ScheduleSpec(localStart:'2026-10-11T09:00:00',timezone:'UTC'))),throwsA(isA<DomainFailure>()));
  });
  test('paused civil dates do not become missed streak days',(){
    final e=CalendarEntry(id:'h',title:'Walk',schedule:const ScheduleSpec(localStart:'2026-10-23T09:00:00',timezone:'Europe/Berlin',repeat:RepeatRule.daily));
    expect(habitStreak(e,DateTime.utc(2026,10,27,12),'UTC',[{'local_date':'2026-10-23','completed':1},{'local_date':'2026-10-27','completed':1}],pauses:[{'start_on':'2026-10-24','end_on':'2026-10-27'}]),2);
  });

}
