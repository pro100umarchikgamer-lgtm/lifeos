import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from tool import check_release_upgrade as upgrade

class ReleaseUpgradeHelpers(unittest.TestCase):
    def financial_tree(self, income='$100', expense='$12.50', difference='$87.50'):
        root=ET.Element('hierarchy')
        for value in (income,expense,difference):ET.SubElement(root,'node',{'content-desc':value})
        return root

    def test_finance_retention_accepts_compact_whole_currency_format(self):
        upgrade.verify_financial_summary(self.financial_tree())
        upgrade.verify_financial_summary(self.financial_tree(income='$100.00'))

    def test_finance_retention_rejects_numeric_substring_and_wrong_precision(self):
        for amount in ('$1100.00','$1000','$100.001'):
            with self.subTest(amount=amount), self.assertRaises(AssertionError):
                upgrade.verify_financial_summary(self.financial_tree(income=amount))

    def test_finance_retention_requires_both_records_and_their_exact_net(self):
        for values in ({'income':'$99.99'},{'expense':'$12.51'},{'difference':'$0'},{'difference':'$-87.50'}):
            with self.subTest(values=values), self.assertRaises(AssertionError):
                upgrade.verify_financial_summary(self.financial_tree(**values))

    def test_finance_retention_cannot_mix_another_currency(self):
        with self.assertRaises(AssertionError):
            upgrade.verify_financial_summary(self.financial_tree(income='€100.00'))

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

    def test_fixture_disables_automatic_timezone_before_setting_and_verifies_it(self):
        with patch.object(upgrade, 'adb', side_effect=[b'', b'', b'Europe/Moscow\n']) as adb:
            upgrade.device_timezone('Europe/Moscow')
            self.assertEqual(adb.call_args_list[0].args, ('shell','settings','put','global','auto_time_zone','0'))
            self.assertEqual(adb.call_args_list[1].args, ('shell','cmd','alarm','set-timezone','Europe/Moscow'))
    def test_fixture_waits_for_asynchronous_timezone_acknowledgement(self):
        with patch.object(upgrade, 'adb', side_effect=[b'', b'', b'Etc/UTC\n', b'Europe/Moscow\n']) as adb, patch.object(upgrade.time, 'sleep') as sleep, patch.object(upgrade.time, 'monotonic', return_value=0):
            upgrade.device_timezone('Europe/Moscow')
            sleep.assert_called_once_with(0.25)
            self.assertEqual(adb.call_count, 4)

    def test_fixture_rejects_ignored_timezone_change(self):
        with patch.object(upgrade, 'adb', side_effect=[b'', b'', b'Etc/UTC\n']), patch.object(upgrade.time, 'monotonic', side_effect=[0, 11]):
            with self.assertRaisesRegex(AssertionError, 'timezone mismatch'):
                upgrade.device_timezone('Europe/Moscow')

    def test_saved_task_below_calendar_is_revealed_without_skipping_assertion(self):
        empty = ET.fromstring('<hierarchy />')
        task = ET.fromstring('<hierarchy><node content-desc="ULADIM_upgrade_probe_112001" enabled="true" bounds="[0,0][100,50]" /></hierarchy>')
        with patch.object(upgrade, 'xml', side_effect=[empty, task]), patch.object(upgrade, 'scroll') as scroll, patch.object(upgrade.time, 'sleep'):
            self.assertEqual(upgrade.find(upgrade.PROBE, reveal=True).get('content-desc'), upgrade.PROBE)
            scroll.assert_called_once_with()

    def test_editor_replaces_input_and_requires_exact_fixture_value_before_save(self):
        with patch.object(upgrade, 'tap'), patch.object(upgrade, 'adb') as adb, patch.object(upgrade, 'find', return_value=ET.fromstring('<node text="expected" />')):
            upgrade.enter_text('expected')
            self.assertEqual(adb.call_args_list[1].args, ('shell','input','keyevent',*(['KEYCODE_DEL']*64)))
    def test_editor_rejects_prefixed_input_instead_of_hiding_a_record_mismatch(self):
        with patch.object(upgrade, 'tap'), patch.object(upgrade, 'adb'), patch.object(upgrade, 'find', return_value=ET.fromstring('<node text="Yexpected" />')):
            with self.assertRaisesRegex(AssertionError, 'Fixture text mismatch'):
                upgrade.enter_text('expected')
