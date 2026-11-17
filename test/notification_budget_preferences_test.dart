import 'package:flutter_test/flutter_test.dart';
import 'package:lifeos/notifications/notification_center.dart';
import 'package:lifeos/sync/contracts.dart';
import 'notification_center_test.dart' show InboxCache, InboxApi;

class BudgetInboxApi extends InboxApi {
  Json settings = {
    'budget_enabled': false,
    'budget_thresholds': [50, 80, 100],
    'timezone': 'UTC'
  };
  @override
  Future<Json> request(String path, {Json? body}) async {
    if (path == '/v1/account/inbox/settings') {
      if (offline) throw const SyncFailure('offline');
      if (body != null) settings = clone(body);
      return clone(settings);
    }
    return super.request(path, body: body);
  }
}

void main() {
  test(
      'budget preferences default off, queue offline, restore and stay account scoped',
      () async {
    final cache = InboxCache();
    final api = BudgetInboxApi();
    final c = NotificationCenter(cache: cache);
    await c.initialize();
    await c.attachAccount('https://a.test|alice', api);
    await c.loadBudgetSettings();
    expect(c.budgetEnabled, isFalse);
    expect(c.budgetThresholds, [50, 80, 100]);
    api.offline = true;
    await c.saveBudgetSettings(
        enabled: true,
        thresholds: [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        timezone: 'Europe/Moscow');
    await c.refresh();
    expect(c.budgetEnabled, isTrue);
    c.dispose();
    final restored = NotificationCenter(cache: cache);
    await restored.initialize();
    await restored.attachAccount('https://a.test|alice', api);
    expect(restored.budgetEnabled, isTrue);
    expect(
        restored.budgetThresholds, [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]);
    api.offline = false;
    await restored.refresh();
    expect(api.settings['budget_enabled'], isTrue);
    expect(api.settings['timezone'], 'Europe/Moscow');
    await restored.attachAccount('https://a.test|bob', BudgetInboxApi());
    expect(restored.budgetEnabled, isFalse);
    expect(restored.budgetThresholds, [50, 80, 100]);
    restored.dispose();
  });
  test(
      'a failed encrypted settings write preserves disabled state and sends nothing',
      () async {
    final cache = InboxCache();
    final api = BudgetInboxApi();
    final c = NotificationCenter(cache: cache);
    await c.initialize();
    await c.attachAccount('https://a.test|alice', api);
    cache.failWrites = true;
    await c.saveBudgetSettings(
        enabled: true, thresholds: [50, 80, 100], timezone: 'UTC');
    expect(c.budgetEnabled, isFalse);
    expect(api.settings['budget_enabled'], isFalse);
    expect(c.budgetError, 'inbox_storage_failed');
    c.dispose();
  });
}
