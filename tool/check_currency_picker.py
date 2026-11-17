"""Shared compact currency search against real forms and a disposable backend."""
from pathlib import Path
import os
import sys
from playwright.sync_api import sync_playwright, expect
from tool.check_web_platform import fixture, login


def main():
    out=Path('web_evidence/currency-picker');out.mkdir(parents=True,exist_ok=True)
    with fixture() as (origin,backend,actor,workspace),sync_playwright() as p:
        browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
        page=browser.new_page(viewport={'width':375,'height':812},locale='ru-RU')
        if '--source-styles' in sys.argv:
            styles=Path('backend/webassets/design.css').read_text()+'\n'+Path('backend/webassets/app/focus.css').read_text()
            page.route('**/assets/design.css',lambda route:route.fulfill(status=200,content_type='text/css',body=styles))
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        login(page,origin)
        page.evaluate("editRecord('account')")
        d=page.get_by_role('dialog')
        currency=d.locator('input[name=currency]')
        picker=d.locator('.currency-picker-list')
        expect(currency).to_have_attribute('role','combobox')
        expect(currency).to_have_value('RUB')
        expect(picker).to_be_hidden()
        currency.click()
        expect(picker).to_be_hidden()
        # A localized search is not yet a committed currency code. Blurring it
        # must not throw in the shared amount/precision change listener.
        currency.fill('узбек')
        d.locator('input[name=name]').click()
        expect(picker).to_be_hidden()
        assert not errors,errors
        currency.fill('узбек')
        expect(picker.get_by_role('option')).to_have_count(1)
        expect(picker).to_contain_text('UZS')
        currency.press('ArrowDown');currency.press('Enter')
        expect(currency).to_have_value('UZS');expect(picker).to_be_hidden()
        toggle=d.get_by_role('button',name='Выбрать валюту',exact=True)
        toggle.click()
        expect(picker).to_be_visible()
        assert picker.get_by_role('option').count()>50
        box=picker.bounding_box();assert box and box['height']<=221,box
        assert box['x']>=0 and box['x']+box['width']<=375,box
        page.screenshot(path=str(out/'phone-compact-open.png'))
        currency.press('Escape');expect(picker).to_be_hidden()
        expect(d).to_be_visible()
        # Typing yields only a few choices; opening the chevron explicitly allows scrolling all.
        currency.fill('');expect(picker.get_by_role('option')).to_have_count(8)
        currency.fill('UZS');currency.press('ArrowDown');currency.press('Enter')
        d.locator('input[name=name]').fill('Synthetic UZS account')
        d.locator('input[name=amount]').fill('2.45')
        d.get_by_role('button',name='Сохранить',exact=True).click()
        expect(d).to_have_count(0)
        rows=backend.pull(actor,workspace,0)['records']
        assert any(row['kind']=='account' and row['data']['name']=='Synthetic UZS account' and row['data']['currency']=='UZS' and row['data']['opening_minor']==245 for row in rows)
        page.set_viewport_size({'width':820,'height':1180})
        page.evaluate("editRecord('account',records('account').find(a=>a.data.currency==='UZS'))")
        d=page.get_by_role('dialog');currency=d.locator('input[name=currency]');picker=d.locator('.currency-picker-list')
        expect(currency).to_have_value('UZS');expect(d.locator('input[name=amount]')).to_have_value('2.45')
        expect(picker).to_be_hidden()
        currency.fill('KWD');currency.press('ArrowDown');currency.press('Enter')
        expect(currency).to_have_value('KWD')
        d.locator('input[name=amount]').fill('1.234')
        d.get_by_role('button',name='Сохранить',exact=True).click();expect(d).to_have_count(0)
        rows=backend.pull(actor,workspace,0)['records']
        assert any(row['kind']=='account' and row['data']['currency']=='KWD' and row['data']['opening_minor']==1234 for row in rows)
        page.evaluate("editRecord('account',records('account').find(a=>a.data.currency==='KWD'))")
        d=page.get_by_role('dialog');currency=d.locator('input[name=currency]');picker=d.locator('.currency-picker-list')
        expect(currency).to_have_value('KWD');expect(picker).to_be_hidden()
        d.get_by_role('button',name='Выбрать валюту',exact=True).click()
        expect(picker).to_be_visible()
        box=picker.bounding_box();assert box and box['height']<=221,box
        page.screenshot(path=str(out/'ipad-compact-open.png'))
        d.locator('input[name=name]').click();expect(picker).to_be_hidden()
        # A readonly currency remains a plain fixed value even if a click is dispatched.
        currency.evaluate('(input)=>{input.readOnly=true}')
        d.locator('.currency-picker-toggle').evaluate('(button)=>button.click()')
        expect(picker).to_be_hidden()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert not errors,errors
        browser.close()
    print('PASS: shared currency search stays compact, keyboard/name/code selection works, UZS/KWD amounts and editing persist, readonly fields stay fixed')


if __name__=='__main__':main()
