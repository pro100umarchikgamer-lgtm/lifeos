"""Apply mandatory storage privacy settings to generated platform shells."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
android = ROOT / 'android/app/src/main/AndroidManifest.xml'
if android.exists():
    source = android.read_text()
    source = re.sub(r'\s+android:(allowBackup|fullBackupContent|dataExtractionRules)="[^"]*"', '', source)
    source = source.replace('<application', '<application android:allowBackup="false" android:fullBackupContent="false" android:dataExtractionRules="@xml/data_extraction_rules"', 1)
    android.write_text(source)
    rules = ROOT / 'android/app/src/main/res/xml/data_extraction_rules.xml'
    rules.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element('data-extraction-rules')
    for kind in ['cloud-backup', 'device-transfer']:
        node = ET.SubElement(root, kind)
        for domain in ['root', 'file', 'database', 'sharedpref', 'external']:
            ET.SubElement(node, 'exclude', {'domain': domain, 'path': '.'})
    ET.ElementTree(root).write(rules, encoding='utf-8', xml_declaration=True)
    # SQLCipher and encrypted preferences require Android API 23 or newer.
    for extension in ['kts', '']:
        gradle = ROOT / ('android/app/build.gradle' + ('.' + extension if extension else ''))
        if gradle.exists():
            text = gradle.read_text()
            text = re.sub(r'minSdk\s*=\s*flutter.minSdkVersion', 'minSdk = 23', text)
            text = re.sub(r'minSdkVersion\s+flutter.minSdkVersion', 'minSdkVersion 23', text)
            gradle.write_text(text)

    native = ROOT / 'tool/native/android'
    if native.exists():
        import shutil
        target = ROOT / 'android/app/src/main/kotlin/app/lifeos/lifeos'
        target.mkdir(parents=True, exist_ok=True)
        for file in native.glob('*.kt'):
            shutil.copyfile(file, target / file.name)
        source = android.read_text()
        permissions = ['INTERNET', 'POST_NOTIFICATIONS', 'SCHEDULE_EXACT_ALARM', 'RECEIVE_BOOT_COMPLETED', 'VIBRATE', 'WAKE_LOCK', 'FOREGROUND_SERVICE', 'FOREGROUND_SERVICE_MEDIA_PLAYBACK']
        for permission in permissions:
            if f'android.permission.{permission}' not in source:
                source = source.replace('<application', f'<uses-permission android:name="android.permission.{permission}"/>\n    <application', 1)
        if '.ReminderReceiver' not in source:
            source = source.replace('</application>', """<receiver android:name=".ReminderReceiver" android:exported="false">
              <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED"/>
                <action android:name="android.intent.action.MY_PACKAGE_REPLACED"/>
                <action android:name="android.intent.action.TIMEZONE_CHANGED"/>
                <action android:name="android.intent.action.TIME_SET"/>
                <action android:name="android.app.action.SCHEDULE_EXACT_ALARM_PERMISSION_STATE_CHANGED"/>
              </intent-filter>
            </receiver>
            <service android:name=".AlarmService" android:exported="false" android:foregroundServiceType="mediaPlayback"/>
            </application>""")
        android.write_text(source)
        # java.time on API 23, without raising the minimum Android version.
        for extension in ['kts', '']:
            gradle = ROOT / ('android/app/build.gradle' + ('.' + extension if extension else ''))
            if not gradle.exists():
                continue
            text = gradle.read_text()
            if 'isCoreLibraryDesugaringEnabled' not in text and 'coreLibraryDesugaringEnabled' not in text:
                line = 'isCoreLibraryDesugaringEnabled = true' if extension else 'coreLibraryDesugaringEnabled true'
                text = text.replace('compileOptions {', 'compileOptions {\n        ' + line, 1)
                dependency = 'coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.5")' if extension else "coreLibraryDesugaring 'com.android.tools:desugar_jdk_libs:2.1.5'"
                text += '\ndependencies {\n    ' + dependency + '\n}\n'
            gradle.write_text(text)
