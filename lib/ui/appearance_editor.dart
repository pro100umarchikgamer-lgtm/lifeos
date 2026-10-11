import 'package:flutter/material.dart';
import '../app_controller.dart';
import '../domain/appearance.dart';
import '../domain/models.dart';
import 'design.dart';

class AppearanceEditor extends StatefulWidget {
  const AppearanceEditor({super.key, required this.controller});
  final AppController controller;
  @override
  State<AppearanceEditor> createState() => _AppearanceEditorState();
}
class _AppearanceEditorState extends State<AppearanceEditor> {
  AppController get c => widget.controller;
  late Appearance draft = c.appearance.copyWith(mode: c.theme);
  bool saving = false;
  String? error;
  void preview(Appearance value) { setState(() => draft = value); c.previewAppearance(value); }
  @override
  void dispose() { final controller = c; WidgetsBinding.instance.addPostFrameCallback((_) => controller.previewAppearance(null)); super.dispose(); }
  Widget choices(String label, List<String> values, String selected, ValueChanged<String> change) =>
    Padding(padding: const EdgeInsets.only(bottom: 20), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(c.pack.t(label), style: Theme.of(context).textTheme.titleMedium), const SizedBox(height: 8),
      Wrap(spacing: 8, runSpacing: 4, children: [for (final value in values) ChoiceChip(
        label: Text(c.pack.t('appearance_$value')), selected: value == selected,
        onSelected: saving ? null : (_) => change(value))]),
    ]));
  Future<void> apply() async {
    setState(() { saving = true; error = null; });
    try { await c.preference('appearance_v1', draft.encode()); if (mounted) Navigator.pop(context); }
    catch (e) { if (mounted) setState(() { saving = false; error = e is DomainFailure ? e.key : 'change_failed'; }); }
  }
  @override
  Widget build(BuildContext context) => PopScope(canPop: !saving, child: Scaffold(
    appBar: AppBar(title: Text(c.pack.t('appearance'))),
    body: SafeArea(child: ListView(padding: const EdgeInsets.all(20), children: [
      LifeCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('LifeOS', style: Theme.of(context).textTheme.headlineSmall), const SizedBox(height: 8),
        Text(c.pack.t('appearance_preview')), const SizedBox(height: 12),
        Row(children: [Icon(Icons.check_circle, color: Theme.of(context).colorScheme.primary), const SizedBox(width: 12), Text(c.pack.t('today'), style: Theme.of(context).textTheme.titleMedium)]),
      ])), const SizedBox(height: 24),
      choices('theme', ['system','light','dark'], draft.mode, (v) => preview(draft.copyWith(mode: v))),
      choices('palette', Appearance.palettes, draft.palette, (v) => preview(draft.copyWith(palette: v))),
      SwitchListTile.adaptive(contentPadding: EdgeInsets.zero, title: Text(c.pack.t('wallpaper_colors')),
        subtitle: Text(c.pack.t(c.wallpaperSeed == null ? 'wallpaper_fallback' : 'wallpaper_available')),
        value: draft.dynamic, onChanged: saving ? null : (v) => preview(draft.copyWith(dynamic: v))),
      const SizedBox(height: 16),
      choices('shape', Appearance.shapes, draft.shape, (v) => preview(draft.copyWith(shape: v))),
      choices('surfaces', Appearance.surfaces, draft.surface, (v) => preview(draft.copyWith(surface: v))),
      if (error != null) Text(c.pack.t(error!), style: TextStyle(color: Theme.of(context).colorScheme.error)),
      TextButton(onPressed: saving ? null : () => preview(const Appearance()), child: Text(c.pack.t('reset_default'))),
    ])),
    bottomNavigationBar: SafeArea(child: Padding(padding: const EdgeInsets.all(16), child: FilledButton(
      key: const Key('apply_appearance'), onPressed: saving ? null : apply, child: Text(c.pack.t(saving ? 'saving' : 'apply'))))),
  ));
}
