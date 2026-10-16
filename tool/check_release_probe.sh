#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == true ]]; then
  python3 tool/check_release_upgrade.py --candidate "$RUNNER_TEMP/uladim-candidate.apk"
else
  python3 tool/check_release_upgrade.py --probe --candidate "$RUNNER_TEMP/uladim-112001.apk"
fi
