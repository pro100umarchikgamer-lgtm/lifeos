part of 'models.dart';

enum OfflineTable { accounts, categories, transfers, budgets, plannedPayments, goals, goalEntries, debts, debtEntries, assets, investmentEntries, projects, habits, habitChecks, subjects, studyItems, checklists, checklistItems, wellness, profiles, memberships, dashboard, importBatches, milestones, taskPlacements, noteMetadata, recordLinks }
extension OfflineTableName on OfflineTable {
  String get sqlName => switch (this) {
    OfflineTable.plannedPayments => 'planned_payments', OfflineTable.goals => 'savings_goals',
    OfflineTable.goalEntries => 'savings_entries', OfflineTable.debts => 'debts', OfflineTable.debtEntries => 'debt_entries',
    OfflineTable.assets => 'investment_assets', OfflineTable.investmentEntries => 'investment_entries',
    OfflineTable.habitChecks => 'habit_checks', OfflineTable.subjects => 'learning_subjects', OfflineTable.studyItems => 'study_items',
    OfflineTable.checklistItems => 'checklist_items', OfflineTable.wellness => 'wellness_entries',
    OfflineTable.profiles => 'local_profiles', OfflineTable.memberships => 'local_memberships',
    OfflineTable.milestones => 'project_milestones', OfflineTable.taskPlacements => 'task_placements', OfflineTable.noteMetadata => 'note_metadata', OfflineTable.recordLinks => 'record_links', OfflineTable.importBatches => 'import_batches', OfflineTable.dashboard => 'dashboard_configs', _ => name,
  };
}

sealed class OfflineAction extends AppAction {
  const OfflineAction(super.operationId, this.id, this.expectedRevision);
  final String id;
  final int expectedRevision;
  Map<String,Object?> get target => {'id':id,'expectedRevision':expectedRevision};
}
class SaveAccount extends OfflineAction {
  const SaveAccount(super.operationId,super.id,super.expectedRevision,{required this.name,required this.currency,
    this.kind='cash',this.openingMinor=0,this.archived=false});
  final String name,currency,kind;
  final int openingMinor;
  final bool archived;
  @override
  Map<String,Object?> get payload => {...target,'action':'account.save','name':name.trim(),'currency':currency,
    'kind':kind,'openingMinor':openingMinor,'archived':archived};
}
class SaveCategory extends OfflineAction {
  const SaveCategory(super.operationId,super.id,super.expectedRevision,this.name,{this.parentId,this.archived=false});
  final String name;
  final String? parentId;
  final bool archived;
  @override
  Map<String,Object?> get payload => {...target,'action':'category.save','name':name.trim(),'parentId':parentId,'archived':archived};
}
class SaveTransfer extends OfflineAction {
  const SaveTransfer(super.operationId,super.id,super.expectedRevision,{required this.fromId,required this.toId,
    required this.sentMinor,required this.receivedMinor,required this.date,this.label=''});
  final String fromId,toId,label;
  final int sentMinor,receivedMinor;
  final DateTime date;
  @override
  Map<String,Object?> get payload => {...target,'action':'transfer.save','from':fromId,'to':toId,
    'sent':sentMinor,'received':receivedMinor,'date':dateOnly(date),'label':label.trim()};
}
class ExpenseSplit {
  const ExpenseSplit(this.id,this.amountMinor,{this.categoryId,this.projectId,this.profileId});
  final String id;
  final int amountMinor;
  final String? categoryId,projectId,profileId;
  Map<String,Object?> toJson() => {'id':id,'amountMinor':amountMinor,'categoryId':categoryId,'projectId':projectId,'profileId':profileId};
}
class SetMoneyDetails extends OfflineAction {
  const SetMoneyDetails(super.operationId,super.id,super.expectedRevision,{this.accountId,this.categoryId,this.splits=const []});
  final String? accountId,categoryId;
  final List<ExpenseSplit> splits;
  @override
  Map<String,Object?> get payload => {...target,'action':'money.details','accountId':accountId,'categoryId':categoryId,'splits':splits.map((s)=>s.toJson()).toList()};
}
class SaveBudget extends OfflineAction {
  const SaveBudget(super.operationId,super.id,super.expectedRevision,{required this.name,required this.currency,
    required this.limitMinor,required this.start,this.end,this.categoryId,this.period='month',this.rollover='none'});
  final String name,currency,period,rollover;
  final String? categoryId;
  final int limitMinor;
  final DateTime start;
  final DateTime? end;
  @override
  Map<String,Object?> get payload => {...target,'action':'budget.save','name':name.trim(),'currency':currency,
    'limit':limitMinor,'start':dateOnly(start),'end':end==null?null:dateOnly(end!),'categoryId':categoryId,'period':period,'rollover':rollover};
}
class SavePlannedPayment extends OfflineAction {
  const SavePlannedPayment(super.operationId,super.id,super.expectedRevision,{required this.name,required this.kind,
    required this.currency,required this.amountMinor,required this.schedule,this.accountId,this.categoryId});
  final String name,currency;
  final EntryKind kind;
  final int amountMinor;
  final ScheduleSpec schedule;
  final String? accountId,categoryId;
  @override
  Map<String,Object?> get payload => {...target,'action':'plan.save','name':name.trim(),'kind':kind.name,'currency':currency,
    'amount':amountMinor,'schedule':schedule.toJson(),'accountId':accountId,'categoryId':categoryId};
}
class ConfirmPlannedPayment extends OfflineAction {
  const ConfirmPlannedPayment(super.operationId,super.id,super.expectedRevision,this.occurrence);
  final String occurrence;
  @override
  Map<String,Object?> get payload => {...target,'action':'plan.confirm','occurrence':occurrence};
}
class DeleteOffline extends OfflineAction {
  const DeleteOffline(super.operationId,super.id,super.expectedRevision,this.table);
  final OfflineTable table;
  @override
  Map<String,Object?> get payload => {...target,'action':'entity.delete','table':table.sqlName};
}
class UndoOffline extends OfflineAction {
  const UndoOffline(super.operationId,super.id,super.expectedRevision,this.table);
  final OfflineTable table;
  @override
  Map<String,Object?> get payload => {...target,'action':'entity.undo','table':table.sqlName};
}

