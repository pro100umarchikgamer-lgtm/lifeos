import 'package:flutter/material.dart';

import '../localization/language_pack.dart';
import '../domain/models.dart';
import '../sync/controller.dart';
import '../sync/contracts.dart';
import 'design.dart';
import 'selection.dart';
import 'account_center.dart';

class FamilyPage extends StatefulWidget {
  const FamilyPage({super.key, required this.controller, required this.pack});
  final FamilyController controller;
  final LanguagePack pack;
  @override
  State<FamilyPage> createState() => _FamilyPageState();
}

class _FamilyPageState extends State<FamilyPage> {
  FamilyController get c => widget.controller;
  String t(String key) => widget.pack.t(key);
  String describe(Object? raw) {
    if (raw == null) return t('family_empty_version');
    final value = object(raw),
        data = value['data'] == null ? value : object(value['data']);
    final parts = <String>[
      (data['body'] ??
              data['title'] ??
              data['name'] ??
              data['label'] ??
              t('family_change'))
          .toString(),
    ];
    if (data['currency'] is String) {
      for (final field in ['amount_minor', 'opening_minor', 'limit_minor']) {
        if (data[field] is int) {
          parts.add(
            Currency.fromCode(data['currency'] as String)
                .format(data[field] as int),
          );
        }
      }
    }
    if (data['date'] != null) parts.add(data['date'].toString());
    if (data['completed'] != null) {
      parts.add(t(data['completed'] == 1 ? 'complete' : 'family_task_undo'));
    }
    if (data['items'] is List) {
      for (final item in data['items'] as List) {
        parts.add(
          '${object(item)['completed'] == true ? '✓' : '○'} ${object(item)['name']}',
        );
      }
    }
    return parts.join('\n');
  }

  final email = TextEditingController(),
      password = TextEditingController(),
      passwordAgain = TextEditingController(),
      code = TextEditingController();
  bool register = false;
  bool showPassword = false;
  String? formError;
  @override
  void initState() {
    super.initState();
  }

  @override
  void dispose() {
    for (final field in [email, password, passwordAgain, code]) {
      field.dispose();
    }
    super.dispose();
  }

