import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../app_controller.dart';
import '../domain/models.dart';
import 'design.dart';

const dashboardWidgets=['financial','tasks','notes','projects','habits','shopping'];
Map<String,Object?> dashboardChoice(AppController c,String key) => c.offline[OfflineTable.dashboard]?.where((r)=>r['widget']==key).firstOrNull ?? {'widget':key,'visible':dashboardWidgets.indexOf(key)<3?1:0,'expanded':1,'position':dashboardWidgets.indexOf(key)*10+10};
class DashboardEditor extends StatefulWidget {
  const DashboardEditor({super.key,required this.controller});final AppController controller;
  @override State<DashboardEditor> createState()=>_DashboardEditorState();
}
class _DashboardEditorState extends State<DashboardEditor> {
  AppController get c=>widget.controller;bool busy=false;
  Future<void> save(Map<String,Object?> row,{bool? visible,bool? expanded,int? position}) async {
    if(busy)return;setState(()=>busy=true);
    try{await c.execute(SaveDashboard(const Uuid().v4(),row['id'] as String? ?? const Uuid().v4(),row['revision'] as int? ?? 0,widget:row['widget'] as String,position:position??row['position'] as int,visible:visible??row['visible']==1,expanded:expanded??row['expanded']==1));}
    catch(e){if(mounted)ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:Text(c.pack.t(e is DomainFailure?e.key:'change_failed'))));}
    finally{if(mounted)setState(()=>busy=false);}
  }
  @override Widget build(BuildContext context)=>ListenableBuilder(listenable:c,builder:(context,_) {
    final rows=[for(final w in dashboardWidgets)dashboardChoice(c,w)]..sort((a,b){final v=(a['position'] as int).compareTo(b['position'] as int);return v==0?(a['widget'] as String).compareTo(b['widget'] as String):v;});
    return Scaffold(appBar:AppBar(title:Text(c.pack.t('dashboard_customize'))),body:SafeArea(child:ListView.builder(padding:const EdgeInsets.all(16),itemCount:rows.length,itemBuilder:(context,index){final row=rows[index];return Padding(padding:const EdgeInsets.only(bottom:12),child:LifeCard(child:Column(children:[
      SwitchListTile(title:Text(c.pack.t('widget_${row['widget']}')),value:row['visible']==1,onChanged:busy?null:(v)=>save(row,visible:v)),
      SwitchListTile(title:Text(c.pack.t('expanded_view')),value:row['expanded']==1,onChanged:busy?null:(v)=>save(row,expanded:v)),
      Row(mainAxisAlignment:MainAxisAlignment.end,children:[IconButton(tooltip:c.pack.t('move_up'),onPressed:busy||index==0||rows[index-1]['position']==0?null:()=>save(row,position:(rows[index-1]['position'] as int)-1),icon:const Icon(Icons.arrow_upward)),IconButton(tooltip:c.pack.t('move_down'),onPressed:busy||index==rows.length-1||rows[index+1]['position']==100?null:()=>save(row,position:(rows[index+1]['position'] as int)+1),icon:const Icon(Icons.arrow_downward))]),
    ])));})));
  });
}
