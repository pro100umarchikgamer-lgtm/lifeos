"""Focused Web feedback journeys against real local APIs and disposable records.

Uses source CSS until the root performs the single final bundle build. Screens
and requests contain synthetic fixture data only. No production access.
"""
import argparse
import base64
import json
import math
import os
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect
from tool.check_finance_filter_fit import source_styles
from tool.check_web_platform import fixture, login
from tool.web_browser_navigation import open_tab, open_settings, open_finance_section

OUT = Path(os.environ.get('ULADIM_WEB_FEEDBACK_EVIDENCE', '/tmp/web-feedback-evidence'))


def choose(page, carrier, value):
    label = carrier.locator('option[value="' + value + '"]').inner_text()
    wrapper = carrier.locator('..')
    wrapper.locator(':scope > button').click()
    menu = wrapper.locator('[role=listbox]')
    expect(menu).to_be_visible()
    box = menu.bounding_box()
    viewport = page.viewport_size
    assert box['x'] >= 0 and box['x'] + box['width'] <= viewport['width'] + 1, box
    assert box['y'] >= 0 and box['y'] + box['height'] <= viewport['height'] + 1, box
    menu.get_by_role('option', name=label, exact=True).click()
    expect(carrier).to_have_value(value)


def color(value):
    if value.startswith('#'):
        return [int(value[index:index+2], 16) for index in (1, 3, 5)]
    return [float(part.strip()) for part in value.split('(')[1].split(')')[0].split(',')[:3]]


def luminance(value):
    channels = [item / 255 for item in color(value)]
    values = [item / 12.92 if item <= .04045 else ((item + .055) / 1.055) ** 2.4 for item in channels]
    return sum(a * b for a, b in zip(values, (.2126, .7152, .0722)))


def contrast(first, second):
    values = sorted((luminance(first), luminance(second)))
    return (values[1] + .05) / (values[0] + .05)