  Future<String?> ask(String label, {bool secret = false}) async {
    final field = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(label),
        content: TextField(
          controller: field,
          obscureText: secret,
          autofocus: true,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(t('cancel')),
          ),
          FilledButton(
            onPressed: () =>
                Navigator.pop(context, secret ? field.text : field.text.trim()),
            child: Text(t('save')),
          ),
        ],
      ),
    );
    // Dialog exit animation may still hold the controller for one frame.
    Future<void>.delayed(const Duration(seconds: 1), field.dispose);
    return result;
  }

  Future<void> command(String action, Json values) => c.run(() async {
    await c.family(action, values);
  });
  Future<void> invite() async {
    final mail = await ask(t('family_invite_email'));
    if (mail == null || mail.isEmpty || !mounted) return;
    String role = 'adult';
    String? profile;
    final choice = await showDialog<String>(
      context: context,
      builder: (ctx) => SimpleDialog(
        title: Text(t('family_role')),
        children: [
          for (final r in ['parent', 'adult', 'child'])
            SimpleDialogOption(
              onPressed: () => Navigator.pop(ctx, r),
              child: Text(t('family_$r')),
            ),
        ],
      ),
    );
    if (choice == null || !mounted) return;
    role = choice;
    if (role == 'child') {
      final profiles = (c.roster?['profiles'] as List? ?? [])
          .map(object)
          .toList();
      profile = await showDialog<String>(
        context: context,
        builder: (ctx) => SimpleDialog(
          title: Text(t('family_child')),
          children: [
            for (final p in profiles)
              SimpleDialogOption(
                onPressed: () => Navigator.pop(ctx, p['id'] as String),
                child: Text(p['name'] as String),
              ),
          ],
        ),
      );
      if (profile == null) return;
    }
    Json? result;
    await c.run(() async {
      result = await c.family('invite.create', {
        'email': mail,
        'role': role,
        'profile_id': profile,
      });
    });
    if (result != null && mounted) {
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text(t('family_invitation')),
          content: SelectableText(
            '${t('family_invite_hint')}\n\n${result!['invitation']}',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: Text(t('close')),
            ),
          ],
        ),
      );
    }
  }

  Future<void> child([Json? profile]) async {
    final name = TextEditingController(text: profile?['name'] as String? ?? '');
    final permissions = (profile?['permissions'] as List? ?? ['view_shared'])
        .cast<String>()
        .toSet();
    final save = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, set) => AlertDialog(
          title: Text(t('family_child')),
          content: SizedBox(
            width: 420,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: name,
                    decoration: InputDecoration(labelText: t('family_name')),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    t('ux3_child_presets'),
                    style: Theme.of(ctx).textTheme.titleSmall,
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final preset in {
                        'ux3_preset_simple': ['view_shared', 'complete_tasks'],
                        'ux3_preset_allowance': [
                          'view_shared',
                          'view_budget',
                          'record_spending',
                          'request_money',
                          'complete_tasks',
                          'edit_own',
                        ],
                        'ux3_preset_independent': [
                          'view_shared',
                          'view_budget',
                          'record_spending',
                          'request_money',
                          'create_tasks',
                          'complete_tasks',
                          'edit_own',
                        ],
                      }.entries)
                        ActionChip(
                          label: Text(t(preset.key)),
                          onPressed: () => set(() {
                            permissions
                              ..clear()
                              ..addAll(preset.value);
                          }),
                        ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  for (final p in [
                    'view_budget',
                    'record_spending',
                    'edit_own',
                    'request_money',
                    'view_shared',
                    'create_tasks',
                    'complete_tasks',
                  ])
                    CheckboxListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(t('family_permission_$p')),
                      value: permissions.contains(p),
                      onChanged: (v) => set(() {
                        if (v == true) {
                          permissions.add(p);
                        } else {
                          permissions.remove(p);
                        }
                      }),
                    ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: Text(t('cancel')),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: Text(t('save')),
            ),
          ],
        ),
      ),
    );
    if (save == true) {
      await command('child.save', {
        'profile_id': profile?['id'] ?? FamilyController.uuid.v4(),
        'name': name.text.trim(),
        'permissions': permissions.toList(),
        'revision': profile?['revision'] ?? 0,
      });
    }
    Future<void>.delayed(const Duration(seconds: 1), name.dispose);
  }

  Future<void> confirm(String label, Future<void> Function() action) async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(label),
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
    if (yes == true) await action();
  }

  Future<void> edit([Json? record]) async {
    if (!mounted) return;
    await Navigator.push<void>(
      context,
      MaterialPageRoute(
        builder: (_) => FamilyRecordEditor(
          controller: c,
          pack: widget.pack,
          record: record,
        ),
      ),
    );
  }

  Widget button(String label, VoidCallback action, {IconData? icon}) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: OutlinedButton.icon(
      onPressed: c.busy ? null : action,
      icon: Icon(icon ?? Icons.chevron_right),
      label: Text(t(label)),
    ),
  );
  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: c,
    builder: (context, _) => Scaffold(
      appBar: AppBar(
        toolbarHeight: MediaQuery.textScalerOf(context).scale(20) > 28
            ? 96
            : null,
        title: Text(t('family_account'), maxLines: 2),
      ),
      body: SafeArea(
        child: ListView(
          padding: EdgeInsets.symmetric(
            horizontal: MediaQuery.sizeOf(context).width > 720
                ? (MediaQuery.sizeOf(context).width - 640) / 2
                : 20,
            vertical: 20,
          ),
          children: [
            if (c.busy) const LinearProgressIndicator(),
            if (c.error != null)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text(
                  t('family_error_${c.error}'),
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            if (c.account == null) ...[
              LifeCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.shield_outlined),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            t('ux3_account_title'),
                            style: Theme.of(context).textTheme.titleLarge
                                ?.copyWith(fontWeight: FontWeight.w700),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(t('ux3_account_body')),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              if (c.accountOrigin.isEmpty)
                LifeCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        t('ux3_cloud_unavailable'),
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 8),
                      Text(t('ux3_cloud_unavailable_body')),
                    ],
                  ),
                ),
              const SizedBox(height: 12),
              Text(
                t('family_optional'),
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 12),
              TextButton.icon(
                onPressed: () => Navigator.maybePop(context),
                icon: const Icon(Icons.phone_android),
                label: Text(t('ux3_continue_local')),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 16),
                child: Wrap(
                  spacing: 12,
                  runSpacing: 8,
                  children: [
                    ChoiceChip(
                      label: Text(t('family_login')),
                      selected: !register,
                      onSelected: c.busy
                          ? null
                          : (_) => setState(() => register = false),
                    ),
                    ChoiceChip(
                      label: Text(t('family_register')),
                      selected: register,
                      onSelected: c.busy
                          ? null
                          : (_) => setState(() => register = true),
                    ),
                  ],
                ),
              ),
              Text(t('family_email')),
              const SizedBox(height: 6),
              TextField(
                controller: email,
                keyboardType: TextInputType.emailAddress,
                autofillHints: const [AutofillHints.email],
                textInputAction: TextInputAction.next,
                autocorrect: false,
                decoration: const InputDecoration(),
              ),
              const SizedBox(height: 12),
              Text(t('family_password')),
              const SizedBox(height: 6),
              TextField(
                controller: password,
                obscureText: !showPassword,
                autocorrect: false,
                enableSuggestions: false,
                autofillHints: [
                  register ? AutofillHints.newPassword : AutofillHints.password,
                ],
                decoration: InputDecoration(
                  prefixIcon: const Icon(Icons.lock_outline),
                  suffixIcon: IconButton(
                    tooltip: t(
                      showPassword ? 'ux3_hide_password' : 'ux3_show_password',
                    ),
                    onPressed: () =>
                        setState(() => showPassword = !showPassword),
                    icon: Icon(
                      showPassword
                          ? Icons.visibility_off_outlined
                          : Icons.visibility_outlined,
                    ),
                  ),
                ),
              ),
              if (register) ...[
                const SizedBox(height: 12),
                Text(t('repeat_password')),
                const SizedBox(height: 6),
                TextField(
                  controller: passwordAgain,
                  obscureText: true,
                  autocorrect: false,
                  enableSuggestions: false,
                  decoration: const InputDecoration(),
                ),
              ],
              if (formError != null)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text(t(formError!)),
                ),
              ExpansionTile(
                title: Text(t('family_recovery')),
                children: [
                  Text(t('family_recovery_hint')),
                  TextField(
                    controller: code,
                    decoration: InputDecoration(labelText: t('family_code')),
                  ),
                  TextButton(
                    onPressed: c.busy || c.accountOrigin.isEmpty
                        ? null
                        : () => c.recover(c.accountOrigin, email.text.trim()),
                    child: Text(t('family_recovery_send')),
                  ),
                  TextButton(
                    onPressed: c.busy || c.accountOrigin.isEmpty
                        ? null
                        : () async {
                            await c.resetPassword(
                              c.accountOrigin,
                              email.text.trim(),
                              code.text.trim(),
                              password.text,
                            );
                            if (c.error == null) {
                              password.clear();
                              code.clear();
                            }
                          },
                    child: Text(t('family_recovery_reset')),
                  ),
                ],
              ),
              if (register && c.pendingRegistrationEmail == email.text.trim()) ...[
                Text(t('family_verify_hint')),
                TextField(controller: code, decoration: InputDecoration(labelText: t('family_code')),
                  textInputAction: TextInputAction.done),
                const SizedBox(height: 12),
              ],
              FilledButton(
                onPressed: c.busy || c.accountOrigin.isEmpty
                    ? null
                    : () async {
                        if (register && c.pendingRegistrationEmail != email.text.trim() &&
                            (password.text.length < 7 ||
                                password.text.length > 256)) {
                          setState(
                            () => formError = 'family_error_password_length',
                          );
                          return;
                        }
                        if (register && c.pendingRegistrationEmail != email.text.trim() && password.text != passwordAgain.text) {
                          setState(() => formError = 'password_mismatch');
                          return;
                        }
                        setState(() => formError = null);
                        await c.signIn(
                          c.accountOrigin,
                          email.text.trim(),
                          password.text,
                          register: register,
                          verificationCode: register && c.pendingRegistrationEmail == email.text.trim() ? code.text.trim() : null,
                        );
                        password.clear();
                        passwordAgain.clear();
                      },
                child: Text(t(register ? (c.pendingRegistrationEmail == email.text.trim() ? 'family_verify' : 'family_register') : 'family_login')),
              ),
            ] else ...[
              Text(
                c.account!['email'] as String? ?? t('family_account'),
                style: Theme.of(context).textTheme.titleLarge,
              ),
              button('account_manage', () => Navigator.of(context).push<void>(MaterialPageRoute(
                builder: (_) => AccountCenter(controller: c, pack: widget.pack),
              )), icon: Icons.manage_accounts_outlined),
              button('family_logout', () => c.signOut(), icon: Icons.logout),
              button('family_password_change', () async {
                final old = await ask(t('family_old_password'), secret: true);
                if (old == null || !mounted) return;
                final next = await ask(t('family_new_password'), secret: true);
                if (next != null) await c.password(old, next);
              }),
              if (!c.verified) ...[
                Text(t('family_verify_hint')),
                TextField(
                  controller: code,
                  decoration: InputDecoration(labelText: t('family_code')),
                ),
                button('family_verify', () => c.verify(code.text.trim())),
                button(
                  'ux3_resend_verification',
                  () => c.resendVerification(),
                  icon: Icons.mark_email_unread_outlined,
                ),
              ] else ...[
                LifeHero(
                  icon: Icons.people_outline,
                  title: t('ux3_family_title'),
                  body: t(
                    c.spaces.isEmpty
                        ? 'ux3_family_steps'
                        : 'ux3_family_manage_body',
                  ),
                ),
                const SizedBox(height: 16),
                button('family_sync', () => c.refresh(), icon: Icons.sync),
                button('family_create', () async {
                  final name = await ask(t('family_name'));
                  if (name != null) {
                    await command('workspace.create', {
                      'name': name,
                      'kind': 'family',
                      'workspace_id': FamilyController.uuid.v4(),
                    });
                  }
                }),
                button('family_accept', () async {
                  final value = await ask(t('family_invitation'));
                  if (value != null) await c.accept(value);
                }),
                for (final space in c.spaces)
                  ListTile(
                    title: Text(space['name'] as String),
                    subtitle: Text(t('family_${space['role']}')),
                    selected: c.workspace == space['id'],
                    trailing: const Icon(Icons.chevron_right),
                    onTap: c.busy
                        ? null
                        : () => c.select(space['id'] as String),
                  ),
                if (c.workspace != null) ...[
                  for (final raw in c.roster?['invitations'] as List? ?? [])
                    ListTile(
                      title: Text(object(raw)['email'] as String),
                      subtitle: Text(t('family_${object(raw)['role']}')),
                      trailing: IconButton(
                        icon: const Icon(Icons.cancel_outlined),
                        onPressed: c.busy
                            ? null
                            : () => confirm(
                                t('family_invite_revoke'),
                                () => command('invite.revoke', {
                                  'invitation_id': object(raw)['id'],
                                }),
                              ),
                      ),
                    ),
                  for (final raw in c.roster?['parent_changes'] as List? ?? [])
                    if (object(raw)['target_id'] == c.account!['user_id'])
                      button(
                        'family_consent_approve',
                        () => confirm(
                          t('family_consent_approve'),
                          () => command('parent.change.approve', {
                            'change_id': object(raw)['id'],
                            'revision': object(raw)['revision'],
                          }),
                        ),
                      ),
                  if (c.parent)
                    for (final raw in c.roster?['members'] as List? ?? [])
                      if (object(raw)['role'] == 'parent' &&
                          object(raw)['user_id'] !=
                              c.roster!['space']['creator_id'])
                        button(
                          'family_parent_consent',
                          () => confirm(
                            t('family_parent_consent'),
                            () => command('parent.change.request', {
                              'change_id': FamilyController.uuid.v4(),
                              'user_id': object(raw)['user_id'],
                              'role': 'adult',
                              'revision': object(raw)['revision'],
                            }),
                          ),
                        ),

                  const Divider(),
                  Text(t('family_sync_hint')),
                  Text('${t('family_pending')}: ${c.pending.length}'),
                  if (c.parent) ...[
                    button(
                      'family_invite',
                      invite,
                      icon: Icons.person_add_outlined,
                    ),
                    button(
                      'family_child_add',
                      () => child(),
                      icon: Icons.child_care,
                    ),
                  ],
                  for (final raw in c.roster?['profiles'] as List? ?? [])
                    ListTile(
                      title: Text(object(raw)['name'] as String),
                      subtitle: Text(t('family_child')),
                      onTap: c.parent && !c.busy
                          ? () => child(object(raw))
                          : null,
                    ),
                  for (final raw in c.roster?['members'] as List? ?? []) ...[
                    ListTile(
                      title: Text(t('family_${object(raw)['role']}')),
                      subtitle: object(raw)['user_id'] == c.account!['user_id']
                          ? Text(t('family_you'))
                          : null,
                      trailing:
                          c.parent &&
                              !['parent', 'owner'].contains(object(raw)['role'])
                          ? IconButton(
                              icon: const Icon(Icons.person_remove_outlined),
                              onPressed: c.busy
                                  ? null
                                  : () => confirm(
                                      t('family_remove'),
                                      () => command('member.remove', {
                                        'user_id': object(raw)['user_id'],
                                        'revision': object(raw)['revision'],
                                      }),
                                    ),
                            )
                          : null,
                    ),
                  ],
                  if (c.roster != null)
                    button('family_record_add', () => edit(), icon: Icons.add),
                  for (final issue in c.issues)
                    LifeCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text(t('family_conflict')),
                          Text(t('family_local_version')),
                          SelectableText(describe(issue['operation'])),
                          Text(t('family_server_version')),
                          SelectableText(
                            object(issue['result'])['server'] == null
                                ? t('family_error_${object(issue['result'])['error']}')
                                : describe(object(issue['result'])['server']),
                          ),
                          if (object(issue['result'])['status'] == 'conflict' &&
                              object(issue['result'])['server'] != null)
                            button(
                              'family_keep_local',
                              () => confirm(
                                t('family_keep_local'),
                                () => c.resolve(issue, true),
                              ),
                            ),
                          button(
                            'family_use_server',
                            () => confirm(
                              t('family_use_server'),
                              () => c.resolve(issue, false),
                            ),
                          ),
                        ],
                      ),
                    ),
                  for (final op in c.pending)
                    ListTile(
                      leading: const Icon(Icons.schedule),
                      title: Text(t('family_pending')),
                      subtitle: Text(
                        (op['data']?['title'] ??
                                op['data']?['name'] ??
                                op['data']?['body'] ??
                                op['record_id'])
                            .toString(),
                        maxLines: 2,
                      ),
                    ),
                  for (final record in c.records)
                    ListTile(
                      leading: Icon(
                        record['visibility'] == 'private'
                            ? Icons.lock_outline
                            : Icons.people_outline,
                      ),
                      title: Text(
                        (record['data']['title'] ??
                                record['data']['name'] ??
                                record['data']['label'] ??
                                record['data']['body'] ??
                                t('family_kind_${record['kind']}'))
                            .toString(),
                        maxLines: 3,
                      ),
                      subtitle: Text(t('family_kind_${record['kind']}')),
                      onTap: c.busy ? null : () => edit(record),
                    ),
                  if (c.roster?['space']?['creator_id'] ==
                      c.account!['user_id'])
                    button(
                      'family_dissolve',
                      () => confirm(
                        t('family_dissolve_confirm'),
                        () => command('workspace.dissolve', {
                          'revision': c.roster!['space']['revision'],
                        }),
                      ),
                    )
                  else if (c.roster != null)
                    button(
                      'family_leave',
                      () => confirm(
                        t('family_leave'),
                        () => command('workspace.leave', {
                          'revision': c.roster!['space']['member_revision'],
                        }),
                      ),
                    ),
                ],
              ],
            ],
          ],
        ),
      ),
    ),
  );
}

