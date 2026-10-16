part of 'local_store.dart';
extension PersonalModulesPersistence on LocalStore {
  Future<void> _guardModuleCalendar(sql.Transaction tx,String id) async {
    for(final table in ['projects','project_milestones','habits','study_items','debts','planned_payments']){if((await tx.query(table,columns:['id'],where:'calendar_id=? AND deleted_at IS NULL',whereArgs:[id],limit:1)).isNotEmpty)throw const DomainFailure('module_calendar_owned');}
  }

  Future<String?> _moduleCalendar(sql.Transaction tx,OfflineAction action,String table,String title,ScheduleSpec? schedule,String now,{bool paused=false}) async {
    final row=action.expectedRevision==0?null:await _scoped(tx,table,action.id);
    final oldId=row?['calendar_id'] as String?;final calendar=oldId??(schedule==null?null:LocalStore._uuid.v4());
    if(schedule==null){if(oldId!=null)await tx.update('calendar_entries',{'deleted_at':now,'updated_at':now,'revision':((await _scoped(tx,'calendar_entries',oldId,deleted:true))['revision'] as int)+1},where:'id=?',whereArgs:[oldId]);return null;}
    final prior=oldId==null?null:await _scoped(tx,'calendar_entries',oldId,deleted:true);
    if(prior?['deleted_at']!=null)await tx.update('calendar_entries',{'deleted_at':null},where:'id=? AND revision=?',whereArgs:[calendar,prior!['revision']]);
    await _saveCalendar(tx,calendar!,title,schedule,now,expectedRevision:prior?['revision'] as int?);
    // Keep the schedule while paused; reconciliation ignores soft-deleted calendar entries.
    await tx.update('calendar_entries',{'deleted_at':paused?now:null},where:'id=?',whereArgs:[calendar]);
    return calendar;
  }
  Future<void> _optional(sql.Transaction tx,String table,String? id) async {if(id!=null)await _scoped(tx,table,id);}
  Future<void> _applyPersonal(sql.Transaction tx,OfflineAction action,String now) async {
    switch(action) {
      case CopyChecklist():
        final source=await _scoped(tx,'checklists',action.sourceId);
        if(source['revision']!=action.sourceRevision)throw const DomainFailure('revision_conflict');
        await _writeEntity(tx,'checklists',action,{'name':action.name.trim(),'kind':source['kind'],'project_id':source['project_id'],'note_id':null},now);
        for(final item in await tx.query('checklist_items',where:'checklist_id=? AND deleted_at IS NULL',whereArgs:[action.sourceId])){
          if(item['owner_id']!=ownerId||item['workspace_id']!=workspaceId)throw const DomainFailure('record_missing');
          await tx.insert('checklist_items',{'id':LocalStore._uuid.v4(),'owner_id':ownerId,'workspace_id':workspaceId,'checklist_id':action.id,'name':item['name'],'quantity':item['quantity'],'completed':0,'task_id':null,'created_at':now,'updated_at':now});
        }
      case SaveProfile():
        if(action.id==ownerId&&(action.kind!='adult'||action.archived))throw const DomainFailure('owner_immutable');
        if(action.guardianId!=null){final guardian=await _scoped(tx,'local_profiles',action.guardianId!);if(guardian['kind']!='adult'||guardian['archived']==1)throw const DomainFailure('invalid_profile');}
        if(action.expectedRevision>0&&(action.kind!='adult'||action.archived)&&(await tx.query('local_profiles',columns:['id'],where:'guardian_id=?',whereArgs:[action.id],limit:1)).isNotEmpty)throw const DomainFailure('invalid_profile');
        await _writeEntity(tx,'local_profiles',action,{'name':action.name.trim(),'kind':action.kind,'guardian_id':action.guardianId,'archived':action.archived?1:0},now);
      case SaveMembership():
        await _scoped(tx,'local_profiles',action.profileId);
        if(action.profileId==ownerId)throw const DomainFailure('owner_immutable');
        if(action.expectedRevision>0&&(await _scoped(tx,'local_memberships',action.id))['role']=='owner')throw const DomainFailure('owner_immutable');
        await _writeEntity(tx,'local_memberships',action,{'profile_id':action.profileId,'role':action.role,'permissions':action.permissions},now);
      case SaveProject():
        final calendar=await _moduleCalendar(tx,action,'projects',action.name,action.dueOn==null?null:ScheduleSpec(localStart:'${dateOnly(action.dueOn!)}T09:00:00',timezone:'device',allDay:true),now,paused:action.status=='done');
        await _optional(tx,'budgets',action.budgetId);await _writeEntity(tx,'projects',action,{'name':action.name.trim(),'goal':action.goal.trim(),'status':action.status,'due_on':action.dueOn==null?null:dateOnly(action.dueOn!),'budget_id':action.budgetId,'calendar_id':calendar},now);
      case SaveMilestone():
        final calendar=await _moduleCalendar(tx,action,'project_milestones',action.name,action.dueOn==null?null:ScheduleSpec(localStart:'${dateOnly(action.dueOn!)}T09:00:00',timezone:'device',allDay:true),now,paused:action.completed);
        await _scoped(tx,'projects',action.projectId);await _writeEntity(tx,'project_milestones',action,{'project_id':action.projectId,'name':action.name.trim(),'due_on':action.dueOn==null?null:dateOnly(action.dueOn!),'completed':action.completed?1:0,'calendar_id':calendar},now);
      case SetTaskPlacement():
        await _scoped(tx,'tasks',action.taskId);await _optional(tx,'projects',action.projectId);
        var parent=action.parentTaskId;final seen={action.taskId};
        while(parent!=null){if(!seen.add(parent))throw const DomainFailure('task_cycle');await _scoped(tx,'tasks',parent);final placement=await tx.query('task_placements',where:'task_id=? AND deleted_at IS NULL',whereArgs:[parent]);parent=placement.firstOrNull?['parent_task_id'] as String?;}
        await _writeEntity(tx,'task_placements',action,{'task_id':action.taskId,'project_id':action.projectId,'parent_task_id':action.parentTaskId,'priority':action.priority},now);
      case SaveHabit():
        final previous=action.expectedRevision==0?null:await _scoped(tx,'habits',action.id);
        final calendar=await _moduleCalendar(tx,action,'habits',action.name,action.schedule,now,paused:action.paused);
        await _writeEntity(tx,'habits',action,{'name':action.name.trim(),'paused':action.paused?1:0,'calendar_id':calendar},now);
        final clock=DateTime.now(),zone=action.schedule.timezone;
        final day=dateOnly(zone=='device'?clock:tz.TZDateTime.from(clock,calendarLocation(zone)));
        if(action.paused&&previous?['paused']!=1)await tx.insert('habit_pauses',{'id':LocalStore._uuid.v4(),'habit_id':action.id,'start_on':day});
        if(!action.paused&&previous?['paused']==1)await tx.update('habit_pauses',{'end_on':day},where:'habit_id=? AND end_on IS NULL',whereArgs:[action.id]);
      case CheckHabit():
        final habit=await _scoped(tx,'habits',action.habitId);
        final calendar=await _scoped(tx,'calendar_entries',habit['calendar_id'] as String,deleted:true);
        final spec=ScheduleSpec(localStart:calendar['local_start'] as String,timezone:calendar['timezone'] as String,repeat:RepeatRule.values.byName(calendar['repeat_rule'] as String),interval:calendar['repeat_interval'] as int,until:calendar['until_date'] as String?);
        final location=calendarLocation(spec.timezone=='device'?action.timezone=='device'?tz.local.name:action.timezone:spec.timezone),day=DateTime.parse(action.localDate);
        final occurrences=const CalendarEngine().between(CalendarEntry(id:calendar['id'] as String,title:calendar['title'] as String,schedule:spec),tz.TZDateTime(location,day.year,day.month,day.day),tz.TZDateTime(location,day.year,day.month,day.day+1),location.name);
        if(occurrences.isEmpty)throw const DomainFailure('invalid_date');
        await _writeEntity(tx,'habit_checks',action,{'habit_id':action.habitId,'local_date':action.localDate,'timezone':action.timezone,'completed':action.completed?1:0},now);
        for(final o in occurrences){if(action.completed){await tx.insert('calendar_occurrences',{'entry_id':calendar['id'],'revision':calendar['revision'],'epoch':o.at.millisecondsSinceEpoch,'status':'completed','updated_at':now},conflictAlgorithm:sql.ConflictAlgorithm.replace);}else{await tx.delete('calendar_occurrences',where:'entry_id=? AND revision=? AND epoch=? AND status=?',whereArgs:[calendar['id'],calendar['revision'],o.at.millisecondsSinceEpoch,'completed']);}}

      case SaveSubject():await _optional(tx,'projects',action.projectId);await _writeEntity(tx,'learning_subjects',action,{'name':action.name.trim(),'project_id':action.projectId},now);
      case SaveStudyItem():
        await _scoped(tx,'learning_subjects',action.subjectId);await _optional(tx,'tasks',action.taskId);
        final calendar=await _moduleCalendar(tx,action,'study_items',action.name,action.schedule,now,paused:action.completed);
        await _writeEntity(tx,'study_items',action,{'subject_id':action.subjectId,'name':action.name.trim(),'task_id':action.taskId,'calendar_id':calendar,'completed':action.completed?1:0},now);
      case SaveChecklist():await _optional(tx,'notes',action.noteId);await _optional(tx,'projects',action.projectId);await _writeEntity(tx,'checklists',action,{'name':action.name.trim(),'kind':action.kind,'note_id':action.noteId,'project_id':action.projectId},now);
      case SaveChecklistItem():await _scoped(tx,'checklists',action.checklistId);await _optional(tx,'tasks',action.taskId);await _writeEntity(tx,'checklist_items',action,{'checklist_id':action.checklistId,'name':action.name.trim(),'quantity':action.quantity.trim(),'completed':action.completed?1:0,'task_id':action.taskId},now);
      case SetNoteMetadata():await _scoped(tx,'notes',action.noteId);await _writeEntity(tx,'note_metadata',action,{'note_id':action.noteId,'tags':action.tags.map((t)=>t.trim()).join(',')},now);
      case SaveRecordLink():
        await _scoped(tx,'notes',action.noteId);
        await _scoped(tx,switch(action.targetType){'task'=>'tasks','note'=>'notes','project'=>'projects','goal'=>'savings_goals',_=>throw const DomainFailure('invalid_action')},action.targetId);
        await _writeEntity(tx,'record_links',action,{'note_id':action.noteId,'target_type':action.targetType,'target_id':action.targetId},now);
      case SaveWellness():await _writeEntity(tx,'wellness_entries',action,{'kind':action.kind,'local_date':action.localDate,'minutes':action.minutes,'label':action.label.trim()},now);
      case SaveDashboard():await _writeEntity(tx,'dashboard_configs',action,{'widget':action.widget,'visible':action.visible?1:0,'position':action.position,'expanded':action.expanded?1:0},now);
      default:throw const DomainFailure('invalid_action');
    }
  }
  Future<void> _validatePersonal(sql.Transaction tx,String owner,String space) async {
    Future<void> check(String table,Object? id) async {if(id!=null)await _scoped(tx,table,id as String,deleted:true,owner:owner,space:space);}
    final profiles=await tx.query('local_profiles');
    final owners=profiles.where((p)=>p['id']==owner&&p['kind']=='adult'&&p['deleted_at']==null&&p['archived']==0);
    if(owners.length!=1)throw const DomainFailure('backup_invalid');
    for(final p in profiles){if(p['guardian_id']!=null){await check('local_profiles',p['guardian_id']);final parent=profiles.where((g)=>g['id']==p['guardian_id']).single;if(parent['kind']!='adult')throw const DomainFailure('invalid_profile');}}
    final members=await tx.query('local_memberships');
    if(members.where((m)=>m['role']=='owner'&&m['profile_id']==owner&&m['deleted_at']==null&&m['permissions']==7).length!=1||members.any((m)=>m['role']=='owner'&&m['profile_id']!=owner))throw const DomainFailure('backup_invalid');
    for(final m in members){await check('local_profiles',m['profile_id']);}
    for(final p in await tx.query('projects')){await check('budgets',p['budget_id']);await check('calendar_entries',p['calendar_id']);}
    for(final m in await tx.query('project_milestones')){await check('projects',m['project_id']);await check('calendar_entries',m['calendar_id']);}
    for(final item in await tx.query('task_placements')) {
      await check('tasks',item['task_id']);await check('projects',item['project_id']);var parent=item['parent_task_id'] as String?;final seen={item['task_id']};
      while(parent!=null){if(!seen.add(parent))throw const DomainFailure('task_cycle');await check('tasks',parent);final row=await tx.query('task_placements',where:'task_id=? AND deleted_at IS NULL',whereArgs:[parent]);parent=row.firstOrNull?['parent_task_id'] as String?;}
    }
    for(final p in await tx.query('habit_pauses')){await check('habits',p['habit_id']);OfflineValidation.civil(p['start_on'] as String);if(p['end_on']!=null)OfflineValidation.civil(p['end_on'] as String);}
    for(final h in await tx.query('habits')){await check('calendar_entries',h['calendar_id']);}
    for(final h in await tx.query('habit_checks')){await check('habits',h['habit_id']);OfflineValidation.civil(h['local_date'] as String);CalendarEngine.validate(ScheduleSpec(localStart:'${h['local_date']}T09:00:00',timezone:h['timezone'] as String));}
    for(final s in await tx.query('learning_subjects')){await check('projects',s['project_id']);}
    for(final s in await tx.query('study_items')){await check('learning_subjects',s['subject_id']);await check('tasks',s['task_id']);await check('calendar_entries',s['calendar_id']);if(s['task_id']!=null&&s['calendar_id']!=null)throw const DomainFailure('single_schedule');}
    for(final list in await tx.query('checklists')){await check('notes',list['note_id']);await check('projects',list['project_id']);}
    for(final item in await tx.query('checklist_items')){await check('checklists',item['checklist_id']);await check('tasks',item['task_id']);}
    for(final item in await tx.query('note_metadata')){await check('notes',item['note_id']);}
    for(final item in await tx.query('record_links')){await check('notes',item['note_id']);await check(switch(item['target_type']){'task'=>'tasks','note'=>'notes','project'=>'projects','goal'=>'savings_goals',_=>throw const DomainFailure('backup_invalid')},item['target_id']);}
    for(final item in await tx.query('wellness_entries')){OfflineValidation.civil(item['local_date'] as String);}
  }
}
