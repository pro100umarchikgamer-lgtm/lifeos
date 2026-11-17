import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from tool import check_release_upgrade as upgrade


class ManualTimezoneDevice:
    """Model the asynchronous settings/service boundary, not an Android app."""
    def __init__(self, *, ignored=0, unsupported=False, automatic_delay=0):
        self.zone = 'Etc/UTC'
        self.automatic = True
        self.ignored = ignored
        self.unsupported = unsupported
        self.automatic_delay = automatic_delay
        self.requests = []
        self.commands = []

    def adb(self, *args, **kwargs):
        self.commands.append(args)
        command = args[1:]
        if command[:3] == ('settings', 'put', 'global'):
            # The setting write alone need not have reached the detector yet.
            return b''
        if command[:2] == ('settings', 'get'):
            return b'0\n'
        if command[:2] == ('cmd', 'time_zone_detector'):
            if command[2] == 'set_auto_detection_enabled':
                self.automatic = False
                return b'Automatic detection disabled\n'
            if command[2] == 'is_auto_detection_enabled':
                if self.automatic_delay:
                    self.automatic_delay -= 1
                    return b'true\n'
                return str(self.automatic).lower().encode() + b'\n'
            if command[2] == 'suggest_manual_time_zone':
                if self.unsupported:
                    raise upgrade.subprocess.CalledProcessError(1, args, output=b'Unknown command: suggest_manual_time_zone\n')
                self.requests.append(command[-1])
                if not self.automatic and len(self.requests) > self.ignored:
                    self.zone = command[-1]
                return b'Manual suggestion received\n'
        if command[:3] == ('cmd', 'alarm', 'set-timezone'):
            self.requests.append(command[-1])
            if not self.automatic and len(self.requests) > self.ignored:
                self.zone = command[-1]
            return b'Alarm request received\n'
        if command == ('getprop', 'persist.sys.timezone'):
            return self.zone.encode() + b'\n'
        if command[:2] in [('dumpsys', 'time_zone_detector'), ('cmd', 'time_zone_detector')]:
            return b'Synthetic timezone service diagnostic\n'
        raise AssertionError('Unexpected timezone command: ' + repr(args))


