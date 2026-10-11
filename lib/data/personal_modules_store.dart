part of 'local_store.dart';
extension PersonalModulesPersistence on LocalStore {
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
      case SaveProject():await _optional(tx,'budgets',action.budgetId);await _writeEntity(tx,'projects',action,{'name':action.name.trim(),'goal':action.goal.trim(),'status':action.status,'due_on':action.dueOn==null?null:dateOnly(action.dueOn!),'budget_id':action.budgetId},now);
      case SaveMilestone():await _scoped(tx,'projects',action.projectId);await _writeEntity(tx,'project_milestones',action,{'project_id':action.projectId,'name':action.name.trim(),'due_on':action.dueOn==null?null:dateOnly(action.dueOn!),'completed':action.completed?1:0},now);
      case SetTaskPlacement():
        await _scoped(tx,'tasks',action.taskId);await _optional(tx,'projects',action.projectId);
        var parent=action.parentTaskId;final seen={action.taskId};
        while(parent!=null){if(!seen.add(parent))throw const DomainFailure('task_cycle');await _scoped(tx,'tasks',parent);final placement=await tx.query('task_placements',where:'task_id=? AND deleted_at IS NULL',whereArgs:[parent]);parent=placement.firstOrNull?['parent_task_id'] as String?;}
        await _writeEntity(tx,'task_placements',action,{'task_id':action.taskId,'project_id':action.projectId,'parent_task_id':action.parentTaskId,'priority':action.priority},now);
      case SaveHabit():
        final calendar=await _moduleCalendar(tx,action,'habits',action.name,action.schedule,now,paused:action.paused);
        await _writeEntity(tx,'habits',action,{'name':action.name.trim(),'paused':action.paused?1:0,'calendar_id':calendar},now);
      case CheckHabit():await _scoped(tx,'habits',action.habitId);await _writeEntity(tx,'habit_checks',action,{'habit_id':action.habitId,'local_date':action.localDate,'timezone':action.timezone,'completed':action.completed?1:0},now);
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
    for(final p in await tx.query('projects')){await check('budgets',p['budget_id']);}
    for(final m in await tx.query('project_milestones')){await check('projects',m['project_id']);}
    for(final item in await tx.query('task_placements')) {
      await check('tasks',item['task_id']);await check('projects',item['project_id']);var parent=item['parent_task_id'] as String?;final seen={item['task_id']};
      while(parent!=null){if(!seen.add(parent))throw const DomainFailure('task_cycle');await check('tasks',parent);final row=await tx.query('task_placements',where:'task_id=? AND deleted_at IS NULL',whereArgs:[parent]);parent=row.firstOrNull?['parent_task_id'] as String?;}
    }
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