class FamilyRecordEditor extends StatefulWidget {
  const FamilyRecordEditor({
    super.key,
    required this.controller,
    required this.pack,
    this.record,
    this.initialKind,
    this.initialFlow,
  });
  final FamilyController controller;
  final LanguagePack pack;
  final Json? record;
  final String? initialKind, initialFlow;
  @override
  State<FamilyRecordEditor> createState() => _FamilyRecordEditorState();
}

class _FamilyRecordEditorState extends State<FamilyRecordEditor> {
  void changed() {
    if (mounted) setState(() {});
  }

  String kind = 'note',
      visibility = 'private',
      role = 'adult',
      flow = 'expense',
      period = 'month',
      rollover = 'none',
      assignment = 'any';
  String account = '', from = '', to = '';
  final title = TextEditingController(),
      amount = TextEditingController(text: '0'),
      received = TextEditingController(text: '0'),
      currency = TextEditingController(text: 'RUB'),
      date = TextEditingController(text: dateOnly(DateTime.now())),
      end = TextEditingController(),
      items = TextEditingController(),
      start = TextEditingController(
        text: '${dateOnly(DateTime.now())}T09:00:00',
      ),
      zone = TextEditingController(text: 'Europe/Moscow');
  bool completed = false, saving = false, review = false, allDay = false;
  String repeat = 'none';
  int interval = 1;
  String? repeatUntil;
  final Map<String, bool> itemCompletion = {};
  Set<String> audience = {};
  String? error;
  FamilyController get c => widget.controller;
  String t(String key) => widget.pack.t(key);
  bool get own =>
      widget.record == null ||
      widget.record!['owner_id'] == c.account?['user_id'];
  bool get completionOnly => role == 'child' && !own;
  bool get canEdit => widget.record?['editable'] != false;
  List<Json> get accounts =>
      c.records.where((r) => r['kind'] == 'account').toList();
  int parseAmount(
    TextEditingController field,
    String code, {
    bool signed = false,
    bool zero = false,
  }) {
    final text = field.text.trim();
    if (zero && RegExp(r'^0([.,]0+)?$').hasMatch(text)) return 0;
    final negative = signed && text.startsWith('-');
    return Currency.fromCode(code).parse(negative ? text.substring(1) : text) *
        (negative ? -1 : 1);
  }

