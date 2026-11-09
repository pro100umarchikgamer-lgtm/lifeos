#!/usr/bin/env bash
set -euo pipefail
mkdir -p web_evidence
PYTHONPATH=. python3 tool/serve_family_test_backend.py > web_evidence/android-fixture-backend.log 2>&1 &
family_test_pid=$!
cleanup() {
  ci_exit_status=$?
  if (( ci_exit_status != 0 )); then
    adb devices -l > web_evidence/android-devices.txt 2>&1 || true
    adb -s emulator-5554 reverse --list > web_evidence/android-reverse.txt 2>&1 || true
    adb -s emulator-5554 logcat -d -t 250 '*:E' > web_evidence/android-errors.txt 2>&1 || true
  fi
  kill "$family_test_pid" 2>/dev/null || true
  exit "$ci_exit_status"
}
trap cleanup EXIT
timeout 60s adb -s emulator-5554 wait-for-device
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
# All four original suites (nine tests), with one debug test-app installation.
# Bound launcher hangs while leaving time to retain transport diagnostics.
timeout --signal=TERM --kill-after=15s 14m flutter test integration_test/ci_encrypted_suite_test.dart -d emulator-5554 --reporter expanded
