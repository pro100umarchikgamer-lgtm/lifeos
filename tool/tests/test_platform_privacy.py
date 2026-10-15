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
            self.assertEqual(app.attrib[namespace + 'label'], 'ULADIM')
            self.assertEqual(app.attrib[namespace + 'allowBackup'], 'false')
            self.assertEqual(app.attrib[namespace + 'fullBackupContent'], 'false')
            rules = ET.parse(root / 'android/app/src/main/res/xml/data_extraction_rules.xml')
            for category in ['cloud-backup', 'device-transfer']:
                domains = {node.attrib['domain'] for node in rules.findall(category + '/exclude')}
                self.assertEqual(domains, {'root', 'file', 'database', 'sharedpref', 'external'})
            self.assertIn('minSdk = 23', gradle.read_text())

    def test_native_components_permissions_and_desugaring_are_injected_once(self):
        source = (ROOT / 'tool/configure_platforms.py').read_text()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / 'android/app/src/main/AndroidManifest.xml'
            manifest.parent.mkdir(parents=True)
            manifest.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application><activity android:name=".MainActivity" /></application></manifest>')
            gradle = root / 'android/app/build.gradle.kts'
            gradle.write_text('android { compileOptions { } defaultConfig { minSdk = flutter.minSdkVersion } }')
            native = root / 'tool/native/android'
            native.mkdir(parents=True)
            (native / 'MainActivity.kt').write_text((ROOT / 'tool/native/android/MainActivity.kt').read_text())
            (native / 'ReminderRuntime.kt').write_text((ROOT / 'tool/native/android/ReminderRuntime.kt').read_text())
            injected = source.replace("ROOT = Path(__file__).resolve().parents[1]", 'ROOT = Path(test_root)')
            for _ in range(2):
                exec(compile(injected, 'configure_platforms.py', 'exec'), {'test_root': directory})
            xml = ET.parse(manifest)
            ns = '{http://schemas.android.com/apk/res/android}'
            permissions = [e.attrib[ns+'name'] for e in xml.findall('uses-permission')]
            self.assertEqual(len(permissions),len(set(permissions)))
            self.assertIn('android.permission.SCHEDULE_EXACT_ALARM',permissions)
            self.assertNotIn('android.permission.USE_EXACT_ALARM',permissions)
            receivers = xml.findall('application/receiver')
            self.assertEqual(len(receivers),1)
            self.assertEqual(receivers[0].attrib[ns+'exported'],'false')
            actions = {e.attrib[ns+'name'] for e in receivers[0].findall('intent-filter/action')}
            self.assertIn('android.intent.action.BOOT_COMPLETED',actions)
            self.assertIn('android.intent.action.TIMEZONE_CHANGED',actions)
            self.assertEqual(gradle.read_text().count('isCoreLibraryDesugaringEnabled'),1)
            self.assertEqual(gradle.read_text().count('coreLibraryDesugaring('),1)
            self.assertTrue((root / 'android/app/src/main/kotlin/app/lifeos/lifeos/ReminderRuntime.kt').exists())