class SaveGoal extends OfflineAction {
  const SaveGoal(super.operationId,super.id,super.expectedRevision,{required this.name,required this.currency,required this.targetMinor,this.targetOn,this.accountId});
  final String name,currency;final int targetMinor;final DateTime? targetOn;final String? accountId;
  @override Map<String,Object?> get payload=>{...target,'action':'goal.save','name':name.trim(),'currency':currency,'target':targetMinor,'targetOn':targetOn==null?null:dateOnly(targetOn!),'accountId':accountId};
}
class SaveGoalEntry extends OfflineAction {
  const SaveGoalEntry(super.operationId,super.id,super.expectedRevision,{required this.goalId,required this.amountMinor,required this.date,this.transactionId,this.transferId});
  final String goalId;final int amountMinor;final DateTime date;final String? transactionId,transferId;
  @override Map<String,Object?> get payload=>{...target,'action':'goal.entry','goalId':goalId,'amount':amountMinor,'date':dateOnly(date),'transactionId':transactionId,'transferId':transferId};
}
class SaveDebt extends OfflineAction {
  const SaveDebt(super.operationId,super.id,super.expectedRevision,{required this.name,required this.currency,required this.principalMinor,this.direction='owing',this.schedule});
  final String name,currency,direction;final int principalMinor;final ScheduleSpec? schedule;
  @override Map<String,Object?> get payload=>{...target,'action':'debt.save','name':name.trim(),'currency':currency,'principal':principalMinor,'direction':direction,'schedule':schedule?.toJson()};
}
class SaveDebtEntry extends OfflineAction {
  const SaveDebtEntry(super.operationId,super.id,super.expectedRevision,{required this.debtId,required this.principalMinor,required this.date,this.interestMinor=0,this.feeMinor=0,this.flow='repay',this.transactionId});
  final String debtId,flow;final int principalMinor,interestMinor,feeMinor;final DateTime date;final String? transactionId;
  @override Map<String,Object?> get payload=>{...target,'action':'debt.entry','debtId':debtId,'principal':principalMinor,'interest':interestMinor,'fee':feeMinor,'flow':flow,'date':dateOnly(date),'transactionId':transactionId};
}
class SaveAsset extends OfflineAction {
  const SaveAsset(super.operationId,super.id,super.expectedRevision,this.name,this.currency);
  final String name,currency;
  @override Map<String,Object?> get payload=>{...target,'action':'asset.save','name':name.trim(),'currency':currency};
}
class SaveInvestmentEntry extends OfflineAction {
  const SaveInvestmentEntry(super.operationId,super.id,super.expectedRevision,{required this.assetId,required this.kind,required this.cashMinor,required this.date,this.quantityMicros=0,this.feeMinor=0,this.transactionId});
  final String assetId,kind;final int cashMinor,quantityMicros,feeMinor;final DateTime date;final String? transactionId;
  @override Map<String,Object?> get payload=>{...target,'action':'asset.entry','assetId':assetId,'kind':kind,'cash':cashMinor,'quantity':quantityMicros,'fee':feeMinor,'date':dateOnly(date),'transactionId':transactionId};
}

class ConfirmImport extends OfflineAction {
  const ConfirmImport(super.operationId,super.id,super.expectedRevision,{required this.contentKey,required this.rows,this.accountId});
  final String contentKey;final List<ImportedMoney> rows;final String? accountId;
  @override Map<String,Object?> get payload=>{...target,'action':'import.confirm','contentKey':contentKey,'rows':rows.map((r)=>r.toJson()).toList(),'accountId':accountId};
}
class ReverseImport extends OfflineAction {
  const ReverseImport(super.operationId,super.id,super.expectedRevision);
  @override Map<String,Object?> get payload=>{...target,'action':'import.reverse'};
}

