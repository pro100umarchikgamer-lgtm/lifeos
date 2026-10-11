#!/usr/bin/env bash
set -euo pipefail
# The secret is passed only via env; never enable shell tracing here.
: "${LIFEOS_TEST_KEYSTORE_BASE64:?Configure the protected GitHub Actions keystore secret first}"
umask 077
mkdir -p "$HOME/.android"
keystore="$HOME/.android/debug.keystore"
trap 'rm -f "$keystore"' EXIT
printf '%s' "$LIFEOS_TEST_KEYSTORE_BASE64" | base64 --decode > "$keystore"
unset LIFEOS_TEST_KEYSTORE_BASE64
expected=$(tr -d '\r\n' < docs/ANDROID_TEST_CERT.sha256)
[[ "$expected" =~ ^[0-9a-f]{64}$ ]]
actual=$(keytool -exportcert -keystore "$keystore" -storepass android -alias androiddebugkey 2>/dev/null | sha256sum | cut -d' ' -f1)
[[ "$actual" == "$expected" ]] || { echo 'Signing certificate does not match the pinned LifeOS test identity.' >&2; exit 1; }
# Existing Flutter template uses this keystore for debug. Fail if it changes.
grep -Eq 'applicationId = "app.lifeos.lifeos"' android/app/build.gradle.kts
[[ "${GITHUB_RUN_ATTEMPT}" -lt 1000 ]]
version_code=$((GITHUB_RUN_NUMBER * 1000 + GITHUB_RUN_ATTEMPT))
[[ "$version_code" -gt 1 && "$version_code" -le 2147483647 ]]
flutter build apk --debug --build-number "$version_code"
apk=build/app/outputs/flutter-apk/app-debug.apk
sdk_root=${ANDROID_HOME:-${ANDROID_SDK_ROOT:?Android SDK unavailable}}
apksigner=$(find "$sdk_root/build-tools" -mindepth 2 -maxdepth 2 -name apksigner | sort -V | tail -n 1)
"$apksigner" verify --verbose --print-certs "$apk" > apk-certificate.txt
apk_cert=$(sed -n 's/^Signer #1 certificate SHA-256 digest: //p' apk-certificate.txt | tr '[:upper:]' '[:lower:]')
[[ "$apk_cert" == "$expected" ]] || { echo 'APK certificate mismatch.' >&2; exit 1; }
aapt=$(dirname "$apksigner")/aapt
"$aapt" dump badging "$apk" > apk-manifest.txt
grep -q "package: name='app.lifeos.lifeos' versionCode='$version_code'" apk-manifest.txt
printf 'commit=%s\napplicationId=app.lifeos.lifeos\nversionCode=%s\ncertificateSHA256=%s\n' "$GITHUB_SHA" "$version_code" "$apk_cert" > apk-identity.txt
cat apk-identity.txt
