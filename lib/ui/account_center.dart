import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../localization/language_pack.dart';
import '../sync/contracts.dart';
import '../sync/controller.dart';
import 'design.dart';
import 'settings_surfaces.dart';
import 'subscription_access.dart';
import 'privacy_lifecycle.dart';
import '../platform/native_bridge.dart';

import 'package:flutter/services.dart';

typedef AccountRequest = Future<Json> Function(String path, {Json? body});

PreferredSizeWidget _accountBar(
  BuildContext context,
  String title, {
  List<Widget>? actions,
}) {
  final theme = Theme.of(context);
  final style = theme.appBarTheme.titleTextStyle ?? theme.textTheme.titleLarge!;
  final media = MediaQuery.of(context);
  final available = media.size.width -
      media.padding.horizontal -
      32 -
      (Navigator.of(context).canPop() ? 56 : 0) -
      (actions == null ? 0 : actions.length * 48 + 8);
  final titleLayout = TextPainter(
    text: TextSpan(text: title, style: style),
    textDirection: Directionality.of(context),
    textScaler: media.textScaler,
  )..layout(maxWidth: available.clamp(1, double.infinity).toDouble());
  return AppBar(
    titleSpacing: 16,
    titleTextStyle: style,
    toolbarHeight: (titleLayout.height + 24)
        .clamp(kToolbarHeight, double.infinity)
        .toDouble(),
    title: Text(title,
        softWrap: true, maxLines: 10, overflow: TextOverflow.visible),
    actions: actions,
  );
}

