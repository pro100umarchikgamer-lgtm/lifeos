import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../account/referrals.dart';
import '../localization/language_pack.dart';
import '../platform/native_bridge.dart';
import '../sync/contracts.dart';
import '../sync/controller.dart';
import 'design.dart';
import 'settings_surfaces.dart';

String referralText(LanguagePack pack, String key) =>
    pack.strings['referrals_$key'] ?? _fallback[key]!;

const _fallback = {
  'title': 'Invite friends',
  'intro': 'Share ULADIM with people who may find it useful.',
  'count': 'Joined through your invitation',
  'people': 'Invited friends',
  'empty': 'No one has joined yet.',
  'create': 'Create invite link',
  'link': 'Your link',
  'copy': 'Copy',
  'share': 'Share',
  'copied': 'Link copied',
  'loading': 'Loading invitations…',
  'retry': 'Retry',
  'load_error': 'Could not load invitations. Check your connection and retry.',
  'action_error': 'Could not save. Check your connection and retry.',
  'verify': 'Sign in and verify your email to invite friends.',
  'identity_changed':
      'Your account changed. Open invitations again from Profile.',
  'more': 'Show more',
  'member': 'Member',
  'alias_title': 'Your name for the inviter',
  'alias_hint':
      'Optional: only a first name and surname initial, such as “Umar U.” Contacts, activity and purchases stay private.',
  'first': 'First name',
  'initial': 'Surname initial',
  'show_name': 'Show this name',
  'hide_name': 'Keep my name private',
  'name_saved': 'Name saved',
  'claim_title': 'Were you invited?',
  'claim_hint':
      'Accept only if you want to. Your friend will see only the short name you choose.',
  'claim_label': 'Invitation code or link',
  'claim_action': 'Accept invitation',
  'claim_done': 'Invitation accepted',
  'self': 'This is your own link.',
  'already_attributed': 'This account has already accepted another invitation.',
  'invalid_invitation': 'This invitation is not valid.',
};

class ReferralsPage extends StatefulWidget {
  const ReferralsPage(
      {super.key, required this.controller, required this.pack, this.native});
  final FamilyController controller;
  final LanguagePack pack;
  final NativeBridge? native;
  @override
  State<ReferralsPage> createState() => _ReferralsPageState();
}

class _ReferralsPageState extends State<ReferralsPage> {
  late final principal = widget.controller.capturePrincipal();
  final first = TextEditingController(),
      initial = TextEditingController(),
      claim = TextEditingController();
  ReferralSummary? summary;
  List<String> people = [];
  String? alias, error;
  bool busy = false;
  FamilyController get c => widget.controller;
  String t(String key) => referralText(widget.pack, key);
  bool get current => c.isCurrentPrincipal(principal);
  bool get eligible =>
      current && c.api != null && c.account != null && c.verified;

  @override
  void initState() {
    super.initState();
    c.addListener(accountChanged);
    load();
  }

  void accountChanged() {
    if (!mounted) return;
    if (!eligible) {
      first.clear();
      initial.clear();
      claim.clear();
      ScaffoldMessenger.of(context).hideCurrentSnackBar();
      setState(() {
        summary = null;
        people = [];
        alias = null;
        error = null;
      });
    }
  }

  @override
  void dispose() {
    c.removeListener(accountChanged);
    first.dispose();
    initial.dispose();
    claim.dispose();
    super.dispose();
  }

  String failure(Object failure, {bool loading = false}) => t(switch (failure) {
        SyncFailure(code: 'referral_self') => 'self',
        SyncFailure(code: 'referral_already_attributed') =>
          'already_attributed',
        SyncFailure(code: 'referral_invalid') => 'invalid_invitation',
        SyncFailure(code: 'verify_email' || 'unauthorized') => 'verify',
        _ => loading ? 'load_error' : 'action_error',
      });

  void notice(String text) {
    if (!mounted || !eligible) return;
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(SnackBar(content: Text(text)));
  }

  Future<void> run(Future<void> Function() action,
      {bool loading = false}) async {
    if (!eligible || busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await action();
    } catch (failure) {
      if (mounted && eligible) {
        final text = this.failure(failure, loading: loading);
        if (summary == null) {
          setState(() => error = text);
        } else {
          notice(text);
        }
      }
    } finally {
      if (mounted) {
        setState(() {
          busy = false;
          if (!eligible) {
            summary = null;
            people = [];
            alias = null;
          }
        });
      }
    }
  }

  Future<void> load() => run(() async {
        final result =
            await Future.wait([c.referralSummary(), c.referralAlias()]);
        if (!mounted || !eligible) return;
        setState(() {
          summary = result[0] as ReferralSummary;
          people = [...summary!.people];
          alias = result[1] as String;
        });
      }, loading: true);

  Future<void> create() => run(() async {
        final result = await c.createReferralCode();
        if (mounted && eligible) {
          setState(() {
            summary = result;
            people = [...result.people];
          });
        }
      });

  Future<void> more() => run(() async {
        final offset = summary?.nextOffset;
        if (offset == null) return;
        final result = await c.referralSummary(offset: offset);
        if (mounted && eligible) {
          setState(() {
            summary = result;
            people.addAll(result.people);
          });
        }
      }, loading: true);

