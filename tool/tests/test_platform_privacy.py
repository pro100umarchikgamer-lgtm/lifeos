from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]

class PlatformPrivacyTests(unittest.TestCase):
    def test_configurator_disables_automatic_backup_and_is_repeatable(self):
        source = (ROOT / 'tool/configure_platforms.py').read_text()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / 'android/app/src/main/AndroidManifest.xml'
            manifest.parent.mkdir(parents=True)
            manifest.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application android:allowBackup="true" android:label="LifeOS" /></manifest>')
            gradle = root / 'android/app/build.gradle.kts'
            gradle.write_text('android { defaultConfig { minSdk = flutter.minSdkVersion } }')
            injected = source.replace("ROOT = Path(__file__).resolve().parents[1]", 'ROOT = Path(test_root)')
            for _ in range(2):
                exec(compile(injected, 'configure_platforms.py', 'exec'), {'test_root': directory})
            app = ET.parse(manifest).find('application')
            namespace = '{http://schemas.android.com/apk/res/android}'
            self.assertEqual(app.attrib[namespace + 'allowBackup'], 'false')
            self.assertEqual(app.attrib[namespace + 'fullBackupContent'], 'false')
            rules = ET.parse(root / 'android/app/src/main/res/xml/data_extraction_rules.xml')
            for category in ['cloud-backup', 'device-transfer']:
                domains = {node.attrib['domain'] for node in rules.findall(category + '/exclude')}
                self.assertEqual(domains, {'root', 'file', 'database', 'sharedpref', 'external'})
            self.assertIn('minSdk = 23', gradle.read_text())