  String amountText(int minor, String code) =>
      Currency.fromCode(code).format(minor).split(' ').first;
  @override
  void initState() {
    super.initState();
    c.addListener(changed);
    kind = widget.initialKind ?? kind;
    flow = widget.initialFlow ?? flow;
    role = c.roster?['space']?['role'] as String? ?? 'adult';
    final r = widget.record;
    if (r != null) {
      kind = r['kind'] as String;
      visibility = r['visibility'] as String;
      audience = (r['audience'] as List).cast<String>().toSet();
      final d = object(r['data']);
      title.text = (d['body'] ?? d['title'] ?? d['name'] ?? d['label'] ?? '')
          .toString();
      currency.text = d['currency'] as String? ?? 'RUB';
      amount.text = amountText(
        (d['amount_minor'] ??
                d['opening_minor'] ??
                d['limit_minor'] ??
                d['sent_minor'] ??
                0)
            as int,
        currency.text,
      );
      date.text = (d['date'] ?? d['start_on'] ?? date.text) as String;
      end.text = d['end_on'] as String? ?? '';
      completed = d['completed'] == 1;
      review = d['review'] == 1;
      if (role == 'child' && kind == 'task') {
        final marks = (r['progress'] as List? ?? []).map(object);
        completed =
            marks
                .where(
                  (m) => m['profile_id'] == c.roster?['space']?['profile_id'],
                )
                .firstOrNull?['completed'] ==
            1;
      }
      account = d['account_id'] as String? ?? '';
      from = d['from_id'] as String? ?? '';
      to = d['to_id'] as String? ?? '';
      flow = d['kind'] as String? ?? 'expense';
      period = d['period'] as String? ?? 'month';
      rollover = d['rollover'] as String? ?? 'none';
      assignment = d['assignment'] as String? ?? 'any';
      if (kind == 'transfer') {
        final target = accounts.where((r) => r['id'] == to).firstOrNull;
        received.text = amountText(
          d['received_minor'] as int,
          target?['data']?['currency'] as String? ?? currency.text,
        );
      }
      if (kind == 'shopping') {
        for (final item in d['items'] as List) {
          final value = object(item);
          itemCompletion[value['id'] as String] = value['completed'] as bool;
        }
      }
      if (kind == 'shopping') {
        items.text = (d['items'] as List)
            .map((i) => object(i)['name'])
            .join('\n');
      }
      if (kind == 'event') {
        final schedule = object(d['schedule']);
        start.text = schedule['localStart'] as String;
        zone.text = schedule['timezone'] as String;
        allDay = schedule['allDay'] as bool;
        repeat = schedule['repeat'] as String;
        interval = schedule['interval'] as int;
        repeatUntil = schedule['until'] as String?;
      }
    } else if (role == 'child') {
      if (!c.creatableKinds.contains(kind)) {
        kind = c.creatableKinds.firstOrNull ?? 'transaction';
      }
      flow = 'expense';
      visibility = 'shared';
      audience = {c.roster!['space']['profile_id'] as String};
    }
  }

