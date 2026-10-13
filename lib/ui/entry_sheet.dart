import 'dart:math' as math;

import 'package:flutter/material.dart';

/// Shared keyboard-safe sheet: only fields scroll, the primary action stays visible.
class EntrySheet extends StatelessWidget {
  const EntrySheet({
    super.key,
    required this.children,
    required this.saving,
    required this.saveLabel,
    required this.onSave,
  });
  final List<Widget> children;
  final bool saving;
  final String saveLabel;
  final VoidCallback onSave;
  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, bounds) {
      final keyboard = MediaQuery.viewInsetsOf(context).bottom;
      final available = math.max(
        0.0,
        math.min(MediaQuery.sizeOf(context).height * .9, bounds.maxHeight) -
            keyboard -
            28,
      );
      return PopScope(
        canPop: !saving,
        child: Padding(
          padding: EdgeInsets.fromLTRB(20, 12, 20, 16 + keyboard),
          child: ConstrainedBox(
            constraints: BoxConstraints(maxHeight: available),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Flexible(
                  fit: FlexFit.loose,
                  child: SingleChildScrollView(
                    keyboardDismissBehavior:
                        ScrollViewKeyboardDismissBehavior.onDrag,
                    child: AbsorbPointer(
                      absorbing: saving,
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: children,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                FilledButton(
                  key: const Key('save'),
                  onPressed: saving ? null : onSave,
                  child: saving
                      ? Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Theme.of(context).colorScheme.onPrimary,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Flexible(
                              child: Text(
                                saveLabel,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        )
                      : Text(saveLabel),
                ),
              ],
            ),
          ),
        ),
      );
    },
  );
}
