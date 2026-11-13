import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../account/lifecycle_authorizer.dart';
import '../localization/language_pack.dart';
import '../platform/native_bridge.dart';
import '../sync/contracts.dart';
import '../sync/controller.dart';
import 'settings_surfaces.dart';
import 'design.dart';

class AccountPrivacyLifecycle extends StatefulWidget {
  const AccountPrivacyLifecycle(
      {super.key,
      required this.controller,
      required this.pack,
      required this.request,
      required this.initialData,
      required this.onSupport,
      this.native});
  final FamilyController controller;
  final LanguagePack pack;
  final LifecycleRequest request;
  final Json initialData;
  final NativeBridge? native;
  final VoidCallback onSupport;
  @override
  State<AccountPrivacyLifecycle> createState() =>
      _AccountPrivacyLifecycleState();
}

class _AccountPrivacyLifecycleState extends State<AccountPrivacyLifecycle> {
  late Json data;
  late final String _account;
  late final Object? _api;
  bool busy = false, cloudUnavailable = false;
  String? error;
  String t(String key) => widget.pack.t(key);
  String get _identity =>
      '${widget.controller.account?['user_id']}|${widget.controller.accountOrigin}';
  bool get _current =>
      mounted &&
      widget.controller.account != null &&
      _account == _identity &&
      identical(_api, widget.controller.api);
  @override
  void initState() {
    super.initState();
    data = clone(widget.initialData);
    _account = _identity;
    _api = widget.controller.api;
    widget.controller.addListener(_accountChanged);
  }

  @override
  void didUpdateWidget(covariant AccountPrivacyLifecycle old) {
    super.didUpdateWidget(old);
    if (!identical(old.initialData, widget.initialData) && _current) {
      data = clone(widget.initialData);
    }
  }

  void _accountChanged() {
    if (mounted && !_current) {
      setState(() {
        data = {};
        error = t('privacy_identity_changed');
      });
    }
  }