def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--built-styles',action='store_true')
    parser.add_argument('--output',type=Path,default=OUT)
    args=parser.parse_args();OUT=args.output
    OUT.mkdir(parents=True, exist_ok=True)
    checks, errors, samples, http_errors = [], [], [], []
    styles = None if args.built_styles else source_styles()
    with fixture() as (origin, backend, actor, wid), sync_playwright() as p:
        now = int(time.time())
        staff, case_id, other_case, other = [str(uuid.uuid4()) for _ in range(4)]
        with backend.transaction() as db:
            db.execute('INSERT INTO staff(id,user_id,roles,mfa_secret,created_at) VALUES(?,?,?,?,?)',
                       (staff, actor['id'], '["support"]', 'fixture-not-used-for-sign-in', now))
            db.execute('INSERT INTO support_recovery_cases VALUES(?,?,NULL,?,\'waiting_owner\',1,?,?,0,?,?)',
                       (case_id, actor['id'], 'records', now, now+86400, now, staff))
        launch = {'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}
        browser = p.chromium.launch(**launch)

        def advance_window():
            # Fast independent relaunches must not share one per-IP rate window.
            next_window = int(backend.clock()) + 61
            backend.clock = lambda: next_window

        def response_seen(response):
            if response.status == 429 or response.status >= 500:
                failure = {'status':response.status, 'method':response.request.method, 'path':urlsplit(response.url).path}
                http_errors.append(failure)
                print(json.dumps({'web_feedback_http_failure':failure}), flush=True)

        def context(**options):
            advance_window()
            ctx = browser.new_context(service_workers='block', reduced_motion='reduce', **options)
            if styles is not None:ctx.route('**/assets/design.css', lambda route: route.fulfill(content_type='text/css', body=styles))
            ctx.on('response', response_seen)
            ctx.on('page', lambda page: page.on('pageerror', lambda error: errors.append(str(error))))
            return ctx

        # Hold the deferred application, so the HTML splash is inspected before authentication.
        ctx = context(viewport={'width':390,'height':844}, color_scheme='dark')
        ctx.add_init_script("try{localStorage.setItem('uladim-interface',JSON.stringify({theme:'light',palette:'rose',appearanceIntensity:100,lang:'ru'}))}catch{}")
        held = {}
        ctx.route('**/app/assets/app.js', lambda route: held.update(route=route))
        page = ctx.new_page();page.goto(origin+'/app', wait_until='commit')
        expect(page.locator('.boot-splash')).to_be_visible()
        page.wait_for_function("document.documentElement.dataset.bootTheme==='light'")
        boot = page.evaluate("({theme:document.documentElement.dataset.bootTheme,body:getComputedStyle(document.body).backgroundColor,page:getComputedStyle(document.documentElement).getPropertyValue('--boot-page').trim()})")
        assert color(boot['body']) == color(boot['page']), boot
        assert min(color(boot['body'])) > 190, boot
        # This intentionally held deferred script can keep document.fonts.ready pending.
        # Capture the already asserted HTML splash without waiting for the held app.
        capture = ctx.new_cdp_session(page)
        frame = capture.send('Page.captureScreenshot', {'format':'png', 'captureBeyondViewport':False})
        (OUT/'saved-light-before-app-390.png').write_bytes(base64.b64decode(frame['data']))
        capture.detach()
        held['route'].continue_();page.wait_for_load_state('domcontentloaded');ctx.close()
        checks.append({'case':'saved-light-html-splash-before-deferred-app','system':'dark','boot':boot})

        ctx = context(viewport={'width':390,'height':900}, color_scheme='light');page=ctx.new_page();login(page,origin)
        for tab, section in [('money','ledger'),('money','accounts'),('account','appearance'),('notes',''),('calendar','')]:
            if tab == 'account':open_tab(page,'Профиль');open_settings(page,section)
            elif tab == 'money':open_tab(page,'Финансы');open_finance_section(page,section)
            else:open_tab(page,{'notes':'Заметки','calendar':'Календарь'}[tab])
            expect(page.locator('main#content')).to_have_attribute('data-view', tab+'/'+(section if tab=='account' else '')+'/'+(section if tab=='money' else ''))
            advance_window();page.reload();expect(page.locator('main#content')).to_have_attribute('data-view', tab+'/'+(section if tab=='account' else '')+'/'+(section if tab=='money' else ''))
            assert 'selectedspace='+wid in page.url
        checks.append({'case':'refresh-keeps-five-real-sections','containsPrivateRecordData':False})

        open_tab(page,'Профиль');open_settings(page,'appearance')
        for theme in ('light','dark'):
            choose(page,page.locator('select[name=theme]'),theme)
            theme_samples=[]
            for intensity in (0,50,100):
                slider=page.locator('input[name=appearance-intensity]')
                slider.evaluate("el=>window.originalAppearanceSlider=el")
                slider.evaluate("(el,value)=>{el.value=String(value);el.dispatchEvent(new Event('input',{bubbles:true}));}",intensity)
                assert slider.evaluate('el=>el===window.originalAppearanceSlider')
                sample=page.evaluate("""()=>{const card=document.querySelector('.appearance-settings'),field=document.querySelector('select[name=theme]').choiceField.querySelector('button');return {page:getComputedStyle(document.body).backgroundColor,card:getComputedStyle(card).backgroundColor,input:getComputedStyle(field).backgroundColor,text:getComputedStyle(card).color,error:getComputedStyle(document.body).getPropertyValue('--expense').trim()};}""")
                assert contrast(sample['text'],sample['card'])>=4.5,sample
                assert contrast(sample['error'],sample['input'])>=4.5,sample
                sample.update(theme=theme,intensity=intensity);samples.append(sample);theme_samples.append(sample)
                page.screenshot(path=str(OUT/f'appearance-{theme}-{intensity}-390.png'),full_page=True)
            for surface in ('page','card','input'):
                assert len({item[surface] for item in theme_samples})==3,(theme,surface,theme_samples)
                assert math.dist(color(theme_samples[0][surface]),color(theme_samples[-1][surface]))>=8,(theme,surface)
            assert len({item['text'] for item in theme_samples})==1
        checks.append({'case':'real-page-card-field-surfaces-0-50-100','themes':['light','dark'],'sliderNodePreserved':True,'contrastMinimum':4.5})

        # Exercise the visible control inside the actual task dialog at each requested width.
        for width in (320,390,820):
            page.set_viewport_size({'width':width,'height':900});open_tab(page,'Задачи')
            page.locator('main .intro button').click();dialog=page.locator('dialog[open]')
            dialog.locator('.record-options summary').click()
            visibility=dialog.locator('select[name=visibility]');choose(page,visibility,'shared')
            assert visibility.locator('option[value=shared]').inner_text()=='В этом пространстве'
            trigger=visibility.locator('..').locator(':scope > button');trigger.click();page.keyboard.press('Escape')
            expect(dialog).to_be_visible();expect(trigger).to_have_attribute('aria-expanded','false')
            dialog.locator('input[name=name]').fill('Проверка меню '+str(width))
            held={}
            def sync(route):
                body=route.request.post_data_json
                if any(item.get('action')=='record.put' for item in body.get('operations',[])):held.update(route=route)
                else:route.continue_()
            page.route('**/account/api/sync',sync)
            dialog.locator('button[type=submit]').click();expect(trigger).to_be_disabled();held['route'].continue_()
            expect(dialog).to_be_hidden();page.unroute('**/account/api/sync',sync)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        checks.append({'case':'visible-task-visibility-menu','widths':[320,390,820],'escapeKeepsDialog':True,'pendingDisabled':True,'nativeFormPreserved':True})

        open_tab(page,'Профиль');name=page.locator('input[name=display_name]');expect(name).to_be_visible()
        name.fill('  Cafe\u0301 <safe>  ');name.locator('xpath=ancestor::form').locator('button[type=submit]').click();expect(name).to_have_value('Café <safe>')
        advance_window();page.reload();name=page.locator('input[name=display_name]');expect(name).to_have_value('Café <safe>')
        name.fill('');name.locator('xpath=ancestor::form').locator('button[type=submit]').click();expect(name).to_have_value('')
        result=page.request.get(origin+'/account/api/identity').json();assert result=={'display_name':None},result
        checks.append({'case':'optional-self-name-nfc-roundtrip-and-clear','profileNamesRead':False})

        advance_window();page.goto(origin+'/app?view=money&section=ledger&settings=recovery&case='+case_id)
        confirm=page.locator('.recovery-case-confirm');expect(confirm).to_be_visible();confirm.click()
        expect(page.locator('.recovery-cases')).to_contain_text('Исходный аккаунт подтверждён.')
        with backend.connect() as db:
            assert db.execute('SELECT COUNT(*) AS n FROM record_recovery_requests').fetchone()['n']==0
            assert db.execute('SELECT state FROM support_recovery_cases WHERE id=?',(case_id,)).fetchone()['state']=='confirmed'
        advance_window();page.reload();expect(page.locator('.recovery-cases')).to_contain_text('Исходный аккаунт подтверждён.')
        # A different original target never appears in the current owner's list/detail.
        other_session=backend.register('other-fixture@example.test','valid-fixture-long-password')
        other_actor=backend.authenticate(other_session['token'])
        with backend.transaction() as db:
            db.execute('INSERT INTO support_recovery_cases VALUES(?,?,NULL,?,\'waiting_owner\',1,?,?,0,?,?)',
                       (other_case,other_actor['id'],'records',now,now+86400,now,staff))
        advance_window();page.goto(origin+'/app?settings=recovery&case='+other_case)
        expect(page.locator('.recovery-cases')).to_contain_text('Это обращение недоступно для этого аккаунта.')
        expect(page.locator('.recovery-case-confirm')).to_have_count(0)
        assert 'other-fixture@example.test' not in page.locator('main').inner_text()
        page.screenshot(path=str(OUT/'wrong-owner-case-820.png'),full_page=True)
        checks.append({'case':'real-owner-confirmation-and-wrong-account-404','recordConsentCreated':False,'refreshKeepsCase':True})

        advance_window();page.goto(origin+'/app?view=money&section=analysis');expect(page.locator('select[name=chart-mode] option')).to_have_count(6)
        with backend.transaction() as db:
            for key,enabled in [('chart_styles',False),('support_entry',True),('compact_onboarding',True)]:
                db.execute('INSERT INTO feature_flags VALUES(?,?,?,?,?)',(key,json.dumps({'enabled':enabled,'rollout':100}),1,staff,now))
        advance_window();page.reload();expect(page.locator('select[name=chart-mode] option')).to_have_count(1);expect(page.locator('select[name=chart-mode]')).to_have_value('bar');expect(page.locator('.header-support')).to_be_visible()
        page.locator('.header-support').click();expect(page.locator('.settings-content')).to_have_attribute('data-section','support')
        page.set_viewport_size({'width':320,'height':900});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.set_viewport_size({'width':820,'height':900})
        page.route('**/account/api/spaces',lambda route:route.fulfill(json={'spaces':[]}))
        advance_window();page.goto(origin+'/app?view=today');expect(page.locator('.setup-panel')).to_have_attribute('data-compact','true');expect(page.locator('.setup-panel > p')).to_have_count(0)
        checks.append({'case':'actual-session-interface-flag-consumers','defaultChartStyles':6,'disabledChart':'bar','supportShortcut':True,'compactIntro':True,'emptySpaces':'fixture response'})
        assert errors==[],errors
        assert http_errors==[],http_errors
        ctx.close();browser.close()
    (OUT/'checks.json').write_text(json.dumps({'checks':checks,'surfaces':samples,'pageErrors':errors,'httpErrors':http_errors,'stylesheet':'built bundle' if args.built_styles else 'source layers'},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'checks':len(checks),'pageErrors':errors,'output':str(OUT)},ensure_ascii=False))


if __name__=='__main__':main()