class ReleaseUpgradeHelpers(unittest.TestCase):
    def timezone_case(self, device, *, fails=False, zone='Europe/Moscow'):
        elapsed = [0.0]
        def advance(seconds): elapsed[0] += seconds
        with tempfile.TemporaryDirectory() as folder, patch.object(upgrade, 'OUT', Path(folder)), \
                patch.object(upgrade, 'adb', side_effect=device.adb), \
                patch.object(upgrade.time, 'sleep', side_effect=advance), \
                patch.object(upgrade.time, 'monotonic', side_effect=lambda: elapsed[0]):
            if fails:
                with self.assertRaisesRegex(AssertionError, 'timezone mismatch'):
                    upgrade.device_timezone(zone)
            else:
                upgrade.device_timezone(zone)
            return json.loads((Path(folder) / ('timezone-' + zone.replace('/', '_') + '.json')).read_text())

    def test_timezone_waits_for_manual_detector_mode_before_setting(self):
        device = ManualTimezoneDevice(automatic_delay=2)
        report = self.timezone_case(device)
        self.assertEqual(device.zone, 'Europe/Moscow')
        self.assertFalse(device.automatic)
        self.assertTrue(report['verified'])
        self.assertEqual(report['requested'], 'Europe/Moscow')

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
        device = ManualTimezoneDevice()
        report = self.timezone_case(device)
        self.assertTrue(all(sample['manual'] for sample in report['samples']))
        self.assertEqual(report['actual'], 'Europe/Moscow')
        self.assertFalse(device.automatic)

    def test_fixture_waits_for_asynchronous_timezone_acknowledgement(self):
        report = self.timezone_case(ManualTimezoneDevice(ignored=2))
        self.assertEqual(report['attempts'], 2)
        self.assertEqual([sample['actual'] for sample in report['samples'][-2:]],
                         ['Europe/Moscow', 'Europe/Moscow'])

    def test_fixture_rejects_ignored_timezone_change(self):
        report = self.timezone_case(ManualTimezoneDevice(ignored=99), fails=True)
        self.assertFalse(report['verified'])
        self.assertEqual(report['actual'], 'Etc/UTC')
        self.assertEqual(report['attempts'], 3)

    def test_timezone_keeps_failed_setter_output_and_uses_verified_manual_fallback(self):
        report = self.timezone_case(ManualTimezoneDevice(unsupported=True))
        failure = next(row for row in report['commands'] if row['returncode'] == 1)
        self.assertIn('Unknown command', failure['output'])
        self.assertEqual(report['actual'], 'Europe/Moscow')
        self.assertTrue(any(row['command'][:3] == ['cmd', 'alarm', 'set-timezone']
                            for row in report['commands']))

    def test_acknowledged_ignored_manual_suggestion_uses_alarm_fallback(self):
        report = self.timezone_case(ManualTimezoneDevice(ignored=1))
        self.assertEqual(report['attempts'], 1)
        self.assertEqual(report['actual'], 'Europe/Moscow')
        self.assertTrue(any(row['command'][:3] == ['cmd', 'alarm', 'set-timezone']
                            for row in report['commands']))

    def test_timezone_never_suggests_manual_zone_while_detector_reports_automatic(self):
        device = ManualTimezoneDevice(automatic_delay=99)
        report = self.timezone_case(device, fails=True)
        self.assertFalse(report['verified'])
        self.assertEqual(device.requests, [])

    def test_timezone_verifies_both_moscow_and_utc_transitions(self):
        device = ManualTimezoneDevice()
        self.assertEqual(self.timezone_case(device)['actual'], 'Europe/Moscow')
        self.assertEqual(self.timezone_case(device, zone='Etc/UTC')['actual'], 'Etc/UTC')

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


class NativeNotificationEvidence(unittest.TestCase):
    def report(self,package=upgrade.APP,channel='lifeos.important',tag='test',importance=4,active=True):
        record=f"    NotificationRecord(0x123: pkg={package} user=UserHandle{{0}} id=1 tag={tag} importance={importance} key=0|{package}|1|{tag}|10123: Notification(channel={channel} shortcut=null))\n"
        return 'Current Notification Manager state:\n  Notification List:\n'+(record if active else '')+'  Enqueued Notification List:\n  Historical notifications:\n'+record

    def test_requires_active_high_priority_test_notification_from_exact_app(self):
        upgrade.verify_active_test_notification(self.report())
        for changes in ({'package':'other.app'},{'package':upgrade.APP+'.other'},{'channel':'lifeos.standard'},{'channel':'lifeos.important.other'},{'tag':'test.other'},{'importance':3},{'active':False}):
            with self.subTest(changes=changes),self.assertRaises(AssertionError):
                upgrade.verify_active_test_notification(self.report(**changes))

    def test_missing_os_list_does_not_become_delivery_success(self):
        with self.assertRaisesRegex(AssertionError,'active notification list'):
            upgrade.verify_active_test_notification('Notification service unavailable')

    def test_local_retained_apk_must_match_independently_pinned_signed_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'303001.apk';source.write_bytes(b'verified-signed-apk')
            release=('source','run',hashlib.sha256(source.read_bytes()).hexdigest())
            with patch.dict(upgrade.os.environ,{'RUNNER_TEMP':folder}),patch.dict(upgrade.RETAINED_RELEASES,{303001:release}):
                self.assertEqual(upgrade.previous(303001,source).read_bytes(),source.read_bytes())
                source.write_bytes(b'different-signed-apk')
                with self.assertRaisesRegex(AssertionError,'bytes changed'):
                    upgrade.previous(303001,source)
