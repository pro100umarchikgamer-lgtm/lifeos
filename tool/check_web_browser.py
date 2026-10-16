"""Actual rendered browser acceptance against a loopback-only synthetic backend.

HTTP localhost is used only for this disposable development fixture. Production
HTTPS checks remain enabled and no certificate verification is disabled.
"""
from dataclasses import replace
import json
import tempfile
import threading
from pathlib import Path
from wsgiref.simple_server import make_server, WSGIRequestHandler
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright, expect
from backend.config import Settings
from backend.control import Control, totp
from backend.production import Application
from backend.service import Backend

OUT=Path('web_evidence')
PASSWORD='synthetic-browser-password'

class Quiet(WSGIRequestHandler):
    def log_message(self,*args): pass


def check_header_layout(page):
    for width in (320,390,430):
        page.set_viewport_size({'width':width,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),(page.url,width)
        assert page.locator('.brand').evaluate('''element => {
            const range=document.createRange();range.selectNodeContents(element.firstChild);
            return range.getClientRects().length===1;
        }'''),('wordmark wraps',width)
        for link in page.locator('header nav a').all():
            box=link.bounding_box()
            if box is not None:assert box['height']>=48,('navigation target',width,box)
    page.set_viewport_size({'width':390,'height':844})


def main():
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        mail={}
        backend=Backend(Path(folder)/'synthetic.db',deliver=lambda e,c:mail.update({e:c}))
        backend.cipher=Fernet(Fernet.generate_key())
        with backend.connect() as db:db.execute('CREATE TABLE http_limits(key TEXT PRIMARY KEY,count BIGINT NOT NULL,until_at BIGINT NOT NULL)')
        for email in ('owner@example.test','tester@example.test'):
            session=backend.register(email,PASSWORD);actor=backend.authenticate(session['token']);backend.verify(actor,mail[email])
        control=Control(backend);enrollment=control.bootstrap('owner@example.test')
        settings=Settings.load({'DATABASE_URL':'postgresql://example/db','EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),'RATE_LIMIT_KEY':'synthetic-browser-rate-key-'+'x'*32,'SMTP_HOST':'127.0.0.1','SMTP_TLS':'none','EMAIL_FROM':'fixture@example.test'})
        server=make_server('127.0.0.1',0,lambda e,s:[],handler_class=Quiet)
        site='http://localhost:'+str(server.server_port)
        staff='http://control.localhost:'+str(server.server_port)
        # No user/service data or credentials from the runner enter this fixture.
        app=Application(backend,replace(settings,site_origin=site,control_origin=staff,require_https=False,registration_allowlist=('new@example.test',)))
        server.set_app(app)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch()
                for theme in ('light','dark'):
                    context=browser.new_context(viewport={'width':390,'height':844},color_scheme=theme)
                    page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    for name,path in (('home','/'),('plans','/plans'),('privacy','/privacy'),('account_login','/account')):
                        page.goto(site+path);expect(page.locator('h1')).to_be_visible()
                        check_header_layout(page)
                        page.screenshot(path=str(OUT/(name+'_'+theme+'.png')),full_page=True)
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),path
                    page.get_by_label('Электронная почта',exact=True).fill('tester@example.test')
                    page.get_by_label('Пароль',exact=True).fill(PASSWORD)
                    page.get_by_role('button',name='Продолжить',exact=True).click()
                    expect(page.get_by_role('heading',name='Ваш ULADIM')).to_be_visible()
                    expect(page.get_by_role('heading',name='Ваш доступ: Free')).to_be_visible()
                    page.screenshot(path=str(OUT/('customer_'+theme+'.png')),full_page=True)
                    page.get_by_role('button',name='Поддержка',exact=True).click()
                    page.get_by_label('Тема',exact=True).fill('Synthetic browser support '+theme)
                    page.get_by_label('Сообщение',exact=True).fill('A synthetic fixture, no personal records.')
                    page.get_by_role('button',name='Отправить',exact=True).click()
                    expect(page.get_by_role('heading',name='Synthetic browser support '+theme,exact=True)).to_be_visible()
                    page.screenshot(path=str(OUT/('support_'+theme+'.png')),full_page=True)
                    page.goto(staff+'/')
                    expect(page.get_by_role('heading',name='Вход в Control')).to_be_visible()
                    page.screenshot(path=str(OUT/('control_login_'+theme+'.png')),full_page=True)
                    # TOTP counters are replay-protected; use a fresh context/counter
                    # for the second theme, never regenerate or weaken the assertion.
                    if theme=='light':
                        page.get_by_label('Электронная почта',exact=True).fill('owner@example.test')
                        page.get_by_label('Пароль',exact=True).fill(PASSWORD)
                        page.get_by_label('Код приложения-аутентификатора',exact=True).fill(totp(enrollment['totp_secret'],int(backend.clock())//30))
                        page.get_by_role('button',name='Продолжить',exact=True).click()
                        expect(page.get_by_role('heading',name='Обзор сервиса')).to_be_visible()
                        page.screenshot(path=str(OUT/'control_dashboard_light.png'),full_page=True)
                        page.get_by_label('Раздел Control',exact=True).select_option('users')
                        page.get_by_label('ID или почта',exact=True).fill('tester@example.test')
                        page.get_by_role('button',name='Найти',exact=True).click()
                        expect(page.get_by_role('heading',name='tester@example.test')).to_be_visible()
                        page.screenshot(path=str(OUT/'control_users_light.png'),full_page=True)
                        page.get_by_role('button',name='Открыть аккаунт',exact=True).click()
                        expect(page.get_by_role('heading',name='Доступ: Free',exact=True)).to_be_visible()
                        page.get_by_label('Причина выдачи',exact=True).fill('Synthetic 30-day closed test')
                        page.get_by_label('Уровень',exact=True).select_option('Premium')
                        page.get_by_label('Основание',exact=True).select_option('promo')
                        page.get_by_label('Срок доступа',exact=True).select_option('30')
                        page.get_by_role('button',name='Выдать доступ',exact=True).click()
                        expect(page.get_by_role('heading',name='Доступ: Premium',exact=True)).to_be_visible()
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                        page.screenshot(path=str(OUT/'control_user_grant_light.png'),full_page=True)
                        with backend.connect() as db:
                            grant=db.execute('SELECT * FROM entitlement_grants').fetchone()
                        assert grant['source']=='promo' and grant['tier']=='Premium'
                        assert 29*86400 < grant['valid_until']-int(backend.clock()) <= 30*86400
                        page.get_by_role('button',name='Отозвать выдачу',exact=True).click()
                        page.get_by_label('Причина отзыва',exact=True).fill('Synthetic test finished')
                        page.get_by_role('button',name='Подтвердить отзыв выдачи',exact=True).click()
                        expect(page.get_by_role('heading',name='Доступ: Free',exact=True)).to_be_visible()
                        expect(page.get_by_role('heading',name='Premium · Отозван',exact=True)).to_be_visible()
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                        page.screenshot(path=str(OUT/'control_user_revoked_light.png'),full_page=True)
                    assert not errors,errors
                    context.close()
                browser.close()
        finally:
            server.shutdown();server.server_close();thread.join(5)
    (OUT/'RESULT.json').write_text(json.dumps({'result':'passed','fixture':'loopback synthetic only','screenshots':len(list(OUT.glob('*.png'))),'production_deployed':False},indent=2)+'\n')
    print('Browser acceptance passed; real rendered screenshots saved to web_evidence.')

if __name__=='__main__':main()
