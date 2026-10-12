import 'dart:math' as math;
import 'package:flutter/material.dart';

/// The same bounded, keyboard-safe picker for preferences and form values.
class LifeSelect<T> extends StatelessWidget {
  const LifeSelect({super.key, required this.label, required this.value,
    required this.choices, required this.onChanged, this.searchLabel, this.showLabel=true});
  final String label;
  final bool showLabel;
  final T value;
  final Map<T, String> choices;
  final ValueChanged<T>? onChanged;
  final String? searchLabel;

  @override
  Widget build(BuildContext context) => Semantics(button: true, enabled: onChanged != null,
    child: InkWell(borderRadius: BorderRadius.circular(20), onTap: onChanged == null ? null : () async {
      FocusScope.of(context).unfocus();
      final T? selected;
      if(choices.length<=8) {
        final box=context.findRenderObject() as RenderBox;
        final overlay=Navigator.of(context).overlay!.context.findRenderObject() as RenderBox;
        final origin=box.localToGlobal(Offset.zero,ancestor:overlay);
        selected=await showMenu<T>(context:context,
          position:RelativeRect.fromRect(origin&box.size,Offset.zero&overlay.size),
          constraints:const BoxConstraints(minWidth:180,maxWidth:320,maxHeight:360),
          shape:RoundedRectangleBorder(borderRadius:BorderRadius.circular(20)),
          items:[for(final entry in choices.entries)PopupMenuItem<T>(key:ValueKey('choice_${entry.key}'),value:entry.key,child:Text(entry.value))]);
      } else {
        selected = await showModalBottomSheet<T>(context: context, useSafeArea: true,
        isScrollControlled: true, showDragHandle: true,
        sheetAnimationStyle: MediaQuery.disableAnimationsOf(context) ? AnimationStyle.noAnimation : null,
        builder: (_) => _ChoiceSheet<T>(label: label, value: value, choices: choices, searchLabel: searchLabel));
      }
      if (selected != null && context.mounted) onChanged?.call(selected);
    }, child: Column(crossAxisAlignment:CrossAxisAlignment.stretch,mainAxisSize:MainAxisSize.min,children:[
      if(showLabel)...[Padding(padding:const EdgeInsets.only(left:4,bottom:6),child:Text(label,style:Theme.of(context).textTheme.bodyMedium)),],
      InputDecorator(decoration: InputDecoration(enabled: onChanged != null,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14)),
      child: Row(children: [Expanded(child: Text(choices[value] ?? '$value', maxLines: 2,
        overflow: TextOverflow.ellipsis)), const SizedBox(width: 8), const Icon(Icons.expand_more_rounded)])),])));
}

class _ChoiceSheet<T> extends StatefulWidget {
  const _ChoiceSheet({required this.label, required this.value, required this.choices, this.searchLabel});
  final String label;
  final T value;
  final Map<T, String> choices;
  final String? searchLabel;
  @override
  State<_ChoiceSheet<T>> createState() => _ChoiceSheetState<T>();
}

class _ChoiceSheetState<T> extends State<_ChoiceSheet<T>> {
  String query = '';
  @override
  Widget build(BuildContext context) {
    final media = MediaQuery.of(context);
    final height = math.max(100.0, math.min(media.size.height * .65,
      media.size.height - media.viewInsets.bottom - media.padding.top - 80));
    final entries = widget.choices.entries.where((e) =>
      '${e.value} ${e.key}'.toLowerCase().contains(query.trim().toLowerCase())).toList();
    return Padding(padding: EdgeInsets.only(bottom: media.viewInsets.bottom),
      child: SafeArea(top: false, child: ConstrainedBox(constraints: BoxConstraints(maxHeight: height),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Padding(padding: const EdgeInsets.fromLTRB(20, 0, 8, 8), child: Row(children: [
            Expanded(child: Text(widget.label, style: Theme.of(context).textTheme.titleLarge,
              maxLines: 2, overflow: TextOverflow.ellipsis)),
            IconButton(tooltip: MaterialLocalizations.of(context).closeButtonTooltip,
              onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close_rounded)),
          ])),
          if (widget.searchLabel != null) Padding(padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            child: TextField(key: const Key('selection_search'), decoration: InputDecoration(
              labelText: widget.searchLabel, prefixIcon: const Icon(Icons.search_rounded)),
              onChanged: (v) => setState(() => query = v))),
          Flexible(child: ListView.builder(shrinkWrap: true, padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
            itemCount: entries.length, itemBuilder: (context, index) {
              final entry = entries[index], selected = entry.key == widget.value;
              return Padding(padding: const EdgeInsets.only(bottom: 4), child: Material(
                color: selected ? Theme.of(context).colorScheme.primaryContainer : Colors.transparent,
                borderRadius: BorderRadius.circular(16), child: ListTile(
                  key: ValueKey('choice_${entry.key}'), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  selected: selected, title: Text(entry.value),
                  trailing: selected ? const Icon(Icons.check_rounded) : null,
                  onTap: () => Navigator.pop(context, entry.key))));
            })),
        ]))));
  }
}
