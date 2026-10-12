import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/domain/models.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/ui/app.dart';
import 'package:lifeos/ui/personal_modules.dart';
import 'package:lifeos/ui/selection.dart';
import 'widget_test.dart' show UIStore;

void main() {
  timezone.initializeTimeZones();
  late PackCatalog catalog;
  setUpAll(() async { catalog=await PackCatalog.load(); });
  for(final width in [320.0,390.0,430.0]) {
    for(final dark in [false,true]) {
      for(final table in personalModules) {
        testWidgets('first ${table.name} action accessible at $width dark=$dark', (tester) async {
          tester.view.devicePixelRatio=1;tester.view.physicalSize=Size(width,844);
          addTearDown(tester.view.resetPhysicalSize);addTearDown(tester.view.resetDevicePixelRatio);
          final store=UIStore();final c=AppController(store,catalog,'ru');await c.load();
          await tester.pumpWidget(MaterialApp(theme:ThemeData(brightness:dark?Brightness.dark:Brightness.light),builder:(context,child)=>MediaQuery(data:MediaQuery.of(context).copyWith(textScaler:const TextScaler.linear(2)),child:child!),home:PersonalModulesPage(controller:c,table:table)));
          await tester.pumpAndSettle();
          expect(find.text(c.pack.t('offline_module_hint')),findsNothing);
          await tester.scrollUntilVisible(find.byKey(const Key('module_create')).hitTestable(),150);
          expect(tester.getSize(find.byKey(const Key('module_create'))).height,greaterThanOrEqualTo(48));
          await tester.tap(find.byKey(const Key('module_create')).hitTestable());await tester.pumpAndSettle();
          expect(find.byType(PersonalModuleEditor),findsOneWidget);expect(find.byType(BottomSheet),findsNothing);
          expect(find.byKey(const Key('save')),findsOneWidget);expect(tester.takeException(),isNull);
          expect(store.actions,isEmpty);c.dispose();
        });
      }
    }
  }
  testWidgets('shopping checkbox edits the existing immutable target and revision', (tester) async {
    final store=UIStore();final c=AppController(store,catalog,'ru');await c.load();
    c.offline[OfflineTable.checklists]=[{'id':'list-existing','name':'Покупки','kind':'shopping','revision':2}];
    c.offline[OfflineTable.checklistItems]=[{'id':'item-existing','checklist_id':'list-existing','name':'Молоко','quantity':'1 л','completed':0,'task_id':null,'revision':4}];
    await tester.pumpWidget(MaterialApp(home:PersonalModulesPage(controller:c,table:OfflineTable.checklists)));await tester.pumpAndSettle();
    await tester.tap(find.byType(Checkbox));await tester.pumpAndSettle();
    final action=store.actions.single as SaveChecklistItem;
    expect(action.id,'item-existing');expect(action.expectedRevision,4);expect(action.checklistId,'list-existing');expect(action.name,'Молоко');expect(action.completed,isTrue);expect(action.quantity,'1 л');
  });
  testWidgets('anchored kind choice preserves an unsaved list draft and stable edit identity', (tester) async {
    final store=UIStore();final c=AppController(store,catalog,'ru');await c.load();
    await tester.pumpWidget(MaterialApp(home:Scaffold(resizeToAvoidBottomInset:false,body:PersonalModuleEditor(controller:c,table:OfflineTable.checklists,row:const {'id':'list-existing','name':'Список','kind':'shopping','revision':3}))));
    await tester.pumpAndSettle();await tester.enterText(find.byType(TextField).first,'Домашние дела');
    final kindChoice=find.byWidgetPredicate((w)=>w is LifeSelect<String>&&w.label==c.pack.t('kind'));
    await tester.ensureVisible(kindChoice);await tester.tap(kindChoice);await tester.pumpAndSettle();
    expect(find.byType(BottomSheet),findsNothing);
    await tester.tap(find.byKey(const ValueKey('choice_chores')));await tester.pumpAndSettle();
    expect(find.text('Домашние дела'),findsWidgets);
    await tester.tap(find.byKey(const Key('save')));await tester.pumpAndSettle();
    final action=store.actions.single as SaveChecklist;expect(action.id,'list-existing');expect(action.expectedRevision,3);expect(action.name,'Домашние дела');expect(action.kind,'chores');
  });
  testWidgets('profile offers human settings and no false family access controls', (tester) async {
    final store=UIStore();final c=AppController(store,catalog,'ru');await c.load();
    await tester.pumpWidget(LifeOSApp(controller:c));await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('profile_button')));await tester.pumpAndSettle();
    expect(find.byKey(const Key('settings_0')),findsOneWidget);expect(find.byKey(const Key('settings_1')),findsOneWidget);expect(find.byKey(const Key('settings_2')),findsOneWidget);
    expect(find.text(c.pack.t('module_memberships')),findsNothing);expect(find.text(c.pack.t('profiles_local_only')),findsNothing);expect(store.actions,isEmpty);
  });
}
