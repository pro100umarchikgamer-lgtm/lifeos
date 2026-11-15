import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/notifications/notification_center.dart';

void main() {
  String translate(String key) =>
      {
        'system_task_reminder': 'Task reminder',
        'system_budget_threshold': 'Budget at {threshold}%',
        'module_budgets': 'Budgets',
      }[key] ??
      key;
  test(
      'system messages follow selected language; announcements and local content stay exact',
      () {
    final task = InboxMessage({
      'id': 'task',
      'kind': 'reminder',
      'title': 'ULADIM',
      'body': 'Напоминание о задаче',
      'message_key': 'system_task_reminder'
    });
    expect(task.localizedBody(translate), 'Task reminder');
    final announcement = InboxMessage({
      'id': 'announcement',
      'kind': 'announcement',
      'title': 'PRIVATE TITLE',
      'body': 'PRIVATE BODY',
      'message_key': 'system_task_reminder'
    });
    expect(announcement.localizedBody(translate), 'PRIVATE BODY');
    expect(announcement.localizedTitle(translate), 'PRIVATE TITLE');
    final personal = InboxMessage(task.data, local: true);
    expect(personal.localizedBody(translate), 'Напоминание о задаче');
    final budget = InboxMessage({
      'id': 'budget',
      'kind': 'budget',
      'title': 'Бюджеты',
      'body': 'Original',
      'title_key': 'module_budgets',
      'message_key': 'system_budget_threshold',
      'message_args': {'threshold': 80}
    });
    expect(budget.localizedTitle(translate), 'Budgets');
    expect(budget.localizedBody(translate), 'Budget at 80%');
    final invalid = InboxMessage({
      ...budget.data,
      'message_args': {'threshold': '<script>'}
    });
    expect(invalid.localizedBody(translate), 'Original');
  });
}
