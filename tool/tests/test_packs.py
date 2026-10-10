import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('packs', ROOT / 'tool/validate_packs.py')
packs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packs)

class PackTests(unittest.TestCase):
    def test_installed_packs_are_complete_and_compatible(self):
        self.assertGreaterEqual(packs.validate(), 2)

    def test_launch_scope_is_fifteen_languages_with_two_uzbek_scripts(self):
        targets = packs.read(ROOT / 'tool/launch_locales.json')
        self.assertEqual(len(targets), 16)
        self.assertEqual(len({tag.split('-')[0] for tag in targets}), 15)
        self.assertIn('uz-Latn', targets)
        self.assertIn('uz-Cyrl', targets)

    def test_incomplete_launch_cannot_pass_release_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'en.json').write_text((ROOT / 'assets/locales/en.json').read_text())
            with self.assertRaisesRegex(ValueError, 'missing launch locales'):
                packs.validate(release=True, directory=path)

    def test_bad_keys_plural_placeholders_and_versions_rejected(self):
        base = packs.read(ROOT / 'assets/locales/en.json')
        cases = []
        missing = copy.deepcopy(base)
        del missing['strings']['save']
        cases.append(missing)
        placeholder = copy.deepcopy(base)
        placeholder['plurals']['record_count']['other'] = '{amount} records'
        cases.append(placeholder)
        incompatible = copy.deepcopy(base)
        incompatible['schemaVersion'] = 99
        cases.append(incompatible)
        for invalid in cases:
            with self.subTest(pack=invalid), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                (path / 'en.json').write_text(json.dumps(base))
                invalid['locale'] = 'test'
                (path / 'test.json').write_text(json.dumps(invalid))
                with self.assertRaises(ValueError):
                    packs.validate(directory=path)
