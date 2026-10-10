#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v flutter >/dev/null 2>&1; then
  printf '%s\n' 'Нужен Flutter SDK. Исходные файлы не изменены.' >&2
  exit 1
fi
task_template=$(mktemp -d)
trap 'rm -rf "$task_template"' EXIT
flutter create --no-pub --platforms=android,ios --org app.lifeos --project-name lifeos "$task_template/platforms"
for platform in android ios; do
  if [[ ! -e "$platform" ]]; then
    cp -R "$task_template/platforms/$platform" "$platform"
  fi
done
python3 tool/configure_platforms.py
