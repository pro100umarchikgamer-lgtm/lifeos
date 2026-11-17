import 'package:flutter/material.dart';

import '../domain/public_links.dart';
import '../localization/language_pack.dart';
import 'settings_surfaces.dart';

String helpCenterTitle(LanguagePack pack) => pack.t('help_title');

/// Help stays available without a cloud account. Legal documents are opened at
/// the public site so operator and retention details have a single source.
class HelpCenterScreen extends StatefulWidget {
  const HelpCenterScreen({
    super.key,
    required this.pack,
    required this.onOpenLink,
  });

  final LanguagePack pack;
  final Future<void> Function(Uri) onOpenLink;

  @override
  State<HelpCenterScreen> createState() => _HelpCenterScreenState();
}

class _HelpCenterScreenState extends State<HelpCenterScreen> {
  final search = TextEditingController();
  String query = '';
  LanguagePack get pack => LanguagePackScope.maybeOf(context) ?? widget.pack;
  String h(String key) => pack.t(key);

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  Future<void> open(String path) async {
    try {
      await widget.onOpenLink(
          publicSitePage(path).replace(queryParameters: {'lang': pack.tag}));
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(h('help_c836034ed40c'))));
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final entries = <_HelpAnswer>[
      _HelpAnswer('today', h('help_7b5576d13790'), h('help_72ac412e122c'),
          h('help_e3974b13afef')),
      _HelpAnswer('sync', h('help_0cd94b34fcb7'), h('help_2b4816ca5d46'),
          h('help_3e8103371cc5')),
      _HelpAnswer('import', h('help_0cd94b34fcb7'), h('help_31dc684ba346'),
          h('help_2b821449ee55')),
      _HelpAnswer('notifications', h('help_0cd94b34fcb7'),
          h('help_b7b264f4c1af'), h('help_03193ad5d581')),
      _HelpAnswer('finances', h('help_0c1d71b5f66c'), h('help_f77f8068707f'),
          h('help_d68a7cd2d22b')),
      _HelpAnswer('family', h('help_0c1d71b5f66c'), h('help_a53b27aa125d'),
          h('help_e8936649ef7c')),
      _HelpAnswer('security', h('help_a7d44f975eec'), h('help_f743b80d7bb2'),
          h('help_d45a7bac69d0')),
      _HelpAnswer('privacy', h('help_a7d44f975eec'), h('help_ebe531ecd5e2'),
          h('help_22a7ea39583b')),
      _HelpAnswer('deletion', h('help_a7d44f975eec'), h('help_99a8d1165936'),
          h('help_21ffdc96f68f')),
      _HelpAnswer('plans', h('help_1ba86395a3c0'), h('help_fefbe1f1458f'),
          h('help_7ef84223913c')),
      _HelpAnswer('support', h('help_1ba86395a3c0'), h('help_3f7a1af304d6'),
          h('help_689a5f40dfb9')),
    ];
    final words = query.toLowerCase().trim().split(RegExp(r'\s+'));
    final visible = entries
        .where((entry) => words.every((word) =>
            '${entry.group} ${entry.question} ${entry.answer}'
                .toLowerCase()
                .contains(word)))
        .toList();
    return Scaffold(
      appBar: settingsAppBar(context, helpCenterTitle(pack)),
      body: SafeArea(
        top: false,
        child: ListView(
          padding: settingsPagePadding(context),
          children: [
            Text(h('help_01510bd47693'), style: theme.textTheme.headlineMedium),
            const SizedBox(height: 12),
            Text(h('help_1a20259dabbf'),
                style: theme.textTheme.bodyLarge
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
            const SizedBox(height: 24),
            TextField(
              key: const Key('help_search'),
              controller: search,
              textInputAction: TextInputAction.search,
              decoration: InputDecoration(
                labelText: h('help_abcf6781ffa2'),
                prefixIcon: const Icon(Icons.search),
                suffixIcon: query.isEmpty
                    ? null
                    : IconButton(
                        tooltip: h('help_3b8784ec4445'),
                        onPressed: () {
                          search.clear();
                          setState(() => query = '');
                        },
                        icon: const Icon(Icons.close),
                      ),
                border: const OutlineInputBorder(),
              ),
              onChanged: (value) => setState(() => query = value),
            ),
            const SizedBox(height: 12),
            Semantics(
              liveRegion: true,
              child: Text(
                  h('help_2d4e672fda03')
                      .replaceAll('{count}', '${visible.length}'),
                  style: theme.textTheme.bodySmall),
            ),
            const SizedBox(height: 12),
            if (visible.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 24),
                child: Text(h('help_187db74b62e2')),
              ),
            for (final group
                in visible.map((entry) => entry.group).toSet()) ...[
              Padding(
                padding: const EdgeInsets.only(top: 20, bottom: 12),
                child: Text(group, style: theme.textTheme.titleMedium),
              ),
              SettingsGroup(children: [
                for (final entry
                    in visible.where((entry) => entry.group == group))
                  ExpansionTile(
                    key:
                        ValueKey('help_answer_${entry.id}_${query.isNotEmpty}'),
                    title: Text(entry.question),
                    tilePadding:
                        const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                    childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                    expandedCrossAxisAlignment: CrossAxisAlignment.start,
                    initiallyExpanded: query.isNotEmpty,
                    children: [
                      Text(entry.answer,
                          style: theme.textTheme.bodyMedium
                              ?.copyWith(height: 1.7)),
                      const SizedBox(height: 8),
                      TextButton.icon(
                        onPressed: () => open('/faq#${entry.id}'),
                        icon: const Icon(Icons.open_in_new, size: 18),
                        label: Text(h('help_488283b847d7')),
                      ),
                    ],
                  ),
              ]),
            ],
            const SizedBox(height: 32),
            SettingsGroup(children: [
              SettingsRow(
                title: h('help_aec27a879c14'),
                icon: Icons.support_agent_outlined,
                onTap: () => open('/support'),
              ),
              SettingsRow(
                title: h('help_090429d46c70'),
                icon: Icons.privacy_tip_outlined,
                onTap: () => open('/privacy'),
              ),
              SettingsRow(
                title: h('help_e26e662a5cb5'),
                icon: Icons.description_outlined,
                onTap: () => open('/terms'),
              ),
            ]),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}

class _HelpAnswer {
  const _HelpAnswer(this.id, this.group, this.question, this.answer);
  final String id;
  final String group;
  final String question;
  final String answer;
}
