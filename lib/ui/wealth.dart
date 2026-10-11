import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../app_controller.dart';
import '../domain/models.dart';
import '../domain/wealth_engine.dart';
import 'design.dart';
import 'selection.dart';
import 'entry_sheet.dart';
import 'calendar.dart';
import 'finance_foundation.dart';
import 'money_format.dart';

String unitsText(int value) {final s=value.toString().padLeft(7,'0');return '${s.substring(0,s.length-6)}.${s.substring(s.length-6)}';}
class WealthPage extends StatefulWidget {
  const WealthPage({super.key,required this.controller,this.parent,this.initial=OfflineTable.goals});
  final AppController controller;final Map<String,Object?>? parent;final OfflineTable initial;
  @override State<WealthPage> createState()=>_WealthPageState();
}
class _WealthPageState extends State<WealthPage> {
  AppController get c=>widget.controller;
  late OfflineTable table=widget.initial;
  static const parents=[OfflineTable.goals,OfflineTable.debts,OfflineTable.assets];
  OfflineTable children(OfflineTable t)=>switch(t){OfflineTable.goals=>OfflineTable.goalEntries,OfflineTable.debts=>OfflineTable.debtEntries,_=>OfflineTable.investmentEntries};
  String summary(Map<String,Object?> row) {
    const w=WealthEngine();String money(BigInt v)=>formatMoney(Currency.fromCode((widget.parent??row)['currency'] as String),v,locale:c.region);
    return switch(table){
      OfflineTable.goals=>'${money(w.savings(row['id'] as String,c.offline[OfflineTable.goalEntries]??[]))} / ${money(BigInt.from(row['target_minor'] as int))}',
      OfflineTable.debts=>'${c.pack.t('principal_remaining')}: ${money(w.principal(row,c.offline[OfflineTable.debtEntries]??[]))}',
      OfflineTable.assets=>investmentSummary(row,money),
      OfflineTable.goalEntries=>money(BigInt.from(row['amount_minor'] as int)),
      OfflineTable.debtEntries=>'${c.pack.t('principal')}: ${money(BigInt.from(row['principal_minor'] as int))}\n${c.pack.t('interest')}: ${money(BigInt.from(row['interest_minor'] as int))} · ${c.pack.t('fee')}: ${money(BigInt.from(row['fee_minor'] as int))}',
      _=>'${c.pack.t('investment_${row['kind']}')}: ${money(BigInt.from(row['cash_minor'] as int))}',
    };
  }
  String investmentSummary(Map<String,Object?> row,String Function(BigInt) money) {
    final s=const WealthEngine().investment(row['id'] as String,c.offline[OfflineTable.investmentEntries]??[]);
    return '${c.pack.t('realized_gain')}: ${money(s.realizedMinor)}\n${c.pack.t('unrealized_gain')}: ${s.unrealizedMinor==null?c.pack.t('valuation_unknown'):money(s.unrealizedMinor!)}\n${c.pack.t('manual_estimate')}';
  }
  Future<void> edit([Map<String,Object?>? row])=>showModalBottomSheet<void>(context:context,isScrollControlled:true,useSafeArea:true,isDismissible:false,enableDrag:false,builder:(_)=>WealthEditor(controller:c,table:table,row:row,parent:widget.parent));
  @override Widget build(BuildContext context)=>ListenableBuilder(listenable:c,builder:(context,_) {
    final parentKey=switch(table){OfflineTable.goalEntries=>'goal_id',OfflineTable.debtEntries=>'debt_id',_=>'asset_id'};
    final rows=(c.offline[table]??[]).where((r)=>widget.parent==null||r[parentKey]==widget.parent!['id']).toList();
    return Scaffold(appBar:AppBar(title:Text(c.pack.t('wealth'))),body:SafeArea(child:Column(children:[
      if(widget.parent==null)Padding(padding:const EdgeInsets.all(16),child:Wrap(spacing:8,children:[for(final t in parents)ChoiceChip(label:Text(c.pack.t('module_${t.name}')),selected:table==t,onSelected:(_)=>setState(()=>table=t))])),
      Padding(padding:const EdgeInsets.symmetric(horizontal:16),child:Text(c.pack.t('wealth_link_help'))),
      Expanded(child:ListView.builder(padding:const EdgeInsets.all(16),itemCount:rows.isEmpty?1:rows.length,itemBuilder:(context,i){if(rows.isEmpty)return LifeCard(child:Text(c.pack.t('offline_empty')));final row=rows[i];return Padding(padding:const EdgeInsets.only(bottom:12),child:LifeCard(child:Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[
        ListTile(contentPadding:EdgeInsets.zero,title:Text(row['name'] as String? ?? row['occurred_on'] as String? ?? ''),subtitle:Text(summary(row)),onTap:()=>edit(row),trailing:const Icon(Icons.edit_outlined)),
        if(parents.contains(table))TextButton(onPressed:()=>Navigator.push<void>(context,MaterialPageRoute(builder:(_)=>WealthPage(controller:c,parent:row,initial:children(table)))),child:Text(c.pack.t('movements'))),
        if(!parents.contains(table))TextButton(onPressed:()async{try{await c.execute(DeleteOffline(const Uuid().v4(),row['id'] as String,row['revision'] as int,table));}catch(e){if(context.mounted)ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:Text(c.pack.t(e is DomainFailure?e.key:'change_failed'))));}},child:Text(c.pack.t('delete'))),
      ])));})),
    ])),floatingActionButton:FloatingActionButton(onPressed:()=>edit(),tooltip:c.pack.t('add'),child:const Icon(Icons.add)));
  });
}
class WealthEditor extends StatefulWidget {
  const WealthEditor({super.key,required this.controller,required this.table,this.row,this.parent});
  final AppController controller;final OfflineTable table;final Map<String,Object?>? row,parent;
  @override State<WealthEditor> createState()=>_WealthEditorState();
}
class _WealthEditorState extends State<WealthEditor> {
  AppController get c=>widget.controller;
  late final id=widget.row?['id'] as String? ?? const Uuid().v4();final operation=const Uuid().v4();
  late final name=TextEditingController(text:widget.row?['name'] as String? ?? '');
  late final currency=TextEditingController(text:(widget.parent??widget.row)?['currency'] as String? ?? c.currency);
  late final amount=TextEditingController(text:minorText((widget.row?['target_minor']??widget.row?['amount_minor']??widget.row?['principal_minor']??widget.row?['cash_minor']??0) as int,currency.text));
  late final interest=TextEditingController(text:minorText(widget.row?['interest_minor'] as int? ?? 0,currency.text));
  late final fee=TextEditingController(text:minorText(widget.row?['fee_minor'] as int? ?? 0,currency.text));
  late final quantity=TextEditingController(text:unitsText(widget.row?['quantity_micros'] as int? ?? 0));
  late String direction=widget.row?['direction'] as String? ?? 'owing',flow=widget.row?['flow'] as String? ?? 'repay',kind=widget.row?['kind'] as String? ?? 'buy';
  late String account=widget.row?['account_id'] as String? ?? '',transaction=widget.row?['transaction_id'] as String? ?? '',transfer=widget.row?['transfer_id'] as String? ?? '';
  late DateTime date=DateTime.parse(widget.row?['occurred_on'] as String? ?? dateOnly(c.now));
  late DateTime? targetOn=widget.row?['target_on']==null?null:DateTime.parse(widget.row!['target_on'] as String);
  late ScheduleSpec? schedule=c.calendar.where((e)=>e.id==widget.row?['calendar_id']).firstOrNull?.schedule;
  bool saving=false;String? error;
  @override void dispose(){for(final field in [name,currency,amount,interest,fee,quantity]){field.dispose();}super.dispose();}
  Widget field(TextEditingController value,String key,{bool number=false})=>Padding(padding:const EdgeInsets.only(bottom:12),child:TextField(controller:value,keyboardType:number?const TextInputType.numberWithOptions(decimal:true,signed:true):TextInputType.text,decoration:InputDecoration(labelText:c.pack.t(key))));
  Widget select(String key,String value,Map<String,String> choices,ValueChanged<String> changed)=>Padding(padding:const EdgeInsets.only(bottom:12),child:LifeSelect<String>(label:c.pack.t(key),value:value,choices:choices,onChanged:(v)=>setState(()=>changed(v))));
  Future<void> pick({bool target=false})async{final d=await showDatePicker(context:context,initialDate:target?targetOn??c.now:date,firstDate:DateTime(1900),lastDate:DateTime(2200,12,31));if(d!=null&&mounted)setState((){if(target)targetOn=d;else date=d;});}
  Future<void> save()async{if(saving)return;setState((){saving=true;error=null;});try{
    final rev=widget.row?['revision'] as int? ?? 0,code=Currency.fromCode(currency.text).code;
    final value=signedMinor(amount.text,code),parent=widget.parent?['id'] as String?;
    final AppAction action=switch(widget.table){
      OfflineTable.goals=>SaveGoal(operation,id,rev,name:name.text,currency:code,targetMinor:value,targetOn:targetOn,accountId:account.isEmpty?null:account),
      OfflineTable.goalEntries=>SaveGoalEntry(operation,id,rev,goalId:parent!,amountMinor:value,date:date,transactionId:transaction.isEmpty?null:transaction,transferId:transfer.isEmpty?null:transfer),
      OfflineTable.debts=>SaveDebt(operation,id,rev,name:name.text,currency:code,principalMinor:value,direction:direction,schedule:schedule),
      OfflineTable.debtEntries=>SaveDebtEntry(operation,id,rev,debtId:parent!,principalMinor:value,interestMinor:signedMinor(interest.text,code),feeMinor:signedMinor(fee.text,code),date:date,flow:flow,transactionId:transaction.isEmpty?null:transaction),
      OfflineTable.assets=>SaveAsset(operation,id,rev,name.text,code),
      OfflineTable.investmentEntries=>SaveInvestmentEntry(operation,id,rev,assetId:parent!,kind:kind,cashMinor:value,feeMinor:signedMinor(fee.text,code),quantityMicros:['buy','sell'].contains(kind)?const Currency('UNIT',6).parse(quantity.text):0,date:date,transactionId:transaction.isEmpty?null:transaction),
      _=>throw const DomainFailure('invalid_action'),
    };
    await c.execute(action);if(mounted)Navigator.pop(context);
  }catch(e){if(mounted)setState((){saving=false;error=e is DomainFailure?e.key:'save_failed';});}}
  @override Widget build(BuildContext context){final isEntry=widget.parent!=null;return EntrySheet(saving:saving,saveLabel:c.pack.t(saving?'saving':'save'),onSave:save,children:[
    Row(children:[Expanded(child:Text(c.pack.t('module_${widget.table.name}'),style:Theme.of(context).textTheme.titleLarge)),IconButton(tooltip:c.pack.t('cancel'),onPressed:()=>Navigator.pop(context),icon:const Icon(Icons.close))]),
    if(!isEntry)...[field(name,'name'),field(currency,'currency')],
    if(widget.table!=OfflineTable.assets)field(amount,widget.table==OfflineTable.goals?'target_amount':widget.table==OfflineTable.debts||widget.table==OfflineTable.debtEntries?'principal':'amount',number:true),
    if(widget.table==OfflineTable.goals)...[
      select('account',account,{'':c.pack.t('virtual_earmark'),for(final a in c.offline[OfflineTable.accounts]??[])a['id'] as String:a['name'] as String},(v)=>account=v),
      OutlinedButton(onPressed:()=>pick(target:true),child:Text(targetOn==null?c.pack.t('target_date'):MaterialLocalizations.of(context).formatMediumDate(targetOn!))),
    ],
    if(widget.table==OfflineTable.debts)...[
      select('debt_direction',direction,{'owing':c.pack.t('debt_owing'),'owed':c.pack.t('debt_owed')},(v)=>direction=v),
      ScheduleEditor(controller:c,value:schedule,onChanged:(v)=>setState(()=>schedule=v)),
    ],
    if(widget.table==OfflineTable.debtEntries)...[
      select('debt_flow',flow,{'repay':c.pack.t('repay'),'advance':c.pack.t('advance')},(v)=>flow=v),field(interest,'interest',number:true),field(fee,'fee',number:true),
    ],
    if(widget.table==OfflineTable.investmentEntries)...[
      select('kind',kind,{for(final k in ['buy','sell','dividend','distribution','valuation'])k:c.pack.t('investment_$k')},(v)=>kind=v),
      if(['buy','sell'].contains(kind))field(quantity,'quantity',number:true),field(fee,'fee',number:true),Text(c.pack.t('manual_estimate')),
    ],
    if(isEntry)...[
      OutlinedButton(onPressed:()=>pick(),child:Text(MaterialLocalizations.of(context).formatMediumDate(date))),
      Text(c.pack.t('wealth_link_help')),
      select('linked_transaction',transaction,{'':c.pack.t('unassigned'),for(final r in c.records.where((r)=>r.amountMinor!=null))r.id:'${r.date} · ${r.text} · ${r.currency!.format(r.amountMinor!)}'},(v)=>transaction=v),
      if(widget.table==OfflineTable.goalEntries)select('linked_transfer',transfer,{'':c.pack.t('unassigned'),for(final t in c.offline[OfflineTable.transfers]??[])t['id'] as String:'${t['occurred_on']} · ${t['label']}'},(v)=>transfer=v),
    ],
    if(error!=null)Text(c.pack.t(error!),style:TextStyle(color:Theme.of(context).colorScheme.error)),
  ]);}
}
