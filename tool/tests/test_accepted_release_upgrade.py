"""The producer must prove an actual accepted312 stage immediately before candidate install."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from tool import check_release_upgrade as upgrade

class AcceptedUpgradeTests(unittest.TestCase):
    def test_accepted_baseline_is_the_exact_published312_bytes(self):
        self.assertEqual(upgrade.ACCEPTED_VERSION,312001)
        self.assertEqual(upgrade.RETAINED_RELEASES[312001],(
            '84b0bdf2c6d54132691d22323553496f6b3b1d43','43367262708',
            '66d123cef79f85b7b2665bdcad0e6309db4a694e9a5076ed871450154c762872'))
    def test_accepted_chain_arguments_are_explicit_and_monotonic(self):
        args=upgrade.arguments(['--baseline','134001','--through-version','303001','--accepted-version','312001','--download'])
        self.assertEqual((args.baseline,args.through_version,args.accepted_version),(134001,303001,312001))
        for values in (['--accepted-file','unknown.apk'],['--baseline','312001','--accepted-version','312001'],['--probe','--accepted-version','312001']):
            with self.subTest(values=values),self.assertRaises(AssertionError):upgrade.arguments(values)
    def test_changed312_bytes_cannot_be_installed_as_accepted_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'old.apk';path.write_bytes(b'changed')
            with patch.object(upgrade,'adb') as adb,self.assertRaisesRegex(AssertionError,'bytes changed'):
                upgrade.accepted_baseline(path,'10001')
            adb.assert_not_called()
    def test_accepted_stage_checks_uid_version_finances_and_creates_new312_task(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'evidence';path=Path(folder)/'old.apk';path.write_bytes(b'test-onlyAPK')
            tree=ET.fromstring('<hierarchy><node text="$100"/><node text="$12.50"/><node text="$87.50"/></hierarchy>')
            def adb(*args,**kwargs):
                if args[0]=='install':return b'Success\n'
                return b'Package app.lifeos.lifeos\n userId=10001\n versionCode=312001\n'
            def screenshot(name):out.mkdir(exist_ok=True);(out/(name+'.png')).write_bytes(b'\x89PNG\r\n\x1a\n')
            with patch.multiple(upgrade,OUT=out,ACCEPTED_SHA256=hashlib.sha256(path.read_bytes()).hexdigest()),patch.object(upgrade,'adb',side_effect=adb) as commands,patch.object(upgrade,'uid',return_value='10001'),patch.object(upgrade,'start'),patch.object(upgrade,'tap') as tap,patch.object(upgrade,'find') as find,patch.object(upgrade,'screenshot',side_effect=screenshot),patch.object(upgrade,'xml',return_value=tree),patch.object(upgrade,'legacy_editor') as editor,patch.object(upgrade,'enter_text') as enter:
                result=upgrade.accepted_baseline(path,'10001')
            self.assertTrue(result['acceptedBaselineTaskAndFinancialDataRetained'])
            self.assertEqual(result['directUpgradeFromVersionCode'],312001)
            self.assertEqual(commands.call_args_list[0].args,('install','-r',str(path)))
            editor.assert_called_once_with('Task');enter.assert_called_once_with(upgrade.ACCEPTED_PROBE)
            self.assertIn((('Tasks',),{}),[(c.args,c.kwargs) for c in tap.call_args_list])
            self.assertEqual([c.args[0] for c in find.call_args_list],[upgrade.PROBE,upgrade.ACCEPTED_PROBE])
            for name in ['accepted-312001-control-task','accepted-312001-finances','accepted-312001-created-task']:
                self.assertTrue((out/(name+'.png')).is_file());self.assertTrue((out/(name+'.xml')).is_file())
            self.assertIn('versionCode=312001',(out/'accepted-312001-package.txt').read_text())
    def test_accepted_stage_rejects_identity_change_before_any_ui_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'old.apk';path.write_bytes(b'test')
            with patch.object(upgrade,'ACCEPTED_SHA256',hashlib.sha256(path.read_bytes()).hexdigest()),patch.object(upgrade,'adb',return_value=b'Success'),patch.object(upgrade,'uid',return_value='other'),patch.object(upgrade,'start') as start,self.assertRaisesRegex(AssertionError,'identity changed'):
                upgrade.accepted_baseline(path,'10001')
            start.assert_not_called()
if __name__=='__main__':unittest.main()
