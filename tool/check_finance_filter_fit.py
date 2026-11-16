"""Check real finance filter geometry; optional Chromium intrinsic-size stress.

Uses disposable synthetic records, never production. --intrinsic-stress is a
Chromium surrogate for larger native iPad date controls, not a Safari test.
"""
import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import sync_playwright, expect
from tool.check_web_platform import fixture, login
from tool.web_browser_navigation import open_tab, open_finance_section


def source_styles():
    root = Path('backend/webassets')
    base = (root / 'design.css').read_text().split('/* FOCUS_VISUAL_LAYERS */')[0].rstrip()
    layers = ['app/focus.css', 'app/workspace-sections.css', 'public-focus.css',
              'app/import-presentation.css', 'app/reference.css', 'app/reference-workspaces.css',
              'app/reference-account.css', 'app/reference-auth.css', 'app/experience.css', 'app/refinements.css']
    return base + '\n' + '\n'.join((root / name).read_text() for name in layers)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', default='chromium', choices=['chromium', 'webkit'])
    parser.add_argument('--intrinsic-stress', action='store_true')
    parser.add_argument('--built-styles', action='store_true')
    parser.add_argument('--output', default='web_evidence/finance-filter-fit')
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    checks = []
    failures = []
    with fixture(https=True) as (origin, backend, actor, wid), sync_playwright() as p:
        account_id = str(uuid4())
        backend.batch(actor, wid, [{'id': str(uuid4()), 'action': 'record.put', 'record_id': account_id,
            'revision': 0, 'kind': 'account', 'visibility': 'private', 'audience': [],
            'data': {'name': 'Основной накопительный счёт для семейных расходов и путешествий — длинное имя',
                     'currency': 'RUB', 'opening_minor': 0}}])
        options = {'executable_path': os.environ['ULADIM_CHROMIUM']} if args.engine == 'chromium' and os.environ.get('ULADIM_CHROMIUM') else {}
        browser = getattr(p, args.engine).launch(**options)
        context = browser.new_context(viewport={'width': 1280, 'height': 960}, locale='ru-RU',
                                      service_workers='block', reduced_motion='reduce', ignore_https_errors=True)
        if not args.built_styles or args.intrinsic_stress:
            css = Path('backend/webassets/design.css').read_text() if args.built_styles else source_styles()
            if args.intrinsic_stress:
                # Simulate a larger platform-native date minimum, without changing CSP.
                css = 'input[type=date][name]{min-inline-size:18em;box-sizing:content-box}\n' + css
            context.route('**/assets/design.css', lambda route: route.fulfill(status=200, content_type='text/css', body=css))
        page = context.new_page()
        login(page, origin)
        open_tab(page, 'Финансы')
        open_finance_section(page, 'ledger')
        panel = page.locator('.finance-filter-panel')
        panel.locator('summary').click()
        expect(panel.locator('.finance-filters')).to_be_visible()
        for width in (820, 1024, 1280):
            page.set_viewport_size({'width': width, 'height': 960})
            for filled in (False, True):
                for theme in ('light', 'dark'):
                    page.evaluate('(theme) => {state.theme=theme;document.body.dataset.theme=theme}', theme)
                    panel.locator('input[name=finance-from]').fill('2026-11-01' if filled else '')
                    panel.locator('input[name=finance-to]').fill('2026-11-30' if filled else '')
                    panel.locator('select[name=finance-account]').select_option(account_id)
                    values = panel.locator('.finance-filters').evaluate('''grid => {
                        const rect = el => {const r=el.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width}};
                        const fields=[...grid.querySelectorAll('input,select')].map(field=>{const el=field.choiceField?.querySelector('button.field-menu-trigger')||field;return {name:field.name,box:rect(el),parent:rect(el.parentElement),value:field.value};});
                        const overflow=document.documentElement.scrollWidth>innerWidth;
                        const offenders=overflow ? [...document.body.querySelectorAll('*')].filter(el=>{
                            const r=el.getBoundingClientRect(),s=getComputedStyle(el);
                            return r.width>0 && s.visibility!=='hidden' && s.display!=='none' &&
                                (r.right>innerWidth+1 || r.x < -1 || el.scrollWidth>el.clientWidth+1);
                        }).map(el=>({tag:el.tagName,id:el.id,classes:el.className,name:el.getAttribute('name'),
                            box:rect(el),clientWidth:el.clientWidth,scrollWidth:el.scrollWidth,
                            overflowX:getComputedStyle(el).overflowX,
                            text:el.textContent.trim().slice(0,120)})).slice(0,80) : [];
                        return {grid:rect(grid),fields,overflow,viewport:innerWidth,
                            documentWidth:document.documentElement.scrollWidth,offenders};
                    }''')
                    defects = []
                    for field in values['fields']:
                        box, parent = field['box'], field['parent']
                        if box['x'] < parent['x'] - 1 or box['right'] > parent['right'] + 1:
                            defects.append(field['name'] + ':outside-wrapper')
                        if box['x'] < values['grid']['x'] - 1 or box['right'] > values['grid']['right'] + 1:
                            defects.append(field['name'] + ':outside-panel')
                    for index, a in enumerate(values['fields']):
                        for b in values['fields'][index + 1:]:
                            x_overlap = min(a['box']['right'], b['box']['right']) - max(a['box']['x'], b['box']['x'])
                            y_overlap = min(a['box']['bottom'], b['box']['bottom']) - max(a['box']['y'], b['box']['y'])
                            if x_overlap > 1 and y_overlap > 1:
                                defects.append(a['name'] + ':overlaps:' + b['name'])
                    if values['overflow']:
                        defects.append('document:horizontal-overflow')
                    row = {'width': width, 'filled': filled, 'theme': theme, 'defects': defects, **values}
                    checks.append(row)
                    if defects:
                        failures.append(row)
                        if not filled and theme == 'light':
                            page.screenshot(path=str(out / f'overflow-{width}.png'), full_page=True)
                    if width == 1280 and filled and theme == 'light':
                        page.screenshot(path=str(out / 'finance-filters.png'))
        browser.close()
    report = {'engine': args.engine, 'intrinsic_stress': args.intrinsic_stress, 'checks': checks, 'failures': failures}
    (out / 'checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    assert not failures, f'{len(failures)}/{len(checks)} filter states overlap or overflow; see {out}/checks.json'
    print(f'FINANCE_FILTER_FIT_OK {len(checks)} states; {args.engine}; intrinsic_stress={args.intrinsic_stress}')


if __name__ == '__main__':
    main()
