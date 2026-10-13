import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/app.dart';
import 'package:lifeos/ui/personal_modules.dart';
import 'package:lifeos/ui/finance_foundation.dart';
import 'visual_snapshot_test.dart' show SnapshotStore,sampleRecords;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();timezone.initializeTimeZones();
  late PackCatalog catalog;
  setUpAll(() async {
    final bytes=await File('test/fonts/NotoSans-Regular.ttf').readAsBytes();
    await (FontLoader('Roboto')..addFont(Future.value(ByteData.sublistView(bytes)))).load();
    await (FontLoader('MaterialIcons')..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
    catalog=await PackCatalog.load();
  });
  for(final width in [320,390,430]) {
    for(final theme in ['light','dark']) {
      for(final populated in [false,true]) {
        for(final screen in ['projects','habits','subjects','checklists','wellness','profile','finance']) {
          testWidgets('recovery_${screen}_${populated?'active':'empty'}_${theme}_$width', (tester) async {
            tester.view.devicePixelRatio=1;tester.view.physicalSize=Size(width.toDouble(),844);
            addTearDown(tester.view.resetPhysicalSize);addTearDown(tester.view.resetDevicePixelRatio);
            final c=AppController(SnapshotStore(populated?sampleRecords():[],theme),catalog,'ru');await c.load();
            if(populated) {
              c.offline[OfflineTable.projects]=[{'id':'project','name':'Ремонт кухни','goal':'Удобное пространство','status':'active','revision':2}];
              c.offline[OfflineTable.habits]=[{'id':'habit','name':'Прогулка','paused':0,'revision':1}];
              c.offline[OfflineTable.subjects]=[{'id':'subject','name':'Математика','revision':1}];
              c.offline[OfflineTable.studyItems]=[{'id':'study','subject_id':'subject','name':'Подготовиться к экзамену','completed':0,'revision':1}];
              c.offline[OfflineTable.checklists]=[{'id':'list','name':'Покупки на неделю','kind':'shopping','revision':2}];
              c.offline[OfflineTable.checklistItems]=[{'id':'item','checklist_id':'list','name':'Молоко','quantity':'1 л','completed':0,'task_id':null,'revision':3}];
              c.offline[OfflineTable.wellness]=[{'id':'activity','label':'Прогулка вечером','kind':'activity','minutes':30,'local_date':'2026-10-12','revision':1}];
              c.offline[OfflineTable.accounts]=[{'id':'account','name':'Наличные','kind':'cash','currency':'RUB','opening_minor':12250000,'revision':1}];
            }
            await tester.pumpWidget(LifeOSApp(controller:c,builder:(context,child)=>MediaQuery(data:MediaQuery.of(context).copyWith(textScaler:const TextScaler.linear(2),disableAnimations:true),child:child!)));
            await tester.pumpAndSettle();
            final context=tester.element(find.byType(HomeShell));
            if(screen=='profile') {
              await tester.tap(find.byKey(const Key('profile_button')));
            } else if(screen=='finance') {
              Navigator.push<void>(context,MaterialPageRoute(builder:(_)=>FinanceFoundation(controller:c)));
            } else {
              final table=personalModules.singleWhere((t)=>t.name==screen);
              Navigator.push<void>(context,MaterialPageRoute(builder:(_)=>PersonalModulesPage(controller:c,table:table)));
            }
            await tester.pumpAndSettle();expect(tester.takeException(),isNull);
            await expectLater(find.byType(MaterialApp),matchesGoldenFile('goldens/recovery_${screen}_${populated?'active':'empty'}_${theme}_$width.png'));
            expect(tester.takeException(),isNull);
            await tester.pumpWidget(const SizedBox.shrink());await tester.pumpAndSettle();c.dispose();
          });
        }
      }
    }
  }
}
