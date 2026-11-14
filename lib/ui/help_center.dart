import 'package:flutter/material.dart';

import '../domain/public_links.dart';
import 'settings_surfaces.dart';

String helpCenterTitle(String languageTag) =>
    languageTag == 'ru' ? 'Помощь и ответы' : 'Help & answers';

/// Help stays available without a cloud account. Legal documents are opened at
/// the public site so operator and retention details have a single source.
class HelpCenterScreen extends StatefulWidget {
  const HelpCenterScreen({
    super.key,
    required this.languageTag,
    required this.onOpenLink,
  });

  final String languageTag;
  final Future<void> Function(Uri) onOpenLink;

  @override
  State<HelpCenterScreen> createState() => _HelpCenterScreenState();
}

class _HelpCenterScreenState extends State<HelpCenterScreen> {
  final search = TextEditingController();
  String query = '';
  bool get ru => widget.languageTag == 'ru';
  String text(String russian, String english) => ru ? russian : english;

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  Future<void> open(String path) async {
    try {
      await widget.onOpenLink(publicSitePage(path));
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(text('Не удалось открыть ссылку. Повторите попытку.',
              'Could not open the link. Please try again.'))));
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final entries = <_HelpAnswer>[
      _HelpAnswer(
          'today',
          text('Начало работы', 'Getting started'),
          text('С чего начать?', 'Where should I start?'),
          text(
              'Добавьте одну задачу или заметку в личном пространстве. Затем настройте календарь и финансовые счета в удобном вам порядке.',
              'Add one task or note to your personal space. Then set up your calendar and financial accounts in the order that suits you.')),
      _HelpAnswer(
          'sync',
          text('Устройства и записи', 'Devices & records'),
          text('Где мои записи на другом устройстве?',
              'Where are my records on another device?'),
          text(
              'Проверьте аккаунт и выбранное пространство. Для облачной синхронизации нужно соединение. Локальные записи Android не загружаются автоматически только из-за входа в аккаунт.',
              'Check your account and selected space. Cloud sync needs a connection. Signing in alone does not automatically upload all local Android records.')),
      _HelpAnswer(
          'import',
          text('Устройства и записи', 'Devices & records'),
          text('Как перенести записи?', 'How do I import records?'),
          text(
              'В веб-приложении откройте «Профиль → Импорт и синхронизация». Выберите файл, проверьте предпросмотр и подтвердите нужные записи. Исходный файл остаётся у вас.',
              'In the web app, open Profile → Import and sync. Choose a file, review the preview and confirm the records you want. Your source file stays with you.')),
      _HelpAnswer(
          'notifications',
          text('Устройства и записи', 'Devices & records'),
          text('Почему не пришло напоминание?',
              'Why did a reminder not arrive?'),
          text(
              'Проверьте время и часовой пояс события, разрешение уведомлений и настройки батареи устройства. На каждом устройстве уведомления настраиваются отдельно.',
              'Check the event time and time zone, notification permission and device battery settings. Notifications are configured separately on each device.')),
      _HelpAnswer(
          'finances',
          text('Финансы и семья', 'Money & family'),
          text('Приложение переводит деньги?', 'Does the app transfer money?'),
          text(
              'ULADIM ведёт учёт введённых вами сумм. Запись перевода между счетами не перемещает деньги в банке. Проверяйте валюту, суммы и импорт перед сохранением.',
              'ULADIM records the amounts you enter. A transfer between bookkeeping accounts does not move money at a bank. Review currencies, amounts and imports before saving.')),
      _HelpAnswer(
          'family',
          text('Финансы и семья', 'Money & family'),
          text('Кто видит семейные записи?', 'Who can see family records?'),
          text(
              'Доступ зависит от пространства, роли и настроек записи. Личные сведения сохраняйте в личном пространстве. Перед добавлением данных другого человека убедитесь, что вправе ими делиться.',
              'Access depends on the space, member role and record settings. Keep personal information in your personal space. Make sure you have the right to share another person’s data.')),
      _HelpAnswer(
          'security',
          text('Аккаунт и приватность', 'Account & privacy'),
          text('Как защитить аккаунт?', 'How do I protect my account?'),
          text(
              'Используйте уникальный пароль и доступную двухфакторную защиту. Храните резервные коды отдельно. Отзовите доступ потерянного устройства в профиле. Пароль и одноразовые коды не сообщайте никому.',
              'Use a unique password and the available two-factor protection. Keep backup codes safe. Revoke a lost device from your profile. Never share your password or one-time codes.')),
      _HelpAnswer(
          'privacy',
          text('Аккаунт и приватность', 'Account & privacy'),
          text('Есть ли реклама и аналитика?', 'Are there ads or analytics?'),
          text(
              'Рекламной аналитики и рекламных трекеров нет. Для работы используются необходимые сведения аккаунта, записи, которые вы сохраняете, и данные безопасности. Подробности — в политике конфиденциальности.',
              'There are no advertising analytics or advertising trackers. The service uses necessary account details, records you save and security information. Read the privacy policy for details.')),
      _HelpAnswer(
          'deletion',
          text('Аккаунт и приватность', 'Account & privacy'),
          text('Как удалить аккаунт?', 'How do I delete my account?'),
          text(
              'В профиле откройте аккаунт и приватность, затем удаление. Сначала сохраните нужные данные и проверьте общие пространства. Запрос можно отменить в течение 24 часов. Копии на устройствах очищаются отдельно.',
              'Open account and privacy in your profile, then deletion. Save what you need and review shared spaces first. You can cancel the request within 24 hours. Device copies must be cleared separately.')),
      _HelpAnswer(
          'plans',
          text('Доступ и помощь', 'Access & support'),
          text('Нужна ли подписка?', 'Do I need a subscription?'),
          text(
              'Все текущие функции бесплатны. Карта не нужна, покупки отключены. Plus готовится на будущее; окончательные условия ещё не опубликованы. Возможности с искусственным интеллектом пока недоступны.',
              'All current features are free. No card is needed and purchases are disabled. Plus is planned for the future; final terms have not been announced. AI features are not available yet.')),
      _HelpAnswer(
          'support',
          text('Доступ и помощь', 'Access & support'),
          text('Что написать в поддержку?', 'What should I send to support?'),
          text(
              'Опишите действие и сообщение на экране, устройство и версию приложения. Скройте личные сведения на снимке экрана. Не отправляйте пароли, коды, выписки и документы.',
              'Describe the action and message on screen, your device and app version. Hide personal information in screenshots. Do not send passwords, codes, bank statements or identity documents.')),
    ];
    final words = query.toLowerCase().trim().split(RegExp(r'\s+'));
    final visible = entries
        .where((entry) => words.every((word) =>
            '${entry.group} ${entry.question} ${entry.answer}'
                .toLowerCase()
                .contains(word)))
        .toList();
    return Scaffold(
      appBar: settingsAppBar(context, helpCenterTitle(widget.languageTag)),
      body: SafeArea(
        top: false,
        child: ListView(
          padding: settingsPagePadding(context),
          children: [
            Text(text('Найдём ответ', 'Let’s find an answer'),
                style: theme.textTheme.headlineMedium),
            const SizedBox(height: 12),
            Text(
                text(
                    'Короткие подсказки для повседневных дел. Подробные инструкции и документы доступны на сайте.',
                    'Quick help for everyday tasks. Detailed guides and documents are available on the website.'),
                style: theme.textTheme.bodyLarge
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
            const SizedBox(height: 24),
            TextField(
              key: const Key('help_search'),
              controller: search,
              textInputAction: TextInputAction.search,
              decoration: InputDecoration(
                labelText: text('Поиск по вопросам', 'Search questions'),
                prefixIcon: const Icon(Icons.search),
                suffixIcon: query.isEmpty
                    ? null
                    : IconButton(
                        tooltip: text('Очистить поиск', 'Clear search'),
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
                  text('Ответов: ${visible.length}',
                      'Answers: ${visible.length}'),
                  style: theme.textTheme.bodySmall),
            ),
            const SizedBox(height: 12),
            if (visible.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 24),
                child: Text(text(
                    'Подходящего ответа пока нет. Попробуйте другое слово или обратитесь в поддержку.',
                    'No matching answer yet. Try another word or contact support.')),
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
                        label: Text(
                            text('Подробнее на сайте', 'Read more online')),
                      ),
                    ],
                  ),
              ]),
            ],
            const SizedBox(height: 32),
            SettingsGroup(children: [
              SettingsRow(
                title: text('Поддержка', 'Support'),
                icon: Icons.support_agent_outlined,
                onTap: () => open('/support'),
              ),
              SettingsRow(
                title: text('Конфиденциальность', 'Privacy policy'),
                icon: Icons.privacy_tip_outlined,
                onTap: () => open('/privacy'),
              ),
              SettingsRow(
                title: text('Условия использования', 'Terms of use'),
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