class AccountCenter extends StatelessWidget {
  const AccountCenter({
    super.key,
    required this.controller,
    required this.pack,
    this.request,
    this.native,
  });
  final FamilyController controller;
  final LanguagePack pack;
  final AccountRequest? request;
  final NativeBridge? native;

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: _accountBar(context, pack.t('account_manage')),
        body: SafeArea(
          child: ListView(
            padding: settingsPagePadding(context),
            children: [
              Padding(
                padding: const EdgeInsets.only(bottom: 24),
                child: Text(
                  controller.account?['email'] as String? ??
                      pack.t('family_account'),
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              SettingsGroup(
                children: [
                  for (final section in _AccountSection.values)
                    SettingsRow(
                      icon: section.icon,
                      title: pack.t(section.key),
                      onTap: () => Navigator.of(context).push<void>(
                        MaterialPageRoute(
                          builder: (_) => _AccountSectionPage(
                            controller: controller,
                            pack: pack,
                            section: section,
                            request: request,
                            native: native,
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ],
          ),
        ),
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
  const _AccountSectionPage({
    required this.controller,
    required this.pack,
    required this.section,
    this.request,
    this.native,
  });
  final FamilyController controller;
  final LanguagePack pack;
  final _AccountSection section;
  final AccountRequest? request;
  final NativeBridge? native;
  @override
  State<_AccountSectionPage> createState() => _AccountSectionState();
}

class _AccountSectionState extends State<_AccountSectionPage> {
  Json? data;
  String? error;
  bool busy = false, principalUnavailable = false;
  late final AccountPrincipal _principalAtOpen;
  bool get _current =>
      mounted && widget.controller.account != null &&
      widget.controller.isCurrentPrincipal(_principalAtOpen);
  void _principalChanged() {
    if (mounted && !_current) {
      setState(() {
        data = null;
        error = t(principalUnavailable
            ? 'privacy_cloud_unavailable'
            : 'privacy_identity_changed');
      });
    }
  }

  @override
  void dispose() {
    widget.controller.removeListener(_principalChanged);
    super.dispose();
  }

  String t(String key) => widget.pack.t(key);
  AccountRequest get request {
    final delegate = widget.request;
    final client = widget.controller.api;
    return (String path, {Json? body}) async {
      if (!_current) throw const SyncFailure('identity_mismatch');
      final result = await (delegate ?? client!.request)(path, body: body);
      if (!_current) throw const SyncFailure('identity_mismatch');
      return result;
    };
  }

  Widget _principalPage(Widget Function() build) => AnimatedBuilder(
      animation: widget.controller,
      builder: (context, _) => _current ? build() : Scaffold(
          appBar: _accountBar(context, t('account_privacy')),
          body: SafeArea(child: Padding(
              padding: settingsPagePadding(context),
              child: Text(t('privacy_identity_changed'))))));

  @override
  void initState() {
    super.initState();
    _principalAtOpen = widget.controller.capturePrincipal();
    widget.controller.addListener(_principalChanged);
    load();
  }

  String get path => switch (widget.section) {
        _AccountSection.access => '/v1/account/entitlements',
        _AccountSection.devices => '/v1/account/devices',
        _AccountSection.support => '/v1/support',
        _AccountSection.privacy => '/v1/account/lifecycle/deletion',
      };

  Future<void> run(Future<void> Function() action) async {
    if (busy || !_current) return;
    final principal = widget.controller.capturePrincipal();
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await action();
    } on SyncFailure catch (failure) {
      if (!_current) return;
      if (failure.code == 'account_unavailable') {
        final restricted = await widget.controller
            .recheckUnavailablePrincipal(
                expectedPrincipal: principal, request: request);
        if (mounted) {
          setState(() {
            principalUnavailable = restricted;
            data = restricted ? null : data;
            error = t(restricted
                ? 'privacy_cloud_unavailable'
                : 'privacy_action_unavailable');
          });
        }
        return;
      }
      if (mounted) {
        setState(
          () => error = failure.code == 'ownership_transfer_required'
              ? t('account_delete_notice')
              : t('family_error_${failure.code}'),
        );
      }
    } catch (_) {
      if (mounted) setState(() => error = t('family_error_offline'));
    } finally {
      if (mounted) {
        setState(() {
          busy = false;
          if (!_current) {
            data = null;
            error = t(principalUnavailable
                ? 'privacy_cloud_unavailable'
                : 'privacy_identity_changed');
          }
        });
      }
    }
  }

  Future<void> load() => run(() async {
        final result = await request(path);
        if (mounted) setState(() => data = result);
      });

  Future<String?> ask(
    String label, {
    bool secret = false,
    bool multiline = false,
  }) async {
    if (!_current) return null;
    final value = await Navigator.of(context).push<String>(
      MaterialPageRoute(
        builder: (_) => _principalPage(() => AccountInputPage(
          title: label,
          confirm: t('confirm'),
          cancel: t('cancel'),
          secret: secret,
          multiline: multiline,
        )),
      ),
    );
    return _current ? value : null;
  }

  Future<void> revoke(String id, {bool current = false}) async {
    final password = await ask(t('family_password'), secret: true);
    if (password == null || !mounted) return;
    await run(() async {
      await request(
        '/v1/account/devices/revoke',
        body: {'device_id': id, 'password': password},
      );
      if (current) {
        if (!_current) return;
        await widget.controller.signOut();
        if (mounted && widget.controller.account == null) {
          Navigator.of(context).popUntil((route) => route.isFirst);
        }
        return;
      }
      final result = await request(path);
      if (mounted) setState(() => data = result);
    });
  }

  Future<void> sendTicket() async {
    final draft =
        await Navigator.of(context).push<Map<String, String>>(MaterialPageRoute(
      builder: (_) => _SupportComposePage(pack: widget.pack),
    ));
    if (draft == null || !mounted) return;
    final subject = draft['subject']!, message = draft['message']!;
    await run(() async {
      await request(
        '/v1/support',
        body: {'category': 'other', 'subject': subject, 'message': message},
      );
      final result = await request(path);
      if (mounted) setState(() => data = result);
    });
  }

  Future<void> openTicket(Json ticket) async {
    await run(() async {
      final result = await request(
        '/v1/support/thread?id=${Uri.encodeQueryComponent(ticket['id'] as String)}',
      );
      if (!mounted) return;
      List<Json> messages =
          (result['messages'] as List? ?? []).map(object).toList();
      bool sending = false;
      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (context) => StatefulBuilder(
            builder: (ctx, update) => Scaffold(
              appBar: _accountBar(
                ctx,
                t('account_support'),
                actions: [
                  IconButton(
                    tooltip: t('account_send'),
                    icon: const Icon(Icons.reply),
                    onPressed: sending
                        ? null
                        : () async {
                            final message = await ask(
                              t('account_message'),
                              multiline: true,
                            );
                            if (message == null || !ctx.mounted) return;
                            update(() => sending = true);
                            try {
                              await request(
                                '/v1/support/reply',
                                body: {
                                  'ticket_id': ticket['id'],
                                  'message': message,
                                },
                              );
                              final refreshed = await request(
                                '/v1/support/thread?id=${Uri.encodeQueryComponent(ticket['id'] as String)}',
                              );
                              if (ctx.mounted) {
                                update(
                                  () => messages =
                                      (refreshed['messages'] as List)
                                          .map(object)
                                          .toList(),
                                );
                              }
                            } catch (_) {
                              if (ctx.mounted) {
                                ScaffoldMessenger.of(ctx).showSnackBar(
                                  SnackBar(
                                    content: Text(t('family_error_offline')),
                                  ),
                                );
                              }
                            } finally {
                              if (ctx.mounted) {
                                update(() => sending = false);
                              }
                            }
                          },
                  ),
                ],
              ),
              body: SafeArea(
                child: ListView(
                  padding: const EdgeInsets.all(20),
                  children: [
                    Text(
                      ticket['subject'] as String,
                      style: Theme.of(ctx).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 16),
                    if (sending) const LinearProgressIndicator(),
                    for (final message in messages)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: LifeCard(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                t(
                                  message['is_staff'] == 1
                                      ? 'account_support'
                                      : 'family_account',
                                ),
                                style: Theme.of(context).textTheme.labelLarge,
                              ),
                              const SizedBox(height: 8),
                              Text(message['body'] as String),
                            ],
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
    });
  }

  Future<void> emailChange() async {
    final email = await ask(t('family_email'));
    if (email == null || !mounted) return;
    final password = await ask(t('family_password'), secret: true);
    if (password == null || !mounted) return;
    bool sent = false;
    await run(() async {
      await request(
        '/v1/account/lifecycle/email',
        body: {'email': email.trim(), 'password': password},
      );
      sent = true;
    });
    if (!sent || !mounted) return;
    final code = await ask(t('family_code'));
    if (code == null || !mounted) return;
    bool changed = false;
    await run(() async {
      await request(
        '/v1/account/lifecycle/confirm-email',
        body: {'code': code.trim(), 'password': password},
      );
      changed = true;
    });
    if (!changed || !mounted) return;
    if (!_current) return;
    await widget.controller.signOut();
    if (mounted && widget.controller.account == null) {
      Navigator.of(context).popUntil((route) => route.isFirst);
    }
  }

  Future<void> showPrivateMaterial(
    String title,
    String body,
    String material,
  ) async {
    if (!_current) return;
    await Navigator.of(context).push<void>(MaterialPageRoute(
        builder: (ctx) => _principalPage(() => Scaffold(
              appBar: _accountBar(ctx, title),
              body: SafeArea(
                  child: ListView(padding: settingsPagePadding(ctx), children: [
                Text(body),
                const SizedBox(height: 24),
                LifeCard(child: SelectableText(material)),
                const SizedBox(height: 24),
                FilledButton(
                    onPressed: () => Navigator.pop(ctx),
                    child: Text(t('account_done'))),
              ])),
            ))));
  }

  Future<void> manageGoogle() async {
    Json? status;
    await run(() async {
      status = await request('/v1/account/google');
    });
    if (status == null || !mounted) return;
    if (status!['has_password'] != true) {
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(t('account_google_methods')),
          content: Text(t('account_google_password_first')),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: Text(t('close')),
            ),
          ],
        ),
      );
      return;
    }
    final linked = status!['google_linked'] == true;
    if (!linked && status!['google_enabled'] != true) {
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(t('account_google_methods')),
          content: Text(t('family_error_google_unavailable')),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: Text(t('close')),
            ),
          ],
        ),
      );
      return;
    }
    final proceed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(t('account_google_methods')),
        content: Text(
          t(linked ? 'account_google_linked' : 'account_google_unlinked'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text(t('cancel')),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(
              t(
                linked ? 'account_google_disconnect' : 'account_google_connect',
              ),
            ),
          ),
        ],
      ),
    );
    if (proceed != true || !mounted) return;
    final password = await ask(t('family_old_password'), secret: true);
    if (password == null || !mounted) return;
    Json? mfa;
    await run(() async {
      mfa = await request('/v1/account/mfa');
    });
    if (mfa == null || !mounted) return;
    String? code;
    if (mfa!['enabled'] == true) {
      code = await ask(t('family_code'), secret: true);
      if (code == null || !mounted) return;
    }
    await run(() async {
      if (status!['google_linked'] == true) {
        await request(
          '/v1/account/google/unlink',
          body: {'password': password, 'code': code},
        );
        if (!_current) return;
        await widget.controller.signOut();
      } else {
        final grant = await request(
          '/v1/account/google/link',
          body: {'password': password, 'code': code},
        );
        try {
          final token = await (widget.native ?? NativeBridge()).googleSignIn(
            grant['client_id'] as String,
            grant['nonce'] as String,
          );
          if (!_current) return;
          await request(
            '/v1/auth/google/finish',
            body: {'challenge': grant['challenge'], 'id_token': token},
          );
        } on PlatformException catch (error) {
          if (error.code != 'google_cancelled') throw SyncFailure(error.code);
        }
      }
    });
    if (mounted && widget.controller.account == null) {
      Navigator.of(context).popUntil((route) => route.isFirst);
    }
  }

  Future<void> manageMfa() async {
    Json? status;
    await run(() async {
      status = await request('/v1/account/mfa');
    });
    if (status == null || !mounted) return;
    final enabled = status!['enabled'] == true;
    if (enabled) {
      final yes = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(t('account_mfa_disable')),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: Text(t('cancel')),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: Text(t('confirm')),
            ),
          ],
        ),
      );
      if (yes != true || !mounted) return;
    }
    final password = await ask(t('family_password'), secret: true);
    if (password == null || !mounted) return;
    Json? enrollment;
    if (!enabled) {
      await run(() async {
        enrollment = await request(
          '/v1/account/mfa/begin',
          body: {'password': password},
        );
      });
      if (enrollment == null || !mounted) return;
      await showPrivateMaterial(
        t('account_mfa'),
        t('account_mfa_setup'),
        enrollment!['totp_secret'] as String,
      );
      if (!mounted) return;
    }
    final code = await ask(t('family_code'));
    if (code == null || !mounted) return;
    Json? changed;
    await run(() async {
      changed = await request(
        '/v1/account/mfa/${enabled ? 'disable' : 'enable'}',
        body: {
          'password': password,
          'code': code.trim(),
          if (!enabled) 'enrollment': enrollment!['enrollment'],
        },
      );
    });
    if (changed == null || !mounted) return;
    if (!enabled) {
      await showPrivateMaterial(
        t('account_mfa'),
        t('account_mfa_recovery'),
        (changed!['recovery_codes'] as List).join('\n\n'),
      );
      if (!mounted) return;
    }
    if (!_current) return;
    await widget.controller.signOut();
    if (mounted && widget.controller.account == null) {
      Navigator.of(context).popUntil((route) => route.isFirst);
    }
  }

  String date(Object? value) => value is int
      ? DateFormat.yMMMd(widget.pack.tag.split('-').first)
          .add_Hm()
          .format(DateTime.fromMillisecondsSinceEpoch(value * 1000))
      : '—';

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: _accountBar(context, t(widget.section.key)),
        body: SafeArea(
          child: ListView(
            padding: settingsPagePadding(context),
            children: [
              if (busy) const LinearProgressIndicator(),
              if (error != null) ...[
                Text(
                  error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
                Text(t('account_cloud_required')),
                TextButton(
                    onPressed: busy ? null : load, child: Text(t('retry'))),
              ],
              if (data != null || widget.section == _AccountSection.access)
                ...switch (widget.section) {
                  _AccountSection.access => [
                      SubscriptionAccess(
                        pack: widget.pack,
                        access: data ?? const {},
                        verified: error == null && !busy,
                      ),
                      if (error == null &&
                          !busy &&
                          data?['tier'] == 'Plus' &&
                          data?['valid_until'] != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 16),
                          child: Text(date(data!['valid_until'])),
                        ),
                    ],
                  _AccountSection.devices => [
                      SettingsGroup(
                        children: [
                          for (final raw in data!['devices'] as List? ?? [])
                            SettingsRow(
                              icon: Icons.devices_outlined,
                              title: object(raw)['label'] as String,
                              subtitle: date(object(raw)['last_seen_at']),
                              trailing: object(raw)['revoked_at'] == 0
                                  ? TextButton(
                                      onPressed: busy
                                          ? null
                                          : () => revoke(
                                                object(raw)['id'] as String,
                                                current:
                                                    object(raw)['current'] ==
                                                        true,
                                              ),
                                      child: Text(t('account_revoke')),
                                    )
                                  : null,
                            ),
                        ],
                      ),
                    ],
                  _AccountSection.support => [
                      FilledButton.icon(
                        onPressed: busy ? null : sendTicket,
                        icon: const Icon(Icons.add_comment_outlined),
                        label: Text(t('account_send')),
                      ),
                      const SizedBox(height: 16),
                      for (final raw in data!['tickets'] as List? ?? [])
                        ListTile(
                          title: Text(object(raw)['subject'] as String),
                          subtitle: Text(date(object(raw)['updated_at'])),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: busy ? null : () => openTicket(object(raw)),
                        ),
                    ],
                  _AccountSection.privacy => [
                      SettingsGroup(
                        children: [
                          SettingsRow(
                            icon: Icons.key_outlined,
                            title: t('account_google_methods'),
                            onTap: busy ? null : manageGoogle,
                          ),
                          SettingsRow(
                            icon: Icons.phonelink_lock_outlined,
                            title: t('account_mfa'),
                            onTap: busy ? null : manageMfa,
                          ),
                          SettingsRow(
                            icon: Icons.alternate_email,
                            title: t('account_email_change'),
                            onTap: busy ? null : emailChange,
                          ),
                        ],
                      ),
                      const SizedBox(height: 20),
                      AccountPrivacyLifecycle(
                        controller: widget.controller,
                        pack: widget.pack,
                        request: request,
                        native: widget.native,
                        initialData: data!,
                        onSupport: () =>
                            Navigator.of(context).push<void>(MaterialPageRoute(
                          builder: (_) => _AccountSectionPage(
                              controller: widget.controller,
                              pack: widget.pack,
                              section: _AccountSection.support,
                              request: widget.request,
                              native: widget.native),
                        )),
                      ),
                    ],
                },
            ],
          ),
        ),
      );
}

