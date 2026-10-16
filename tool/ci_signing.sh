#!/usr/bin/env bash
set -euo pipefail
# The secret is passed only via env; never enable shell tracing here.
: "${LIFEOS_TEST_KEYSTORE_BASE64:?Configure the protected GitHub Actions keystore secret first}"
umask 077
keystore="${RUNNER_TEMP:?GitHub runner temporary directory unavailable}/lifeos-signing/debug.keystore"
mkdir -p "$(dirname "$keystore")"
trap 'rm -f "$keystore"' EXIT
printf '%s' "$LIFEOS_TEST_KEYSTORE_BASE64" | base64 --decode > "$keystore"
unset LIFEOS_TEST_KEYSTORE_BASE64
expected=$(tr -d '\r\n' < docs/ANDROID_TEST_CERT.sha256)
[[ "$expected" =~ ^[0-9a-f]{64}$ ]]
actual=$(keytool -exportcert -keystore "$keystore" -storepass android -alias androiddebugkey 2>/dev/null | sha256sum | cut -d' ' -f1)
[[ "$actual" == "$expected" ]] || { echo 'Signing certificate does not match the pinned LifeOS test identity.' >&2; exit 1; }
# Bind the generated Gradle debug configuration to the restored secret explicitly.
grep -Eq 'applicationId = "app.lifeos.lifeos"' android/app/build.gradle.kts
export LIFEOS_DEBUG_KEYSTORE_PATH="$keystore"
python3 - <<'LIFEOS_GRADLE_SIGNING'
from pathlib import Path
p = Path('android/app/build.gradle.kts')
s = p.read_text()
marker = '// LifeOS persistent CI test signing'
if marker not in s:
    s += '''
// LifeOS persistent CI test signing
android {
    signingConfigs {
        getByName("debug") {
            storeFile = file(System.getenv("LIFEOS_DEBUG_KEYSTORE_PATH"))
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }
    buildTypes {
        getByName("release") {
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}
'''
    p.write_text(s)
LIFEOS_GRADLE_SIGNING
[[ "${GITHUB_RUN_ATTEMPT}" -lt 1000 ]]
version_code=$((GITHUB_RUN_NUMBER * 1000 + GITHUB_RUN_ATTEMPT))
[[ "$version_code" -gt 112001 && "$version_code" -le 2147483647 ]]
build_args=(--release --build-number "$version_code")
if [[ -n "${LIFEOS_API_ORIGIN:-}" ]]; then
    python3 tool/validate_api_origin.py
    build_args+=(--dart-define "LIFEOS_API_ORIGIN=$LIFEOS_API_ORIGIN")
fi
flutter build apk "${build_args[@]}"
apk=build/app/outputs/flutter-apk/app-release.apk
sdk_root=${ANDROID_HOME:-${ANDROID_SDK_ROOT:?Android SDK unavailable}}
apksigner=$(find "$sdk_root/build-tools" -mindepth 2 -maxdepth 2 -name apksigner | sort -V | tail -n 1)
"$apksigner" verify --verbose --print-certs "$apk" > apk-certificate.txt
cat apk-certificate.txt
apk_cert=$(python3 - <<'LIFEOS_APK_CERT'
from pathlib import Path
import re
report = Path('apk-certificate.txt').read_text()
expected = Path('docs/ANDROID_TEST_CERT.sha256').read_text().strip()
digests = set(re.findall(
    r'^(?:Signer #1|V[0-9.]+ Signer):? certificate SHA-256 digest: ([0-9a-fA-F]{64})\s*$',
    report, re.MULTILINE))
if not re.search(r'^Number of signers: 1\s*$', report, re.MULTILINE) or {d.lower() for d in digests} != {expected}:
    raise SystemExit('APK certificate mismatch or unsupported signer report.')
print(expected)
LIFEOS_APK_CERT
)
aapt=$(dirname "$apksigner")/aapt
"$aapt" dump badging "$apk" > apk-manifest.txt
grep -q "package: name='app.lifeos.lifeos' versionCode='$version_code'" apk-manifest.txt
grep -q "application-label:'ULADIM'" apk-manifest.txt
printf 'commit=%s\napplicationId=app.lifeos.lifeos\nversionCode=%s\ncertificateSHA256=%s\n' "$GITHUB_SHA" "$version_code" "$apk_cert" > apk-identity.txt
printf 'displayName=ULADIM\napiOrigin=%s\n' "${LIFEOS_API_ORIGIN:-unconfigured}" >> apk-identity.txt
cat apk-identity.txt
