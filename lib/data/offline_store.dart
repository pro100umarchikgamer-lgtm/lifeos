part of 'local_store.dart';

extension OfflinePersistence on LocalStore {
  Future<Map<String,Object?>> _scoped(sql.Transaction tx,String table,String id,{bool deleted=false,String? owner,String? space}) async {
    final rows=await tx.query(table,where:'id=? AND owner_id=? AND workspace_id=?',whereArgs:[id,owner??ownerId,space??workspaceId]);
    if(rows.length!=1||!deleted&&rows.single['deleted_at']!=null) throw const DomainFailure('record_missing');
    return Map<String,Object?>.from(rows.single);
  }
  Future<void> _writeEntity(sql.Transaction tx,String table,OfflineAction action,Map<String,Object?> values,String now,{bool undo=false}) async {
    Map<String,Object?>? before;
    if(action.expectedRevision==0) {
      await tx.insert(table,{'id':action.id,'owner_id':ownerId,'workspace_id':workspaceId,'created_at':now,'updated_at':now,...values});
    } else {
      before=await _scoped(tx,table,action.id,deleted:undo);
      if(before['revision']!=action.expectedRevision) throw const DomainFailure('revision_conflict');
      final changed=await tx.update(table,{...values,'revision':action.expectedRevision+1,'updated_at':now},
        where:'id=? AND owner_id=? AND workspace_id=? AND revision=?',whereArgs:[action.id,ownerId,workspaceId,action.expectedRevision]);
      if(changed!=1) throw const DomainFailure('revision_conflict');
    }
    final after=await _scoped(tx,table,action.id,deleted:true);
    await tx.insert('entity_changes',{'operation_id':action.operationId,'table_name':table,'record_id':action.id,
      'revision':after['revision'],'before_json':before==null?null:jsonEncode(before),'after_json':jsonEncode(after)});
  }
  Future<void> _moneyRelations(sql.Transaction tx,String id,{String? owner,String? space}) async {
    final row=await _scoped(tx,'transactions',id,deleted:true,owner:owner,space:space);
    if(row['account_id']!=null) {
      final account=await _scoped(tx,'accounts',row['account_id'] as String,deleted:true,owner:owner,space:space);
      if(account['currency']!=row['currency']) throw const DomainFailure('currency_mismatch');
    }
    if(row['category_id']!=null) await _scoped(tx,'categories',row['category_id'] as String,deleted:true,owner:owner,space:space);
    final splits=await tx.query('transaction_splits',where:'transaction_id=?',whereArgs:[id]);
    if(splits.isNotEmpty && (row['kind']!='expense'||splits.fold(BigInt.zero,(v,s)=>v+BigInt.from(s['amount_minor'] as int))!=BigInt.from(row['amount_minor'] as int))) throw const DomainFailure('split_total');
    for(final s in splits) {
      if(s['category_id']!=null) await _scoped(tx,'categories',s['category_id'] as String,deleted:true,owner:owner,space:space);
      if(s['project_id']!=null) await _scoped(tx,'projects',s['project_id'] as String,deleted:true,owner:owner,space:space);
      if(s['profile_id']!=null) await _scoped(tx,'local_profiles',s['profile_id'] as String,deleted:true,owner:owner,space:space);
    }
  }
  Future<void> _replaceSplits(sql.Transaction tx,String id,List<ExpenseSplit> splits) async {
    await tx.delete('transaction_splits',where:'transaction_id=?',whereArgs:[id]);
    for(final s in splits) { await tx.insert('transaction_splits',{'id':s.id,'transaction_id':id,'amount_minor':s.amountMinor,
      'category_id':s.categoryId,'project_id':s.projectId,'profile_id':s.profileId}); }
  }
  Future<void> _auditMoneyAfter(sql.Transaction tx,String id,String operation) async {
    await _moneyRelations(tx,id);
    final row=await _scoped(tx,'transactions',id,deleted:true);
    final splits=await tx.query('transaction_splits',where:'transaction_id=?',whereArgs:[id]);
    await tx.update('record_changes',{'after_json':jsonEncode({...row,'__splits':splits})},where:'operation_id=?',whereArgs:[operation]);
  }
  Future<void> _validateOfflineRestore(sql.Transaction tx,String owner,String space) async {
    for(final t in await tx.query('transfers')) {
      final a=await _scoped(tx,'accounts',t['from_account_id'] as String,deleted:true,owner:owner,space:space);
      final b=await _scoped(tx,'accounts',t['to_account_id'] as String,deleted:true,owner:owner,space:space);
      if(a['currency']==b['currency']&&t['sent_minor']!=t['received_minor']) throw const DomainFailure('backup_invalid');
    }
    for(final c in await tx.query('categories')) {
      var parent=c['parent_id'] as String?; final seen={c['id']};
      while(parent!=null) { if(!seen.add(parent)) throw const DomainFailure('backup_invalid'); parent=(await _scoped(tx,'categories',parent,deleted:true,owner:owner,space:space))['parent_id'] as String?; }
    }
    for(final p in await tx.query('planned_payments')) {
      await _scoped(tx,'calendar_entries',p['calendar_id'] as String,deleted:true,owner:owner,space:space);
      if(p['account_id']!=null && (await _scoped(tx,'accounts',p['account_id'] as String,deleted:true,owner:owner,space:space))['currency']!=p['currency']) throw const DomainFailure('backup_invalid');
      if(p['category_id']!=null) await _scoped(tx,'categories',p['category_id'] as String,deleted:true,owner:owner,space:space);
    }
    await _validateWealth(tx,owner:owner,space:space);
    await _validatePersonal(tx,owner,space);
    for(final batch in await tx.query('import_batches')) {
      final imported=await tx.query('import_rows',where:'batch_id=?',whereArgs:[batch['id']]);
      if(imported.length!=batch['row_count']||!RegExp(r'^[0-9a-f]{64}$').hasMatch(batch['content_key'] as String))throw const DomainFailure('backup_invalid');
      for(final r in imported){await _scoped(tx,'transactions',r['transaction_id'] as String,deleted:true,owner:owner,space:space);if(!RegExp(r'^[0-9a-f]{64}$').hasMatch(r['origin_key'] as String)||!RegExp(r'^[0-9a-f]{64}$').hasMatch(r['fingerprint'] as String))throw const DomainFailure('backup_invalid');}
    }
    final allowed={...OfflineTable.values.map((t)=>t.sqlName)};
    for(final change in await tx.query('entity_changes')) {
      if(!allowed.contains(change['table_name'])) throw const DomainFailure('backup_invalid');
      await _scoped(tx,change['table_name'] as String,change['record_id'] as String,deleted:true,owner:owner,space:space);
      for(final field in ['before_json','after_json']) {
        if(change[field]==null) continue;
        final v=await _historySnapshot(tx,change['table_name'] as String,jsonDecode(change[field] as String),change['record_id'] as String,owner:owner,space:space);
        if(v['id']!=change['record_id']||v['owner_id']!=owner||v['workspace_id']!=space||v['revision'] is! int) throw const DomainFailure('backup_invalid');
      }
    }
  }
  Future<String> _applyOffline(sql.Transaction tx,OfflineAction action,String now) async {
    switch(action) {
      case CopyChecklist()||SaveProfile()||SaveMembership()||SaveProject()||SaveMilestone()||SetTaskPlacement()||SaveHabit()||CheckHabit()||SaveSubject()||SaveStudyItem()||SaveChecklist()||SaveChecklistItem()||SetNoteMetadata()||SaveRecordLink()||SaveWellness()||SaveDashboard():await _applyPersonal(tx,action,now);
      case ConfirmImport()||ReverseImport(): return _applyImport(tx,action,now);
      case SaveGoal()||SaveGoalEntry()||SaveDebt()||SaveDebtEntry()||SaveAsset()||SaveInvestmentEntry(): await _applyWealth(tx,action,now);
      case SaveAccount():
        if(action.expectedRevision>0) {
          final before=await _scoped(tx,'accounts',action.id);
          if(before['currency']!=Currency.fromCode(action.currency).code) {
            final used=await tx.rawQuery('SELECT id FROM transactions WHERE account_id=? UNION ALL SELECT id FROM transfers WHERE from_account_id=? OR to_account_id=? LIMIT 1',[action.id,action.id,action.id]);
            if(used.isNotEmpty) throw const DomainFailure('currency_mismatch');
          }
        }
        await _writeEntity(tx,'accounts',action,{'name':action.name.trim(),'currency':Currency.fromCode(action.currency).code,'kind':action.kind,'opening_minor':action.openingMinor,'archived':action.archived?1:0},now);
      case SaveCategory():
        var parent=action.parentId; final visited={action.id};
        while(parent!=null) { if(!visited.add(parent)) throw const DomainFailure('invalid_action'); parent=(await _scoped(tx,'categories',parent))['parent_id'] as String?; }
        await _writeEntity(tx,'categories',action,{'name':action.name.trim(),'parent_id':action.parentId,'archived':action.archived?1:0},now);
      case SaveTransfer():
        final from=await _scoped(tx,'accounts',action.fromId), to=await _scoped(tx,'accounts',action.toId);
        if(from['currency']==to['currency']&&action.sentMinor!=action.receivedMinor) throw const DomainFailure('currency_mismatch');
        await _writeEntity(tx,'transfers',action,{'from_account_id':action.fromId,'to_account_id':action.toId,'sent_minor':action.sentMinor,'received_minor':action.receivedMinor,'occurred_on':dateOnly(action.date),'label':action.label.trim()},now);
      case SetMoneyDetails():
        final before=await _scoped(tx,'transactions',action.id);
        await _mutate(tx,'transactions',action.id,action.expectedRevision,{'account_id':action.accountId,'category_id':action.categoryId,if(action.amountMinor!=null)'amount_minor':action.amountMinor},action.operationId,now,expectedKind:EntryKind.values.byName(before['kind'] as String));
        await _replaceSplits(tx,action.id,action.splits); await _auditMoneyAfter(tx,action.id,action.operationId);
      case SaveBudget():
        if(action.categoryId!=null) await _scoped(tx,'categories',action.categoryId!);
        await _writeEntity(tx,'budgets',action,{'name':action.name.trim(),'currency':Currency.fromCode(action.currency).code,'limit_minor':action.limitMinor,'category_id':action.categoryId,
          'period':action.period,'start_on':dateOnly(action.start),'end_on':action.end==null?null:dateOnly(action.end!),'rollover':action.rollover},now);
      case SavePlannedPayment():
        if(action.accountId!=null && (await _scoped(tx,'accounts',action.accountId!))['currency']!=Currency.fromCode(action.currency).code) throw const DomainFailure('currency_mismatch');
        if(action.categoryId!=null) await _scoped(tx,'categories',action.categoryId!);
        final before=action.expectedRevision==0?null:await _scoped(tx,'planned_payments',action.id);
        final calendar=before?['calendar_id'] as String? ?? LocalStore._uuid.v4();
        final old=before==null?null:await _scoped(tx,'calendar_entries',calendar);
        await _saveCalendar(tx,calendar,action.name,action.schedule,now,expectedRevision:old?['revision'] as int?);
        await _writeEntity(tx,'planned_payments',action,{'name':action.name.trim(),'kind':action.kind.name,'currency':Currency.fromCode(action.currency).code,'amount_minor':action.amountMinor,
          'account_id':action.accountId,'category_id':action.categoryId,'calendar_id':calendar},now);
      case ConfirmPlannedPayment():
        final plan=await _scoped(tx,'planned_payments',action.id);
        if(plan['revision']!=action.expectedRevision) throw const DomainFailure('revision_conflict');
        final prior=await tx.query('planned_confirmations',where:'plan_id=? AND occurrence=?',whereArgs:[action.id,action.occurrence]);
        if(prior.isNotEmpty) return prior.single['transaction_id'] as String;
        final schedule=await _scoped(tx,'calendar_entries',plan['calendar_id'] as String);
        final spec=ScheduleSpec(localStart:schedule['local_start'] as String,timezone:schedule['timezone'] as String,repeat:RepeatRule.values.byName(schedule['repeat_rule'] as String),interval:schedule['repeat_interval'] as int,until:schedule['until_date'] as String?);
        // Only an actual occurrence of this plan may be confirmed.
        final civil=DateTime.parse(action.occurrence), location=tz.getLocation(spec.timezone=='device'?'UTC':spec.timezone);
        final event=CalendarEntry(id:plan['calendar_id'] as String,title:plan['name'] as String,schedule:spec);
        final occurrences=const CalendarEngine().between(event,tz.TZDateTime(location,civil.year,civil.month,civil.day),tz.TZDateTime(location,civil.year,civil.month,civil.day+1),'UTC');
        if(occurrences.isEmpty) throw const DomainFailure('invalid_date');
        final money=LocalStore._uuid.v4();
        await tx.insert('transactions',{'id':money,'owner_id':ownerId,'workspace_id':workspaceId,'kind':plan['kind'],'amount_minor':plan['amount_minor'],
          'currency':plan['currency'],'minor_digits':Currency.fromCode(plan['currency'] as String).digits,'occurred_on':action.occurrence,'label':plan['name'],
          'account_id':plan['account_id'],'category_id':plan['category_id'],'created_at':now,'updated_at':now});
        await _moneyRelations(tx,money);
        await tx.insert('planned_confirmations',{'plan_id':action.id,'occurrence':action.occurrence,'transaction_id':money});
        return money;
      case DeleteOffline() || UndoOffline():
        final table=action is DeleteOffline?action.table:(action as UndoOffline).table;
        if(![OfflineTable.accounts,OfflineTable.categories,OfflineTable.transfers,OfflineTable.budgets,OfflineTable.plannedPayments,OfflineTable.goals,OfflineTable.goalEntries,OfflineTable.debts,OfflineTable.debtEntries,OfflineTable.assets,OfflineTable.investmentEntries,OfflineTable.projects,OfflineTable.milestones,OfflineTable.taskPlacements,OfflineTable.habits,OfflineTable.habitChecks,OfflineTable.subjects,OfflineTable.studyItems,OfflineTable.checklists,OfflineTable.checklistItems,OfflineTable.noteMetadata,OfflineTable.recordLinks,OfflineTable.wellness].contains(table)) throw const DomainFailure('invalid_action');
        if(action is DeleteOffline) {
          if(table==OfflineTable.habitChecks)throw const DomainFailure('clear_habit_check');
          if(table==OfflineTable.accounts||table==OfflineTable.categories) throw const DomainFailure('archive_instead');
          final children=switch(table){OfflineTable.projects=>[('project_milestones','project_id'),('task_placements','project_id'),('learning_subjects','project_id'),('checklists','project_id')],OfflineTable.goals=>[('savings_entries','goal_id')],OfflineTable.debts=>[('debt_entries','debt_id')],OfflineTable.assets=>[('investment_entries','asset_id')],OfflineTable.subjects=>[('study_items','subject_id')],OfflineTable.checklists=>[('checklist_items','checklist_id')],_=> <(String,String)>[]};
          for(final (child,key) in children){if((await tx.query(child,columns:['id'],where:'$key=? AND deleted_at IS NULL',whereArgs:[action.id],limit:1)).isNotEmpty)throw const DomainFailure('has_active_children');}
          await _writeEntity(tx,table.sqlName,action,{'deleted_at':now},now);
          if([OfflineTable.projects,OfflineTable.milestones,OfflineTable.plannedPayments,OfflineTable.debts,OfflineTable.habits,OfflineTable.studyItems].contains(table)) {
            final row=await _scoped(tx,table.sqlName,action.id,deleted:true);
            if(row['calendar_id']!=null) await tx.update('calendar_entries',{'deleted_at':now,'revision':((await _scoped(tx,'calendar_entries',row['calendar_id'] as String,deleted:true))['revision'] as int)+1,'updated_at':now},where:'id=?',whereArgs:[row['calendar_id']]);
          }
        } else {
          if([OfflineTable.projects,OfflineTable.milestones,OfflineTable.plannedPayments,OfflineTable.debts,OfflineTable.habits,OfflineTable.studyItems].contains(table)) throw const DomainFailure('undo_unavailable');
          final history=await tx.query('entity_changes',where:'table_name=? AND record_id=? AND revision=?',whereArgs:[table.sqlName,action.id,action.expectedRevision]);
          if(history.isEmpty||history.single['before_json']==null) throw const DomainFailure('undo_unavailable');
          final values=await _historySnapshot(tx,table.sqlName,jsonDecode(history.single['before_json'] as String),action.id);
          for(final key in ['id','owner_id','workspace_id','created_at','updated_at','revision']) { values.remove(key); }
          await _writeEntity(tx,table.sqlName,action,values,now,undo:true);
          if(table==OfflineTable.categories){var parent=values['parent_id'] as String?;final seen={action.id};while(parent!=null){if(!seen.add(parent))throw const DomainFailure('invalid_action');parent=(await _scoped(tx,'categories',parent,deleted:true))['parent_id'] as String?;}}
          if([OfflineTable.projects,OfflineTable.taskPlacements,OfflineTable.milestones,OfflineTable.subjects,OfflineTable.checklists,OfflineTable.checklistItems,OfflineTable.recordLinks].contains(table))await _validatePersonal(tx,ownerId,workspaceId);
        }
    }
    if(action is! CopyChecklist&&action is! SaveProfile&&action is! SaveMembership&&action is! SaveProject&&action is! SaveMilestone&&action is! SetTaskPlacement&&action is! SaveHabit&&action is! CheckHabit&&action is! SaveSubject&&action is! SaveStudyItem&&action is! SaveChecklist&&action is! SaveChecklistItem&&action is! SetNoteMetadata&&action is! SaveRecordLink&&action is! SaveWellness&&action is! SaveDashboard)await _validateWealth(tx);
    return action.id;
  }
}
