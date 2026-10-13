#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH=. python3 tool/serve_family_test_backend.py &
family_test_pid=$!
trap 'kill "$family_test_pid" 2>/dev/null || true' EXIT
adb -s emulator-5554 reverse tcp:8787 tcp:8787
python3 - <<'PY'
import socket,time
for attempt in range(30):
    try:
        with socket.create_connection(('127.0.0.1',8787),timeout=1):
            break
    except OSError:
        time.sleep(.25)
else:
    raise SystemExit('Disposable family backend did not start')
PY
flutter test integration_test/offline_storage_test.dart integration_test/offline_expansion_test.dart integration_test/family_sync_storage_test.dart integration_test/family_two_client_test.dart -d emulator-5554