class _SupportComposePage extends StatefulWidget {
  const _SupportComposePage({required this.pack});
  final LanguagePack pack;
  @override
  State<_SupportComposePage> createState() => _SupportComposeState();
}

class _SupportComposeState extends State<_SupportComposePage> {
  final subject = TextEditingController(), message = TextEditingController();
  @override
  void dispose() {
    subject.dispose();
    message.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: _accountBar(context, widget.pack.t('account_support')),
        body: SafeArea(
            child: ListView(padding: settingsPagePadding(context), children: [
          TextField(
              controller: subject,
              maxLength: 254,
              textInputAction: TextInputAction.next,
              onChanged: (_) => setState(() {}),
              decoration:
                  InputDecoration(labelText: widget.pack.t('account_subject'))),
          const SizedBox(height: 16),
          TextField(
              controller: message,
              minLines: 5,
              maxLines: 10,
              maxLength: 8000,
              onChanged: (_) => setState(() {}),
              decoration:
                  InputDecoration(labelText: widget.pack.t('account_message'))),
          const SizedBox(height: 20),
          FilledButton(
              onPressed:
                  subject.text.trim().isEmpty || message.text.trim().isEmpty
                      ? null
                      : () => Navigator.pop(context, {
                            'subject': subject.text.trim(),
                            'message': message.text.trim()
                          }),
              child: Text(widget.pack.t('account_send'))),
        ])),
      );
}
