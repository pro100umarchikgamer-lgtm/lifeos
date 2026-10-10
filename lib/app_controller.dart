import 'package:flutter/foundation.dart';

import 'domain/action_engine.dart';
import 'domain/models.dart';
import 'localization/language_pack.dart';

class AppController extends ChangeNotifier {
  AppController(this.store, this.catalog, this.deviceLanguage);
  final ActionStore store;
  final PackCatalog catalog;
  final String deviceLanguage;
  List<Record> records = [];
  Map<String, String> preferences = {};
  final Set<String> pendingTasks = {};
  LanguagePack get pack => catalog.resolve(preferences['language'] ?? deviceLanguage);
  String get currency => preferences['currency'] ?? 'USD';
  String get theme => preferences['theme'] ?? 'system';
  ActionEngine get engine => ActionEngine(store);

  Future<void> load() async {
    preferences = await store.settings();
    await refresh();
  }
  Future<void> refresh() async {
    records = await store.records();
    notifyListeners();
  }
  Future<void> preference(String key, String value) async {
    await store.setSetting(key, value);
    preferences[key] = value;
    notifyListeners();
  }
}
