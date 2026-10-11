import 'package:flutter/material.dart';
import '../app_controller.dart';
import '../domain/models.dart';
import 'personal_modules.dart';
import 'finance_foundation.dart';
import 'wealth.dart';

(OfflineTable,Map<String,Object?>)? calendarModule(AppController c,String id) {
  for(final t in [OfflineTable.habits,OfflineTable.studyItems,OfflineTable.debts,OfflineTable.plannedPayments]) {
    final row=c.offline[t]?.where((r)=>r['calendar_id']==id).firstOrNull;
    if(row!=null)return (t,row);
  }
  return null;
}
Future<void> openModuleCalendar(BuildContext context,AppController c,(OfflineTable,Map<String,Object?>) module)=>showModalBottomSheet<void>(context:context,useSafeArea:true,isScrollControlled:true,isDismissible:false,enableDrag:false,builder:(_)=>switch(module.$1){
  OfflineTable.plannedPayments=>FinanceEditor(controller:c,table:module.$1,row:module.$2),
  OfflineTable.debts=>WealthEditor(controller:c,table:module.$1,row:module.$2),
  _=>PersonalModuleEditor(controller:c,table:module.$1,row:module.$2),
});
