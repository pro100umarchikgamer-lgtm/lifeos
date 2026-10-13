import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../domain/models.dart';
import '../domain/family_finance.dart';
import '../sync/contracts.dart';
import 'design.dart';
import 'family.dart';
import 'money_format.dart';

class FamilyDashboard extends StatelessWidget {
  const FamilyDashboard({super.key, required this.controller, this.tab = 0});
  final AppController controller;
  final int tab;
  @override
  Widget build(BuildContext context) {
    final c = controller, f = c.family!;
    String t(String key) => c.pack.t(key);
    return ListenableBuilder(
      listenable: f,
      builder: (context, _) {
        final rows = f.records,
            spaces = f.spaces.where((s) => s['id'] == f.workspace);
        final name =
            spaces.firstOrNull?['name'] as String? ?? t('family_account');
        final kinds = switch (tab) {
          1 => {'task', 'event'},
          2 => {'account', 'transaction', 'transfer', 'budget', 'request'},
          3 => {'note', 'shopping'},
          _ => {'account', 'budget', 'task', 'event', 'shopping', 'request'},
        };
        Future<void> open([Json? record]) => Navigator.push<void>(
          context,
          MaterialPageRoute(
            builder: (_) =>
                FamilyRecordEditor(controller: f, pack: c.pack, record: record),
          ),
        );
        String detail(Json r) {
          if (r['kind'] == 'account') {
            return formatMoney(
              Currency.fromCode(r['data']['currency'] as String),
              const FamilyFinance().accountBalance(r, rows),
              locale: c.region,
            );
          }
          if (r['kind'] == 'budget') {
            return '${t('remaining')}: ${formatMoney(Currency.fromCode(r['data']['currency'] as String), const FamilyFinance().budgetRemaining(r, rows, c.now), locale: c.region)}';
          }
          if (r['kind'] == 'transaction' || r['kind'] == 'request') {
            return Currency.fromCode(r['data']['currency'] as String)
                .format(r['data']['amount_minor'] as int);
          }
          if (r['kind'] == 'task') {
            return t(
              r['data']['completed'] == 1 ? 'completed' : 'family_task_undo',
            );
          }
          if (r['kind'] == 'shopping') {
            return '${(r['data']['items'] as List).where((i) => object(i)['completed'] == true).length}/${(r['data']['items'] as List).length}';
          }
          if (r['kind'] == 'event') {
            return r['data']['schedule']['localStart'] as String;
          }
          return t('family_kind_${r['kind']}');
        }

        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    name,
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                ),
                IconButton(
                  tooltip: t('family_sync'),
                  onPressed: f.busy ? null : () => f.refresh(),
                  icon: const Icon(Icons.sync),
                ),
              ],
            ),
            Text(
              t('family_visible_totals'),
              style: Theme.of(context).textTheme.bodySmall,
            ),
            if (f.busy) const LinearProgressIndicator(),
            if (f.error != null)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Text(t('family_error_${f.error}')),
              ),
            if (f.pending.isNotEmpty || f.issues.isNotEmpty)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.cloud_upload_outlined),
                title: Text(
                  '${t('family_pending')}: ${f.pending.length} · ${t('family_conflict')}: ${f.issues.length}',
                ),
                onTap: () => Navigator.push<void>(
                  context,
                  MaterialPageRoute(
                    builder: (_) => FamilyPage(controller: f, pack: c.pack),
                  ),
                ),
              ),
            const SizedBox(height: 12),
            if (f.creatableKinds.isNotEmpty)
              FilledButton.icon(
                onPressed: f.busy ? null : () => open(),
                icon: const Icon(Icons.add),
                label: Text(t('family_record_add')),
              ),
            const SizedBox(height: 12),
            for (final r in rows.where((r) => kinds.contains(r['kind'])))
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: LifeCard(
                  child: ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(
                      r['visibility'] == 'private'
                          ? Icons.lock_outline
                          : Icons.people_outline,
                    ),
                    title: Text(
                      (r['data']['title'] ??
                              r['data']['name'] ??
                              r['data']['body'] ??
                              r['data']['label'] ??
                              t('family_kind_${r['kind']}'))
                          .toString(),
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                    ),
                    subtitle: Text(
                      '${t('family_kind_${r['kind']}')} · ${detail(r)}',
                    ),
                    onTap: f.busy ? null : () => open(r),
                  ),
                ),
              ),
            if (!rows.any((r) => kinds.contains(r['kind'])))
              LifeCard(child: Text(t('offline_empty'))),
            TextButton.icon(
              onPressed: () => Navigator.push<void>(
                context,
                MaterialPageRoute(
                  builder: (_) => FamilyPage(controller: f, pack: c.pack),
                ),
              ),
              icon: const Icon(Icons.manage_accounts_outlined),
              label: Text(t('family_account')),
            ),
          ],
        );
      },
    );
  }
}
