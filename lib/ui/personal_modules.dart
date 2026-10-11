import 'package:timezone/timezone.dart' as tz;
import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../app_controller.dart';
import '../domain/models.dart';
import '../domain/habit_progress.dart';
import 'design.dart';
import 'entry_sheet.dart';
import 'selection.dart';
import 'calendar.dart';
import 'record_detail.dart';
import 'quick_add.dart';
import 'wealth.dart';
import 'money_format.dart';

const personalModules=[OfflineTable.projects,OfflineTable.habits,OfflineTable.subjects,OfflineTable.checklists,OfflineTable.wellness];
class PersonalModulesPage extends StatefulWidget {
  const PersonalModulesPage({super.key,required this.controller,required this.table,this.parentId,this.noteId});
  final AppController controller;final OfflineTable table;final String? parentId,noteId;
  @override State<PersonalModulesPage> createState()=>_PersonalModulesPageState();
}
class _PersonalModulesPageState extends State<PersonalModulesPage> {
  AppController get c=>widget.controller;String query='';bool busy=false;int shown=50;
  String title(Map<String,Object?> row)=>row['name'] as String? ?? (widget.table==OfflineTable.memberships?(c.offline[OfflineTable.profiles]??[]).where((p)=>p['id']==row['profile_id']).firstOrNull?['name'] as String? : null) ?? row['label'] as String? ?? row['local_date'] as String? ?? row['tags'] as String? ?? c.pack.t('module_${widget.table.name}');
  Future<void> edit([Map<String,Object?>? row]) async {
    await showModalBottomSheet<void>(context:context,useSafeArea:true,isScrollControlled:true,isDismissible:false,enableDrag:false,
      builder:(_)=>PersonalModuleEditor(controller:c,table:widget.table,row:row,parentId:widget.parentId,noteId:widget.noteId));
  }
  void open(OfflineTable table,String parent) {Navigator.push<void>(context,MaterialPageRoute(builder:(_)=>PersonalModulesPage(controller:c,table:table,parentId:parent)));}
  Future<void> change(AppAction action) async {
    if(busy)return;setState(()=>busy=true);
    try{await c.execute(action);}catch(e){if(mounted)ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:Text(c.pack.t(e is DomainFailure?e.key:'change_failed'))));}
    finally{if(mounted)setState(()=>busy=false);}
  }
  Widget details(Map<String,Object?> row) {
    final id=row['id'] as String;
    switch(widget.table) {
      case OfflineTable.profiles:return Text(c.pack.t('profile_${row['kind']}'));
      case OfflineTable.memberships:return Text(c.pack.t('member_${row['role']}'));
      case OfflineTable.projects:
        final placements=(c.offline[OfflineTable.taskPlacements]??[]).where((p)=>p['project_id']==id).toList();
        final tasks=c.records.where((r)=>r.kind==EntryKind.task&&placements.any((p)=>p['task_id']==r.id)).toList();
        final actual=<String,BigInt>{};
        for(final allocation in c.allocations.where((a)=>a['project_id']==id)){final money=c.records.where((r)=>r.id==allocation['transaction_id']).firstOrNull;if(money?.currency!=null){final code=money!.currency!.code;actual[code]=(actual[code]??BigInt.zero)+BigInt.from(allocation['amount_minor'] as int);}}
        final budget=(c.offline[OfflineTable.budgets]??[]).where((b)=>b['id']==row['budget_id']).firstOrNull;
        return Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[if(budget!=null)Text('${c.pack.t('linked_budget')}: ${budget['name']} · ${formatMoney(Currency.fromCode(budget['currency'] as String),budget['limit_minor'] as int,locale:c.region)}'),for(final total in actual.entries)Text('${c.pack.t('project_actual_all_time')}: ${formatMoney(Currency.fromCode(total.key),total.value,locale:c.region)}'),Text('${tasks.where((t)=>t.completed).length}/${tasks.length} · ${c.pack.t('status_${row['status']}')}'),
          if(tasks.isNotEmpty)LinearProgressIndicator(value:tasks.where((t)=>t.completed).length/tasks.length),
          Wrap(spacing:8,children:[TextButton(onPressed:()=>open(OfflineTable.milestones,id),child:Text(c.pack.t('module_milestones'))),TextButton(onPressed:()=>open(OfflineTable.taskPlacements,id),child:Text(c.pack.t('project_tasks')))]),
        ]);
      case OfflineTable.habits:
        final spec=storedSchedule(row);final checks=(c.offline[OfflineTable.habitChecks]??[]).where((h)=>h['habit_id']==id).toList();
        final date=dateOnly(spec==null||spec.timezone=='device'?DateTime.now():tz.TZDateTime.now(tz.getLocation(spec.timezone))),today=checks.where((h)=>h['local_date']==date).firstOrNull;
        final streak=spec==null?0:habitStreak(CalendarEntry(id:id,title:title(row),schedule:spec),c.now,c.deviceZone,checks,pauses:[for(final p in row['__pauses'] as List? ?? [])Map<String,Object?>.from(p as Map)]);
        return Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[Text(row['paused']==1?c.pack.t('status_paused'):'${c.pack.t('habit_streak')}: $streak'),
          CheckboxListTile(contentPadding:EdgeInsets.zero,title:Text(c.pack.t('check_today')),value:today?['completed']==1,onChanged:busy||row['paused']==1?null:(v)=>change(CheckHabit(const Uuid().v4(),today?['id'] as String? ?? const Uuid().v4(),today?['revision'] as int? ?? 0,habitId:id,localDate:date,timezone:spec==null||spec.timezone=='device'?c.deviceZone:spec.timezone,completed:v==true))),
          TextButton(onPressed:()=>open(OfflineTable.habitChecks,id),child:Text(c.pack.t('check_history')))]);
      case OfflineTable.subjects:return TextButton(onPressed:()=>open(OfflineTable.studyItems,id),child:Text(c.pack.t('module_studyItems')));
      case OfflineTable.checklists:return Wrap(spacing:8,children:[TextButton(onPressed:()=>open(OfflineTable.checklistItems,id),child:Text(c.pack.t('module_checklistItems'))),if(row['kind']=='chores')TextButton(onPressed:busy?null:()=>change(CopyChecklist(const Uuid().v4(),const Uuid().v4(),0,sourceId:id,sourceRevision:row['revision'] as int,name:'${row['name']} · ${c.pack.t('new_copy')}')),child:Text(c.pack.t('use_template')))]);
      case OfflineTable.checklistItems:
        final linked=c.records.where((r)=>r.id==row['task_id']).firstOrNull;
        return CheckboxListTile(contentPadding:EdgeInsets.zero,title:Text(row['quantity'] as String),value:linked?.completed??row['completed']==1,onChanged:busy?null:(v)=>change(linked==null?SaveChecklistItem(const Uuid().v4(),id,row['revision'] as int,checklistId:row['checklist_id'] as String,name:row['name'] as String,quantity:row['quantity'] as String,completed:v==true,taskId:row['task_id'] as String?):CompleteTask(const Uuid().v4(),linked.id,v==true,expectedRevision:linked.revision)));
      case OfflineTable.taskPlacements:
        final task=c.records.where((r)=>r.id==row['task_id']).firstOrNull;
        return task==null?Text(c.pack.t('record_missing')):ListTile(contentPadding:EdgeInsets.zero,title:Text(task.text),leading:Checkbox(value:task.completed,onChanged:busy?null:(v)=>change(CompleteTask(const Uuid().v4(),task.id,v==true,expectedRevision:task.revision))),onTap:()=>Navigator.push<void>(context,MaterialPageRoute(builder:(_)=>RecordDetail(controller:c,id:task.id))));
      case OfflineTable.wellness:return Text('${c.pack.t('wellness_${row['kind']}')} · ${row['minutes']} ${c.pack.t('minutes')}');
      case OfflineTable.recordLinks:
        final target=row['target_id'] as String;final type=row['target_type'];
        return TextButton(onPressed:()=>type=='task'||type=='note'?Navigator.push<void>(context,MaterialPageRoute(builder:(_)=>RecordDetail(controller:c,id:target))):type=='project'?open(OfflineTable.projects,target):Navigator.push<void>(context,MaterialPageRoute(builder:(_)=>WealthPage(controller:c))),child:Text(c.pack.t('open_link')));
      default:return Text('${row['due_on']??row['local_date']??''} ${row['quantity']??''}');
    }
  }
  @override Widget build(BuildContext context)=>ListenableBuilder(listenable:c,builder:(context,_) {
    final foreign=switch(widget.table){OfflineTable.milestones||OfflineTable.taskPlacements=>'project_id',OfflineTable.habitChecks=>'habit_id',OfflineTable.studyItems=>'subject_id',OfflineTable.checklistItems=>'checklist_id',_=>null};
    final rows=(c.offline[widget.table]??[]).where((r)=>(widget.parentId==null||(foreign==null?r['id']==widget.parentId:r[foreign]==widget.parentId))&&(widget.noteId==null||r['note_id']==widget.noteId)&&title(r).toLowerCase().contains(query.toLowerCase())).toList();
    return Scaffold(appBar:AppBar(title:Text(c.pack.t('module_${widget.table.name}'))),body:SafeArea(child:Column(children:[
      Padding(padding:const EdgeInsets.all(16),child:TextField(decoration:InputDecoration(labelText:c.pack.t('search'),prefixIcon:const Icon(Icons.search)),onChanged:(v)=>setState((){query=v;shown=50;}))),
      if(widget.table==OfflineTable.taskPlacements) TextButton.icon(onPressed:()=>showEntryEditor(context,c,EntryKind.task),icon:const Icon(Icons.add),label:Text(c.pack.t('create_task'))),
      Expanded(child:ListView.builder(padding:const EdgeInsets.all(16),itemCount:rows.isEmpty?1:(rows.length<shown?rows.length:shown)+(rows.length>shown?1:0),itemBuilder:(context,index) {
        if(rows.isEmpty)return LifeCard(child:Text(c.pack.t('offline_empty')));
        if(index==shown)return TextButton(onPressed:()=>setState(()=>shown+=50),child:Text(c.pack.t('load_more')));
        final row=rows[index];return Padding(padding:const EdgeInsets.only(bottom:12),child:LifeCard(child:Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[
          ListTile(contentPadding:EdgeInsets.zero,title:Text(title(row)),trailing:const Icon(Icons.edit_outlined),onTap:row['role']=='owner'?null:()=>edit(row)),details(row),
          if(![OfflineTable.profiles,OfflineTable.memberships,OfflineTable.habitChecks].contains(widget.table))TextButton.icon(onPressed:busy?null:() async {final yes=await showDialog<bool>(context:context,builder:(context)=>AlertDialog(title:Text(c.pack.t('delete')),content:Text(c.pack.t('delete_confirm')),actions:[TextButton(onPressed:()=>Navigator.pop(context,false),child:Text(c.pack.t('cancel'))),FilledButton(onPressed:()=>Navigator.pop(context,true),child:Text(c.pack.t('delete')))]));if(yes==true)await change(DeleteOffline(const Uuid().v4(),row['id'] as String,row['revision'] as int,widget.table));},icon:const Icon(Icons.delete_outline),label:Text(c.pack.t('delete'))),
        ])));
      })),
    ])),floatingActionButton:FloatingActionButton(onPressed:busy?null:()=>edit(),tooltip:c.pack.t('add'),child:const Icon(Icons.add)));
  });
}
class PersonalModuleEditor extends StatefulWidget {
  const PersonalModuleEditor({super.key,required this.controller,required this.table,this.row,this.parentId,this.noteId});
  final AppController controller;final OfflineTable table;final Map<String,Object?>? row;final String? parentId,noteId;
  @override State<PersonalModuleEditor> createState()=>_PersonalModuleEditorState();
}
class _PersonalModuleEditorState extends State<PersonalModuleEditor> {
  AppController get c=>widget.controller;OfflineTable get table=>widget.table;
  late final id=widget.row?['id'] as String? ?? const Uuid().v4();final operation=const Uuid().v4();
  late final name=TextEditingController(text:widget.row?['name'] as String? ?? widget.row?['label'] as String? ?? '');
  late final detail=TextEditingController(text:widget.row?['goal'] as String? ?? widget.row?['quantity'] as String? ?? widget.row?['tags'] as String? ?? '');
  late final minutes=TextEditingController(text:'${widget.row?['minutes']??30}');
  late String guardian=widget.row?['guardian_id'] as String? ?? '',profile=widget.row?['profile_id'] as String? ?? '',role=widget.row?['role'] as String? ?? 'viewer';
  late bool archived=widget.row?['archived']==1;
  late String project=widget.row?['project_id'] as String? ?? (table==OfflineTable.milestones||table==OfflineTable.taskPlacements?widget.parentId??'':''),
    parent=widget.row?['parent_task_id'] as String? ?? '',task=widget.row?['task_id'] as String? ?? '',
    note=widget.row?['note_id'] as String? ?? widget.noteId??'',budget=widget.row?['budget_id'] as String? ?? '',
    kind=widget.row?['kind'] as String? ?? (table==OfflineTable.wellness?'activity':table==OfflineTable.profiles?'adult':'shopping'),status=widget.row?['status'] as String? ?? 'active',
    targetType=widget.row?['target_type'] as String? ?? 'task',target=widget.row?['target_id'] as String? ?? '';
  late int priority=widget.row?['priority'] as int? ?? 0;
  late bool completed=widget.row?['completed']==1,paused=widget.row?['paused']==1;
  late DateTime date=DateTime.parse(widget.row?['local_date'] as String? ?? dateOnly(c.now));
  late DateTime? due=widget.row?['due_on']==null?null:DateTime.parse(widget.row!['due_on'] as String);
  late ScheduleSpec? schedule=storedSchedule(widget.row)??(table==OfflineTable.habits?ScheduleSpec(localStart:'${dateOnly(c.now)}T09:00:00',timezone:c.timezone,repeat:RepeatRule.daily):null);
  bool saving=false;String? error;
  @override void dispose(){name.dispose();detail.dispose();minutes.dispose();super.dispose();}
  Map<String,String> choices(OfflineTable table)=>{'':c.pack.t('unassigned'),for(final row in c.offline[table]??[])row['id'] as String:row['name'] as String? ?? ''};
  Map<String,String> records(EntryKind kind)=>{'':c.pack.t('unassigned'),for(final r in c.records)if(r.kind==kind)r.id:r.text.split('\n').first};
  Widget select<T>(String key,T value,Map<T,String> options,ValueChanged<T> changed)=>Padding(padding:const EdgeInsets.only(bottom:12),child:LifeSelect<T>(label:c.pack.t(key),value:value,choices:options,onChanged:(v)=>setState(()=>changed(v)),searchLabel:c.pack.t('search')));
  Widget input(TextEditingController controller,String key)=>Padding(padding:const EdgeInsets.only(bottom:12),child:TextField(controller:controller,decoration:InputDecoration(labelText:c.pack.t(key))));
  Widget pick(bool optional)=>Row(children:[Expanded(child:OutlinedButton.icon(onPressed:() async {final value=await showDatePicker(context:context,initialDate:optional?due??c.now:date,firstDate:DateTime(1900),lastDate:DateTime(2200,12,31));if(value!=null&&mounted)setState((){if(optional){due=value;}else{date=value;}});},icon:const Icon(Icons.calendar_today),label:Text(optional?due==null?c.pack.t('no_date'):MaterialLocalizations.of(context).formatMediumDate(due!):MaterialLocalizations.of(context).formatMediumDate(date)))),if(optional&&due!=null)IconButton(tooltip:c.pack.t('clear'),onPressed:()=>setState(()=>due=null),icon:const Icon(Icons.close))]);
  Future<void> save() async {
    if(saving)return;setState((){saving=true;error=null;});
    try {
      final rev=widget.row?['revision'] as int? ?? 0;
      String? optional(String text)=>text.isEmpty?null:text;
      final action=switch(table) {
        OfflineTable.profiles=>SaveProfile(operation,id,rev,name:name.text,kind:kind,guardianId:kind=='adult'?null:optional(guardian),archived:archived),
        OfflineTable.memberships=>SaveMembership(operation,id,rev,profileId:profile,role:role,permissions:switch(role){'viewer'=>1,'contributor'=>3,_=>7}),
        OfflineTable.projects=>SaveProject(operation,id,rev,name:name.text,goal:detail.text,status:status,dueOn:due,budgetId:optional(budget)),
        OfflineTable.milestones=>SaveMilestone(operation,id,rev,projectId:project,name:name.text,dueOn:due,completed:completed),
        OfflineTable.taskPlacements=>SetTaskPlacement(operation,id,rev,taskId:task,projectId:optional(project),parentTaskId:optional(parent),priority:priority),
        OfflineTable.habits=>SaveHabit(operation,id,rev,name:name.text,schedule:schedule!,paused:paused),
        OfflineTable.habitChecks=>CheckHabit(operation,id,rev,habitId:widget.row?['habit_id'] as String? ?? widget.parentId!,localDate:dateOnly(date),timezone:c.timezone=='device'?c.deviceZone:c.timezone,completed:completed),
        OfflineTable.subjects=>SaveSubject(operation,id,rev,name:name.text,projectId:optional(project)),
        OfflineTable.studyItems=>SaveStudyItem(operation,id,rev,subjectId:widget.row?['subject_id'] as String? ?? widget.parentId!,name:name.text,taskId:optional(task),schedule:schedule,completed:completed),
        OfflineTable.checklists=>SaveChecklist(operation,id,rev,name:name.text,kind:kind,noteId:optional(note),projectId:optional(project)),
        OfflineTable.checklistItems=>SaveChecklistItem(operation,id,rev,checklistId:widget.row?['checklist_id'] as String? ?? widget.parentId!,name:name.text,quantity:detail.text,completed:completed,taskId:optional(task)),
        OfflineTable.noteMetadata=>SetNoteMetadata(operation,id,rev,noteId:note,tags:detail.text.split(',').map((t)=>t.trim()).where((t)=>t.isNotEmpty).toList()),
        OfflineTable.recordLinks=>SaveRecordLink(operation,id,rev,noteId:note,targetType:targetType,targetId:target),
        OfflineTable.wellness=>SaveWellness(operation,id,rev,kind:kind,localDate:dateOnly(date),minutes:int.parse(minutes.text),label:name.text),
        _=>throw const DomainFailure('invalid_action'),
      };
      await c.execute(action);if(mounted)Navigator.pop(context);
    }catch(e){if(mounted)setState((){saving=false;error=e is DomainFailure?e.key:'save_failed';});}
  }
  @override Widget build(BuildContext context)=>EntrySheet(saving:saving,saveLabel:c.pack.t(saving?'saving':'save'),onSave:save,children:[
    Row(children:[Expanded(child:Text(c.pack.t('module_${table.name}'),style:Theme.of(context).textTheme.titleLarge)),IconButton(tooltip:c.pack.t('cancel'),onPressed:saving?null:()=>Navigator.pop(context),icon:const Icon(Icons.close))]),
    if(![OfflineTable.taskPlacements,OfflineTable.habitChecks,OfflineTable.noteMetadata,OfflineTable.recordLinks,OfflineTable.memberships].contains(table))input(name,'name'),
    if(table==OfflineTable.profiles)...[Text(c.pack.t('profiles_local_only')),select('kind',kind,{'adult':c.pack.t('profile_adult'),'child':c.pack.t('profile_child')},(v)=>kind=v),if(kind=='child')select('guardian',guardian,{'':c.pack.t('unassigned'),for(final p in c.offline[OfflineTable.profiles]??[])if(p['kind']=='adult'&&p['archived']==0&&p['id']!=id)p['id'] as String:p['name'] as String},(v)=>guardian=v),SwitchListTile(title:Text(c.pack.t('archived')),value:archived,onChanged:(v)=>setState(()=>archived=v))],
    if(table==OfflineTable.memberships)...[Text(c.pack.t('membership_metadata')),select('local_profile',profile,choices(OfflineTable.profiles),(v)=>profile=v),select('role',role,{for(final r in ['viewer','contributor','manager'])r:c.pack.t('member_$r')},(v)=>role=v)],
    if(table==OfflineTable.projects)...[input(detail,'project_goal'),select('status',status,{for(final k in ['active','paused','done'])k:c.pack.t('status_$k')},(v)=>status=v),pick(true),select('module_budgets',budget,choices(OfflineTable.budgets),(v)=>budget=v)],
    if([OfflineTable.milestones,OfflineTable.taskPlacements,OfflineTable.subjects,OfflineTable.checklists].contains(table))select('module_projects',project,choices(OfflineTable.projects),(v)=>project=v),
    if(table==OfflineTable.milestones)pick(true),
    if(table==OfflineTable.taskPlacements)...[select('task',task,records(EntryKind.task),(v)=>task=v),select('parent_task',parent,{for(final e in records(EntryKind.task).entries)if(e.key!=task)e.key:e.value},(v)=>parent=v),select('priority',priority,{for(var i=0;i<=3;i++)i:c.pack.t('priority_$i')},(v)=>priority=v)],
    if(table==OfflineTable.habits)...[ScheduleEditor(controller:c,value:schedule,optional:false,onChanged:(v)=>setState(()=>schedule=v)),SwitchListTile(title:Text(c.pack.t('pause_habit')),value:paused,onChanged:(v)=>setState(()=>paused=v))],
    if([OfflineTable.milestones,OfflineTable.habitChecks,OfflineTable.studyItems,OfflineTable.checklistItems].contains(table))SwitchListTile(title:Text(c.pack.t('completed')),value:completed,onChanged:(v)=>setState(()=>completed=v)),
    if(table==OfflineTable.habitChecks)pick(false),
    if([OfflineTable.studyItems,OfflineTable.checklistItems].contains(table))select('linked_task',task,records(EntryKind.task),(v){task=v;if(v.isNotEmpty)schedule=null;}),
    if(table==OfflineTable.studyItems&&task.isEmpty)ScheduleEditor(controller:c,value:schedule,optional:true,onChanged:(v)=>setState(()=>schedule=v)),
    if(table==OfflineTable.checklists)...[select('kind',kind,{for(final k in ['note','shopping','chores'])k:c.pack.t('checklist_$k')},(v)=>kind=v),select('note',note,records(EntryKind.note),(v)=>note=v)],
    if(table==OfflineTable.checklistItems)input(detail,'quantity'),
    if(table==OfflineTable.noteMetadata)...[if(widget.noteId==null)select('note',note,records(EntryKind.note),(v)=>note=v),input(detail,'tags')],
    if(table==OfflineTable.recordLinks)...[if(widget.noteId==null)select('note',note,records(EntryKind.note),(v)=>note=v),select('link_type',targetType,{for(final k in ['task','note','project','goal'])k:c.pack.t(k=='project'?'module_projects':k=='goal'?'module_goals':k)},(v){targetType=v;target='';}),select('linked_record',target,targetType=='task'||targetType=='note'?records(targetType=='task'?EntryKind.task:EntryKind.note):choices(targetType=='project'?OfflineTable.projects:OfflineTable.goals),(v)=>target=v)],
    if(table==OfflineTable.wellness)...[select('kind',kind,{'activity':c.pack.t('wellness_activity'),'sleep':c.pack.t('wellness_sleep')},(v)=>kind=v),pick(false),TextField(controller:minutes,keyboardType:TextInputType.number,decoration:InputDecoration(labelText:c.pack.t('minutes'))),Text(c.pack.t('wellness_nonmedical'))],
    if(error!=null)Text(c.pack.t(error!),style:TextStyle(color:Theme.of(context).colorScheme.error)),
  ]);
}
