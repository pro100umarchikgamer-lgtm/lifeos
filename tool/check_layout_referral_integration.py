"""Actual customer HTTP, list persistence, invitation consent and session cleanup."""
import os
from pathlib import Path
from uuid import uuid4
import json
from playwright.sync_api import sync_playwright, expect
from backend.layout_preferences import LayoutPreferences
from backend.referrals import Referrals
from tool.check_web_platform import fixture, login, PASSWORD
from tool.check_finance_filter_fit import source_styles
from tool.web_browser_navigation import open_tab, open_finance_section


def main():
    out=Path('web_evidence/layout-referral-integration');out.mkdir(parents=True,exist_ok=True)
    with fixture() as (origin,backend,actor,wid),sync_playwright() as p:
        def put(kind,data):
            rid=str(uuid4());backend.batch(actor,wid,[{'id':str(uuid4()),'action':'record.put','record_id':rid,'revision':0,'kind':kind,'visibility':'private','audience':[],'data':data}]);return rid
        for label in ('Накопления','Путешествия'):put('account',{'name':label,'currency':'RUB','opening_minor':12505})
        for label in ('Подарки','Дом'):
            put('budget',{'name':label,'currency':'RUB','limit_minor':60000,'period':'month','start_on':'2026-11-01','end_on':None,'rollover':'none','participants':[]})
        mail={};backend.deliver=lambda e,c:mail.__setitem__(e,c)
        def user(email):
            session=backend.register(email,PASSWORD);value=backend.authenticate(session['token']);backend.verify(value,mail[email]);return backend.authenticate(session['token'])
        inviter=user('incoming@example.test');friend=user('friend-private@example.test')
        referrals=Referrals(backend,origin)
        incoming=referrals.create_code(inviter,{})['invite']['code']
        own=referrals.create_code(actor,{})['invite']['code']
        referrals.claim(friend,{'code':own});referrals.alias(friend,{'first_name':'Умар','surname_initial':'U'})
        layouts=LayoutPreferences(backend)
        browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
        context=browser.new_context(viewport={'width':1280,'height':1000},locale='ru-RU',has_touch=True,service_workers='block',reduced_motion='reduce')
        css=source_styles();context.route('**/assets/design.css',lambda route:route.fulfill(status=200,content_type='text/css',body=css))
        page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        claims=[];page.on('request',lambda req:claims.append(req.url) if '/referrals/claim' in req.url and req.method=='POST' else None)
        page.goto(origin+'/app?ref='+incoming+'&setup=preserve')
        expect(page.locator('input[name=password]')).to_be_visible()
        assert 'ref=' not in page.url and 'setup=preserve' in page.url
        assert page.evaluate('UladimReferrals.pending()')==incoming
        login(page,origin)
        expect(page.locator('.referral-pending')).to_be_visible()
        assert not claims,'Invitation was automatically claimed'
        page.locator('.referral-pending').get_by_role('button',name='Принять приглашение').click()
        expect(page.locator('.referral-pending')).to_have_count(0)
        assert len(claims)==1 and page.evaluate('UladimReferrals.pending()') is None
        open_tab(page,'Финансы');open_finance_section(page,'accounts')
        toggle=page.locator('.layout-order-toggle');expect(toggle).to_be_visible()
        original=page.locator('.account-balance').evaluate_all('nodes=>nodes.map(n=>n.dataset.account)')
        toggle.click();page.locator('.account-balance').last.get_by_role('button',name='Поднять',exact=False).press('Enter')
        expect(page.locator('.layout-order-status')).to_contain_text('Порядок сохранён.')
        saved=layouts.get(actor,wid,'account')['order'];assert saved==[original[0],original[2],original[1]]
        page.reload();expect(page.get_by_role('heading',name='Сегодня',exact=True)).to_be_visible()
        open_tab(page,'Финансы');open_finance_section(page,'accounts');expect(page.locator('.layout-order-toggle')).to_be_visible()
        assert page.locator('.account-balance').evaluate_all('nodes=>nodes.map(n=>n.dataset.account)')==saved
        page.set_viewport_size({'width':390,'height':844})
        page.locator('.layout-order-toggle').tap()
        page.locator('.account-balance').first.get_by_role('button',name='Опустить',exact=False).tap()
        expect(page.locator('.layout-order-status')).to_contain_text('Порядок сохранён.')
        assert layouts.get(actor,wid,'account')['order']==[saved[1],saved[0],saved[2]]
        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
        page.screenshot(path=str(out/'accounts-phone-order.png'))
        open_finance_section(page,'budgets');expect(page.locator('.layout-order-toggle')).to_be_visible()
        budgets=page.locator('.finance-budget-card').evaluate_all('nodes=>nodes.map(n=>n.dataset.budget)')
        page.locator('.layout-order-toggle').tap()
        page.locator('.finance-budget-card').nth(1).get_by_role('button',name='Поднять',exact=False).tap()
        expect(page.locator('.layout-order-status')).to_contain_text('Порядок сохранён.')
        assert layouts.get(actor,wid,'budget')['order']==[budgets[1],budgets[0],budgets[2]]
        # Browser requests hit the actual same-origin route, without replacing fetch.
        rejected=page.evaluate('''async wid=>{
            const missing=await fetch('/account/api/layout-order',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({workspace_id:wid,kind:'account',order:[]})});
            const foreign=await fetch('/account/api/layout-order?workspace=00000000-0000-0000-0000-000000000001&kind=account');
            return [missing.status,foreign.status];
        }''',wid)
        assert rejected==[403,403],rejected
        open_tab(page,'Профиль')
        link=page.locator('[data-settings-section=referrals]');expect(link).to_be_visible();link.click()
        person=page.locator('.referral-people li');expect(person).to_have_text('Умар U.')
        assert person.locator('a,button').count()==0
        text=page.locator('.referral-section').inner_text()
        assert friend['email'] not in text and friend['id'] not in text
        page.screenshot(path=str(out/'referrals-phone.png'))
        private_ids=[actor['id'],wid,*saved,*budgets]
        storage=page.evaluate('JSON.stringify({...localStorage})')
        assert not any(value in storage for value in private_ids)
        # Real logout in a second tab clears both its invitation and the first
        # tab's pending marker/cache through the production BroadcastChannel.
        capture='code=>{const u=new URL(location.href);u.searchParams.set("ref",code);history.replaceState(null,"",u);UladimReferrals.captureInvite()}'
        page.evaluate(capture,incoming)
        second=context.new_page();second.goto(origin+'/app');expect(second.get_by_role('heading',name='Сегодня',exact=True)).to_be_visible()
        second.evaluate(capture,incoming)
        open_tab(second,'Профиль');second.locator('.profile-logout').click()
        second.locator('.signout-panel button[type=submit]').click()
        expect(second.locator('input[name=password]')).to_be_visible()
        expect(page.locator('input[name=password]')).to_be_visible()
        assert page.evaluate('UladimReferrals.pending()') is None and second.evaluate('UladimReferrals.pending()') is None
        assert page.evaluate('personalLayoutCache.size')==0
        assert not errors,errors
        browser.close()
    print('LAYOUT_REFERRAL_INTEGRATION_OK real HTTP: desktop/phone account+budget persistence; explicit claim; private nonclickable names; CSRF/foreign scope; logout broadcast cleanup')


if __name__=='__main__':main()
