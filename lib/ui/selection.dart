import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../localization/language_pack.dart';

/// An app-owned menu grows from the field; dismissing it preserves its value.
class LifeSelect<T> extends StatelessWidget {
  const LifeSelect(
      {super.key,
      required this.label,
      required this.value,
      required this.choices,
      required this.onChanged,
      this.searchLabel,
      this.queryChoices,
      this.showLabel = true,
      this.dialog = false});
  final String label;
  final bool showLabel, dialog;
  final T value;
  final Map<T, String> choices;
  final ValueChanged<T>? onChanged;
  final String? searchLabel;
  final Map<T, String> Function(String)? queryChoices;

  Future<void> _open(BuildContext context) async {
    FocusScope.of(context).unfocus();
    final field = context.findRenderObject()! as RenderBox;
    final anchor = field.localToGlobal(Offset.zero) & field.size;
    final themes = InheritedTheme.capture(
        from: context, to: Navigator.of(context, rootNavigator: true).context);
    final selected = await showGeneralDialog<T>(
        context: context,
        barrierDismissible: true,
        barrierColor: Colors.transparent,
        barrierLabel:
            MaterialLocalizations.of(context).modalBarrierDismissLabel,
        transitionDuration: MediaQuery.disableAnimationsOf(context)
            ? Duration.zero
            : const Duration(milliseconds: 140),
        transitionBuilder: (_, animation, __, child) =>
            FadeTransition(opacity: animation, child: child),
        pageBuilder: (_, __, ___) => themes.wrap(_ChoiceMenu<T>(
            anchor: anchor,
            label: label,
            value: value,
            choices: choices,
            searchLabel: searchLabel,
            queryChoices: queryChoices,
            emptyLabel: LanguagePackScope.maybeOf(context)?.t('search_empty') ??
                'No matching records')));
    if (selected != null && context.mounted) onChanged?.call(selected);
  }

  @override
  Widget build(BuildContext context) {
    final border = Theme.of(context).inputDecorationTheme.border;
    final radius = border is OutlineInputBorder
        ? border.borderRadius
        : BorderRadius.circular(16);
    final shape = RoundedRectangleBorder(borderRadius: radius);
    return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (showLabel)
            Padding(
                padding: const EdgeInsets.only(left: 4, bottom: 6),
                child:
                    Text(label, style: Theme.of(context).textTheme.bodyMedium)),
          Builder(
              builder: (fieldContext) => Material(
                    color: Theme.of(context).inputDecorationTheme.fillColor ??
                        Theme.of(context).colorScheme.surface,
                    shape: shape,
                    clipBehavior: Clip.antiAlias,
                    child: Semantics(
                      label: label,
                      button: true,
                      enabled: onChanged != null,
                      child: InkWell(
                        customBorder: shape,
                        onTap: onChanged == null
                            ? null
                            : () => _open(fieldContext),
                        child: ConstrainedBox(
                          constraints: const BoxConstraints(minHeight: 48),
                          child: InputDecorator(
                              decoration: InputDecoration(
                                  fillColor: Colors.transparent,
                                  enabled: onChanged != null,
                                  contentPadding: const EdgeInsets.symmetric(
                                      horizontal: 16, vertical: 14)),
                              child: Row(children: [
                                Expanded(
                                    child: Text(choices[value] ?? '$value',
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis)),
                                const SizedBox(width: 8),
                                const Icon(Icons.expand_more_rounded),
                              ])),
                        ),
                      ),
                    ),
                  )),
        ]);
  }
}

class _ChoiceMenu<T> extends StatefulWidget {
  const _ChoiceMenu(
      {required this.anchor,
      required this.label,
      required this.value,
      required this.choices,
      required this.emptyLabel,
      this.searchLabel,
      this.queryChoices});
  final Rect anchor;
  final String label, emptyLabel;
  final T value;
  final Map<T, String> choices;
  final String? searchLabel;
  final Map<T, String> Function(String)? queryChoices;
  @override
  State<_ChoiceMenu<T>> createState() => _ChoiceMenuState<T>();
}

class _ChoiceMenuState<T> extends State<_ChoiceMenu<T>> {
  String query = '';
  late T highlighted = widget.value;
  final nodes = <T, FocusNode>{};
  bool get searchable =>
      widget.searchLabel != null ||
      widget.queryChoices != null ||
      widget.choices.length > 8;
  List<MapEntry<T, String>> get entries {
    final candidates = <T, String>{
      ...widget.choices,
      ...?widget.queryChoices?.call(query)
    };
    return candidates.entries
        .where((entry) => '${entry.value} ${entry.key}'
            .toLowerCase()
            .contains(query.trim().toLowerCase()))
        .toList();
  }

