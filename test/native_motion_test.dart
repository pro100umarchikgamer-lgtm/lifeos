import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/ui/design.dart';

void main() {
  testWidgets(
      'shared routes are brief and reduced motion keeps pages still with Back usable',
      (tester) async {
    final theme = lifeTheme(Brightness.light);
    final transition =
        theme.pageTransitionsTheme.builders[TargetPlatform.android]!;
    expect(
        transition.transitionDuration.inMilliseconds, lessThanOrEqualTo(220));
    await tester.pumpWidget(MaterialApp(
        theme: theme,
        builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context).copyWith(disableAnimations: true),
            child: child!),
        home: Builder(
            builder: (context) => Scaffold(
                body: TextButton(
                    onPressed: () => Navigator.push<void>(
                        context,
                        MaterialPageRoute(
                            builder: (_) => const Scaffold(
                                body: Align(
                                    alignment: Alignment.topLeft,
                                    child: Text('Details',
                                        key: Key('motion_target')))))),
                    child: const Text('Open'))))));
    await tester.tap(find.text('Open'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 1));
    expect(find.byKey(const Key('motion_target')), findsOneWidget);
    expect(
        tester.getTopLeft(find.byKey(const Key('motion_target'))), Offset.zero);
    await tester.pumpAndSettle();
    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();
    expect(find.text('Open'), findsOneWidget);
    expect(find.text('Details'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
