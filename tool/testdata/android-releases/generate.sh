#!/bin/sh
# Generate tiny Android packages containing only a binary manifest. The disposable
# keystore is deleted after signing. Set FRAMEWORK_RES to android.jar or framework-res.apk.
set -eu
target=$(cd "$(dirname "$0")" && pwd)
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
cd "$scratch"
keytool -genkeypair -alias fixture -keystore fixture.p12 -storepass fixture-only -keypass fixture-only -keyalg RSA -keysize 2048 -validity 3650 -dname 'CN=ULADIM isolated test fixture'
for name in first second wrong-package; do
  package=app.lifeos.lifeos
  version=400002
  case "$name" in second) version=400003;; wrong-package) package=app.fixture.other;; esac
  cat > AndroidManifest.xml <<EOF
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="$package" android:versionCode="$version" android:versionName="1.2.3">
  <uses-sdk android:minSdkVersion="24" android:targetSdkVersion="34"/>
  <application android:hasCode="false" android:label="ULADIM fixture"/>
</manifest>
EOF
  "${AAPT:-aapt}" package -f -M AndroidManifest.xml -I "${FRAMEWORK_RES:-/usr/share/android-framework-res/framework-res.apk}" -F unsigned.apk
  "${APKSIGNER:-apksigner}" sign --ks fixture.p12 --ks-pass pass:fixture-only --v4-signing-enabled false --out "$target/$name.apk" unsigned.apk
done
keytool -exportcert -keystore fixture.p12 -storepass fixture-only -alias fixture | sha256sum | cut -d' ' -f1 > "$target/certificate.sha256"
