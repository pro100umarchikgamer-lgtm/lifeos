import 'package:flutter/material.dart';
import 'design.dart';

/// A quiet, bounded settings group. Rows keep their labels visible at large
/// text sizes; the whole row remains a touch target.
class SettingsGroup extends StatelessWidget {
  const SettingsGroup({super.key, required this.children});
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Material(
        color: Theme.of(context).extension<LifeSurfaces>()?.treatment == 'tonal'
            ? Theme.of(context).colorScheme.surfaceContainerLow
            : Theme.of(context).colorScheme.surface,
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(
                Theme.of(context).extension<LifeSurfaces>()?.radius ?? 16),
            side: BorderSide(
                color: Theme.of(context).extension<LifeSurfaces>()?.treatment ==
                        'outlined'
                    ? Theme.of(context).colorScheme.outline
                    : Theme.of(context).colorScheme.outlineVariant)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            for (var i = 0; i < children.length; i++) ...[
              if (i > 0)
                const Padding(
                  padding: EdgeInsets.only(left: 52, right: 16),
                  child: Divider(height: 1),
                ),
              children[i],
            ],
          ],
        ),
      );
}

class SettingsRow extends StatelessWidget {
  const SettingsRow({
    super.key,
    required this.title,
    required this.icon,
    this.subtitle,
    this.onTap,
    this.trailing,
    this.destructive = false,
  });
  final String title;
  final IconData icon;
  final String? subtitle;
  final VoidCallback? onTap;
  final Widget? trailing;
  final bool destructive;

  @override
  Widget build(BuildContext context) => ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        minLeadingWidth: 24,
        horizontalTitleGap: 12,
        leading: Icon(
          icon,
          size: 22,
          color: destructive ? Theme.of(context).colorScheme.error : null,
        ),
        title: Text(
          title,
          style: TextStyle(
            color: destructive ? Theme.of(context).colorScheme.error : null,
          ),
        ),
        subtitle: subtitle == null ? null : Text(subtitle!),
        trailing: trailing ??
            (onTap == null ? null : const Icon(Icons.chevron_right, size: 20)),
        onTap: onTap,
      );
}

/// Full pages use the same readable measure on phones and tablets.
EdgeInsets settingsPagePadding(BuildContext context) => EdgeInsets.symmetric(
      horizontal: MediaQuery.sizeOf(context).width > 672
          ? (MediaQuery.sizeOf(context).width - 640) / 2
          : 16,
      vertical: 16,
    );

PreferredSizeWidget settingsAppBar(BuildContext context, String title) {
  final theme = Theme.of(context);
  final style = theme.appBarTheme.titleTextStyle ?? theme.textTheme.titleLarge!;
  final media = MediaQuery.of(context);
  final width = media.size.width -
      media.padding.horizontal -
      32 -
      (Navigator.of(context).canPop() ? 56 : 0);
  final text = TextPainter(
      text: TextSpan(text: title, style: style),
      textDirection: Directionality.of(context),
      textScaler: media.textScaler)
    ..layout(maxWidth: width.clamp(1, double.infinity).toDouble());
  return AppBar(
      title: Text(title, softWrap: true),
      toolbarHeight:
          (text.height + 24).clamp(kToolbarHeight, double.infinity).toDouble());
}

class AccountInputPage extends StatefulWidget {
  const AccountInputPage({
    super.key,
    required this.title,
    required this.confirm,
    required this.cancel,
    this.secret = false,
    this.multiline = false,
    this.description,
    this.initialValue = '',
  });
  final String title, confirm, cancel, initialValue;
  final String? description;
  final bool secret, multiline;
  @override
  State<AccountInputPage> createState() => _AccountInputPageState();
}

class _AccountInputPageState extends State<AccountInputPage> {
  late final field = TextEditingController(text: widget.initialValue);
  bool visible = false;
  @override
  void dispose() {
    field.dispose();
    super.dispose();
  }

  void submit() {
    if (field.text.trim().isNotEmpty) Navigator.pop(context, field.text);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: settingsAppBar(context, widget.title),
        body: SafeArea(
          child: ListView(
            padding: settingsPagePadding(context),
            children: [
              if (widget.description != null) ...[
                Text(widget.description!),
                const SizedBox(height: 24),
              ],
              TextField(
                controller: field,
                autofocus: true,
                obscureText: widget.secret && !visible,
                enableSuggestions: !widget.secret,
                autocorrect: !widget.secret,
                minLines: widget.multiline ? 4 : 1,
                maxLines: widget.multiline ? 8 : 1,
                maxLength: widget.secret
                    ? 256
                    : widget.multiline
                        ? 8000
                        : 254,
                textInputAction: widget.multiline
                    ? TextInputAction.newline
                    : TextInputAction.done,
                onChanged: (_) => setState(() {}),
                onSubmitted: widget.multiline ? null : (_) => submit(),
                decoration: InputDecoration(
                  labelText: widget.title,
                  suffixIcon: widget.secret
                      ? IconButton(
                          tooltip: widget.title,
                          onPressed: () => setState(() => visible = !visible),
                          icon: Icon(
                            visible
                                ? Icons.visibility_off_outlined
                                : Icons.visibility_outlined,
                          ),
                        )
                      : null,
                ),
              ),
              const SizedBox(height: 20),
              FilledButton(
                onPressed: field.text.trim().isEmpty ? null : submit,
                child: Text(widget.confirm),
              ),
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: Text(widget.cancel),
              ),
            ],
          ),
        ),
      );
}
