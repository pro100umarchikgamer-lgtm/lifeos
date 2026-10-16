import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../localization/language_pack.dart';
import '../sync/contracts.dart';
import '../sync/controller.dart';
import 'design.dart';

typedef AccountRequest = Future<Json> Function(String path, {Json? body});

class AccountCenter extends StatelessWidget {
  const AccountCenter({super.key, required this.controller, required this.pack,
    this.request});
  final FamilyController controller;
  final LanguagePack pack;
  final AccountRequest? request;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(pack.t('account_manage'))),
    body: SafeArea(child: ListView(padding: const EdgeInsets.all(20), children: [
      Text(controller.account?['email'] as String? ?? pack.t('family_account'),
        style: Theme.of(context).textTheme.titleLarge),
      const SizedBox(height: 12),
      Text(pack.t('account_cloud_required')),
      const SizedBox(height: 20),
      for (final section in _AccountSection.values)
        Padding(padding: const EdgeInsets.only(bottom: 12), child: LifeCard(
          child: ListTile(contentPadding: EdgeInsets.zero,
            leading: Icon(section.icon), title: Text(pack.t(section.key)),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.of(context).push<void>(MaterialPageRoute(
              builder: (_) => _AccountSectionPage(controller: controller,
                pack: pack, section: section, request: request),
            )),
          ),
        )),
    ])),
  );
}

enum _AccountSection {
  access('account_access', Icons.workspace_premium_outlined),
  devices('account_devices', Icons.devices_outlined),
  support('account_support', Icons.chat_bubble_outline),
  privacy('account_privacy', Icons.privacy_tip_outlined);
  const _AccountSection(this.key, this.icon);
  final String key;
  final IconData icon;
}

class _AccountSectionPage extends StatefulWidget {
  const _AccountSectionPage({required this.controller, required this.pack,
    required this.section, this.request});
  final FamilyController controller;
  final LanguagePack pack;
  final _AccountSection section;
  final AccountRequest? request;
  @override
  State<_AccountSectionPage> createState() => _AccountSectionState();
}

class _AccountSectionState extends State<_AccountSectionPage> {
  Json? data;
  String? error;
  bool busy = false;
  String t(String key) => widget.pack.t(key);
  AccountRequest get request => widget.request ?? widget.controller.api!.request;

  @override
  void initState() {
    super.initState();
    load();
  }

  String get path => switch (widget.section) {
    _AccountSection.access => '/v1/account/entitlements',
    _AccountSection.devices => '/v1/account/devices',
    _AccountSection.support => '/v1/support',
    _AccountSection.privacy => '/v1/account/lifecycle/deletion',
  };