class SaveProject extends OfflineAction {
  const SaveProject(super.operationId,super.id,super.expectedRevision,{required this.name,this.goal='',this.status='active',this.dueOn,this.budgetId});
  final String name,goal,status;final DateTime? dueOn;final String? budgetId;
  @override Map<String,Object?> get payload=>{...target,'action':'project.save','name':name.trim(),'goal':goal.trim(),'status':status,'due':dueOn==null?null:dateOnly(dueOn!),'budget':budgetId};
}
class SaveMilestone extends OfflineAction {
  const SaveMilestone(super.operationId,super.id,super.expectedRevision,{required this.projectId,required this.name,this.dueOn,this.completed=false});
  final String projectId,name;final DateTime? dueOn;final bool completed;
  @override Map<String,Object?> get payload=>{...target,'action':'milestone.save','project':projectId,'name':name.trim(),'due':dueOn==null?null:dateOnly(dueOn!),'completed':completed};
}
class SetTaskPlacement extends OfflineAction {
  const SetTaskPlacement(super.operationId,super.id,super.expectedRevision,{required this.taskId,this.projectId,this.parentTaskId,this.priority=0});
  final String taskId;final String? projectId,parentTaskId;final int priority;
  @override Map<String,Object?> get payload=>{...target,'action':'task.place','task':taskId,'project':projectId,'parent':parentTaskId,'priority':priority};
}
class SaveHabit extends OfflineAction {
  const SaveHabit(super.operationId,super.id,super.expectedRevision,{required this.name,required this.schedule,this.paused=false});
  final String name;final ScheduleSpec schedule;final bool paused;
  @override Map<String,Object?> get payload=>{...target,'action':'habit.save','name':name.trim(),'schedule':schedule.toJson(),'paused':paused};
}
class CheckHabit extends OfflineAction {
  const CheckHabit(super.operationId,super.id,super.expectedRevision,{required this.habitId,required this.localDate,required this.timezone,this.completed=true});
  final String habitId,localDate,timezone;final bool completed;
  @override Map<String,Object?> get payload=>{...target,'action':'habit.check','habit':habitId,'date':localDate,'timezone':timezone,'completed':completed};
}
class SaveSubject extends OfflineAction {
  const SaveSubject(super.operationId,super.id,super.expectedRevision,{required this.name,this.projectId});
  final String name;final String? projectId;
  @override Map<String,Object?> get payload=>{...target,'action':'subject.save','name':name.trim(),'project':projectId};
}
class SaveStudyItem extends OfflineAction {
  const SaveStudyItem(super.operationId,super.id,super.expectedRevision,{required this.subjectId,required this.name,this.taskId,this.schedule,this.completed=false});
  final String subjectId,name;final String? taskId;final ScheduleSpec? schedule;final bool completed;
  @override Map<String,Object?> get payload=>{...target,'action':'study.save','subject':subjectId,'name':name.trim(),'task':taskId,'schedule':schedule?.toJson(),'completed':completed};
}
class SaveChecklist extends OfflineAction {
  const SaveChecklist(super.operationId,super.id,super.expectedRevision,{required this.name,this.kind='shopping',this.noteId,this.projectId});
  final String name,kind;final String? noteId,projectId;
  @override Map<String,Object?> get payload=>{...target,'action':'checklist.save','name':name.trim(),'kind':kind,'note':noteId,'project':projectId};
}
class SaveChecklistItem extends OfflineAction {
  const SaveChecklistItem(super.operationId,super.id,super.expectedRevision,{required this.checklistId,required this.name,this.quantity='',this.completed=false,this.taskId});
  final String checklistId,name,quantity;final bool completed;final String? taskId;
  @override Map<String,Object?> get payload=>{...target,'action':'checklist.item','checklist':checklistId,'name':name.trim(),'quantity':quantity.trim(),'completed':completed,'task':taskId};
}
class SetNoteMetadata extends OfflineAction {
  const SetNoteMetadata(super.operationId,super.id,super.expectedRevision,{required this.noteId,required this.tags});
  final String noteId;final List<String> tags;
  @override Map<String,Object?> get payload=>{...target,'action':'note.tags','note':noteId,'tags':tags};
}
class SaveRecordLink extends OfflineAction {
  const SaveRecordLink(super.operationId,super.id,super.expectedRevision,{required this.noteId,required this.targetType,required this.targetId});
  final String noteId,targetType,targetId;
  @override Map<String,Object?> get payload=>{...target,'action':'note.link','note':noteId,'type':targetType,'target':targetId};
}
class SaveWellness extends OfflineAction {
  const SaveWellness(super.operationId,super.id,super.expectedRevision,{required this.kind,required this.localDate,required this.minutes,this.label=''});
  final String kind,localDate,label;final int minutes;
  @override Map<String,Object?> get payload=>{...target,'action':'wellness.save','kind':kind,'date':localDate,'minutes':minutes,'label':label.trim()};
}
class SaveDashboard extends OfflineAction {
  const SaveDashboard(super.operationId,super.id,super.expectedRevision,{required this.widget,required this.position,this.visible=true,this.expanded=false});
  final String widget;final int position;final bool visible,expanded;
  @override Map<String,Object?> get payload=>{...target,'action':'dashboard.save','widget':widget,'position':position,'visible':visible,'expanded':expanded};
}
