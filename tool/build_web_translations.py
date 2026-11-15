#!/usr/bin/env python3
"""Compile reviewed source-only UI catalogs. Never reads application/customer data."""
import argparse
import json
import re
from pathlib import Path

TOKEN = re.compile(r'\{([A-Za-z_][\w.]*)\}')


def checked_strings(strings, source):
    if not isinstance(strings, dict):
        raise ValueError('translation strings must be an object')
    result, unused = {}, []
    for key, value in strings.items():
        if key not in source:
            unused.append(key)
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError('empty or non-string translation: ' + key)
        row = source[key]
        for old, new in row.get('template_mapping', {}).items():
            value = value.replace(old, new)
        base = row['values'].get('en') or row['values'].get('ru') or next(iter(row['values'].values()))
        if set(TOKEN.findall(value)) != set(TOKEN.findall(base)):
            raise ValueError('placeholder mismatch: ' + key)
        result[key] = value
    return result, sorted(unused)


def build(repo, translations):
    manifest = json.loads((repo / 'tool/web_i18n_source.json').read_text())
    data = {key: manifest[key] for key in ('schemaVersion', 'languages', 'source', 'groups', 'required')}
    data['translations'] = {}
    coverage = {}
    for lang in manifest['languages']:
        path = translations / (lang + '.json')
        strings, unused = {}, []
        if path.is_file():
            raw = json.loads(path.read_text())
            if raw.get('schemaVersion') != 1 or raw.get('locale') != lang:
                raise ValueError('wrong translation schema/locale: ' + lang)
            strings, unused = checked_strings(raw.get('strings'), manifest['source'])
        data['translations'][lang] = strings
        native = json.loads((repo / 'assets/locales' / (lang + '.json')).read_text())['strings']
        missing = [key for key in manifest['required'] if key not in strings and not manifest['source'][key]['values'].get(lang) and not (manifest['source'][key].get('native_key') in native)]
        coverage[lang] = {'required': len(manifest['required']), 'covered': len(manifest['required']) - len(missing), 'translated_file_keys': len(strings), 'missing': missing, 'unused_candidate_keys': unused}
    return data, coverage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--translations-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--coverage', type=Path)
    parser.add_argument('--require-complete', action='store_true', help='Fail if any supported language needs a fallback')
    parser.add_argument('--check', action='store_true', help='Compare the bundled catalog without rewriting it')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    data, coverage = build(repo, args.translations_dir)
    output = args.output or repo / 'backend/webassets/app/translations.json'
    encoded=json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'
    if args.coverage:
        args.coverage.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({lang: {'covered': row['covered'], 'required': row['required'], 'missing': len(row['missing'])} for lang, row in coverage.items()}))
    if args.require_complete and any(row['missing'] for row in coverage.values()):
        raise SystemExit('Incomplete translations: reviewed strings are required for every supported language')
    if args.check:
        if not output.is_file() or output.read_text()!=encoded:
            raise SystemExit('Bundled translations differ from reviewed source catalogs; rebuild before release')
    else:
        output.write_text(encoded)


if __name__ == '__main__':
    main()