  @override
  void dispose() {
    widget.controller.removeListener(_accountChanged);
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action) async {
    if (busy || !_current) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await action();
    } on SyncFailure catch (failure) {
      if (failure.code == 'account_unavailable') {
        final restricted = await widget.controller
            .recheckUnavailablePrincipal(request: widget.request);
        if (!mounted) return;
        setState(() {
          cloudUnavailable = restricted;
          error = t(restricted
              ? 'privacy_cloud_unavailable'
              : 'privacy_action_unavailable');
        });
        return;
      }
      if (mounted) {
        setState(() => error = t(switch (failure.code) {
              'identity_mismatch' => 'privacy_identity_changed',
              'account_unavailable' => 'privacy_cloud_erasing',
              'ownership_transfer_required' => 'privacy_family_blocked',
              'staff_offboarding_required' => 'privacy_staff_blocked',
              'google_unavailable' ||
              'google_unconfigured' =>
                'privacy_google_unavailable',
              _ => 'family_error_${failure.code}',
            }));
      }
    } catch (_) {
      if (mounted) setState(() => error = t('family_error_offline'));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  String date(Object? seconds) => seconds is num
      ? DateFormat.yMMMd(widget.pack.locale.languageCode).add_Hm().format(
          DateTime.fromMillisecondsSinceEpoch(seconds.toInt() * 1000).toLocal())
      : '';
  Future<String?> _prompt(bool mfa) =>
      Navigator.of(context).push<String>(MaterialPageRoute(
          builder: (_) => AccountInputPage(
                title: t(mfa ? 'family_code' : 'family_old_password'),
                confirm: t('privacy_confirm_action'),
                cancel: t('cancel'),
                secret: true,
                description: mfa ? t('privacy_mfa_hint') : null,
              )));
  Future<LifecycleAuthMethod?> _choose() => showDialog<LifecycleAuthMethod>(
      context: context,
      builder: (ctx) => SimpleDialog(
            title: Text(t('account_google_methods')),
            children: [
              SimpleDialogOption(
                  onPressed: () =>
                      Navigator.pop(ctx, LifecycleAuthMethod.google),
                  child: Text(t('account_google_sign_in'))),
              SimpleDialogOption(
                  onPressed: () =>
                      Navigator.pop(ctx, LifecycleAuthMethod.password),
                  child: Text(t('family_old_password'))),
            ],
          ));
  Future<bool> _confirm(String title, String impact, {String? phrase}) async =>
      await Navigator.of(context).push<bool>(MaterialPageRoute(
          builder: (_) => _LifecycleConfirmation(
                pack: widget.pack,
                title: title,
                impact: impact,
                phrase: phrase,
              ))) ==
      true;
  Future<void> _mutate(String action, Json payload,
          {bool refreshFamily = false}) =>
      _run(() async {
        final fresh = await widget.request('/v1/account/lifecycle/deletion');
        if (!_current) throw const SyncFailure('identity_mismatch');
        final auth = await LifecycleAuthorizer(
                request: widget.request,
                native: widget.native,
                validSession: () => _current)
            .authenticate(fresh, prompt: _prompt, choose: _choose);
        if (auth == null || !_current) return;
        await widget.request('/v1/account/lifecycle/$action',
            body: {...payload, ...auth});
        if (!_current) return;
        final result = await widget.request('/v1/account/lifecycle/deletion');
        if (_current) setState(() => data = result);
        if (refreshFamily) await widget.controller.refresh();
      });
  Future<void> _deletion(bool cancel) async {
    if (!cancel &&
        !await _confirm(
            t('account_delete'),
            t('privacy_delete_impact').replaceAll('{hours}',
                '${((data['grace_seconds'] as num? ?? 86400) / 3600).ceil()}'),
            phrase: 'DELETE')) {
      return;
    }
    if (_current) {
      await _mutate(cancel ? 'cancel-deletion' : 'deletion',
          {if (!cancel) 'confirmation': 'DELETE'});
    }
  }

  Future<void> _closeFamily(Json family) async {
    final impact = t('privacy_close_impact')
        .replaceAll('{name}', family['name'] as String? ?? '');
    if (!await _confirm(t('family_dissolve'), impact, phrase: 'CLOSE FAMILY') ||
        !_current) {
      return;
    }
    await _mutate(
        'close-family',
        {
          'workspace_id': family['id'],
          'revision': family['workspace_revision'],
          'confirmation': 'CLOSE FAMILY'
        },
        refreshFamily: true);
  }

  Future<void> _transfer(Json family, {bool accept = false}) async {
    final recipient = family['eligible_parent_label'] as String? ?? '';
    final impact =
        t(accept ? 'privacy_accept_impact' : 'privacy_transfer_impact')
            .replaceAll('{name}', family['name'] as String? ?? '')
            .replaceAll('{recipient}', recipient);
    if (!await _confirm(
            t(accept ? 'account_accept_transfer' : 'account_transfer'),
            impact) ||
        !_current) {
      return;
    }
    await _mutate(
        accept ? 'accept-transfer' : 'transfer',
        accept
            ? {'transfer_id': family['id']}
            : {
                'workspace_id': family['id'],
                'user_id': family['eligible_parent_id']
              },
        refreshFamily: true);
  }

  @override
  Widget build(BuildContext context) {
    if (cloudUnavailable) return Text(t('privacy_cloud_unavailable'));
    if (!_current) return Text(t('privacy_identity_changed'));
    if (data['request'] is Map && data['request']['state'] == 'erasing') {
      return Text(t('privacy_cloud_erasing'));
    }
    final blocked = (data['ownership_transfer_required'] as List? ?? [])
        .map(object)
        .toList();
    final incoming =
        (data['incoming_transfers'] as List? ?? []).map(object).toList();
    final pending =
        data['request'] is Map && data['request']['state'] == 'pending';
    final staff = data['staff_offboarding_required'] == true;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text(t('privacy_delete_impact').replaceAll('{hours}',
          '${((data['grace_seconds'] as num? ?? 86400) / 3600).ceil()}')),
      if (busy)
        const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: LinearProgressIndicator()),
      if (error != null)
        Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Text(error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error))),
      if (staff)
        Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: LifeCard(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Text(t('privacy_staff_blocked')),
                  TextButton.icon(
                      key: const Key('privacy_staff_support'),
                      onPressed: busy ? null : widget.onSupport,
                      icon: const Icon(Icons.support_agent_outlined),
                      label: Text(t('account_support'))),
                ]))),
      if (blocked.isNotEmpty)
        Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Text(t('privacy_family_blocked'))),
      for (final family in blocked)
        Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: LifeCard(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                  Text(family['name'] as String? ?? '',
                      style: Theme.of(context).textTheme.titleMedium),
                  if (family['pending_until'] is num &&
                      (family['pending_until'] as num) >
                          DateTime.now().millisecondsSinceEpoch / 1000)
                    Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(
                            '${t('privacy_transfer_waiting')} ${date(family['pending_until'])}'))
                  else if (family['eligible_parent_id'] != null &&
                      family['eligible_parent_label'] is String) ...[
                    const SizedBox(height: 8),
                    Text(family['eligible_parent_label'] as String),
                    OutlinedButton.icon(
                        key: Key('privacy_transfer_${family['id']}'),
                        onPressed: busy ? null : () => _transfer(family),
                        icon: const Icon(Icons.swap_horiz),
                        label: Text(t('account_transfer'))),
                  ],
                  if (family['close_family_available'] == true &&
                      family['workspace_revision'] is int)
                    TextButton.icon(
                        key: Key('privacy_close_family_${family['id']}'),
                        onPressed: busy ? null : () => _closeFamily(family),
                        icon: const Icon(Icons.group_off_outlined),
                        label: Text(t('family_dissolve'))),
                ]))),
      for (final family in incoming)
        Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: LifeCard(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                  Text(family['name'] as String? ?? '',
                      style: Theme.of(context).textTheme.titleMedium),
                  OutlinedButton.icon(
                      key: Key('privacy_accept_transfer_${family['id']}'),
                      onPressed:
                          busy ? null : () => _transfer(family, accept: true),
                      icon: const Icon(Icons.handshake_outlined),
                      label: Text(t('account_accept_transfer'))),
                ]))),
      if (pending)
        Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Text(t('privacy_request_pending')
                .replaceAll('{date}', date(data['request']['due_at'])))),
      const SizedBox(height: 12),
      if (!pending)
        OutlinedButton.icon(
            key: const Key('privacy_delete'),
            onPressed: busy || staff || blocked.isNotEmpty
                ? null
                : () => _deletion(false),
            icon: const Icon(Icons.person_remove_outlined),
            label: Text(t('account_delete'))),
      if (pending && data['cancel_available'] == true)
        TextButton(
            key: const Key('privacy_cancel_deletion'),
            onPressed: busy ? null : () => _deletion(true),
            child: Text(t('account_cancel_delete'))),
    ]);
  }
}

