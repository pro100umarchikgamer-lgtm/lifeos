import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from tool import check_release_upgrade as upgrade

class ReleaseUpgradeHelpers(unittest.TestCase):
    def test_transient_empty_accessibility_tree_does_not_abort_readiness(self):
        root = ET.fromstring('<hierarchy><node text="Task" enabled="true" clickable="true" bounds="[0,0][100,50]" /></hierarchy>')
        with patch.object(upgrade, 'xml', side_effect=[ET.ParseError('startup'), root]), patch.object(upgrade.time, 'sleep'):
            self.assertEqual(upgrade.find('Task').get('text'), 'Task')

    def test_uid_uses_package_identity_instead_of_dumpsys_format(self):
        with patch.object(upgrade, 'adb', return_value=b'package:app.lifeos.lifeos uid:10123\n'):
            self.assertEqual(upgrade.uid(), '10123')

    def test_different_package_cannot_satisfy_identity_check(self):
        with patch.object(upgrade, 'adb', return_value=b'package:other.app uid:10123\n'):
            with self.assertRaises(RuntimeError):
                upgrade.uid()

    def test_retained_unlabelled_add_button_is_selected_by_actual_bounds(self):
        root=ET.fromstring('<hierarchy><node clickable="true" bounds="[0,1680][200,1810]" /><node clickable="true" bounds="[480,1660][600,1790]" id="add" /></hierarchy>')
        self.assertEqual(upgrade.legacy_add_node(root,1080,1920).get('id'),'add')