  @override
  void dispose() {
    c.removeListener(changed);
    for (final field in [
      title,
      amount,
      received,
      currency,
      date,
      end,
      items,
      start,
      zone,
    ]) {
      field.dispose();
    }
    super.dispose();
  }

  Json data() {
    final old = widget.record == null
        ? <String, dynamic>{}
        : object(widget.record!['data']);
    if (completionOnly) return {...old, 'completed': completed ? 1 : 0};
    final code = currency.text.trim().toUpperCase();
    if (title.text.trim().isEmpty &&
        !['transaction', 'transfer', 'request'].contains(kind)) {
      throw const FormatException();
    }
    if (['transaction', 'transfer', 'budget'].contains(kind)) {
      if (dateOnly(DateTime.parse(date.text)) != date.text) {
        throw const FormatException();
      }
    }
    if (kind == 'budget' &&
        period == 'custom' &&
        (dateOnly(DateTime.parse(end.text)) != end.text ||
            end.text.compareTo(date.text) < 0)) {
      throw const FormatException();
    }
    switch (kind) {
      case 'note':
        return {'body': title.text.trim()};
      case 'task':
        return {
          'title': title.text.trim(),
          'completed': role == 'child'
              ? old['completed'] ?? 0
              : completed
              ? 1
              : 0,
          'assignment': assignment,
          'assignees': audience.toList(),
          'review': review ? 1 : 0,
        };
      case 'account':
        return {
          'name': title.text.trim(),
          'currency': code,
          'opening_minor': parseAmount(amount, code, signed: true, zero: true),
        };
      case 'transaction':
        return {
          'kind': flow,
          'label': title.text.trim(),
          'currency': code,
          'amount_minor': parseAmount(amount, code),
          'date': date.text,
          'account_id': account.isEmpty ? null : account,
        };
      case 'transfer':
        final a = accounts.singleWhere((r) => r['id'] == from),
            b = accounts.singleWhere((r) => r['id'] == to);
        return {
          'from_id': from,
          'to_id': to,
          'sent_minor': parseAmount(amount, a['data']['currency'] as String),
          'received_minor': parseAmount(
            received,
            b['data']['currency'] as String,
          ),
          'date': date.text,
        };
      case 'budget':
        return {
          'name': title.text.trim(),
          'currency': code,
          'limit_minor': parseAmount(amount, code, zero: true),
          'period': period,
          'start_on': date.text,
          'end_on': period == 'custom' ? end.text : null,
          'rollover': rollover,
          'participants': audience.toList(),
        };
      case 'event':
        return {
          'title': title.text.trim(),
          'schedule': {
            ...(old['schedule'] == null
                ? {
                    'allDay': false,
                    'repeat': 'none',
                    'interval': 1,
                    'until': null,
                  }
                : object(old['schedule'])),
            'localStart': start.text.trim(),
            'timezone': zone.text.trim(),
            'allDay': allDay,
            'repeat': repeat,
            'interval': interval,
            'until': repeat == 'none' ? null : repeatUntil,
          },
        };
      case 'shopping':
        final prior = (old['items'] as List? ?? []).map(object).toList();
        final lines = items.text
            .split('\n')
            .map((v) => v.trim())
            .where((v) => v.isNotEmpty)
            .toList();
        final used = <String>{};
        return {
          'name': title.text.trim(),
          'items': [for (final name in lines) _item(name, prior, used)],
        };
      case 'request':
        return {
          'profile_id': old['profile_id'] ?? audience.single,
          'amount_minor': parseAmount(amount, code),
          'currency': code,
          'label': title.text.trim(),
          'state': old['state'] ?? 'pending',
          'movement_id': old['movement_id'],
        };
      default:
        throw const SyncFailure('invalid_input');
    }
  }

