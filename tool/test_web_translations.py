import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


class WebTranslationBuildTests(unittest.TestCase):
    def implementation(self):
        target = Path(__file__).with_name('build_web_translations.py')
        self.assertTrue(target.is_file(), 'reviewed source catalog compiler exists')
        spec = importlib.util.spec_from_file_location('web_translations', target)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_rejects_missing_template_parameter(self):
        module = self.implementation()
        source = {'x': {'values': {'ru': 'Имя: {arg0}'}}}
        with self.assertRaisesRegex(ValueError, 'placeholder'):
            module.checked_strings({'x': 'Name'}, source)

    def test_normalizes_legacy_source_template_without_evaluating_it(self):
        module = self.implementation()
        source = {'x': {'values': {'ru': 'Имя: {arg0}'}, 'template_mapping': {'${user.name}': '{arg0}'}}}
        self.assertEqual(module.checked_strings({'x': 'Name: ${user.name}'}, source), ({'x': 'Name: {arg0}'}, []))

    def test_technical_candidates_are_reported_and_never_inserted_as_ui(self):
        module = self.implementation()
        strings, unused = module.checked_strings({'known': 'Hallo', 'excluded_enum': 'billing'}, {'known': {'values': {'en': 'Hello'}}})
        self.assertEqual(strings, {'known': 'Hallo'})
        self.assertEqual(unused, ['excluded_enum'])


if __name__ == '__main__':
    unittest.main()