  Future<void> saveAlias({bool hide = false}) => run(() async {
        final result = await c.saveReferralAlias(
            hide ? '' : first.text, hide ? '' : initial.text);
        if (!mounted || !eligible) return;
        first.clear();
        initial.clear();
        setState(() => alias = result);
        notice(t('name_saved'));
      });

  Future<void> accept() => run(() async {
        final code = referralCodeFromInput(claim.text);
        await c.claimReferral(code);
        if (!mounted || !eligible) return;
        claim.clear();
        notice(t('claim_done'));
      });

  Future<void> copy() => run(() async {
        final invite = summary?.invite;
        if (invite == null) return;
        await Clipboard.setData(ClipboardData(text: invite.url.toString()));
        notice(t('copied'));
      });

  Future<void> share() => run(() async {
        final invite = summary?.invite;
        if (invite != null) {
          await (widget.native ?? NativeBridge()).shareReferralLink(invite.url);
        }
      });

  Widget action(String key, VoidCallback? onPressed,
      {IconData? icon, bool filled = false}) {
    final child = Text(t(key), textAlign: TextAlign.center);
    return ConstrainedBox(
        constraints: const BoxConstraints(minHeight: 48),
        child: filled
            ? FilledButton(onPressed: onPressed, child: child)
            : icon == null
                ? OutlinedButton(onPressed: onPressed, child: child)
                : OutlinedButton.icon(
                    onPressed: onPressed,
                    icon: Icon(icon, size: 18),
                    label: child));
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: settingsAppBar(context, t('title')),
        body: SafeArea(
            child: ListView(padding: settingsPagePadding(context), children: [
          if (!eligible)
            LifeCard(child: Text(t(current ? 'verify' : 'identity_changed')))
          else ...[
            if (busy)
              Semantics(
                  liveRegion: true,
                  label: t('loading'),
                  child: const LinearProgressIndicator()),
            if (error != null)
              Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: LifeCard(
                      child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                        Semantics(
                            liveRegion: true,
                            child: Text(error!,
                                style: TextStyle(
                                    color:
                                        Theme.of(context).colorScheme.error))),
                        if (summary == null) ...[
                          const SizedBox(height: 12),
                          action('retry', busy ? null : load)
                        ],
                      ]))),
            if (summary case final data?) ...[
              LifeCard(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                    Text(t('intro'),
                        style: Theme.of(context).textTheme.bodyLarge),
                    const SizedBox(height: 20),
                    Text(t('count')),
                    const SizedBox(height: 4),
                    Text('${data.confirmedCount}',
                        key: const Key('referral_count'),
                        style: Theme.of(context)
                            .textTheme
                            .headlineMedium
                            ?.copyWith(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 20),
                    if (data.invite case final invite?) ...[
                      Text(t('link'),
                          style: Theme.of(context).textTheme.titleSmall),
                      const SizedBox(height: 8),
                      SelectableText(invite.url.toString(),
                          key: const Key('referral_link')),
                      const SizedBox(height: 12),
                      Wrap(spacing: 8, runSpacing: 8, children: [
                        action('copy', busy ? null : copy,
                            icon: Icons.copy_outlined),
                        action('share', busy ? null : share,
                            icon: Icons.ios_share_outlined),
                      ]),
                    ] else
                      action('create', busy ? null : create, filled: true),
                  ])),
              const SizedBox(height: 16),
              LifeCard(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                    Text(t('people'),
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 12),
                    if (people.isEmpty) Text(t('empty')),
                    for (final name in people)
                      Padding(
                          padding: const EdgeInsets.symmetric(vertical: 10),
                          child: Text(name == 'Участник' ? t('member') : name)),
                    if (data.nextOffset != null)
                      action('more', busy ? null : more),
                  ])),
              const SizedBox(height: 16),
              LifeCard(
                  padding: EdgeInsets.zero,
                  child: ExpansionTile(
                      title: Text(t('alias_title')),
                      childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                      children: [
                        Text(t('alias_hint')),
                        const SizedBox(height: 12),
                        if (alias != null)
                          Padding(
                              padding: const EdgeInsets.only(bottom: 12),
                              child: Text(
                                  alias == 'Участник' ? t('member') : alias!)),
                        TextField(
                            controller: first,
                            maxLength: 32,
                            autocorrect: false,
                            decoration: InputDecoration(labelText: t('first'))),
                        const SizedBox(height: 12),
                        TextField(
                            controller: initial,
                            maxLength: 1,
                            autocorrect: false,
                            decoration:
                                InputDecoration(labelText: t('initial'))),
                        const SizedBox(height: 12),
                        Wrap(spacing: 8, runSpacing: 8, children: [
                          action('show_name', busy ? null : () => saveAlias(),
                              filled: true),
                          action('hide_name',
                              busy ? null : () => saveAlias(hide: true)),
                        ]),
                      ])),
              const SizedBox(height: 16),
              LifeCard(
                  padding: EdgeInsets.zero,
                  child: ExpansionTile(
                      title: Text(t('claim_title')),
                      childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                      children: [
                        Text(t('claim_hint')),
                        const SizedBox(height: 12),
                        TextField(
                            controller: claim,
                            maxLength: 256,
                            autocorrect: false,
                            keyboardType: TextInputType.url,
                            decoration:
                                InputDecoration(labelText: t('claim_label'))),
                        const SizedBox(height: 12),
                        action('claim_action', busy ? null : accept,
                            filled: true),
                      ])),
            ],
          ],
        ])),
      );
}