  Future<void> run(Future<void> Function() action) async {
    if (busy) return;
    setState(() {busy = true; error = null;});
    try {await action();}
    on SyncFailure catch (failure) {
      if (mounted) setState(() => error = failure.code == 'ownership_transfer_required' ? t('account_delete_notice') : t('family_error_${failure.code}'));
    } catch (_) {
      if (mounted) setState(() => error = t('family_error_offline'));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> load() => run(() async {
    final result = await request(path);
    if (mounted) setState(() => data = result);
  });

  Future<String?> ask(String label, {bool secret = false, bool multiline = false}) async {
    final input = TextEditingController();
    final result = await showDialog<String>(context: context, builder: (ctx) =>
      AlertDialog(title: Text(label), scrollable: true,
        content: TextField(controller: input, autofocus: true, obscureText: secret,
          maxLines: multiline ? 6 : 1, minLines: multiline ? 3 : 1,
          maxLength: secret ? 256 : (multiline ? 8000 : 254),
          decoration: InputDecoration(labelText: label),
          keyboardType: secret ? TextInputType.visiblePassword : TextInputType.text,
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: Text(t('cancel'))),
          FilledButton(onPressed: () {if (input.text.trim().isNotEmpty) Navigator.pop(ctx, input.text);}, child: Text(t('confirm')))],
      ));
    // Dialog exit animations may still paint the field before disposal.
    Future<void>.delayed(const Duration(seconds: 1), input.dispose);
    return result;
  }

  Future<void> revoke(String id) async {
    final password = await ask(t('family_password'), secret: true);
    if (password == null || !mounted) return;
    await run(() async {
      await request('/v1/account/devices/revoke', body: {'device_id': id, 'password': password});
      final result = await request(path);
      if (mounted) setState(() => data = result);
    });
  }

  Future<void> sendTicket() async {
    final subject = await ask(t('account_subject'));
    if (subject == null || !mounted) return;
    final message = await ask(t('account_message'), multiline: true);
    if (message == null || !mounted) return;
    await run(() async {
      await request('/v1/support', body: {'category': 'other', 'subject': subject, 'message': message});
      final result = await request(path);
      if (mounted) setState(() => data = result);
    });
  }

  Future<void> openTicket(Json ticket) async {
    await run(() async {
      final result = await request('/v1/support/thread?id=${Uri.encodeQueryComponent(ticket['id'] as String)}');
      if (!mounted) return;
      List<Json> messages = (result['messages'] as List? ?? []).map(object).toList();
      bool sending = false;
      await Navigator.of(context).push<void>(MaterialPageRoute(builder: (context) => StatefulBuilder(
        builder: (ctx, update) => Scaffold(
          appBar: AppBar(title: Text(ticket['subject'] as String), actions: [
            IconButton(tooltip: t('account_send'), icon: const Icon(Icons.reply),
              onPressed: sending ? null : () async {
                final message = await ask(t('account_message'), multiline: true);
                if (message == null || !ctx.mounted) return;
                update(() => sending = true);
                try {
                  await request('/v1/support/reply', body: {'ticket_id': ticket['id'], 'message': message});
                  final refreshed = await request('/v1/support/thread?id=${Uri.encodeQueryComponent(ticket['id'] as String)}');
                  if (ctx.mounted) update(() => messages = (refreshed['messages'] as List).map(object).toList());
                } catch (_) {
                  if (ctx.mounted) ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text(t('family_error_offline'))));
                } finally {
                  if (ctx.mounted) update(() => sending = false);
                }
              }),
          ]),
          body: SafeArea(child: ListView(padding: const EdgeInsets.all(20), children: [
            if (sending) const LinearProgressIndicator(),
            for (final message in messages)
              Padding(padding: const EdgeInsets.only(bottom: 12), child: LifeCard(child: Column(
                crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(t(message['is_staff'] == 1 ? 'account_support' : 'family_account'), style: Theme.of(context).textTheme.labelLarge),
                  const SizedBox(height: 8), Text(message['body'] as String),
                ]))),
          ])),
        ),
      )));
    });
  }

  Future<void> deletion(bool cancel) async {
    if (!cancel) {
      final approved = await showDialog<bool>(context: context, builder: (ctx) => AlertDialog(
        title: Text(t('account_delete')), content: SingleChildScrollView(child: Text(t('account_delete_notice'))),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(t('cancel'))),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: Text(t('confirm')))],
      ));
      if (approved != true || !mounted) return;
    }
    final password = await ask(t('family_password'), secret: true);
    if (password == null || !mounted) return;
    await run(() async {
      await request('/v1/account/lifecycle/${cancel ? 'cancel-deletion' : 'deletion'}', body: {
        'password': password, if (!cancel) 'confirmation': 'DELETE',
      });
      final result = await request(path);
      if (mounted) setState(() => data = result);
    });
  }

  Future<void> emailChange() async {
    final email = await ask(t('family_email'));
    if (email == null || !mounted) return;
    final password = await ask(t('family_password'), secret: true);
    if (password == null || !mounted) return;
    bool sent = false;
    await run(() async {
      await request('/v1/account/lifecycle/email', body: {'email': email.trim(), 'password': password});
      sent = true;
    });
    if (!sent || !mounted) return;
    final code = await ask(t('family_code'));
    if (code == null || !mounted) return;
    bool changed = false;
    await run(() async {
      await request('/v1/account/lifecycle/confirm-email', body: {'code': code.trim(), 'password': password});
      changed = true;
    });
    if (!changed || !mounted) return;
    await widget.controller.signOut();
    if (mounted) Navigator.of(context).pop();
  }

  String date(Object? value) => value is int
      ? DateFormat.yMMMd(widget.pack.tag.split('-').first).add_Hm().format(DateTime.fromMillisecondsSinceEpoch(value * 1000))
      : '—';

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(toolbarHeight: 88, title: Text(t(widget.section.key))),
    body: SafeArea(child: ListView(padding: const EdgeInsets.all(20), children: [
      if (busy) const LinearProgressIndicator(),
      if (error != null) ...[Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
        Text(t('account_cloud_required')), TextButton(onPressed: busy ? null : load, child: Text(t('retry')))],
      if (data != null) ...switch (widget.section) {
        _AccountSection.access => [LifeCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(data!['tier'] as String, style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 12), Text(t('account_no_payment')),
          if (data!['valid_until'] != null) Text(date(data!['valid_until'])),
          const SizedBox(height: 16),
          for (final tier in ['Free', 'Plus', 'Premium']) ListTile(contentPadding: EdgeInsets.zero,
            leading: Icon(tier == data!['tier'] ? Icons.check_circle_outline : Icons.circle_outlined), title: Text(tier)),
        ]))],
        _AccountSection.devices => [for (final raw in data!['devices'] as List? ?? [])
          Padding(padding: const EdgeInsets.only(bottom: 12), child: LifeCard(child: Column(
            crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(object(raw)['label'] as String, style: Theme.of(context).textTheme.titleMedium),
              Text(date(object(raw)['last_seen_at'])),
              if (object(raw)['revoked_at'] == 0) TextButton.icon(onPressed: busy ? null : () => revoke(object(raw)['id'] as String),
                icon: const Icon(Icons.logout), label: Text(t('account_revoke'))),
            ])))],
        _AccountSection.support => [
          FilledButton.icon(onPressed: busy ? null : sendTicket, icon: const Icon(Icons.add_comment_outlined), label: Text(t('account_send'))),
          const SizedBox(height: 16),
          for (final raw in data!['tickets'] as List? ?? []) ListTile(
            title: Text(object(raw)['subject'] as String), subtitle: Text(date(object(raw)['updated_at'])),
            trailing: const Icon(Icons.chevron_right), onTap: busy ? null : () => openTicket(object(raw))),
        ],
        _AccountSection.privacy => [
          OutlinedButton.icon(onPressed: busy ? null : emailChange, icon: const Icon(Icons.alternate_email), label: Text(t('account_email_change'))),
          const SizedBox(height: 20), Text(t('account_delete_notice')),
          if (data!['request'] != null) Padding(padding: const EdgeInsets.symmetric(vertical: 16), child: Text(date(object(data!['request'])['due_at']))),
          const SizedBox(height: 16),
          OutlinedButton.icon(onPressed: busy ? null : () => deletion(false), icon: const Icon(Icons.person_remove_outlined), label: Text(t('account_delete'))),
          if (data!['request'] != null && object(data!['request'])['state'] == 'pending')
            TextButton(onPressed: busy ? null : () => deletion(true), child: Text(t('account_cancel_delete'))),
        ],
      },
    ])),
  );
}
