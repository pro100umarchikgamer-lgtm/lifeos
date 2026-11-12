"""Ordinary import hides advanced mapping and presents date ambiguity in place."""
from pathlib import Path
import os
from playwright.sync_api import sync_playwright, expect
from tool.check_web_platform import fixture, login


def main():
    out=Path('web_evidence/import-simple');out.mkdir(parents=True,exist_ok=True)
    with fixture() as (origin,*_),sync_playwright() as p:
        browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
        page=browser.new_page(viewport={'width':1180,'height':900},locale='ru-RU')
        login(page,origin)
        page.evaluate('importStatement()')
        d=page.get_by_role('dialog')
        file=d.locator('input[type=file]')
        file.set_input_files({'name':'clear.csv','mimeType':'text/csv','buffer':b'Date;Amount;Description\n2026-11-12;-2.25;Clear date'})
        expect(d.locator('tbody tr')).to_have_count(1)
        expect(d.locator('details[open]')).to_have_count(0)
        expect(d.locator('.statement-date-help')).to_be_hidden()
        expect(d.locator('select[name=encoding]')).to_be_hidden()
        expect(d.get_by_role('button',name='Импортировать выбранное',exact=True)).to_be_enabled()
        page.screenshot(path=str(out/'ordinary-desktop.png'),full_page=True)
        file.set_input_files({'name':'ambiguous.csv','mimeType':'text/csv','buffer':b'Date;Amount;Description\n04/05/2026;-2.25;Date clarification'})
        expect(d.locator('tbody tr')).to_have_count(1)
        expect(d.locator('.statement-date-help')).to_be_visible()
        expect(d.locator('details[open]')).to_have_count(0)
        expect(d.locator('select[name=dateFormat]')).to_be_visible()
        expect(d.locator('select[name=date]')).to_be_hidden()
        page.set_viewport_size({'width':375,'height':812})
        page.screenshot(path=str(out/'date-clarification-phone.png'),full_page=True)
        d.locator('select[name=dateFormat]').select_option('dmy')
        expect(d.get_by_role('button',name='Импортировать выбранное',exact=True)).to_be_enabled()
        expect(d.locator('tbody')).to_contain_text('2026-05-04')
        page.set_viewport_size({'width':375,'height':812})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(out/'date-choice-phone.png'),full_page=True)
        d.get_by_text('Исправить распознавание',exact=True).click()
        expect(d.locator('select[name=date]')).to_be_visible()
        browser.close()
    print('PASS: automatic import stays simple; ambiguous date has visible shared choice; advanced fields need explicit opening')

if __name__=='__main__':main()
