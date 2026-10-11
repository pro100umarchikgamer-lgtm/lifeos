part of 'local_store.dart';
extension HistoryValidation on LocalStore {
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
    for(final col in columns){final v=row[col['name']];if(!row.containsKey(col['name'])||v==null&&col['notnull']==1||v!=null&&col['type']=='INTEGER'&&v is! int||v!=null&&col['type']=='TEXT'&&v is! String)throw const DomainFailure('backup_invalid');}
    for(final key in ['created_at','updated_at','deleted_at']){if(row[key]!=null&&DateTime.tryParse(row[key] as String)==null)throw const DomainFailure('backup_invalid');}
    Future<void> scoped(String name,Object? target)async{if(target!=null)await _scoped(tx,name,target as String,deleted:true,owner:person,space:workspace);}
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
      await scoped('calendar_entries',schedule['id']);
      CalendarEngine.validate(ScheduleSpec(localStart:schedule['local_start'] as String,timezone:schedule['timezone'] as String,repeat:RepeatRule.values.byName(schedule['repeat_rule'] as String),interval:schedule['repeat_interval'] as int,until:schedule['until_date'] as String?));
    }else if(row['__schedule']!=null){throw const DomainFailure('backup_invalid');}
    return row;
  }
}
