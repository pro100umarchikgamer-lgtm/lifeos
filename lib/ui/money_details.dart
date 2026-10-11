import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../app_controller.dart';
import '../domain/models.dart';
import 'entry_sheet.dart';
import 'selection.dart';
import 'finance_foundation.dart';

class MoneyDetails extends StatefulWidget {
  const MoneyDetails({super.key,required this.controller,required this.record});
  final AppController controller;
  final Record record;
  @override State<MoneyDetails> createState()=>_MoneyDetailsState();
}
class _MoneyDetailsState extends State<MoneyDetails> {
  AppController get c=>widget.controller;
  late String account=widget.record.accountId??'',category=widget.record.categoryId??'';
  final operation=const Uuid().v4();
  late final amounts=<TextEditingController>[], ids=<String>[], categories=<String>[];
  late final projects=<String?>[], profiles=<String?>[];
  bool saving=false;String? error;
  @override void initState(){super.initState();for(final s in c.allocations.where((s)=>s['transaction_id']==widget.record.id)){
    ids.add(s['id'] as String);amounts.add(TextEditingController(text:minorText(s['amount_minor'] as int,widget.record.currency!.code)));
    categories.add(s['category_id'] as String? ?? '');projects.add(s['project_id'] as String?);profiles.add(s['profile_id'] as String?);
  }}
  @override void dispose(){for(final c in amounts){c.dispose();}super.dispose();}
  Map<String,String> choices(OfflineTable table)=>{'':c.pack.t('unassigned'),for(final row in c.offline[table]??[])row['id'] as String:row['name'] as String? ?? ''};
  Future<void> save() async {if(saving)return;setState((){saving=true;error=null;});try{
    await c.execute(SetMoneyDetails(operation,widget.record.id,widget.record.revision,accountId:account.isEmpty?null:account,categoryId:category.isEmpty?null:category,
      splits:[for(var i=0;i<ids.length;i++)ExpenseSplit(ids[i],widget.record.currency!.parse(amounts[i].text),categoryId:categories[i].isEmpty?null:categories[i],projectId:projects[i],profileId:profiles[i])]));
    if(mounted)Navigator.pop(context);
  }catch(e){if(mounted)setState((){saving=false;error=e is DomainFailure?e.key:'save_failed';});}}
  @override Widget build(BuildContext context)=>EntrySheet(saving:saving,saveLabel:c.pack.t(saving?'saving':'save'),onSave:save,children:[
    Text(c.pack.t('account_and_splits'),style:Theme.of(context).textTheme.titleLarge),const SizedBox(height:16),
    LifeSelect<String>(label:c.pack.t('account'),value:account,choices:choices(OfflineTable.accounts),onChanged:(v)=>setState(()=>account=v)),const SizedBox(height:12),
    LifeSelect<String>(label:c.pack.t('category'),value:category,choices:choices(OfflineTable.categories),onChanged:(v)=>setState(()=>category=v)),const SizedBox(height:12),
    if(widget.record.kind==EntryKind.expense)...[
      Text(c.pack.t('split_help')),
      for(var i=0;i<ids.length;i++)Padding(padding:const EdgeInsets.symmetric(vertical:12),child:Column(children:[
        TextField(controller:amounts[i],keyboardType:const TextInputType.numberWithOptions(decimal:true),decoration:InputDecoration(labelText:c.pack.t('amount'))),const SizedBox(height:8),
        LifeSelect<String>(label:c.pack.t('category'),value:categories[i],choices:choices(OfflineTable.categories),onChanged:(v)=>setState(()=>categories[i]=v)),
        const SizedBox(height:8),LifeSelect<String>(label:c.pack.t('module_projects'),value:projects[i]??'',choices:choices(OfflineTable.projects),onChanged:(v)=>setState(()=>projects[i]=v.isEmpty?null:v)),
        const SizedBox(height:8),LifeSelect<String>(label:c.pack.t('module_profiles'),value:profiles[i]??'',choices:choices(OfflineTable.profiles),onChanged:(v)=>setState(()=>profiles[i]=v.isEmpty?null:v)),
        TextButton(onPressed:()=>setState((){amounts.removeAt(i).dispose();ids.removeAt(i);categories.removeAt(i);projects.removeAt(i);profiles.removeAt(i);}),child:Text(c.pack.t('delete'))),
      ])),
      TextButton.icon(onPressed:()=>setState((){ids.add(const Uuid().v4());amounts.add(TextEditingController());categories.add('');projects.add(null);profiles.add(null);}),icon:const Icon(Icons.add),label:Text(c.pack.t('add_split'))),
    ],
    if(error!=null)Text(c.pack.t(error!),style:TextStyle(color:Theme.of(context).colorScheme.error)),
  ]);
}