  Json _item(String name, List<Json> prior, Set<String> used) {
    final match = prior
        .where((i) => i['name'] == name && !used.contains(i['id']))
        .firstOrNull;
    if (match != null) {
      used.add(match['id'] as String);
      return {
        ...match,
        'completed': itemCompletion[match['id']] ?? match['completed'],
      };
    }
    return {
      'id': FamilyController.uuid.v4(),
      'name': name,
      'completed': false,
      'quantity': '',
    };
  }

  Future<void> save() async {
    setState(() => saving = true);
    try {
      if (completionOnly && kind == 'task') {
        await action('task.complete', {
          'profile_id': c.roster!['space']['profile_id'],
          'completed': completed,
        });
        return;
      }
      await c.enqueue({
        'id': FamilyController.uuid.v4(),
        'action': 'record.put',
        'record_id': widget.record?['id'] ?? FamilyController.uuid.v4(),
        'revision': widget.record?['revision'] ?? 0,
        'kind': kind,
        'visibility': visibility,
        'audience': audience.toList(),
        'data': data(),
      });
      if (mounted && (c.error == null || c.error == 'offline')) {
        Navigator.pop(context);
      }
    } catch (_) {
      if (mounted) setState(() => error = 'invalid_input');
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  Future<void> action(String name, Json extra) async {
    final r = widget.record!;
    await c.enqueue({
      'id': FamilyController.uuid.v4(),
      'action': name,
      'record_id': r['id'],
      'revision': r['revision'],
      ...extra,
    });
    if (mounted && (c.error == null || c.error == 'offline')) {
      Navigator.pop(context);
    }
  }

  Future<void> delete() async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(t('family_delete')),
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
    if (yes == true) await action('record.delete', {});
  }

  Future<void> grant(bool revoke) async {
    final members = (c.roster?['members'] as List? ?? [])
        .map(object)
        .where((m) => m['user_id'] != c.account!['user_id'])
        .toList();
    final target = await showDialog<String>(
      context: context,
      builder: (ctx) => SimpleDialog(
        title: Text(t(revoke ? 'family_revoke' : 'family_grant')),
        children: [
          for (final m in members)
            SimpleDialogOption(
              onPressed: () => Navigator.pop(ctx, m['user_id'] as String),
              child: Text(
                '${t('family_${m['role']}')} · ${members.indexOf(m) + 1}',
              ),
            ),
        ],
      ),
    );
    if (target != null && mounted) {
      final edit = revoke
          ? false
          : await showDialog<bool>(
              context: context,
              builder: (ctx) => SimpleDialog(
                title: Text(t('family_grant')),
                children: [
                  SimpleDialogOption(
                    onPressed: () => Navigator.pop(ctx, false),
                    child: Text(t('family_grant_read')),
                  ),
                  SimpleDialogOption(
                    onPressed: () => Navigator.pop(ctx, true),
                    child: Text(t('family_grant_edit')),
                  ),
                ],
              ),
            );
      if (edit == null) return;
      await action('record.grant', {
        'user_id': target,
        'can_edit': edit,
        'revoke': revoke,
      });
    }
  }

  Future<void> fulfill() async {
    final transfers = c.records.where((r) => r['kind'] == 'transfer').toList();
    final target = await showDialog<String>(
      context: context,
      builder: (ctx) => SimpleDialog(
        title: Text(t('family_fulfill')),
        children: [
          for (final r in transfers)
            SimpleDialogOption(
              onPressed: () => Navigator.pop(ctx, r['id'] as String),
              child: Text(
                '${r['data']['date']} · ${Currency.fromCode(accounts.where((a) => a['id'] == r['data']['to_id']).firstOrNull?['data']?['currency'] as String? ?? 'RUB').format(r['data']['received_minor'] as int)}',
              ),
            ),
        ],
      ),
    );
    if (target != null) {
      await action('request.fulfill', {'movement_id': target});
    }
  }

  Widget dateControl(
    TextEditingController value,
    String label, {
    bool timestamp = false,
  }) {
    final current = DateTime.tryParse(value.text) ?? DateTime.now();
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: OutlinedButton.icon(
        icon: const Icon(Icons.calendar_today_outlined),
        label: Text(
          '${t(label)}: ${MaterialLocalizations.of(context).formatMediumDate(current)}',
        ),
        onPressed: () async {
          final chosen = await showDatePicker(
            context: context,
            initialDate: current,
            firstDate: DateTime(1900),
            lastDate: DateTime(2200),
          );
          if (chosen != null && mounted) {
            setState(
              () => value.text = timestamp
                  ? '${dateOnly(chosen)}T${current.hour.toString().padLeft(2, '0')}:${current.minute.toString().padLeft(2, '0')}:00'
                  : dateOnly(chosen),
            );
          }
        },
      ),
    );
  }

