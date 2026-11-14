import 'package:flutter/material.dart';

/// Values stay in their field until the user opens a bounded, searchable picker.
class LifeSelect<T> extends StatelessWidget {
  const LifeSelect({
    super.key,
    required this.label,
    required this.value,
    required this.choices,
    required this.onChanged,
    this.searchLabel,
    this.queryChoices,
    this.showLabel = true,
    this.dialog = false,
  });
  final String label;
  final bool showLabel, dialog;
  final T value;
  final Map<T, String> choices;
  final ValueChanged<T>? onChanged;
  final String? searchLabel;
  final Map<T, String> Function(String)? queryChoices;

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
                  {
                    final picker = _ChoiceDialog<T>(
                      label: label,
                      value: value,
                      choices: choices,
                      searchLabel: searchLabel,
                      queryChoices: queryChoices,
                    );
                    selected = MediaQuery.sizeOf(context).width < 600
                        ? await showModalBottomSheet<T>(
                            context: context,
                            isScrollControlled: true,
                            useSafeArea: true,
                            showDragHandle: true,
                            builder: (_) => picker,
                          )
                        : await showDialog<T>(
                            context: context,
                            builder: (_) => Dialog(
                              insetPadding: const EdgeInsets.all(24),
                              child: picker,
                            ),
                          );
                  }
                  if (selected != null && context.mounted) {
                    onChanged?.call(selected);
                  }
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
                      Expanded(
                          child: Text(choices[value] ?? '$value',
                              maxLines: 2, overflow: TextOverflow.ellipsis)),
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
    this.queryChoices,
  });
  final String label;
  final T value;
  final Map<T, String> choices;
  final String? searchLabel;
  final Map<T, String> Function(String)? queryChoices;
  @override
  State<_ChoiceDialog<T>> createState() => _ChoiceDialogState<T>();
}

class _ChoiceDialogState<T> extends State<_ChoiceDialog<T>> {
  String query = '';
  @override
  Widget build(BuildContext context) {
    final candidates = <T, String>{...widget.choices};
    final extra = widget.queryChoices?.call(query);
    if (extra != null) {
      candidates.addAll(extra);
    }
    final entries = candidates.entries
        .where(
          (e) => '${e.value} ${e.key}'.toLowerCase().contains(
                query.trim().toLowerCase(),
              ),
        )
        .toList();
    final size = MediaQuery.sizeOf(context);
    final available = size.height - MediaQuery.viewInsetsOf(context).bottom;
    final heightLimit = (available * .68).clamp(160.0, 480.0);
    final maxHeight = (76.0 +
            (widget.searchLabel != null || widget.queryChoices != null
                ? 68
                : 0) +
            widget.choices.length.clamp(1, 6) * 56)
        .clamp(0.0, heightLimit);
    final colors = Theme.of(context).colorScheme;
    return AnimatedPadding(
      duration: MediaQuery.disableAnimationsOf(context)
          ? Duration.zero
          : const Duration(milliseconds: 180),
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: SizedBox(
        key: const Key('selection_dialog_body'),
        width: 440,
        height: maxHeight,
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 4, 8, 12),
              child: Row(children: [
                Expanded(
                    child: Text(widget.label,
                        style: Theme.of(context).textTheme.titleMedium)),
                IconButton(
                  tooltip: MaterialLocalizations.of(context).closeButtonTooltip,
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.close_rounded),
                ),
              ]),
            ),
            if (widget.searchLabel != null || widget.queryChoices != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                child: TextField(
                  key: const Key('selection_search'),
                  textInputAction: TextInputAction.search,
                  decoration: InputDecoration(
                    labelText: widget.searchLabel ??
                        MaterialLocalizations.of(context).searchFieldLabel,
                    prefixIcon: const Icon(Icons.search_rounded),
                  ),
                  onChanged: (v) => setState(() => query = v),
                ),
              ),
            Divider(height: 1, color: colors.outlineVariant),
            Expanded(
              child: entries.isEmpty
                  ? Center(
                      child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Text(
                        Localizations.localeOf(context).languageCode == 'ru'
                            ? 'Ничего не найдено'
                            : 'No results',
                        style: Theme.of(context)
                            .textTheme
                            .bodyMedium
                            ?.copyWith(color: colors.onSurfaceVariant),
                      ),
                    ))
                  : ListView.builder(
                      keyboardDismissBehavior:
                          ScrollViewKeyboardDismissBehavior.onDrag,
                      padding: const EdgeInsets.fromLTRB(8, 8, 8, 16),
                      itemCount: entries.length,
                      itemBuilder: (context, i) {
                        final e = entries[i], selected = e.key == widget.value;
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 2),
                          child: Material(
                              color: selected
                                  ? colors.primaryContainer
                                  : colors.surface.withValues(alpha: 0),
                              borderRadius: BorderRadius.circular(12),
                              clipBehavior: Clip.antiAlias,
                              child: ListTile(
                                key: ValueKey('choice_${e.key}'),
                                minTileHeight: 52,
                                shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(12)),
                                selected: selected,
                                title: Text(e.value),
                                trailing: selected
                                    ? const Icon(Icons.check_rounded, size: 20)
                                    : null,
                                onTap: () => Navigator.pop(context, e.key),
                              )),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
