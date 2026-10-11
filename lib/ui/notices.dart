import 'dart:async';
import 'package:flutter/material.dart';

/// Owns a single notice and its hard deadline, including accessible navigation.
class LifeNotices {
  final messengerKey = GlobalKey<ScaffoldMessengerState>();
  Timer? _deadline;
  int _generation = 0;

  void clear() {
    _generation++;
    _deadline?.cancel();
    messengerKey.currentState?.clearSnackBars();
    messengerKey.currentState?.removeCurrentSnackBar();
  }

  void show(String message, {String? undoLabel, Future<void> Function()? undo,
    String Function(Object)? errorLabel}) {
    clear();
    final messenger = messengerKey.currentState;
    if (messenger == null) return;
    final generation = _generation;
    messenger.showSnackBar(SnackBar(content: Text(message),
      duration: const Duration(milliseconds: 3500),
      behavior: SnackBarBehavior.floating,
      actionOverflowThreshold: 1,
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 12),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      action: undo == null ? null : SnackBarAction(label: undoLabel!, onPressed: () async {
        clear();
        final operationGeneration = _generation;
        try { await undo(); }
        catch (error) {
          if (_generation == operationGeneration && errorLabel != null) show(errorLabel(error));
        }
      })));
    // SnackBarAction can keep an accessible snackbar alive beyond its duration.
    _deadline = Timer(const Duration(milliseconds: 3500), () {
      if (_generation == generation) clear();
    });
  }

  void dispose() { _deadline?.cancel(); }
}

class LifeNoticeScope extends InheritedWidget {
  const LifeNoticeScope({super.key, required this.notices, required super.child});
  final LifeNotices notices;
  static LifeNotices of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<LifeNoticeScope>()!.notices;
  @override
  bool updateShouldNotify(LifeNoticeScope oldWidget) => oldWidget.notices != notices;
}

class NoticeNavigationObserver extends NavigatorObserver {
  NoticeNavigationObserver(this.notices);
  final LifeNotices notices;
  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) => notices.clear();
  @override
  void didPop(Route<dynamic> route, Route<dynamic>? previousRoute) => notices.clear();
  @override
  void didReplace({Route<dynamic>? newRoute, Route<dynamic>? oldRoute}) => notices.clear();
}
