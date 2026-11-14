import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../app_controller.dart';
import '../notifications/notification_center.dart';
import 'design.dart';
import 'notification_budget_settings.dart';

String _time(AppController c, InboxMessage message) =>
    DateFormat.yMMMd(c.pack.locale.languageCode)
        .add_Hm()
        .format(message.createdAt.toLocal());

class NotificationBell extends StatelessWidget {
  const NotificationBell({super.key, required this.controller});
  final AppController controller;
  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: controller.inbox,
        builder: (context, _) {
          final count = controller.inbox.unreadCount;
          return TextButton.icon(
            key: const Key('notification_bell'),
            onPressed: () => Navigator.push<void>(
                context,
                MaterialPageRoute(
                    builder: (_) =>
                        NotificationInboxPage(controller: controller))),
            style: TextButton.styleFrom(
                minimumSize: const Size(48, 44),
                padding: const EdgeInsets.symmetric(horizontal: 10)),
            icon: Badge(
              isLabelVisible: count > 0,
              label: Text(count > 99 ? '99+' : '$count'),
              child: const Icon(Icons.notifications_outlined, size: 22),
            ),
            label: Text(controller.pack.t('inbox_title')),
          );
        },
      );
}

class NotificationInboxPage extends StatefulWidget {
  const NotificationInboxPage({super.key, required this.controller});
  final AppController controller;
  @override
  State<NotificationInboxPage> createState() => _NotificationInboxPageState();
}

class _NotificationInboxPageState extends State<NotificationInboxPage> {
  bool _unreadOnly = false;
  AppController get c => widget.controller;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => c.inbox.refresh());
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: c.inbox,
        builder: (context, _) {
          final center = c.inbox;
          final messages = center.messages
              .where((m) => !_unreadOnly || center.isUnread(m))
              .toList();
          return Scaffold(
            appBar: AppBar(title: Text(c.pack.t('inbox_title'))),
            body: SafeArea(
                child: Center(
                    child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 720),
              child: RefreshIndicator(
                onRefresh: center.retry,
                child: ListView(
                  key: const Key('notification_inbox'),
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
                  children: [
                    Text(c.pack.t('inbox_description'),
                        style: Theme.of(context).textTheme.bodyMedium),
                    if (center.hasAccount)
                      Align(
                          alignment: Alignment.centerLeft,
                          child: TextButton.icon(
                            key: const Key('inbox_budget_settings'),
                            onPressed: () => Navigator.push<void>(
                                context,
                                MaterialPageRoute(
                                    builder: (_) =>
                                        NotificationBudgetSettingsPage(
                                            controller: c))),
                            icon: const Icon(Icons.tune_rounded, size: 18),
                            label: Text(c.pack.t('inbox_budget_title')),
                          )),
                    const SizedBox(height: 16),
                    Wrap(spacing: 8, runSpacing: 8, children: [
                      ChoiceChip(
                          label: Text(c.pack.t('inbox_history')),
                          selected: !_unreadOnly,
                          onSelected: (_) =>
                              setState(() => _unreadOnly = false)),
                      ChoiceChip(
                          label: Text(
                              '${c.pack.t('inbox_new')} · ${center.unreadCount}'),
                          selected: _unreadOnly,
                          onSelected: (_) =>
                              setState(() => _unreadOnly = true)),
                    ]),
                    if (center.unreadCount > 0)
                      Align(
                          alignment: Alignment.centerLeft,
                          child: TextButton.icon(
                            key: const Key('inbox_mark_all_read'),
                            onPressed: center.markAllRead,
                            icon: const Icon(Icons.done_all_rounded, size: 18),
                            label: Text(c.pack.t('inbox_read_all')),
                          )),
                    if (center.loading)
                      const Padding(
                          padding: EdgeInsets.symmetric(vertical: 12),
                          child: LinearProgressIndicator()),
                    if (center.error != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 12, bottom: 16),
                        child: LifeCard(
                            child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                              Text(c.pack.t(center.error!),
                                  style:
                                      Theme.of(context).textTheme.bodyMedium),
                              const SizedBox(height: 4),
                              TextButton.icon(
                                  onPressed:
                                      center.loading ? null : center.retry,
                                  icon: const Icon(Icons.refresh_rounded),
                                  label: Text(c.pack.t('retry'))),
                            ])),
                      ),
                    if (!center.hasAccount)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        child: Text(c.pack.t('inbox_local_only'),
                            style: Theme.of(context)
                                .textTheme
                                .bodySmall
                                ?.copyWith(
                                    color: Theme.of(context)
                                        .colorScheme
                                        .onSurfaceVariant)),
                      ),
                    if (messages.isEmpty && !center.loading)
                      Padding(
                        padding: const EdgeInsets.symmetric(
                            vertical: 40, horizontal: 12),
                        child: Column(children: [
                          Icon(Icons.notifications_none_rounded,
                              size: 44,
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurfaceVariant),
                          const SizedBox(height: 16),
                          Text(
                              c.pack.t(
                                  _unreadOnly ? 'inbox_no_new' : 'inbox_empty'),
                              textAlign: TextAlign.center,
                              style: Theme.of(context).textTheme.titleMedium),
                          const SizedBox(height: 8),
                          Text(c.pack.t('inbox_empty_hint'),
                              textAlign: TextAlign.center),
                        ]),
                      ),
                    for (final message in messages)
                      Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: _InboxTile(controller: c, message: message),
                      ),
                    if (center.nextBefore != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 20),
                        child: OutlinedButton(
                            onPressed: center.loading
                                ? null
                                : () => center.refresh(loadMore: true),
                            child: Text(c.pack.t('inbox_load_more'))),
                      ),
                  ],
                ),
              ),
            ))),
          );
        },
      );
}

