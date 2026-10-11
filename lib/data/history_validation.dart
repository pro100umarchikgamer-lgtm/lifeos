part of 'local_store.dart';
extension HistoryValidation on LocalStore {
  void _entitySemantics(String table,Map<String,Object?> row) {
    for(final field in ['occurred_on','local_date','target_on','due_on','start_on','end_on']){if(row[field]!=null)OfflineValidation.civil(row[field] as String);}
    DateTime? day(String key)=>row[key]==null?null:DateTime.parse(row[key] as String);
    const op='restore-validation';final id=row['id'] as String? ?? 'restore-row',rev=row['revision'] as int? ?? 1;
    OfflineAction? action=switch(table){
      'accounts'=>SaveAccount(op,id,rev,name:row['name'] as String,currency:row['currency'] as String,kind:row['kind'] as String,openingMinor:row['opening_minor'] as int,archived:row['archived']==1),
      'categories'=>SaveCategory(op,id,rev,row['name'] as String,parentId:row['parent_id'] as String?),
      'transfers'=>SaveTransfer(op,id,rev,fromId:row['from_account_id'] as String,toId:row['to_account_id'] as String,sentMinor:row['sent_minor'] as int,receivedMinor:row['received_minor'] as int,date:day('occurred_on')!),
      'budgets'=>SaveBudget(op,id,rev,name:row['name'] as String,currency:row['currency'] as String,limitMinor:row['limit_minor'] as int,start:day('start_on')!,end:day('end_on'),categoryId:row['category_id'] as String?,period:row['period'] as String,rollover:row['rollover'] as String),
      'savings_goals'=>SaveGoal(op,id,rev,name:row['name'] as String,currency:row['currency'] as String,targetMinor:row['target_minor'] as int,targetOn:day('target_on')),
      'savings_entries'=>SaveGoalEntry(op,id,rev,goalId:row['goal_id'] as String,amountMinor:row['amount_minor'] as int,date:day('occurred_on')!,transactionId:row['transaction_id'] as String?,transferId:row['transfer_id'] as String?),
      'debts'=>SaveDebt(op,id,rev,name:row['name'] as String,currency:row['currency'] as String,principalMinor:row['principal_minor'] as int,direction:row['direction'] as String),
      'debt_entries'=>SaveDebtEntry(op,id,rev,debtId:row['debt_id'] as String,principalMinor:row['principal_minor'] as int,interestMinor:row['interest_minor'] as int,feeMinor:row['fee_minor'] as int,flow:row['flow'] as String,date:day('occurred_on')!),
      'investment_assets'=>SaveAsset(op,id,rev,row['name'] as String,row['currency'] as String),
      'investment_entries'=>SaveInvestmentEntry(op,id,rev,assetId:row['asset_id'] as String,kind:row['kind'] as String,cashMinor:row['cash_minor'] as int,quantityMicros:row['quantity_micros'] as int,feeMinor:row['fee_minor'] as int,date:day('occurred_on')!),
      'projects'=>SaveProject(op,id,rev,name:row['name'] as String,goal:row['goal'] as String,status:row['status'] as String,dueOn:day('due_on')),
      'project_milestones'=>SaveMilestone(op,id,rev,projectId:row['project_id'] as String,name:row['name'] as String,dueOn:day('due_on')),
      'task_placements'=>SetTaskPlacement(op,id,rev,taskId:row['task_id'] as String,parentTaskId:row['parent_task_id'] as String?,priority:row['priority'] as int),
      'learning_subjects'=>SaveSubject(op,id,rev,name:row['name'] as String),
      'study_items'=>SaveStudyItem(op,id,rev,subjectId:row['subject_id'] as String,name:row['name'] as String),
      'checklists'=>SaveChecklist(op,id,rev,name:row['name'] as String,kind:row['kind'] as String),
      'checklist_items'=>SaveChecklistItem(op,id,rev,checklistId:row['checklist_id'] as String,name:row['name'] as String,quantity:row['quantity'] as String),
      'note_metadata'=>SetNoteMetadata(op,id,rev,noteId:row['note_id'] as String,tags:(row['tags'] as String).split(',').where((t)=>t.isNotEmpty).toList()),
      'record_links'=>SaveRecordLink(op,id,rev,noteId:row['note_id'] as String,targetType:row['target_type'] as String,targetId:row['target_id'] as String),
      'wellness_entries'=>SaveWellness(op,id,rev,kind:row['kind'] as String,localDate:row['local_date'] as String,minutes:row['minutes'] as int,label:row['label'] as String),
      'local_profiles'=>SaveProfile(op,id,rev,name:row['name'] as String,kind:row['kind'] as String,guardianId:row['guardian_id'] as String?),
      'dashboard_configs'=>SaveDashboard(op,id,rev,widget:row['widget'] as String,position:row['position'] as int),
      _=>null,
    };
    // Preserve large, historically valid opening balances from v1; no new floating amounts.
    if(action is SaveAccount){OfflineValidation.name(action.name);Currency.fromCode(action.currency);if(!['cash','card','wallet','deposit','custom'].contains(action.kind))throw const DomainFailure('backup_invalid');}
    else if(action!=null)OfflineValidation.validate(action);
  }
  /// Validate embedded snapshots before they can ever become SQL mutation columns.
  Future<Map<String,Object?>> _historySnapshot(sql.Transaction tx,String table,Object? value,String id,{String? owner,String? space}) async {
    final person=owner??ownerId,workspace=space??workspaceId;
    if(value is! Map)throw const DomainFailure('backup_invalid');
    final row=Map<String,Object?>.from(value);
    final columns=await tx.rawQuery('PRAGMA table_info($table)');
    if(columns.isEmpty||row['id']!=id||row['owner_id']!=person||row['workspace_id']!=workspace||row['revision'] is! int||(row['revision'] as int)<1)throw const DomainFailure('backup_invalid');
    final allowed={for(final col in columns)col['name'],if(table=='transactions')'__splits',if(table=='notes'||table=='tasks')'__schedule'};
    if(row.keys.any((k)=>!allowed.contains(k)))throw const DomainFailure('backup_invalid');
    // Only the category extension may be absent from older immutable transaction history.
    if(table=='transactions')row.putIfAbsent('category_id',()=>null);
    if(table=='projects'||table=='project_milestones')row.putIfAbsent('calendar_id',()=>null);
    for(final col in columns){final v=row[col['name']];if(!row.containsKey(col['name'])||v==null&&col['notnull']==1||v!=null&&col['type']=='INTEGER'&&v is! int||v!=null&&col['type']=='TEXT'&&v is! String)throw const DomainFailure('backup_invalid');}
    for(final key in ['created_at','updated_at','deleted_at']){if(row[key]!=null&&DateTime.tryParse(row[key] as String)==null)throw const DomainFailure('backup_invalid');}
    Future<void> scoped(String name,Object? target)async{if(target!=null)await _scoped(tx,name,target as String,deleted:true,owner:person,space:workspace);}
    _entitySemantics(table,row);
    const foreign={'account_id':'accounts','category_id':'categories','parent_id':'categories','from_account_id':'accounts','to_account_id':'accounts','project_id':'projects','profile_id':'local_profiles','guardian_id':'local_profiles','task_id':'tasks','parent_task_id':'tasks','note_id':'notes','budget_id':'budgets','goal_id':'savings_goals','debt_id':'debts','asset_id':'investment_assets','subject_id':'learning_subjects','checklist_id':'checklists','calendar_id':'calendar_entries','transaction_id':'transactions','transfer_id':'transfers'};
    for(final field in foreign.entries){if(row.containsKey(field.key))await scoped(field.value,row[field.key]);}
    if(table=='transactions') {
      final c=Currency.fromCode(row['currency'] as String);OfflineValidation.money(row['amount_minor'] as int);OfflineValidation.civil(row['occurred_on'] as String);
      if(c.digits!=row['minor_digits']||!['income','expense'].contains(row['kind']))throw const DomainFailure('backup_invalid');
      await scoped('accounts',row['account_id']);await scoped('categories',row['category_id']);
      final parts=row['__splits'];if(parts!=null&&parts is! List)throw const DomainFailure('backup_invalid');
      var total=BigInt.zero;final ids=<String>{};
      for(final raw in parts as List? ?? []) {
        if(raw is! Map||raw.length!=6||!raw.keys.toSet().containsAll(['id','transaction_id','amount_minor','category_id','project_id','profile_id'])||raw['id'] is! String||(raw['id'] as String).isEmpty||!ids.add(raw['id'] as String)||raw['transaction_id']!=id||raw['amount_minor'] is! int)throw const DomainFailure('backup_invalid');
        OfflineValidation.money(raw['amount_minor'] as int);total+=BigInt.from(raw['amount_minor'] as int);
        await scoped('categories',raw['category_id']);await scoped('projects',raw['project_id']);await scoped('local_profiles',raw['profile_id']);
      }
      if(ids.length>100||ids.isNotEmpty&&(row['kind']!='expense'||total!=BigInt.from(row['amount_minor'] as int)))throw const DomainFailure('backup_invalid');
    }
    if(row['__schedule'] case final Map schedule) {
      final link=table=='tasks'?'task_id':'note_id';
      if(schedule[link]!=id)throw const DomainFailure('backup_invalid');
      await _historySnapshot(tx,'calendar_entries',schedule,schedule['id'] as String,owner:person,space:workspace);
      final existing=await _scoped(tx,'calendar_entries',schedule['id'] as String,deleted:true,owner:person,space:workspace);
      if(existing[link]!=id)throw const DomainFailure('backup_invalid');
      CalendarEngine.validate(ScheduleSpec(localStart:schedule['local_start'] as String,timezone:schedule['timezone'] as String,repeat:RepeatRule.values.byName(schedule['repeat_rule'] as String),interval:schedule['repeat_interval'] as int,until:schedule['until_date'] as String?));
    }else if(row['__schedule']!=null){throw const DomainFailure('backup_invalid');}
    return row;
  }
}