  FocusNode node(T key) => nodes.putIfAbsent(key, () => FocusNode());

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => reveal(highlighted));
  }

  void reveal(T key) {
    if (!mounted) return;
    final focus = node(key);
    focus.requestFocus();
    if (focus.context != null) {
      Scrollable.ensureVisible(focus.context!,
          alignment: .5, duration: Duration.zero);
    }
  }

  KeyEventResult onKey(FocusNode _, KeyEvent event) {
    if (event is! KeyDownEvent) return KeyEventResult.ignored;
    if (event.logicalKey == LogicalKeyboardKey.escape) {
      Navigator.pop(context);
      return KeyEventResult.handled;
    }
    final options = entries;
    if (options.isEmpty) return KeyEventResult.ignored;
    if (event.logicalKey == LogicalKeyboardKey.arrowDown ||
        event.logicalKey == LogicalKeyboardKey.arrowUp) {
      final current = options.indexWhere((entry) => entry.key == highlighted);
      final offset = event.logicalKey == LogicalKeyboardKey.arrowDown ? 1 : -1;
      setState(
          () => highlighted = options[(current + offset) % options.length].key);
      reveal(highlighted);
      return KeyEventResult.handled;
    }
    if (event.logicalKey == LogicalKeyboardKey.enter ||
        event.logicalKey == LogicalKeyboardKey.numpadEnter) {
      final choice = options.where((e) => e.key == highlighted).firstOrNull ??
          options.first;
      Navigator.pop(context, choice.key);
      return KeyEventResult.handled;
    }
    return KeyEventResult.ignored;
  }

  @override
  void dispose() {
    for (final focus in nodes.values) {
      focus.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final media = MediaQuery.of(context),
        colors = Theme.of(context).colorScheme;
    final options = entries;
    return LayoutBuilder(builder: (context, bounds) {
      final width =
          math.min(widget.anchor.width, math.min(440.0, bounds.maxWidth - 16));
      final left = widget.anchor.left.clamp(8.0, bounds.maxWidth - width - 8);
      final topEdge = media.padding.top + 8;
      final bottomEdge = bounds.maxHeight -
          math.max(media.viewInsets.bottom, media.padding.bottom) -
          8;
      final anchorTop = widget.anchor.top.clamp(topEdge, bottomEdge);
      final anchorBottom = widget.anchor.bottom.clamp(topEdge, bottomEdge);
      final below = math.max(0.0, bottomEdge - anchorBottom - 4);
      final above = math.max(0.0, anchorTop - topEdge - 4);
      final desired = math.min(
          400.0,
          16 +
              (searchable ? 76 : 0) +
              options.length.clamp(1, 6) * 56 * media.textScaler.scale(1));
      final opensBelow = below >= math.min(desired, 180) || below >= above;
      final height = math.min(desired, opensBelow ? below : above);
      final top = opensBelow ? anchorBottom + 4 : anchorTop - height - 4;
      final border = Theme.of(context).inputDecorationTheme.border;
      final radius = border is OutlineInputBorder
          ? border.borderRadius
          : BorderRadius.circular(16);
      return Stack(children: [
        Positioned(
            left: left,
            top: top,
            width: width,
            height: height,
            child: Semantics(
                scopesRoute: true,
                explicitChildNodes: true,
                namesRoute: true,
                label: widget.label,
                child: Material(
                    key: const Key('selection_dialog_body'),
                    color: colors.surface,
                    elevation: 8,
                    shadowColor: colors.shadow.withValues(alpha: .24),
                    shape: RoundedRectangleBorder(
                        borderRadius: radius,
                        side: BorderSide(color: colors.outlineVariant)),
                    clipBehavior: Clip.antiAlias,
                    child: Focus(
                        onKeyEvent: onKey,
                        child: Column(children: [
                          if (searchable) ...[
                            Padding(
                                padding: const EdgeInsets.all(10),
                                child: TextField(
                                    key: const Key('selection_search'),
                                    textInputAction: TextInputAction.search,
                                    decoration: InputDecoration(
                                        isDense: true,
                                        labelText: widget.searchLabel ??
                                            MaterialLocalizations.of(context)
                                                .searchFieldLabel,
                                        prefixIcon:
                                            const Icon(Icons.search_rounded)),
                                    onChanged: (value) =>
                                        setState(() => query = value))),
                            Divider(height: 1, color: colors.outlineVariant),
                          ],
                          Expanded(
                              child: options.isEmpty
                                  ? Center(
                                      child: Padding(
                                          padding: const EdgeInsets.all(16),
                                          child: Text(widget.emptyLabel)))
                                  : SingleChildScrollView(
                                      keyboardDismissBehavior:
                                          ScrollViewKeyboardDismissBehavior
                                              .onDrag,
                                      padding: const EdgeInsets.all(6),
                                      child: Column(
                                          mainAxisSize: MainAxisSize.min,
                                          children: [
                                            for (final entry in options)
                                              Padding(
                                                  padding: const EdgeInsets.symmetric(
                                                      vertical: 2),
                                                  child: Material(
                                                      color: entry.key == widget.value
                                                          ? colors
                                                              .primaryContainer
                                                          : Colors.transparent,
                                                      borderRadius: BorderRadius.circular(
                                                          10),
                                                      clipBehavior:
                                                          Clip.antiAlias,
                                                      child: ListTile(
                                                          key: ValueKey(
                                                              'choice_${entry.key}'),
                                                          focusNode:
                                                              node(entry.key),
                                                          minTileHeight: 48,
                                                          contentPadding: const EdgeInsets.symmetric(
                                                              horizontal: 12),
                                                          selected: entry.key ==
                                                              widget.value,
                                                          title:
                                                              Text(entry.value),
                                                          trailing: entry.key ==
                                                                  widget.value
                                                              ? const Icon(Icons.check_rounded, size: 20)
                                                              : null,
                                                          onTap: () => Navigator.pop(context, entry.key))))
                                          ]))),
                        ])))))
      ]);
    });
  }
}
