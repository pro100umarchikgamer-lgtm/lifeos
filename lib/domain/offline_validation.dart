import 'models.dart';
import 'calendar_engine.dart';

class OfflineValidation {
  static void money(int value,{bool signed=false,bool zero=false}) {
    if(value.abs()>999999999999999 || !signed && (zero?value<0:value<=0)) throw const DomainFailure('invalid_amount');
  }
  static void name(String value) { if(value.trim().isEmpty || value.length>2000) throw const DomainFailure('required_text'); }
  static void date(DateTime value) { if(value.year<1900||value.year>2200) throw const DomainFailure('invalid_date'); }
  static void civil(String text){final d=DateTime.tryParse(text);if(d==null||dateOnly(d)!=text)throw const DomainFailure('invalid_date');date(d);}
  static void validate(OfflineAction action) {
    if(action.id.isEmpty || action.expectedRevision<0) throw const DomainFailure('invalid_action');
    switch(action) {
      case CopyChecklist():name(action.name);if(action.expectedRevision!=0||action.sourceRevision<1||action.sourceId==action.id)throw const DomainFailure('invalid_action');
      case SaveProfile():name(action.name);if(!['adult','child'].contains(action.kind)||action.kind=='child'&&(action.guardianId==null||action.guardianId==action.id)||action.kind=='adult'&&action.guardianId!=null)throw const DomainFailure('invalid_profile');
      case SaveMembership():if(!['viewer','contributor','manager'].contains(action.role)||action.permissions<0||action.permissions>7)throw const DomainFailure('invalid_action');
      case SaveProject(): name(action.name);if(action.goal.length>2000||!['active','paused','done'].contains(action.status))throw const DomainFailure('invalid_action');if(action.dueOn!=null)date(action.dueOn!);
      case SaveMilestone():name(action.name);if(action.dueOn!=null)date(action.dueOn!);
      case SetTaskPlacement():if(action.taskId==action.parentTaskId||action.priority<0||action.priority>3)throw const DomainFailure('invalid_action');
      case SaveHabit():name(action.name);CalendarEngine.validate(action.schedule);if(action.schedule.repeat==RepeatRule.none)throw const DomainFailure('habit_repeat_required');
      case CheckHabit(): civil(action.localDate);CalendarEngine.validate(ScheduleSpec(localStart:'${action.localDate}T09:00:00',timezone:action.timezone));
      case SaveSubject():name(action.name);
      case SaveStudyItem():name(action.name);if(action.schedule!=null)CalendarEngine.validate(action.schedule!);if(action.taskId!=null&&action.schedule!=null)throw const DomainFailure('single_schedule');
      case SaveChecklist():name(action.name);if(!['note','shopping','chores'].contains(action.kind))throw const DomainFailure('invalid_action');
      case SaveChecklistItem():name(action.name);if(action.quantity.length>100)throw const DomainFailure('invalid_action');
      case SetNoteMetadata():if(action.tags.length>30||action.tags.toSet().length!=action.tags.length||action.tags.any((t)=>t.trim().isEmpty||t.length>50||t.contains(',')))throw const DomainFailure('invalid_action');
      case SaveRecordLink():if(!['task','note','project','goal'].contains(action.targetType)||action.noteId==action.targetId)throw const DomainFailure('invalid_action');
      case SaveWellness():civil(action.localDate);if(!['sleep','activity'].contains(action.kind)||action.minutes<0||action.minutes>1440||action.label.length>2000)throw const DomainFailure('invalid_action');
      case SaveDashboard():if(!['financial','tasks','notes','projects','habits','shopping'].contains(action.widget)||action.position<0||action.position>100)throw const DomainFailure('invalid_action');
      case ConfirmImport():
        if(action.expectedRevision!=0||!RegExp(r'^[0-9a-f]{64}$').hasMatch(action.contentKey)||action.rows.isEmpty||action.rows.length>10000||action.rows.map((r)=>r.originKey).toSet().length!=action.rows.length)throw const DomainFailure('invalid_action');
        for(final r in action.rows){money(r.amountMinor);Currency.fromCode(r.currency);if(r.kind!=EntryKind.income&&r.kind!=EntryKind.expense||!RegExp(r'^[0-9a-f]{64}$').hasMatch(r.originKey)||r.label.length>2000)throw const DomainFailure('invalid_action');final d=DateTime.tryParse(r.date);if(d==null||dateOnly(d)!=r.date)throw const DomainFailure('invalid_date');date(d);}
      case ReverseImport(): if(action.expectedRevision<1)throw const DomainFailure('invalid_action');
      case SaveGoal(): name(action.name);Currency.fromCode(action.currency);money(action.targetMinor,zero:true);if(action.targetOn!=null)date(action.targetOn!);
      case SaveGoalEntry(): money(action.amountMinor,signed:true);date(action.date);if(action.amountMinor==0||action.transactionId!=null&&action.transferId!=null)throw const DomainFailure('invalid_action');
      case SaveDebt(): name(action.name);Currency.fromCode(action.currency);money(action.principalMinor,zero:true);if(!['owing','owed'].contains(action.direction))throw const DomainFailure('invalid_action');if(action.schedule!=null)CalendarEngine.validate(action.schedule!);
      case SaveDebtEntry(): money(action.principalMinor,zero:true);money(action.interestMinor,zero:true);money(action.feeMinor,zero:true);date(action.date);
        if(!['advance','repay'].contains(action.flow)||BigInt.from(action.principalMinor)+BigInt.from(action.interestMinor)+BigInt.from(action.feeMinor)==BigInt.zero)throw const DomainFailure('invalid_action');
      case SaveAsset(): name(action.name);Currency.fromCode(action.currency);
      case SaveInvestmentEntry(): money(action.cashMinor,zero:true);money(action.feeMinor,zero:true);money(action.quantityMicros,zero:true);date(action.date);
        if(!['buy','sell','dividend','distribution','valuation'].contains(action.kind)||['buy','sell'].contains(action.kind)&&action.quantityMicros==0||!['buy','sell'].contains(action.kind)&&action.quantityMicros!=0)throw const DomainFailure('invalid_action');if(action.kind!='buy'&&action.feeMinor>action.cashMinor)throw const DomainFailure('invalid_amount');
      case SaveAccount(): name(action.name); Currency.fromCode(action.currency); money(action.openingMinor,signed:true);
        if(!['cash','card','wallet','deposit','custom'].contains(action.kind)) throw const DomainFailure('invalid_action');
      case SaveCategory(): name(action.name); if(action.parentId==action.id) throw const DomainFailure('invalid_action');
      case SaveTransfer(): money(action.sentMinor); money(action.receivedMinor); date(action.date);
        if(action.fromId.isEmpty||action.toId.isEmpty||action.fromId==action.toId) throw const DomainFailure('invalid_action');
      case SetMoneyDetails(): if(action.expectedRevision<1) throw const DomainFailure('invalid_action'); validateSplits(action.splits);if(action.amountMinor!=null)money(action.amountMinor!);
      case SaveBudget(): name(action.name); Currency.fromCode(action.currency); money(action.limitMinor,zero:true); date(action.start);
        if(!['week','month','year','custom'].contains(action.period)||!['none','positive','negative','both'].contains(action.rollover)||
          action.period=='month'&&action.start.day!=1 || action.period=='year'&&(action.start.day!=1||action.start.month!=1)||
          action.period=='custom'&&(action.end==null||action.end!.isBefore(action.start))) { throw const DomainFailure('invalid_date'); }
        if(action.end!=null) { date(action.end!); }
      case SavePlannedPayment(): name(action.name); Currency.fromCode(action.currency); money(action.amountMinor); CalendarEngine.validate(action.schedule);
        if(action.kind!=EntryKind.expense&&action.kind!=EntryKind.income) throw const DomainFailure('invalid_action');
      case ConfirmPlannedPayment(): final value=DateTime.tryParse(action.occurrence);
        if(action.expectedRevision<1||value==null||dateOnly(value)!=action.occurrence) throw const DomainFailure('invalid_date'); date(value);
      case DeleteOffline() || UndoOffline(): if(action.expectedRevision<1) throw const DomainFailure('invalid_action');
    }
  }
  static void validateSplits(List<ExpenseSplit> splits) {
    if(splits.length>100 || splits.map((s)=>s.id).toSet().length!=splits.length) throw const DomainFailure('invalid_action');
    for(final s in splits) { if(s.id.isEmpty) throw const DomainFailure('invalid_action'); money(s.amountMinor); }
  }
}