class _InboxTile extends StatelessWidget {
  const _InboxTile({required this.controller, required this.message});
  final AppController controller;
  final InboxMessage message;
  @override
  Widget build(BuildContext context) {
    final c = controller, theme = Theme.of(context);
    final fresh = c.inbox.isUnread(message);
    return Material(
      color: !fresh
          ? theme.colorScheme.surfaceContainerLow
          : theme.colorScheme.primaryContainer.withValues(alpha: .35),
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: BorderSide(color: theme.colorScheme.outlineVariant)),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => Navigator.push<void>(
            context,
            MaterialPageRoute(
                builder: (_) =>
                    NotificationDetailPage(controller: c, message: message))),
        child: Padding(
            padding: const EdgeInsets.all(16),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Icon(
                    message.local
                        ? Icons.alarm_outlined
                        : Icons.campaign_outlined,
                    size: 20,
                    color: theme.colorScheme.primary),
                const SizedBox(width: 10),
                Expanded(
                    child: Text(
                        c.pack.t(message.local
                            ? 'inbox_personal'
                            : 'inbox_from_app'),
                        style: theme.textTheme.labelMedium?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant))),
                if (fresh)
                  Padding(
                      padding: const EdgeInsets.only(left: 8),
                      child: Text(c.pack.t('inbox_new'),
                          style: theme.textTheme.labelSmall?.copyWith(
                              color: theme.colorScheme.primary,
                              fontWeight: FontWeight.w700))),
              ]),
              const SizedBox(height: 10),
              Text(message.title,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: fresh ? FontWeight.w700 : FontWeight.w500)),
              const SizedBox(height: 6),
              Text(message.body,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.bodyMedium
                      ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
              const SizedBox(height: 12),
              Text(_time(c, message),
                  style: theme.textTheme.bodySmall
                      ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
            ])),
      ),
    );
  }
}

class NotificationDetailPage extends StatefulWidget {
  const NotificationDetailPage(
      {super.key,
      required this.controller,
      required this.message,
      this.announcement = false});
  final AppController controller;
  final InboxMessage message;
  final bool announcement;
  @override
  State<NotificationDetailPage> createState() => _NotificationDetailPageState();
}