  Widget field(
    TextEditingController controller,
    String label, {
    int lines = 1,
  }) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(t(label), style: Theme.of(context).textTheme.bodyMedium),
        const SizedBox(height: 6),
        TextField(
          controller: controller,
          maxLines: lines,
          keyboardType: ['amount', 'family_received'].contains(label)
              ? const TextInputType.numberWithOptions(
                  decimal: true,
                  signed: true,
                )
              : TextInputType.text,
          decoration: const InputDecoration(),
        ),
      ],
    ),
  );
  Widget select(
    String label,
    String value,
    Map<String, String> choices,
    void Function(String) change,
  ) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: LifeSelect<String>(
      label: t(label),
      value: value,
      choices: choices,
      onChanged: (v) => setState(() => change(v)),
    ),
  );
  @override
  Widget build(BuildContext context) {
    final choices = {for (final k in c.creatableKinds) k: t('family_kind_$k')};
    final accountChoices = {
      '': t('family_none'),
      for (final r in accounts)
        r['id'] as String: '${r['data']['name']} (${r['data']['currency']})',
    };
    return Scaffold(
      appBar: AppBar(
        toolbarHeight: MediaQuery.textScalerOf(context).scale(20) > 28
            ? 96
            : null,
        title: Text(t('family_record_add'), maxLines: 2),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (widget.record == null && choices.isNotEmpty)
              select('family_record_type', kind, choices, (v) => kind = v),
            if (!completionOnly) ...[
              if (kind != 'transfer')
                field(
                  title,
                  ['transaction', 'request'].contains(kind)
                      ? 'label_optional'
                      : 'family_name',
                  lines: kind == 'note' ? 5 : 1,
                ),
              if ([
                'account',
                'transaction',
                'request',
                'budget',
              ].contains(kind)) ...[
                field(currency, 'currency'),
                field(amount, 'amount'),
              ],
              if (['transaction', 'budget', 'transfer'].contains(kind))
                dateControl(
                  date,
                  kind == 'budget' ? 'family_start' : 'family_date',
                ),
              if (kind == 'transaction') ...[
                if (role != 'child')
                  select('family_record_type', flow, {
                    'expense': t('family_expense'),
                    'income': t('family_income'),
                  }, (v) => flow = v),
                select('family_account_select', account, accountChoices, (v) {
                  account = v;
                  if (v.isNotEmpty) {
                    currency.text =
                        accounts.singleWhere(
                              (r) => r['id'] == v,
                            )['data']['currency']
                            as String;
                  }
                }),
              ],
              if (kind == 'transfer') ...[
                select('family_from', from, accountChoices, (v) => from = v),
                select('family_to', to, accountChoices, (v) => to = v),
                field(amount, 'amount'),
                field(received, 'family_received'),
              ],
              if (kind == 'budget') ...[
                select('family_period', period, {
                  for (final p in ['week', 'month', 'year', 'custom'])
                    p: t('family_$p'),
                }, (v) => period = v),
                if (period == 'custom') dateControl(end, 'family_end'),
                select('family_rollover', rollover, {
                  for (final p in ['none', 'positive', 'negative', 'both'])
                    p: t('family_roll_$p'),
                }, (v) => rollover = v),
              ],
              if (kind == 'event') ...[
                dateControl(start, 'family_date', timestamp: true),
                if (!allDay)
                  OutlinedButton.icon(
                    icon: const Icon(Icons.schedule),
                    label: Text(
                      MaterialLocalizations.of(context).formatTimeOfDay(
                        TimeOfDay.fromDateTime(DateTime.parse(start.text)),
                      ),
                    ),
                    onPressed: () async {
                      final before = DateTime.parse(start.text);
                      final time = await showTimePicker(
                        context: context,
                        initialTime: TimeOfDay.fromDateTime(before),
                      );
                      if (time != null && mounted) {
                        setState(
                          () => start.text =
                              '${dateOnly(before)}T${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}:00',
                        );
                      }
                    },
                  ),
                SwitchListTile(
                  title: Text(t('all_day')),
                  value: allDay,
                  onChanged: (v) => setState(() => allDay = v),
                ),
                select('repeat', repeat, {
                  for (final r in [
                    'none',
                    'daily',
                    'weekly',
                    'monthly',
                    'yearly',
                  ])
                    r: t('repeat_$r'),
                }, (v) => repeat = v),
                if (repeat != 'none') ...[
                  select('repeat_interval', '$interval', {
                    for (final i in {1, 2, 3, 4, 6, 12, interval}) '$i': '$i',
                  }, (v) => interval = int.parse(v)),
                  OutlinedButton(
                    onPressed: () async {
                      final chosen = await showDatePicker(
                        context: context,
                        initialDate: DateTime.parse(
                          repeatUntil != null &&
                                  repeatUntil!.compareTo(
                                        start.text.substring(0, 10),
                                      ) >=
                                      0
                              ? repeatUntil!
                              : start.text,
                        ),
                        firstDate: DateTime.parse(start.text),
                        lastDate: DateTime(2200),
                      );
                      if (chosen != null && mounted) {
                        setState(() => repeatUntil = dateOnly(chosen));
                      }
                    },
                    child: Text(
                      '${t('repeat_until')}: ${repeatUntil ?? t('no_limit')}',
                    ),
                  ),
                  if (repeatUntil != null)
                    TextButton(
                      onPressed: () => setState(() => repeatUntil = null),
                      child: Text(t('no_limit')),
                    ),
                ],
                field(zone, 'family_timezone'),
              ],
              if (kind == 'shopping') field(items, 'family_items', lines: 8),
              if (kind == 'task')
                select('family_assignment', assignment, {
                  for (final p in ['single', 'each', 'joint', 'any'])
                    p: t('family_$p'),
                }, (v) => assignment = v),
            ],
            if (kind == 'shopping')
              for (final item
                  in widget.record?['data']?['items'] as List? ?? [])
                CheckboxListTile(
                  title: Text(object(item)['name'] as String),
                  value: itemCompletion[object(item)['id']] ?? false,
                  onChanged: (v) => setState(
                    () => itemCompletion[object(item)['id'] as String] = v!,
                  ),
                ),
            if (kind == 'task' && role != 'child')
              SwitchListTile(
                title: Text(t('family_review_required')),
                value: review,
                onChanged: (v) => setState(() => review = v),
              ),
            if (kind == 'task' &&
                role == 'child' &&
                own &&
                widget.record != null)
              OutlinedButton(
                onPressed: c.busy
                    ? null
                    : () => action('task.complete', {
                        'profile_id': c.roster!['space']['profile_id'],
                        'completed': !completed,
                      }),
                child: Text(t(completed ? 'family_task_undo' : 'complete')),
              ),
            if (kind == 'task' && c.parent)
              for (final raw in widget.record?['progress'] as List? ?? [])
                ListTile(
                  title: Text(
                    (c.roster?['profiles'] as List? ?? [])
                                .map(object)
                                .where(
                                  (p) => p['id'] == object(raw)['profile_id'],
                                )
                                .firstOrNull?['name']
                            as String? ??
                        t('family_child'),
                  ),
                  subtitle: Text(
                    t(
                      object(raw)['approved'] == 1
                          ? 'complete'
                          : 'family_review_pending',
                    ),
                  ),
                  trailing:
                      object(raw)['completed'] == 1 &&
                          object(raw)['approved'] == 0
                      ? TextButton(
                          onPressed: c.busy
                              ? null
                              : () => action('task.review', {
                                  'profile_id': object(raw)['profile_id'],
                                  'completed': true,
                                }),
                          child: Text(t('confirm')),
                        )
                      : null,
                ),
            if (kind == 'task')
              CheckboxListTile(
                title: Text(t('complete')),
                value: completed,
                onChanged: (v) => setState(() => completed = v!),
              ),
            if (role != 'child' && own) ...[
              select('family_visibility', visibility, {
                'private': t('family_private'),
                'shared': t('family_shared'),
              }, (v) => visibility = v),
              if (visibility == 'shared')
                for (final raw in c.roster?['profiles'] as List? ?? [])
                  CheckboxListTile(
                    title: Text(object(raw)['name'] as String),
                    value: audience.contains(object(raw)['id']),
                    onChanged: (v) => setState(() {
                      if (v == true) {
                        audience.add(object(raw)['id'] as String);
                      } else {
                        audience.remove(object(raw)['id']);
                      }
                    }),
                  ),
            ],
            if (error != null) Text(t('family_error_$error')),
            if (c.error != null) Text(t('family_error_${c.error}')),
            const SizedBox(height: 16),
            FilledButton(
              onPressed:
                  saving ||
                      c.busy ||
                      !canEdit ||
                      widget.record == null && choices.isEmpty
                  ? null
                  : save,
              child: Text(t('save')),
            ),
            if (widget.record != null) ...[
              if (kind == 'request' &&
                  c.parent &&
                  widget.record!['data']['state'] == 'pending')
                OutlinedButton(
                  onPressed: c.busy ? null : fulfill,
                  child: Text(t('family_fulfill')),
                ),
              if (own && visibility == 'private') ...[
                OutlinedButton(
                  onPressed: c.busy ? null : () => grant(false),
                  child: Text(t('family_grant')),
                ),
                OutlinedButton(
                  onPressed: c.busy ? null : () => grant(true),
                  child: Text(t('family_revoke')),
                ),
              ],
              OutlinedButton(
                onPressed: c.busy || !canEdit ? null : delete,
                child: Text(t('delete')),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
