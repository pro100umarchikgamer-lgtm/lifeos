import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import 'family_sync_storage_test.dart' as sync_storage;
import 'family_two_client_test.dart' as two_clients;
import 'offline_expansion_test.dart' as expansion;
import 'offline_storage_test.dart' as storage;

// Keep all original suites and assertions in one app installation. Creating the
// binding before groups keeps its final result reporting scoped to the full run.
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  group('Encrypted offline storage', storage.main);
  group('Offline finance expansion', expansion.main);
  group('Encrypted synchronization queue', sync_storage.main);
  group('Two real encrypted clients', two_clients.main);
}
