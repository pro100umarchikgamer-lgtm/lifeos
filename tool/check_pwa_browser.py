"""Rendered, synthetic acceptance. Does not contact production or use user data."""
from dataclasses import replace
import json
import os
import tempfile
import threading
import uuid
from pathlib import Path
from wsgiref.simple_server import make_server, WSGIRequestHandler
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright, expect
from backend.config import Settings
from backend.production import Application
from backend.service import Backend

ENGINE=os.environ.get('ULADIM_BROWSER','chromium')
DESIGN=os.environ.get('ULADIM_DESIGN','')
if DESIGN not in ('','clarity'):raise ValueError('Unknown review design')
OUT=Path('web_evidence/pwa') / (ENGINE if ENGINE!='chromium' else '') / DESIGN
PASSWORD='synthetic-pwa-browser-password'

class Quiet(WSGIRequestHandler):
    def log_message(self,*args): pass


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    checks=[];contrast_evidence=[]
    with tempfile.TemporaryDirectory() as folder:
        mail={}
        backend=Backend(Path(folder)/'fixture.db',deliver=lambda e,c:mail.update({e:c}))
        backend.cipher=Fernet(Fernet.generate_key())
        with backend.connect() as db:db.execute('CREATE TABLE http_limits(key TEXT PRIMARY KEY,count BIGINT NOT NULL,until_at BIGINT NOT NULL)')
        session=backend.register('tester@example.test',PASSWORD)
        actor=backend.authenticate(session['token']);backend.verify(actor,mail[actor['email']]);actor=backend.authenticate(session['token'])
        wid=str(uuid.uuid4())
        backend.family(actor,{'id':str(uuid.uuid4()),'action':'workspace.create','workspace_id':wid,'kind':'personal','name':'Моё пространство'})
        fixtures=[('task',{'title':'Подготовить план на неделю','completed':0,'assignment':'any','assignees':[],'review':0}),('note',{'body':'Идея: выходные без спешки.\nСохранить время для близких.'}),('account',{'name':'Основной счёт','currency':'RUB','opening_minor':1200000}),('transaction',{'kind':'income','amount_minor':15000000,'currency':'RUB','date':'2026-11-01','label':'Доход за месяц','account_id':None}),('transaction',{'kind':'expense','amount_minor':3520000,'currency':'RUB','date':'2026-11-08','label':'Покупки и повседневное','account_id':None})]
        for kind,data in fixtures:
            backend.batch(actor,wid,[{'id':str(uuid.uuid4()),'action':'record.put','record_id':str(uuid.uuid4()),'revision':0,'kind':kind,'visibility':'private','audience':[],'data':data}])
        settings=Settings.load({'DATABASE_URL':'postgresql://example/db','EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),'RATE_LIMIT_KEY':'synthetic-rate-'+'x'*48,'SMTP_HOST':'127.0.0.1','SMTP_TLS':'none','EMAIL_FROM':'fixture@example.test'})
        server=make_server('127.0.0.1',0,lambda e,s:[],handler_class=Quiet)
        origin='http://localhost:'+str(server.server_port)
        # HTTP localhost and SQLite are exclusively a disposable test fixture.
        app=Application(backend,replace(settings,site_origin=origin,control_origin='http://control.localhost:'+str(server.server_port),require_https=False))
        server.set_app(app);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=getattr(p,ENGINE).launch(args=['--no-sandbox'] if ENGINE=='chromium' else [])
                context=browser.new_context(viewport={'width':390,'height':844},color_scheme='light')
                page=context.new_page();errors=[];responses=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('response',lambda r:responses.append({'path':r.url.split(origin)[-1].split('?')[0],'status':r.status}) if '/account/api/' in r.url else None)
                page.goto(origin+'/app'+('?design='+DESIGN if DESIGN else ''));expect(page.get_by_role('heading',name='Войти')).to_be_visible()
                expect(page.locator('.login input[type=password]')).to_have_attribute('autocomplete','current-password')
                expect(page.locator('.login input[name=code]')).to_have_attribute('autocomplete','one-time-code')
                page.get_by_role('button',name='Создать аккаунт',exact=True).click()
                expect(page.get_by_role('dialog').locator('input[type=password]')).to_have_attribute('autocomplete','new-password')
                page.get_by_role('dialog').get_by_role('button',name='Закрыть',exact=True).click()
                expect(page.locator('dialog')).to_have_count(0)
                checks.append('password_manager_and_otp_hints')
                page.get_by_label('Электронная почта',exact=True).fill(actor['email'])
                page.get_by_label('Пароль (минимум 7 символов)',exact=True).fill(PASSWORD)
                page.get_by_role('button',name='Войти',exact=True).click()
                try:
                    expect(page.get_by_role('heading',name='Сегодня',exact=True)).to_be_visible()
                except AssertionError:
                    page.screenshot(path=str(OUT/'login-failure.png'))
                    (OUT/'login-failure.json').write_text(json.dumps({'engine':ENGINE,'fixture':'HTTP loopback only; no production credentials','responses':responses,'cookies':[{'name':c['name'],'secure':c['secure'],'httpOnly':c['httpOnly']} for c in context.cookies()],'body':page.locator('body').inner_text(),'page_errors':errors},ensure_ascii=False,indent=2))
                    raise
                page.screenshot(path=str(OUT/'iphone-today-light.png'),full_page=False)
                assert page.locator('.nav svg[aria-hidden=true]').count()==5
                for nav_button in page.locator('.nav button').all():
                    box=nav_button.bounding_box();assert box['width']>=44 and box['height']>=44
                for w,h,n in [(820,1180,'ipad'),(1440,960,'desktop')]:
                    page.set_viewport_size({'width':w,'height':h})
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    if DESIGN:
                        nav=page.locator('.nav').bounding_box();assert nav['x']==0 and nav['width']<250 and nav['height']>500
                    page.screenshot(path=str(OUT/(n+'-today-light.png')),full_page=False)
                page.set_viewport_size({'width':390,'height':844})
                checks.append('svg_navigation_named_controls_and_tablet_desktop_layout')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.get_by_role('button',name='Задачи',exact=True).click()
                page.get_by_role('button',name='Добавить',exact=True).click()
                dialog=page.get_by_role('dialog')
                heading_id=dialog.get_attribute('aria-labelledby')
                assert heading_id and page.locator('[id="'+heading_id+'"]').inner_text()
                assert dialog.get_by_role('button',name='Закрыть',exact=True).count()==1
                page.get_by_label('Название задачи',exact=True).fill('Новая задача из веба')
                page.get_by_role('button',name='Сохранить',exact=True).click()
                expect(page.get_by_text('Новая задача из веба',exact=True)).to_be_visible()
                assert any(r['data'].get('title')=='Новая задача из веба' for r in backend.pull(actor,wid,0)['records'])
                page.get_by_role('checkbox',name='Новая задача из веба',exact=True).check()
                expect(page.get_by_role('checkbox',name='Новая задача из веба',exact=True)).to_be_checked()
                checks.append('create_and_complete_task_shared_with_android_protocol')
                page.get_by_role('button',name='Заметки',exact=True).click()
                page.get_by_role('button',name='Добавить',exact=True).click()
                page.get_by_label('Текст заметки',exact=True).fill('Одна запись при повторе после потери ответа')
                def lose_response(route):
                    route.fetch();route.abort()
                page.route('**/account/api/sync',lose_response,times=1)
                page.get_by_role('button',name='Сохранить',exact=True).click()
                expect(page.get_by_role('button',name='Повторить',exact=True)).to_be_visible()
                page.get_by_role('button',name='Повторить',exact=True).click()
                expect(page.get_by_text('Одна запись при повторе после потери ответа',exact=True)).to_be_visible()
                self_records=backend.pull(actor,wid,0)['records']
                assert sum(r['data'].get('body')=='Одна запись при повторе после потери ответа' for r in self_records)==1
                checks.append('lost_response_retry_is_idempotent')
                page.get_by_role('button',name='Финансы',exact=True).click()
                expect(page.get_by_role('heading',name='Финансы',exact=True,level=1)).to_be_visible()
                page.screenshot(path=str(OUT/'iphone-finance-light.png'),full_page=False)
                for width,height,name in [(320,740,'small-phone'),(820,1180,'ipad'),(1100,900,'compact-desktop'),(1440,960,'desktop')]:
                    page.set_viewport_size({'width':width,'height':height})
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
                    page.screenshot(path=str(OUT/(name+'-finance.png')),full_page=True)
                checks.append('responsive_320_390_820_1100_1440')
                page.set_viewport_size({'width':390,'height':844})
                page.get_by_role('button',name='Профиль',exact=True).click()
                expect(page.get_by_role('heading',name='Управление аккаунтом',exact=True)).to_be_visible()
                page.screenshot(path=str(OUT/'iphone-account-light.png'),full_page=False)
                def luminance(hex_color):
                    if len(hex_color)==4:hex_color='#'+''.join(c*2 for c in hex_color[1:])
                    assert len(hex_color)==7 and hex_color.startswith('#'),hex_color
                    channels=[int(hex_color[i:i+2],16)/255 for i in (1,3,5)]
                    return sum((c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4)*w for c,w in zip(channels,(.2126,.7152,.0722)))
                for scheme in ('light','dark'):
                    page.emulate_media(color_scheme=scheme)
                    for theme in ('system','light','dark'):
                        page.locator('select[name=theme]').select_option(theme)
                        for palette in ('forest','ocean','pistachio'):
                            page.locator('select[name=palette]').select_option(palette)
                            colors=page.evaluate('''()=>{const s=getComputedStyle(document.body);return Object.fromEntries(['ink','muted','income','expense','bg','card','soft'].map(k=>[k,s.getPropertyValue('--'+k).trim()]));}''')
                            backgrounds=['bg','card']+(['soft'] if DESIGN else [])
                            for fg in ('ink','muted','income','expense'):
                                for bg in backgrounds:
                                    low,high=sorted((luminance(colors[fg]),luminance(colors[bg])))
                                    ratio=(high+.05)/(low+.05)
                                    contrast_evidence.append({'scheme':scheme,'theme':theme,'palette':palette,'foreground':fg,'background':bg,'ratio':round(ratio,3),'minimum':4.5,'passed':ratio>=4.5})
                                    assert ratio>=4.5,(scheme,theme,palette,fg,bg,ratio)
                checks.append('financial_text_contrast_all_themes_and_palettes')
                page.emulate_media(color_scheme='light')
                page.get_by_label('Оформление',exact=True).select_option('dark')
                page.get_by_label('Цветовая палитра',exact=True).select_option('ocean')
                page.get_by_role('button',name='Финансы',exact=True).click()
                page.screenshot(path=str(OUT/'iphone-finance-dark.png'),full_page=False)
                await_sw=page.evaluate('navigator.serviceWorker.ready.then(()=>true)')
                assert await_sw
                page.wait_for_function('Boolean(navigator.serviceWorker.controller)')
                cache_urls=page.evaluate('''async()=>{const out=[];for(const k of await caches.keys()){for(const r of await(await caches.open(k)).keys())out.push(new URL(r.url).pathname);}return out;}''')
                assert cache_urls and all(x.startswith('/app/assets/') for x in cache_urls),cache_urls
                assert not any('/api/' in x for x in cache_urls)
                stored=page.evaluate('Object.keys(localStorage)')
                assert stored==['uladim-interface'],stored
                checks.append('cache_contains_only_interface_and_preferences')
                for locale in json.loads(Path('backend/webassets/app/locales.json').read_text()):
                    page.locator('.nav button').last.click()
                    page.locator('select[name=language]').select_option(locale)
                    expect(page.locator('h1')).to_be_visible()
                    assert page.locator('html').get_attribute('lang')==locale
                    assert not page.get_by_text('family_error_',exact=False).count()
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),locale
                checks.append('all_16_locales_render')
                # Leave selected language in RU for unambiguous logout assertion.
                page.locator('select[name=language]').select_option('ru')
                # A page entering history must not retain a readable private DOM.
                page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true}))")
                assert page.locator('.nav').count()==0, 'private DOM retained in history snapshot'
                assert actor['email'] not in page.locator('body').inner_text()
                assert 'Подготовить план' not in page.locator('body').inner_text()
                page.evaluate("dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}))")
                expect(page.get_by_role('heading',name='Сегодня',exact=True)).to_be_visible()
                checks.append('history_snapshot_scrubbed_before_session_revalidation')
                page.get_by_role('button',name='Профиль',exact=True).click()
                page.get_by_role('button',name='Выйти',exact=True).click()
                expect(page.get_by_role('heading',name='Войти',exact=True)).to_be_visible()
                assert 'Подготовить план' not in page.locator('body').inner_text()
                checks.append('logout_clears_rendered_personal_data')
                assert 'id="message"' in page.evaluate("caches.match('/app/assets/offline.html').then(r=>r.text())")
                server.shutdown();server.server_close();thread.join(5)
                context.set_offline(True)
                page.goto(origin+'/app')
                expect(page.locator('#message')).to_have_text(json.loads(Path('backend/webassets/app/locales.json').read_text())['ru']['strings']['web_online'])
                checks.append('localized_offline_page_contains_no_personal_data')
                assert not errors,errors
                context.close();browser.close()
        finally:
            server.shutdown();server.server_close();thread.join(5)
    (OUT/'RESULT.json').write_text(json.dumps({'result':'passed','checks':checks,'contrast':contrast_evidence,'fixture':'synthetic loopback SQLite; production and real devices not tested','engine':ENGINE,'design':DESIGN or 'current','screenshots':len(list(OUT.glob('*.png')))},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':checks},ensure_ascii=False))

if __name__=='__main__':main()
