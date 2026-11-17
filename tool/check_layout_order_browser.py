"""Keyboard/touch list ordering against real records and layout persistence.

The isolated helper uses a test bridge to LayoutPreferences; parent owns HTTP
routing/CSRF integration. No production access or financial record edits.
"""
import os
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright, expect
from backend.layout_preferences import LayoutPreferences
from tool.check_finance_filter_fit import source_styles
from tool.check_web_platform import fixture, login
from tool.web_browser_navigation import open_tab, open_finance_section


def main():
    out=Path('web_evidence/layout-order');out.mkdir(parents=True,exist_ok=True)
    with fixture() as (origin,backend,actor,wid),sync_playwright() as p:
        for name in ('Накопления','Путешествия'):
            backend.batch(actor,wid,[{'id':str(uuid4()),'action':'record.put','record_id':str(uuid4()),'revision':0,
                'kind':'account','visibility':'private','audience':[],
                'data':{'name':name,'currency':'RUB','opening_minor':12505}}])
        prefs=LayoutPreferences(backend);revision=0
        def save(ids):
            nonlocal revision
            result=prefs.put(actor,wid,'account',ids,revision)
            revision=result['revision'];return result
        browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
        context=browser.new_context(viewport={'width':820,'height':1180},locale='ru-RU',has_touch=True,service_workers='block',reduced_motion='reduce')
        css=source_styles();helper=Path('backend/webassets/app/layout-order.js').read_text()
        context.route('**/assets/design.css',lambda route:route.fulfill(status=200,content_type='text/css',body=css))
        context.route('**/app/assets/layout-order.js',lambda route:route.fulfill(status=200,content_type='text/javascript',body=helper))
        page=context.new_page();page.expose_function('syntheticLayoutSave',save)
        login(page,origin);open_tab(page,'Финансы');open_finance_section(page,'accounts')
        page.add_script_tag(url=origin+'/app/assets/layout-order.js')
        def mount(order):
            page.evaluate('''order=>{
                const container=document.querySelector('.finance-accounts');
                const nodes=[...container.querySelectorAll('.account-balance')];
                const items=nodes.map(element=>{const label=element.querySelector('.account-name>.text').textContent;
                    return{id:records('account').find(record=>record.data.name===label).id,label,element}});
                window.layoutTestItems=items;
                window.layoutTestController=UladimLayoutOrder.mountOrderControls({container,items,kind:'account',order,
                    onSave:ids=>window.syntheticLayoutSave(ids),E,lang:'ru'});
            }''',order)
        mount([])
        original=page.evaluate('layoutTestController.getOrder()')
        toggle=page.locator('.layout-order-toggle')
        expect(page.locator('.layout-order-controls').first).to_be_hidden()
        toggle.tap()
        target=page.locator('.account-balance').nth(1)
        label=target.locator('.account-name>.text').inner_text()
        target.get_by_role('button',name='Поднять · Счёт · '+label,exact=True).press('Enter')
        expect(page.locator('.layout-order-status')).to_contain_text('Порядок сохранён.')
        first=prefs.get(actor,wid,'account')['order']
        assert first==[original[1],original[0],original[2]],(first,original)
        page.locator('.account-balance').first.get_by_role('button',name='Опустить · Счёт · '+label,exact=True).tap()
        page.wait_for_function('layoutTestController.getOrder()[0]===layoutTestItems[0].id')
        assert prefs.get(actor,wid,'account')['order']==original
        # A final keyboard move persists, survives controller recreation, and keeps
        # actual account wrappers/buttons (including edit handlers) intact.
        page.locator('.account-balance').last.get_by_role('button',name='Поднять',exact=False).press('Enter')
        page.wait_for_function('!document.querySelector(".layout-order-toggle").disabled')
        saved=prefs.get(actor,wid,'account')['order']
        assert saved==[original[0],original[2],original[1]],saved
        page.screenshot(path=str(out/'account-order-mode.png'))
        page.evaluate('layoutTestController.destroy()');mount(saved)
        assert page.evaluate('layoutTestController.getOrder()')==saved
        toggle=page.locator('.layout-order-toggle');toggle.tap();toggle.tap()
        expect(page.locator('.layout-order-controls').first).to_be_hidden()
        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
        page.screenshot(path=str(out/'account-order-saved.png'))
        browser.close()
    print('LAYOUT_ORDER_BROWSER_OK keyboard/touch/recreated controller; 3 persisted personal revisions')


if __name__=='__main__':main()
