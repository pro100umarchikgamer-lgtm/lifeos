"""Focused install affordance checks on real local routes and disposable accounts.

Scripted install events test application state only; they do not establish that
an OS install dialog or iOS Share menu worked on a physical device.
"""
import argparse
import json
import os
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import sync_playwright, expect
from tool.check_finance_filter_fit import source_styles
from tool.check_web_platform import fixture, login
from tool.web_browser_navigation import open_tab, open_settings


def native_offer(page, outcome='dismissed'):
    page.evaluate('''outcome=>{
        const event=new Event('beforeinstallprompt',{cancelable:true});
        event.prompt=()=>{window.installCalls=(window.installCalls||0)+1;return Promise.resolve({outcome});};
        dispatchEvent(event);
    }''', outcome)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--built-styles',action='store_true')
    parser.add_argument('--translation-packet',type=Path,help='Preview an unmerged root-owned catalog packet; recorded explicitly in evidence.')
    parser.add_argument('--output',type=Path,default=Path('web_evidence/pwa-install'))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    catalog=json.loads(Path('backend/webassets/app/translations.json').read_text())
    if args.translation_packet:
        packet=json.loads(args.translation_packet.read_text());catalog['source'].update(packet['source'])
        catalog['required']=list(dict.fromkeys(catalog['required']+packet['required']))
        for locale,strings in packet['translations'].items():catalog['translations'].setdefault(locale,{}).update(strings)
    checks=[];errors=[];forbidden=[]
    styles=None if args.built_styles else source_styles()
    with fixture() as (origin,backend,_actor,_wid),sync_playwright() as playwright:
        browser=playwright.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))

        def context(service_workers='block',**options):
            value=browser.new_context(service_workers=service_workers,reduced_motion='reduce',**options)
            if styles is not None:value.route('**/assets/design.css',lambda route:route.fulfill(content_type='text/css',body=styles))
            if args.translation_packet:value.route('**/app/assets/translations.json',lambda route:route.fulfill(json=catalog))
            value.on('page',lambda page:page.on('pageerror',lambda error:errors.append(str(error))))
            value.on('request',lambda request:forbidden.append(request.url) if any(path in request.url for path in ('/notifications/enable','/notifications/test')) else None)
            return value

        for width in (320,390,820):
            ctx=context(viewport={'width':width,'height':900},color_scheme='light');page=ctx.new_page()
            for path in ('/download','/docs#installation'):
                response=page.goto(origin+path,wait_until='domcontentloaded')
                assert "manifest-src 'self'" in response.headers.get('content-security-policy','')
                surface=page.locator('[data-install-placement="guide"]');expect(surface).to_be_visible()
                expect(surface.locator('details')).not_to_have_attribute('open','')
                surface.locator('.install-affordance-button').click();expect(surface.locator('details')).to_have_attribute('open','')
                assert page.locator('dialog[open]').count()==0
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(path,width)
                assert surface.locator('.install-affordance-button').bounding_box()['height']>=44
                checks.append({'case':'public-install','path':path,'width':width,'overflow':False})
            if width==390:page.screenshot(path=str(args.output/'docs-install-390.png'),full_page=True,animations='disabled')
            helper=page.request.get(origin+'/app/assets/install.js')
            assert helper.status==200 and 'javascript' in helper.headers.get('content-type','')
            assert helper.headers.get('cache-control')=='no-store'
            ctx.close()

        ctx=context(viewport={'width':390,'height':844},color_scheme='dark');page=ctx.new_page();login(page,origin)
        draft=page.get_by_label('Что нужно сделать?',exact=True);draft.fill('Keep this unsaved draft')
        page.evaluate('UladimInstall.mount(document.querySelector("main"),{compact:true,placement:"draft-check"})')
        surface=page.locator('[data-install-placement="draft-check"]');draft.focus();native_offer(page)
        expect(surface).to_have_attribute('data-install-state','ready');expect(draft).to_be_focused();expect(draft).to_have_value('Keep this unsaved draft')
        assert page.evaluate('window.installCalls||0')==0
        surface.locator('.install-affordance-button').click();expect(surface).to_have_attribute('data-install-state','dismissed')
        assert page.evaluate('window.installCalls')==1
        surface.locator('.install-affordance-button').click();assert page.evaluate('window.installCalls')==1
        native_offer(page,'accepted');surface.locator('.install-affordance-button').click();expect(surface).to_have_attribute('data-install-state','accepted')
        assert page.evaluate('UladimInstall.isInstalled()') is False
        checks.append({'case':'native-lifecycle','automaticPrompts':0,'consumedEventReused':False,'draftPreserved':True,'acceptanceClaimsInstalled':False})

        open_tab(page,'Профиль');profile=page.locator('[data-install-placement="profile"]');expect(profile).to_be_visible()
        profile.locator('.install-affordance-button').click();expect(profile.locator('details')).to_have_attribute('open','')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(args.output/'profile-install-390-dark.png'),full_page=True,animations='disabled')
        open_settings(page,'appearance');appearance=page.locator('[data-install-placement="appearance"]');expect(appearance).to_be_visible()
        native_offer(page);expect(appearance).to_have_attribute('data-install-state','ready')
        page.evaluate('dispatchEvent(new Event("appinstalled"))');expect(appearance).to_have_attribute('data-install-state','installed')
        expect(appearance.locator('.install-affordance-button')).to_be_hidden()
        checks.append({'case':'profile-appearance','installedEventUpdatesCurrentMount':True})
        ctx.close()

        chrome_ios='Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/130.0.0.0 Mobile/15E148 Safari/604.1'
        for desktop_ua in (False,True):
            ctx=context(viewport={'width':820,'height':900},user_agent=chrome_ios if not desktop_ua else chrome_ios.replace('(iPad; CPU OS 18_0 like Mac OS X)','(Macintosh; Intel Mac OS X 10_15)'))
            if desktop_ua:ctx.add_init_script("Object.defineProperty(navigator,'platform',{value:'MacIntel'});Object.defineProperty(navigator,'maxTouchPoints',{value:5});")
            page=ctx.new_page();page.goto(origin+'/docs#installation');page.locator('.global-language select').select_option('en')
            surface=page.locator('[data-install-placement="guide"]');surface.locator('.install-affordance-button').click()
            expect(surface.locator('[data-install-steps]')).to_contain_text('In Chrome, tap Share beside the address bar → Add to Home Screen → Add.')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            if not desktop_ua:page.screenshot(path=str(args.output/'ipad-chrome-guide-820.png'),full_page=True,animations='disabled')
            checks.append({'case':'iPad-Chrome-manual','desktopUA':desktop_ua,'physicalDevice':False});ctx.close()

        ctx=context(viewport={'width':320,'height':900});page=ctx.new_page();page.goto(origin+'/download')
        for locale in catalog['translations']:
            expected=catalog['translations'][locale].get('pwa_install_button') or catalog['source'].get('pwa_install_button',{}).get('values',{}).get(locale)
            assert expected,('Missing installation translation',locale)
            page.locator('.global-language select').select_option(locale)
            surface=page.locator('[data-install-placement="guide"]');expect(surface.locator('.install-affordance-button')).to_have_text(expected)
            surface.locator('.install-affordance-button').click()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),locale
        checks.append({'case':'all-locales-320','count':len(catalog['translations']),'overflow':False});ctx.close()

        password='synthetic-install-onboarding-password';mail={};deliver=backend._deliver
        def capture(db,email,code,purpose):
            deliver(db,email,code,purpose);mail[email]=code
        with patch.object(backend,'_deliver',capture):session=backend.register('install-onboarding@example.test',password)
        backend.verify(backend.authenticate(session['token']),mail['install-onboarding@example.test'])
        ctx=context(viewport={'width':390,'height':844});page=ctx.new_page();page.goto(origin+'/app')
        page.get_by_label('Электронная почта',exact=True).fill('install-onboarding@example.test');page.locator('input[name=password]').fill(password)
        page.get_by_role('button',name='Войти',exact=True).click();surface=page.locator('[data-install-placement="onboarding"]');expect(surface).to_be_visible()
        surface.locator('.install-affordance-button').click();expect(page.locator('.setup-panel')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(args.output/'onboarding-install-390.png'),full_page=True,animations='disabled')
        checks.append({'case':'onboarding','setupStillAvailable':True});ctx.close()

        ctx=context(service_workers='allow',viewport={'width':390,'height':844});page=ctx.new_page();login(page,origin)
        page.evaluate('navigator.serviceWorker.ready.then(()=>true)')
        page.wait_for_function('Boolean(navigator.serviceWorker.controller)')
        cached=page.evaluate('''async()=>{
            const urls=[];for(const name of await caches.keys())for(const request of await(await caches.open(name)).keys())urls.push(new URL(request.url).pathname);
            return urls;
        }''')
        assert '/app/assets/install.js' in cached and not any('/api/' in url for url in cached),cached
        checks.append({'case':'worker-precache','installHelperIncluded':True,'privateResponsesCached':False});ctx.close()
        assert not forbidden,forbidden;assert not errors,errors
        browser.close()
    result={'result':'passed','checks':checks,'pageErrors':errors,'notificationPermissionActions':forbidden,'translationPacketPreview':str(args.translation_packet) if args.translation_packet else None,'styles':'built' if args.built_styles else 'assembled source','nativeDialogAndPhysicalDeviceTested':False}
    (args.output/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
