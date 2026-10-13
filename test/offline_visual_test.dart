import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/platform/native_bridge.dart';
import 'package:lifeos/ui/app.dart';
import 'package:lifeos/ui/personal_modules.dart';
import 'package:lifeos/ui/finance_foundation.dart';
import 'package:lifeos/ui/statement_import.dart';
import 'package:lifeos/ui/calendar.dart';
import 'package:lifeos/ui/settings.dart';
import 'visual_snapshot_test.dart' show SnapshotStore,sampleRecords;

// Fixture data exists only in tests; no sample transactions enter production storage.
class ImportFixtureBridge extends NativeBridge {
  @override bool get supported=>false;
  @override Future<Map<String,Object?>?> pickStatement()async=>{'name':'fixture.csv','bytes':Uint8List.fromList(utf8.encode('date;amount;description\n2026-10-11;-12.50;Покупка продуктов'))};
}
void main(){
  TestWidgetsFlutterBinding.ensureInitialized();timezone.initializeTimeZones();
  late PackCatalog catalog;
  setUpAll(()async{
    final bytes=await File('test/fonts/NotoSans-Regular.ttf').readAsBytes();
    await (FontLoader('Roboto')..addFont(Future.value(ByteData.sublistView(bytes)))).load();
    await (FontLoader('MaterialIcons')..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
    catalog=await PackCatalog.load();
  });
  for(final width in [320,390,430]){for(final theme in ['light','dark']){for(final screen in ['finance','projects','habit','import','permissions','repeat']){
    testWidgets('offline_${screen}_${theme}_${width}_scaled', (tester)async{
      tester.view.devicePixelRatio=1;tester.view.physicalSize=Size(width.toDouble(),844);
      addTearDown(tester.view.resetPhysicalSize);addTearDown(tester.view.resetDevicePixelRatio);
      final c=AppController(SnapshotStore(sampleRecords(),theme),catalog,'ru',platform:ImportFixtureBridge());await c.load();
      c.offline[OfflineTable.projects]=[{'id':'p','name':'Ремонт кухни','goal':'Удобное пространство','status':'active','revision':1}];
      c.offline[OfflineTable.accounts]=[{'id':'a','name':'Наличные','kind':'cash','currency':'RUB','opening_minor':10000,'revision':1}];
      await tester.pumpWidget(LifeOSApp(controller:c,builder:(context,child)=>MediaQuery(data:MediaQuery.of(context).copyWith(textScaler:const TextScaler.linear(2)),child:child!)));
      await tester.pumpAndSettle();final context=tester.element(find.byType(HomeShell));
      if(screen=='finance')Navigator.push<void>(context,MaterialPageRoute(builder:(_)=>FinanceFoundation(controller:c)));
      if(screen=='projects')Navigator.push<void>(context,MaterialPageRoute(builder:(_)=>PersonalModulesPage(controller:c,table:OfflineTable.projects)));
      if(screen=='habit')showModalBottomSheet<void>(context:context,useSafeArea:true,isScrollControlled:true,builder:(_)=>PersonalModuleEditor(controller:c,table:OfflineTable.habits));
      if(screen=='import'){
        Navigator.push<void>(context,MaterialPageRoute(builder:(_)=>StatementImportPage(controller:c)));await tester.pumpAndSettle();
        await tester.scrollUntilVisible(find.text(c.pack.t('choose_file')).hitTestable(),200,scrollable:find.descendant(of:find.byType(StatementImportPage),matching:find.byType(Scrollable)).first);await tester.tap(find.text(c.pack.t('choose_file')).hitTestable());
        // compute() runs in a real isolate; fake-clock pumpAndSettle alone cannot await it.
        for(var attempt=0;attempt<50;attempt++) {
          await tester.runAsync(()=>Future<void>.delayed(const Duration(milliseconds:100)));
          await tester.pumpAndSettle();
          if(find.text(c.pack.t('import_step_1')).evaluate().isNotEmpty) { break; }
        }
        expect(find.text(c.pack.t('import_step_1')),findsOneWidget);
      }
      if(screen=='permissions'){
        Navigator.push<void>(context,MaterialPageRoute(builder:(_)=>Scaffold(body:SafeArea(child:ListView(key:const Key('offline_test_settings'),children:[PersonalSettings(controller:c)])))));await tester.pumpAndSettle();
        await tester.tap(find.byKey(const Key('settings_1')));await tester.pumpAndSettle();
        await tester.scrollUntilVisible(find.text(c.pack.t('notification_details')).hitTestable(),200,scrollable:find.descendant(of:find.byKey(const Key('settings_section_1')),matching:find.byType(Scrollable)).first);await tester.tap(find.text(c.pack.t('notification_details')).hitTestable());await tester.pumpAndSettle();expect(find.text(c.pack.t('permissions_diagnostics')),findsOneWidget);
      }
      if(screen=='repeat'){
        showModalBottomSheet<void>(context:context,useSafeArea:true,isScrollControlled:true,builder:(_)=>EventEditor(controller:c,date:DateTime(2026,10,11)));await tester.pumpAndSettle();
        await tester.scrollUntilVisible(find.text(c.pack.t('repeat')),250,scrollable:find.descendant(of:find.byType(EventEditor),matching:find.byType(Scrollable)).first);
        await tester.tap(find.text(c.pack.t('repeat')));await tester.pumpAndSettle();
      }
      await tester.pumpAndSettle();expect(tester.takeException(),isNull);
      await expectLater(find.byType(MaterialApp),matchesGoldenFile('goldens/offline_${screen}_${theme}_${width}_scaled.png'));
      expect(tester.takeException(),isNull);
      await tester.pumpWidget(const SizedBox.shrink());await tester.pumpAndSettle();c.dispose();
    });
  }}}
}