class _LifecycleConfirmation extends StatefulWidget {
  const _LifecycleConfirmation(
      {required this.pack,
      required this.title,
      required this.impact,
      this.phrase});
  final LanguagePack pack;
  final String title, impact;
  final String? phrase;
  @override
  State<_LifecycleConfirmation> createState() => _LifecycleConfirmationState();
}

class _LifecycleConfirmationState extends State<_LifecycleConfirmation> {
  final field = TextEditingController();
  @override
  void dispose() {
    field.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: settingsAppBar(context, widget.title),
        body: SafeArea(
            child: ListView(padding: settingsPagePadding(context), children: [
          Text(widget.impact,
              style:
                  Theme.of(context).textTheme.bodyLarge?.copyWith(height: 1.5)),
          if (widget.phrase != null) ...[
            const SizedBox(height: 24),
            Text(widget.pack
                .t('privacy_typed_confirmation')
                .replaceAll('{phrase}', widget.phrase!)),
            const SizedBox(height: 12),
            TextField(
                key: const Key('privacy_confirmation_input'),
                controller: field,
                autocorrect: false,
                onChanged: (_) => setState(() {})),
          ],
          const SizedBox(height: 24),
          FilledButton(
              key: const Key('privacy_confirm_action'),
              onPressed:
                  widget.phrase != null && field.text.trim() != widget.phrase
                      ? null
                      : () => Navigator.pop(context, true),
              child: Text(widget.pack.t('privacy_confirm_action'))),
          const SizedBox(height: 12),
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: Text(widget.pack.t('cancel'))),
        ])),
      );
}
