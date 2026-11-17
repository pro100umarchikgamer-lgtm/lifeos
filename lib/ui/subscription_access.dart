import 'package:flutter/material.dart';

import '../localization/language_pack.dart';
import '../sync/contracts.dart';
import 'settings_surfaces.dart';

/// Release availability is deliberately local and fail-closed as well as server
/// controlled. Cached, legacy or spoofed Premium data cannot offer AI or sales.
class SubscriptionAccess extends StatelessWidget {
  const SubscriptionAccess({
    super.key,
    required this.pack,
    required this.access,
    required this.verified,
  });

  final LanguagePack pack;
  final Json access;
  final bool verified;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final current = access['tier'] == 'Plus' ? 'Plus' : 'Free';
    final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
    final expiry = access['valid_until'];
    final isCurrent =
        verified && (expiry == null || (expiry is int && expiry > now));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(pack.t('plans_available_free'), style: theme.textTheme.titleLarge),
        const SizedBox(height: 12),
        Text(pack.t('plans_preview_notice')),
        const SizedBox(height: 24),
        if (isCurrent) ...[
          Text('${pack.t('plans_current_access')}: $current',
              style: theme.textTheme.titleMedium),
          const SizedBox(height: 16),
        ] else ...[
          Text(pack.t('plans_access_unverified')),
          const SizedBox(height: 16),
        ],
        SettingsGroup(
          children: [
            SettingsRow(
              icon: Icons.check_circle_outline,
              title: 'Free · ${pack.t('plans_available')}',
              subtitle: pack.t('plan_free_description'),
            ),
            SettingsRow(
              icon: Icons.auto_awesome_mosaic_outlined,
              title: 'Plus · ${pack.t('plans_preview')}',
              subtitle: pack.t('plan_plus_description'),
            ),
            SettingsRow(
              icon: Icons.lock_outline,
              title: 'Premium · ${pack.t('plans_unavailable')}',
              subtitle: pack.t('plan_premium_description'),
            ),
          ],
        ),
        const SizedBox(height: 20),
        Text(pack.t('plans_no_billing'), style: theme.textTheme.bodyMedium),
      ],
    );
  }
}
