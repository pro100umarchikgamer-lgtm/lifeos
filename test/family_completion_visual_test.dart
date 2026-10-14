import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as timezone;
import 'package:lifeos/app_controller.dart';
import 'package:lifeos/localization/language_pack.dart';
import 'package:lifeos/sync/controller.dart';
import 'package:lifeos/ui/app.dart';
import 'package:lifeos/ui/family.dart';
import 'package:lifeos/ui/global_search.dart';
import 'package:lifeos/ui/statement_import.dart';

import 'support/sync_memory.dart';
import 'visual_snapshot_test.dart' show SnapshotStore;

// Synthetic identities and records; this fixture never contacts a server.
FamilyController familyFixture({bool child = false}) {
  final f = FamilyController(MemorySyncStore());
  f.account = {
    'user_id': child ? 'child-user' : 'parent-user',
    'verified': true,
  };
  f.workspace = 'family';
  f.spaces = [
    {'id': 'family', 'name': 'Наша семья', 'role': child ? 'child' : 'parent'},
  ];
  f.roster = {
    'space': {
      'id': 'family',
      'role': child ? 'child' : 'parent',
      'profile_id': child ? 'child-profile' : null,
    },
    'members': [],
    'profiles': [
      {
        'id': 'child-profile',
        'name': 'Алекс',
        'permissions': ['record_spending', 'request_money'],
      },
    ],
  };
  f.records = [
    {
      'id': 'shared-account',
      'owner_id': 'parent-user',
      'revision': 1,
      'kind': 'account',
      'visibility': 'shared',
      'audience': ['child-profile'],
      'editable': !child,
      'data': {
        'name': 'Семейный кошелёк',
        'currency': 'RUB',
        'opening_minor': 125000,
      },
    },
    {
      'id': 'shared-task',
      'owner_id': 'parent-user',
      'revision': 2,
      'kind': 'task',
      'visibility': 'shared',
      'audience': ['child-profile'],
      'editable': false,
      'data': {
        'title': 'Подготовить вещи к поездке',
        'completed': 0,
        'assignment': 'single',
        'assignees': ['child-profile'],
        'review': 1,
      },
      'progress': [],
    },
    {
      'id': 'shared-note',
      'owner_id': 'parent-user',
      'revision': 1,
      'kind': 'note',
      'visibility': 'shared',
      'audience': [],
      'editable': !child,
      'data': {'body': 'Планы на выходные'},
    },
  ];
  return f;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  timezone.initializeTimeZones();
  late PackCatalog catalog;
  setUpAll(() async {
    final bytes = await File('test/fonts/NotoSans-Regular.ttf').readAsBytes();
    await (FontLoader(
      'Roboto',
    )..addFont(Future.value(ByteData.sublistView(bytes)))).load();
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
    catalog = await PackCatalog.load();
  });
  for (final width in [320, 430]) {
    for (final theme in ['light', 'dark']) {
      for (final screen in [
        'today',
        'modules',
        'search',
        'import',
        'family',
        'child',
        'money',
        'child_money',
        'account',
        'login',
        'register',
        'event',
        'money_keyboard',
      ]) {
        testWidgets('completion_${screen}_${theme}_$width', (tester) async {
          tester.view.devicePixelRatio = 1;
          tester.view.physicalSize = Size(width.toDouble(), 844);
          addTearDown(tester.view.resetPhysicalSize);
          addTearDown(tester.view.resetDevicePixelRatio);
          final c = AppController(SnapshotStore([], theme), catalog, 'ru');
          await c.load();
          c.family = familyFixture(child: screen.startsWith('child'));
          if (['login', 'register'].contains(screen)) c.family!.account = null;
          if (['family', 'child'].contains(screen)) {
            c.preferences['active_scope'] = 'family';
          }
          await tester.pumpWidget(
            LifeOSApp(
              controller: c,
              builder: (context, child) => MediaQuery(
                data: MediaQuery.of(context).copyWith(
                  textScaler: const TextScaler.linear(1.8),
                  disableAnimations: true,
                  viewInsets: screen == 'money_keyboard'
                      ? const EdgeInsets.only(bottom: 260)
                      : EdgeInsets.zero,
                ),
                child: child!,
              ),
            ),
          );
          await tester.pumpAndSettle();
          final context = tester.element(find.byType(HomeShell));
          Widget? page;
          switch (screen) {
            case 'modules':
              await tester.tap(find.byKey(const Key('nav_modules')));
            case 'search':
              page = GlobalSearchPage(controller: c, family: false);
            case 'import':
              page = StatementImportPage(controller: c);
            case 'money':
            case 'child_money':
            case 'money_keyboard':
              page = FamilyRecordEditor(
                controller: c.family!,
                pack: c.pack,
                initialKind: 'transaction',
              );
            case 'event':
              page = FamilyRecordEditor(
                controller: c.family!,
                pack: c.pack,
                initialKind: 'event',
              );
            case 'register':
            case 'login':
            case 'account':
              page = FamilyPage(controller: c.family!, pack: c.pack);
          }
          if (page != null) {
            Navigator.push<void>(
              context,
              MaterialPageRoute(builder: (_) => page!),
            );
          }
          await tester.pumpAndSettle();
          if (screen == 'register') {
            await tester.scrollUntilVisible(
              find.text(c.pack.t('family_register')),
              180,
              scrollable: find
                  .descendant(
                    of: find.byType(FamilyPage),
                    matching: find.byType(Scrollable),
                  )
                  .first,
            );
            await tester.pumpAndSettle();
            await tester.tap(find.text(c.pack.t('family_register')));
            await tester.pumpAndSettle();
            expect(find.text(c.pack.t('repeat_password')), findsOneWidget);
          }
          expect(tester.takeException(), isNull);
          await expectLater(
            find.byType(MaterialApp),
            matchesGoldenFile(
              'goldens/completion_${screen}_${theme}_$width.png',
            ),
          );
          expect(tester.takeException(), isNull);
          await tester.pumpWidget(const SizedBox.shrink());
          await tester.pumpAndSettle();
          c.dispose();
        });
      }
    }
  }
  test('child creation choices reflect granted permissions', () {
    final f = familyFixture(child: true);
    expect(f.creatableKinds, {'transaction', 'request'});
    f.roster!['profiles'][0]['permissions'] = [];
    expect(f.creatableKinds, isEmpty);
    f.dispose();
  });
}
