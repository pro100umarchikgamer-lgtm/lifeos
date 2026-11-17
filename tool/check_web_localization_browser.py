"""Real source-catalog language switching on disposable loopback records only."""
import json
import os
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright, expect
from tool.check_web_platform import fixture, login
from tool.web_browser_navigation import open_settings, open_tab


def main():
    out = Path('web_evidence/localization')
    out.mkdir(parents=True, exist_ok=True)
    with fixture() as (origin, backend, actor, workspace), sync_playwright() as p:
        operation = {'id': str(uuid4()), 'action': 'record.put', 'record_id': str(uuid4()), 'revision': 0, 'kind': 'task', 'visibility': 'private', 'audience': [], 'data': {'title': 'Поддержка', 'completed': 0, 'assignment': 'any', 'assignees': [], 'review': 0}}
        backend.batch(actor, workspace, [operation])
        browser = p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
        context = browser.new_context(viewport={'width': 390, 'height': 844}, service_workers='block')
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(origin + '/privacy?lang=de#retention')
        expect(page.locator('.help-document')).to_be_visible()
        expect(page.locator('html')).to_have_attribute('lang', 'de')
        assert page.url.endswith('#retention')
        assert 'Конфиденциальность' not in page.locator('h1').inner_text()
        page.evaluate('window.__languageSwitchProof = 731')
        page.locator('.global-language select').select_option('en')
        expect(page.locator('html')).to_have_attribute('lang', 'en')
        expect(page.locator('h1')).to_have_text('Privacy')
        assert page.evaluate('window.__languageSwitchProof') == 731
        assert page.evaluate("JSON.parse(localStorage.getItem('uladim-interface')).lang") == 'en'
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(out / 'privacy_english_mobile.png'), full_page=True)
        page.goto(origin + '/faq?lang=de&lang=en')
        expect(page.locator('.language-query-error')).to_be_visible()
        expect(page.locator('html')).to_have_attribute('lang', 'en')
        assert not errors, errors
        context.close()

        context = browser.new_context(viewport={'width': 390, 'height': 844}, service_workers='block')
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        login(page, origin)
        open_tab(page, 'Профиль')
        open_settings(page, 'appearance')
        page.locator('select[name=language]').select_option('de')
        expect(page.locator('html')).to_have_attribute('lang', 'de')
        page.locator('.nav button[data-tab=tasks][data-section=""]').click()
        expect(page.locator('.task-row').filter(has_text='Поддержка')).to_be_visible()
        assert page.locator('.task-row').filter(has_text='Поддержка').inner_text().find('Поддержка') >= 0
        assert not errors, errors
        page.screenshot(path=str(out / 'german_tasks_original_customer_text.png'), full_page=True)
        browser.close()
    (out / 'checks.json').write_text(json.dumps({'result': 'passed', 'public_native_query_handoff': True, 'duplicate_query_rejected': True, 'same_document_language_switch': True, 'customer_record_text_preserved': True, 'production_mutations': False}, indent=2) + '\n')
    print('LOCALIZATION_REAL_BROWSER_PASS')


if __name__ == '__main__':
    main()
