"""Focused browser acceptance for welcoming visitors and installed PWA launches.

Only loopback synthetic accounts are used. The public visual layer is assembled
in memory with --source-styles; integration checks use the built stylesheet.
"""
from dataclasses import replace
import argparse
import json
import os
from pathlib import Path
import tempfile
import threading
from wsgiref.simple_server import make_server, WSGIRequestHandler
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright, expect
from backend.config import Settings
from backend.production import Application
from backend.service import Backend

OUT=Path('web_evidence/welcome')

class Quiet(WSGIRequestHandler):
    def log_message(self,*args): pass


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-styles',action='store_true',help='Assemble existing source layers in memory without editing the shared bundle')
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        mail={}
        backend=Backend(Path(folder)/'synthetic.db',deliver=lambda e,c:mail.update({e:c}))
        backend.cipher=Fernet(Fernet.generate_key())
        with backend.connect() as db:
            db.execute('CREATE TABLE http_limits(key TEXT PRIMARY KEY,count BIGINT NOT NULL,until_at BIGINT NOT NULL)')
        email='welcome-fixture@example.test';password='synthetic-welcome-password'
        session=backend.register(email,password)
        backend.verify(backend.authenticate(session['token']),mail[email])
        settings=Settings.load({'DATABASE_URL':'postgresql://example/db','EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),'RATE_LIMIT_KEY':'synthetic-welcome-rate-key-'+'x'*32,'SMTP_HOST':'127.0.0.1','SMTP_TLS':'none','EMAIL_FROM':'fixture@example.test'})
        server=make_server('127.0.0.1',0,lambda e,s:[],handler_class=Quiet)
        site='http://localhost:'+str(server.server_port)
        application=Application(backend,replace(settings,site_origin=site,control_origin='http://control.localhost:'+str(server.server_port),require_https=False,registration_mode='open'))
        root=Path('backend/webassets')
        layer_names=['app/focus.css','app/workspace-sections.css','public-focus.css','app/import-presentation.css','app/reference.css','app/reference-workspaces.css','app/reference-account.css','app/reference-auth.css']
        css=root.joinpath('design.css').read_text().split('/* FOCUS_VISUAL_LAYERS */')[0].rstrip()+'\n\n/* FOCUS_VISUAL_LAYERS */\n'+'\n'.join('/* '+name+' */\n'+(root/name).read_text() for name in layer_names)
        def fixture(env,start_response):
            if args.source_styles and env.get('PATH_INFO')=='/assets/design.css':
                start_response('200 OK',[('Content-Type','text/css; charset=utf-8')]);return [css.encode()]
            return application(env,start_response)
        server.set_app(fixture)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        checks=[]
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
                # Public content must not jump into place after network setup.
                context=browser.new_context(viewport={'width':390,'height':844},service_workers='block')
                page=context.new_page();pending_config=[]
                config=page.request.get(site+'/account/api/config').json()
                page.route('**/account/api/config',lambda route:pending_config.append(route))
                page.goto(site+'/',wait_until='domcontentloaded')
                expect(page.locator('.product-hero')).to_be_visible()
                expect(page.locator('.hero-actions > a')).to_have_text('Открыть ULADIM')
                assert not page.locator('a[href*="action=signup"]').count()
                before=page.locator('main').bounding_box()
                assert len(pending_config)==1
                pending_config[0].fulfill(json=config)
                expect(page.locator('.hero-actions > a')).to_have_text('Создать аккаунт')
                after=page.locator('main').bounding_box()
                assert all(abs(before[key]-after[key])<=1 for key in ('x','y','width','height')),(before,after)
                checks.append({'case':'delayed-configuration','publicContentVisible':True,'layoutStable':True,'prematureSignupLinks':0})
                context.close()
                for width,theme in [(320,'light'),(390,'light'),(820,'light'),(1440,'light'),(390,'dark')]:
                    context=browser.new_context(viewport={'width':width,'height':900},color_scheme=theme,service_workers='block')
                    page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                    page.goto(site+'/',wait_until='domcontentloaded')
                    expect(page.locator('main h1')).to_have_text('Важное — в одном месте.')
                    expect(page.locator('.hero-actions > a')).to_have_count(1)
                    expect(page.locator('.hero-actions > a')).to_have_attribute('href','/app?action=signup')
                    expect(page.locator('.hero-actions > a')).to_have_text('Создать аккаунт')
                    assert page.locator('main .plan-comparison, main .product-faq, main .install-guide,dialog').count()==0
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,theme)
                    assert page.locator('.welcome-resources a').count()==5
                    assert page.locator('.preview-workspace').bounding_box()['width']>=240,(width,'preview readability')
                    assert page.locator('.hero-actions > a').bounding_box()['height']<=56,(width,'primary action wraps')
                    manifest=page.locator('link[rel=manifest]')
                    expect(manifest).to_have_attribute('href','/app/assets/manifest.webmanifest')
                    data=page.request.get(site+'/app/assets/manifest.webmanifest').json()
                    assert data['id']=='/app' and data['start_url']=='/app' and data['scope']=='/app'
                    page.screenshot(path=str(OUT/f'guest-{width}-{theme}.png'),full_page=True,animations='disabled')
                    assert not errors,errors
                    checks.append({'case':'guest','width':width,'theme':theme,'overflow':False,'errors':errors})
                    context.close()
                # A real fixture login establishes a server session in the browser.
                context=browser.new_context(viewport={'width':1440,'height':1000},service_workers='block')
                page=context.new_page();page.goto(site+'/app')
                page.get_by_label('Электронная почта',exact=True).fill(email)
                page.locator('input[name=password]').fill(password)
                page.get_by_role('button',name='Войти',exact=True).click()
                expect(page.locator('.nav')).to_be_visible()
                page.goto(site+'/',wait_until='domcontentloaded')
                expect(page.locator('.hero-actions > a')).to_have_text('Открыть моё пространство')
                expect(page.locator('.hero-actions > a')).to_have_attribute('href','/app')
                expect(page.locator('header nav .public-signin')).to_have_text('Моё пространство')
                assert not page.locator('a[href*="action=signup"]').count()
                page.screenshot(path=str(OUT/'returning-desktop.png'),full_page=True,animations='disabled')
                checks.append({'case':'returning','session':'real synthetic fixture','signupLinks':0})
                context.close()
                # Existing iOS shortcuts may still launch at /; both install signals
                # must go to the workspace URL before rendering the marketing page.
                for signal in ('ios','display-mode'):
                    context=browser.new_context(service_workers='block')
                    if signal=='ios':context.add_init_script("Object.defineProperty(navigator,'standalone',{value:true});")
                    else:context.add_init_script("const nativeMatch=matchMedia.bind(window);window.matchMedia=query=>query==='(display-mode: standalone)'?{matches:true,media:query,addEventListener(){},removeEventListener(){}}:nativeMatch(query);")
                    page=context.new_page();public_config=[]
                    page.on('request',lambda request:public_config.append(request.url) if request.url.endswith('/account/api/config') else None)
                    page.goto(site+'/');page.wait_for_url(site+'/app')
                    expect(page.locator('.focus-login')).to_be_visible()
                    assert page.locator('.landing').count()==0
                    checks.append({'case':'installed-launch','signal':signal,'url':'/app','marketingRendered':False})
                    context.close()
                # A failed session check is not evidence that someone is logged out.
                context=browser.new_context(service_workers='block',reduced_motion='reduce')
                page=context.new_page()
                page.route('**/account/api/session',lambda route:route.fulfill(status=503,content_type='application/json',body='{"error":"service_unavailable"}'))
                page.goto(site+'/',wait_until='domcontentloaded')
                expect(page.locator('.hero-actions > a')).to_have_text('Открыть ULADIM')
                expect(page.locator('.hero-actions > a')).to_have_attribute('href','/app')
                assert page.locator('a[href*="action=signup"]').count()==0
                expect(page.locator('.product-hero')).to_have_css('animation-name','none')
                checks.append({'case':'session-service-unavailable','signupLinks':0,'reducedMotion':True})
                context.close();browser.close()
        finally:
            server.shutdown();server.server_close();thread.join(5)
    (OUT/'checks.json').write_text(json.dumps({'result':'passed','fixture':'loopback synthetic data only','stylesheet':'source layers' if args.source_styles else 'built design.css','checks':checks},ensure_ascii=False,indent=2)+'\n')
    print('WELCOME_BROWSER_PASS',len(checks))

if __name__=='__main__':main()
