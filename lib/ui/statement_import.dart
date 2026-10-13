import 'package:flutter/foundation.dart' as background;
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../app_controller.dart';
import '../domain/models.dart';
import '../domain/statement_import.dart';
import 'selection.dart';
import 'design.dart';

class StatementImportPage extends StatefulWidget {
  const StatementImportPage({super.key,required this.controller});
  final AppController controller;
  @override State<StatementImportPage> createState()=>_StatementImportPageState();
}
class _StatementImportPageState extends State<StatementImportPage> {
  AppController get c=>widget.controller;
  final operation=const Uuid().v4(),batch=const Uuid().v4();
  Map<String,StatementTable> sheets={};StatementTable? table;
  String sourceKey='',sheet='',account='',format='iso',decimal='.',error='',encoding='utf8',delimiter='auto',direction='signed';
  late String importCurrency=c.currency;
  int date=0,amount=1,description=2,currency=-1,step=0,header=0;
  bool busy=false;List<ImportedMoney?> preview=[];List<String> errors=[];Set<int> selected={};Set<int> duplicates={};Set<int> alreadyImported={};
  @override void dispose(){sheets.clear();preview.clear();errors.clear();selected.clear();super.dispose();}
  Future<void> pick() async {
    if(busy)return;setState((){busy=true;error='';});
    try {
      final source=await c.native.pickStatement();if(source==null)return;sourceKey=source['sourceKey'] as String? ?? '';
      if(source['sheets'] is Map){sheets={for(final e in (source['sheets'] as Map).entries)e.key as String:StatementTable.checked([for(final row in e.value as List)(row as List).cast<String>()])};}
      else {
        final bytes=source['bytes'] as Uint8List;
        try{sheets={'':StatementTable.checked(await background.compute(parseStatementWorker,{'bytes':bytes,'extension':(source['name'] as String).split('.').last,'encoding':encoding,'delimiter':delimiter}))};}finally{bytes.fillRange(0,bytes.length,0);source.clear();}
      }
      sheet=sheets.keys.first;table=sheets[sheet];header=0;date=0;amount=1;description=2;currency=-1;if(mounted)setState(()=>step=1);
    }catch(e){if(mounted)setState(()=>error=e is DomainFailure?e.key:'import_format');}
    finally{if(mounted)setState(()=>busy=false);}
  }
  Future<void> review() async {
    final source=table;if(source==null)return;
    setState((){busy=true;error='';});
    preview=[];errors=[];selected={};duplicates={};alreadyImported={};
    final mapping=ImportMapping(date:date,amount:amount,description:description,currency:currency,dateFormat:format,decimal:decimal,defaultCurrency:importCurrency,direction:direction);
    final content=sourceKey.isEmpty?await importDigest(source.rows):sourceKey;final seen=<String>{};
    for(var i=header+1;i<source.rows.length;i++) {
      final position=preview.length;
      try{final money=mapping.normalize(source.rows[i]);preview.add(money.identified(await importDigest([content,sheet,i])));errors.add('');if(c.importedOrigins.contains(preview.last!.originKey)){alreadyImported.add(position);}else if(c.records.any(money.matches)||!seen.add(await importDigest(money.canonical))){duplicates.add(position);}else{selected.add(position);}}
      catch(e){preview.add(null);errors.add(c.pack.t(e is DomainFailure?e.key:'import_format'));}
    }
    if(mounted)setState((){busy=false;step=2;});
  }
  Future<void> confirm() async {
    if(busy||selected.isEmpty)return;setState((){busy=true;error='';});
    try {
      final rows=[for(final i in selected.toList()..sort())preview[i]!.identified(preview[i]!.originKey,duplicate:duplicates.contains(i))];
      final key=await importDigest({'rows':rows.map((r)=>r.toJson()).toList(),'account':account});
      await c.execute(ConfirmImport(operation,batch,0,contentKey:key,rows:rows,accountId:account.isEmpty?null:account));
      sheets.clear();table=null;preview.clear();if(mounted)Navigator.pop(context);
    }catch(e){if(mounted)setState(()=>error=e is DomainFailure?e.key:'save_failed');}
    finally{if(mounted)setState(()=>busy=false);}
  }
  Widget select<T>(String key,T value,Map<T,String> choices,ValueChanged<T> onChanged)=>Padding(padding:const EdgeInsets.only(bottom:12),child:LifeSelect<T>(label:c.pack.t(key),value:value,choices:choices,onChanged:busy?null:onChanged,searchLabel:c.pack.t('search')));
  @override Widget build(BuildContext context)=>PopScope(canPop:!busy,child:Scaffold(appBar:AppBar(title:Text(c.pack.t('import_file')),leading:step>0?IconButton(tooltip:MaterialLocalizations.of(context).backButtonTooltip,onPressed:busy?null:()=>setState((){step--;if(step==0){sheets.clear();table=null;}preview.clear();errors.clear();selected.clear();duplicates.clear();alreadyImported.clear();}),icon:const Icon(Icons.arrow_back)):null),body:SafeArea(child:Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[
    Padding(padding:const EdgeInsets.all(16),child:Text(c.pack.t('import_step_$step'),style:Theme.of(context).textTheme.titleLarge)),
    if(error.isNotEmpty)Padding(padding:const EdgeInsets.all(16),child:Text(c.pack.t(error),style:TextStyle(color:Theme.of(context).colorScheme.error))),
    Expanded(child:step==0?ListView(key:const Key('import_choose'),padding:const EdgeInsets.all(16),children:[LifeCard(child:Text(c.pack.t('import_private'))),const SizedBox(height:16),select('encoding',encoding,{'utf8':'UTF-8','utf16':'UTF-16 (BOM)','cp1251':'Windows-1251'},(v)=>setState(()=>encoding=v)),select('file_separator',delimiter,{'auto':c.pack.t('automatic'),';':';',',':',','\t':'TAB'},(v)=>setState(()=>delimiter=v)),FilledButton.icon(onPressed:busy?null:pick,icon:const Icon(Icons.file_open_outlined),label:Text(c.pack.t('choose_file'))) ]):step==1?ListView(key:const Key('import_mapping'),padding:const EdgeInsets.all(16),children:[
      if(sheets.length>1)select('sheet',sheet,{for(final k in sheets.keys)k:k},(v)=>setState((){sheet=v;table=sheets[v];header=0;})),
      select('header_row',header,{for(var i=0;i<table!.rows.length-1&&i<20;i++)i:'${i+1}: ${table!.rows[i].take(3).join(' · ')}'},(v)=>setState(()=>header=v)),
      for(final field in ['date','amount','description','currency'])select<int>(field,switch(field){'date'=>date,'amount'=>amount,'description'=>description,_=>currency},
        {if(field=='currency'||field=='description')-1:field=='currency'?importCurrency:c.pack.t('unassigned'),for(var i=0;i<table!.rows[header].length;i++)i:'${i+1}: ${table!.rows[header][i]}'},(v)=>setState((){switch(field){case 'date':date=v;case 'amount':amount=v;case 'description':description=v;default:currency=v;}})),
      if(currency<0)select('currency',importCurrency,{for(final code in {c.currency,'RUB','USD','EUR','KZT','UZS','UAH','GBP','GEL','AZN','AMD','TJS','KGS'})code:code},(v)=>setState(()=>importCurrency=v)),
      select('amount_direction',direction,{'signed':c.pack.t('sign_rules'),'expense':c.pack.t('expense'),'income':c.pack.t('income')},(v)=>setState(()=>direction=v)),
      select('date_format',format,{'iso':'YYYY-MM-DD / YYYYMMDD','dmy':'DD.MM.YYYY','mdy':'MM/DD/YYYY','excel':c.pack.t('excel_date')},(v)=>setState(()=>format=v)),
      select('decimal_separator',decimal,{'.':'1,234.56',',':'1.234,56'},(v)=>setState(()=>decimal=v)),
      select('account',account,{'':c.pack.t('unassigned'),for(final a in c.offline[OfflineTable.accounts]??[])a['id'] as String:a['name'] as String},(v)=>setState(()=>account=v)),
    ]):ListView.builder(padding:const EdgeInsets.all(16),itemCount:preview.length,itemBuilder:(context,i){final r=preview[i];return CheckboxListTile(value:selected.contains(i),onChanged:busy||r==null||alreadyImported.contains(i)?null:(v)=>setState((){if(v==true){selected.add(i);}else{selected.remove(i);}}),title:Text(r==null?'${i+header+2}: ${errors[i]}':'${c.pack.t(r.kind.name)} · ${r.date} · ${Currency.fromCode(r.currency).format(r.amountMinor)}'),subtitle:Text(r==null?'':'${r.label}${alreadyImported.contains(i)?' · ${c.pack.t('already_imported')}':''}${duplicates.contains(i)?' · ${c.pack.t('import_duplicate')}':''}'));})),
    if(step>0)Padding(padding:const EdgeInsets.all(16),child:FilledButton(onPressed:busy?null:step==1?review:selected.isEmpty?null:confirm,child:Text(busy?c.pack.t('saving'):step==1?c.pack.t('import_preview'):'${c.pack.t('import_confirm')} (${selected.length})'))),
  ]))));
}