class _NotificationDetailPageState extends State<NotificationDetailPage> {
  AppController get c => widget.controller;
  String? _linkError;
  late final String? _accountScope;
  @override
  void initState() {
    super.initState();
    _accountScope = c.inbox.accountScope;
    c.inbox.addListener(_changed);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      c.inbox.markRead(widget.message);
      if (widget.announcement) c.inbox.markPresented(widget.message);
    });
  }

  void _changed() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    c.inbox.removeListener(_changed);
    super.dispose();
  }

  void _close() {
    if (widget.announcement) c.inbox.dismiss(widget.message);
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    final m = widget.message, theme = Theme.of(context);
    if (!m.local && _accountScope != c.inbox.accountScope) {
      return Scaffold(
          appBar: AppBar(title: Text(c.pack.t('inbox_title'))),
          body: Center(
              child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Text(c.pack.t('inbox_empty')))));
    }
    return Scaffold(
      key: widget.announcement
          ? const Key('announcement_fullscreen')
          : const Key('notification_detail'),
      appBar: AppBar(
        automaticallyImplyLeading: !widget.announcement,
        title: Text(
            c.pack.t(widget.announcement ? 'inbox_from_app' : 'inbox_title')),
        actions: widget.announcement
            ? [
                IconButton(
                    key: const Key('announcement_close'),
                    tooltip: c.pack.t('close'),
                    onPressed: _close,
                    icon: const Icon(Icons.close_rounded))
              ]
            : null,
      ),
      body: SafeArea(
          child: Center(
              child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 680),
                  child: ListView(
                    padding: const EdgeInsets.fromLTRB(24, 20, 24, 40),
                    children: [
                      Align(
                          alignment: Alignment.centerLeft,
                          child: Container(
                              padding: const EdgeInsets.all(16),
                              decoration: BoxDecoration(
                                  color: theme.colorScheme.primaryContainer,
                                  borderRadius: BorderRadius.circular(22)),
                              child: Icon(
                                  m.local
                                      ? Icons.alarm_outlined
                                      : Icons.campaign_outlined,
                                  size: 30,
                                  color:
                                      theme.colorScheme.onPrimaryContainer))),
                      const SizedBox(height: 24),
                      Text(m.title,
                          style: theme.textTheme.headlineSmall?.copyWith(
                              fontWeight: FontWeight.w700, height: 1.2)),
                      const SizedBox(height: 12),
                      Text(_time(c, m),
                          style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant)),
                      if (m.local && m.status != null)
                        Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Text(c.pack.t('inbox_status_${m.status}'),
                                style: theme.textTheme.labelMedium)),
                      const SizedBox(height: 24),
                      SelectableText(m.body,
                          style:
                              theme.textTheme.bodyLarge?.copyWith(height: 1.6)),
                      if (m.link != null)
                        Padding(
                            padding: const EdgeInsets.only(top: 24),
                            child: OutlinedButton.icon(
                                onPressed: () async {
                                  try {
                                    await c.native.openExternalLink(m.link!);
                                  } catch (_) {
                                    if (mounted) {
                                      setState(() =>
                                          _linkError = 'inbox_link_failed');
                                    }
                                  }
                                },
                                icon: const Icon(Icons.open_in_new_rounded),
                                label: Text(c.pack.t('inbox_open_link')))),
                      if (_linkError != null)
                        Padding(
                            padding: const EdgeInsets.only(top: 12),
                            child: Text(c.pack.t(_linkError!))),
                      if (widget.announcement)
                        Padding(
                            padding: const EdgeInsets.only(top: 32),
                            child: FilledButton(
                                onPressed: _close,
                                child: Text(c.pack.t('inbox_continue')))),
                    ],
                  )))),
    );
  }
}

/// Retains a visible banner after marking it presented, until the person closes it.
class AnnouncementBanner extends StatefulWidget {
  const AnnouncementBanner({super.key, required this.controller});
  final AppController controller;
  @override
  State<AnnouncementBanner> createState() => _AnnouncementBannerState();
}

class _AnnouncementBannerState extends State<AnnouncementBanner> {
  InboxMessage? _message;
  String? _accountScope;
  final _hidden = <String>{};
  AppController get c => widget.controller;
  @override
  Widget build(BuildContext context) => ListenableBuilder(
      listenable: c.inbox,
      builder: (context, _) {
        if (_accountScope != c.inbox.accountScope) {
          _accountScope = c.inbox.accountScope;
          _message = null;
          _hidden.clear();
        }
        _message ??= c.inbox.announcements
            .where((m) => m.presentation == 'banner' && !_hidden.contains(m.id))
            .firstOrNull;
        final message = _message;
        if (message == null || !c.inbox.hasAccount) {
          return const SizedBox.shrink();
        }
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted && ModalRoute.of(context)?.isCurrent == true) {
            c.inbox.markPresented(message);
          }
        });
        return Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: Material(
              color: Theme.of(context).colorScheme.secondaryContainer,
              borderRadius: BorderRadius.circular(18),
              child:
                  Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Expanded(
                    child: InkWell(
                        borderRadius: BorderRadius.circular(18),
                        onTap: () {
                          Navigator.push<void>(
                              context,
                              MaterialPageRoute(
                                  builder: (_) => NotificationDetailPage(
                                      controller: c, message: message)));
                          setState(() {
                            _hidden.add(message.id);
                            _message = null;
                          });
                        },
                        child: Padding(
                            padding: const EdgeInsets.fromLTRB(16, 14, 8, 14),
                            child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(message.title,
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                      style: Theme.of(context)
                                          .textTheme
                                          .titleSmall
                                          ?.copyWith(
                                              fontWeight: FontWeight.w700)),
                                  const SizedBox(height: 4),
                                  Text(c.pack.t('inbox_read_message'),
                                      style: Theme.of(context)
                                          .textTheme
                                          .bodySmall),
                                ])))),
                IconButton(
                    tooltip: c.pack.t('close'),
                    onPressed: () {
                      c.inbox.dismiss(message);
                      setState(() {
                        _hidden.add(message.id);
                        _message = null;
                      });
                    },
                    icon: const Icon(Icons.close_rounded, size: 20)),
              ]),
            ));
      });
}
