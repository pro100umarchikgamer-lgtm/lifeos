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
