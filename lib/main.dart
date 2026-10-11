import 'package:flutter/material.dart';
import 'package:timezone/data/latest.dart' as timezone;

import 'app_controller.dart';
import 'data/local_store.dart';
import 'domain/models.dart';
import 'localization/language_pack.dart';
import 'ui/app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  timezone.initializeTimeZones();
  final catalog = await PackCatalog.load();
  await launch(catalog);
}

Future<void> launch(PackCatalog catalog) async {
  final language = WidgetsBinding.instance.platformDispatcher.locale.toLanguageTag();
  LocalStore? store;
  try {
    store = await LocalStore.open();
    final controller = AppController(store, catalog, language);
    await controller.load();
    runApp(LifeOSApp(controller: controller));
  } catch (error) {
    await store?.close();
    final pack = catalog.resolve(language);
    final key = error is DomainFailure ? error.key : 'storage_unavailable';
    runApp(MaterialApp(home: Scaffold(body: SafeArea(child: Center(child: Padding(
      padding: const EdgeInsets.all(24), child: Column(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.lock_outline, size: 48),
        const SizedBox(height: 16), Text(pack.t(key), textAlign: TextAlign.center),
        const SizedBox(height: 16), FilledButton(onPressed: () => launch(catalog), child: Text(pack.t('retry'))),
      ])))))));
  }
}
