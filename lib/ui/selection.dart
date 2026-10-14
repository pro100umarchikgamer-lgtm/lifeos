import 'package:flutter/material.dart';

/// Bounded searchable dialogs resize naturally above the keyboard.
class LifeSelect<T> extends StatelessWidget {
  const LifeSelect({
    super.key,
    required this.label,
    required this.value,
    required this.choices,
    required this.onChanged,
    this.searchLabel,
    this.showLabel = true,
    this.dialog = false,
  });
  final String label;
  final bool showLabel, dialog;
  final T value;
  final Map<T, String> choices;
  final ValueChanged<T>? onChanged;
  final String? searchLabel;

  @override
  Widget build(BuildContext context) => Semantics(
    button: true,
    enabled: onChanged != null,
    child: InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onChanged == null
          ? null
          : () async {
              FocusScope.of(context).unfocus();
              final T? selected;
              if (choices.length <= 8 && !dialog) {
                final box = context.findRenderObject() as RenderBox;
                final overlay =
                    Navigator.of(context).overlay!.context.findRenderObject()
                        as RenderBox;
                final origin = box.localToGlobal(
                  Offset.zero,
                  ancestor: overlay,
                );
                selected = await showMenu<T>(
                  context: context,
                  position: RelativeRect.fromRect(
                    origin & box.size,
                    Offset.zero & overlay.size,
                  ),
                  constraints: const BoxConstraints(
                    minWidth: 180,
                    maxWidth: 320,
                    maxHeight: 360,
                  ),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(20),
                  ),
                  items: [
                    for (final e in choices.entries)
                      PopupMenuItem<T>(
                        key: ValueKey('choice_${e.key}'),
                        value: e.key,
                        child: Text(e.value),
                      ),
                  ],
                );
              } else {
                selected = await showDialog<T>(
                  context: context,
                  builder: (_) => _ChoiceDialog<T>(
                    label: label,
                    value: value,
                    choices: choices,
                    searchLabel: searchLabel,
                  ),
                );
              }
              if (selected != null && context.mounted)
                onChanged?.call(selected);
            },
      child: ConstrainedBox(
        constraints: const BoxConstraints(minHeight: 48),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            if (showLabel)
              Padding(
                padding: const EdgeInsets.only(left: 4, bottom: 6),
                child: Text(
                  label,
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ),
            InputDecorator(
              decoration: InputDecoration(
                enabled: onChanged != null,
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 14,
                ),
              ),
              child: Row(
                children: [
                  Expanded(child: Text(choices[value] ?? '$value')),
                  const SizedBox(width: 8),
                  const Icon(Icons.expand_more_rounded),
                ],
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class _ChoiceDialog<T> extends StatefulWidget {
  const _ChoiceDialog({
    required this.label,
    required this.value,
    required this.choices,
    this.searchLabel,
  });
  final String label;
  final T value;
  final Map<T, String> choices;
  final String? searchLabel;
  @override
  State<_ChoiceDialog<T>> createState() => _ChoiceDialogState<T>();
}

class _ChoiceDialogState<T> extends State<_ChoiceDialog<T>> {
  String query = '';
  @override
  Widget build(BuildContext context) {
    final entries = widget.choices.entries
        .where(
          (e) => '${e.value} ${e.key}'.toLowerCase().contains(
            query.trim().toLowerCase(),
          ),
        )
        .toList();
    return Dialog(
      insetPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
      child: LayoutBuilder(
        builder: (context, box) => SizedBox(
          width: 440,
          height: box.maxHeight.clamp(0.0, 480.0),
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 12, 8, 8),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        widget.label,
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                    ),
                    IconButton(
                      tooltip: MaterialLocalizations.of(context)
                          .closeButtonTooltip,
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.close_rounded),
                    ),
                  ],
                ),
              ),
              if (widget.searchLabel != null)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                  child: TextField(
                    key: const Key('selection_search'),
                    textInputAction: TextInputAction.search,
                    decoration: InputDecoration(
                      labelText: widget.searchLabel,
                      prefixIcon: const Icon(Icons.search_rounded),
                    ),
                    onChanged: (v) => setState(() => query = v),
                  ),
                ),
              Expanded(
                child: ListView.builder(
                  keyboardDismissBehavior:
                      ScrollViewKeyboardDismissBehavior.onDrag,
                  padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                  itemCount: entries.length,
                  itemBuilder: (context, i) {
                    final e = entries[i], selected = e.key == widget.value;
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: Material(
                        color: selected
                            ? Theme.of(context).colorScheme.primaryContainer
                            : Colors.transparent,
                        borderRadius: BorderRadius.circular(16),
                        child: ListTile(
                          key: ValueKey('choice_${e.key}'),
                          minTileHeight: 56,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16),
                          ),
                          selected: selected,
                          title: Text(e.value),
                          trailing: selected
                              ? const Icon(Icons.check_rounded)
                              : null,
                          onTap: () => Navigator.pop(context, e.key),
                        ),
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
