"""Password-first and open-signup browser checks on disposable synthetic data.

No SMTP, production traffic, personal email or retained user credentials.
"""
from dataclasses import replace
import json
import tempfile
import threading
from pathlib import Path
from wsgiref.simple_server import make_server
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright, expect
from backend.service import Backend
from backend.config import Settings
from backend.production import Application
from backend.customer_mfa import CustomerMFA
from backend.control import Control, totp
from tool.check_pwa_browser import Quiet

PASSWORD = 'synthetic-password-first-browser'
OUT = Path('web_evidence/registration')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cases = []
    with tempfile.TemporaryDirectory() as folder:
        mail, clock = {}, [1800000000]
        backend = Backend(Path(folder)/'fixture.db', deliver=lambda e,c:mail.update({e:c}), clock=lambda:clock[0])
        backend.cipher = Fernet(Fernet.generate_key())
        with backend.connect() as db:
            db.execute('CREATE TABLE http_limits(key TEXT PRIMARY KEY,count BIGINT NOT NULL,until_at BIGINT NOT NULL)')
        session = backend.register('factor@example.test', PASSWORD)
        actor = backend.authenticate(session['token']); backend.verify(actor,mail[actor['email']]); actor = backend.authenticate(session['token'])
        mfa = CustomerMFA(backend); factor = mfa.begin(actor,PASSWORD)
        mfa.enable(actor,PASSWORD,factor['enrollment'],totp(factor['totp_secret'],clock[0]//30))
        staff_factor = Control(backend).bootstrap(actor['email'])
        server = make_server('127.0.0.1',0,lambda e,s:[],handler_class=Quiet)
        origin = 'http://localhost:'+str(server.server_port)
        staff = 'http://control.localhost:'+str(server.server_port)
        settings = Settings.load({'DATABASE_URL':'postgresql://unused/test','EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),'RATE_LIMIT_KEY':'synthetic-browser-'+'x'*48,'SMTP_HOST':'localhost','SMTP_TLS':'none','EMAIL_FROM':'fixture@example.test'})
        app = Application(backend,replace(settings,site_origin=origin,control_origin=staff,require_https=False,registration_mode='open'))
        server.set_app(app)
        thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                for width, height in [(390,844),(834,1194),(1440,1000)]:
                    for route in ['/app','/account']:
                        context = browser.new_context(viewport={'width':width,'height':height},color_scheme='light')
                        page = context.new_page(); errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
                        clock[0] += 901 # A new independent fixture window, no production limiter bypass.
                        page.goto(origin+route)
                        expect(page.locator('input[name=code]')).to_have_count(0)
                        expect(page.locator('input[type=password]')).to_have_count(1)
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                        page.screenshot(path=str(OUT/(route[1:]+'-login-'+str(width)+'.png')),full_page=True)
                        page.get_by_label('Электронная почта',exact=True).fill(actor['email'])
                        page.get_by_label('Пароль (минимум 7 символов)',exact=True).fill('incorrect-password')
                        with page.expect_response('**/account/api/login') as response:
                            page.get_by_role('button',name='Войти',exact=True).click()
                        assert response.value.status==401
                        expect(page.locator('input[name=code]')).to_have_count(0)
                        page.get_by_label('Пароль (минимум 7 символов)',exact=True).fill(PASSWORD)
                        page.get_by_role('button',name='Войти',exact=True).click()
                        expect(page.locator('input[name=code]')).to_be_visible()
                        expect(page.locator('input[type=password]')).to_have_count(0)
                        expect(page.locator('input[name=code]')).to_have_attribute('autocomplete','one-time-code')
                        page.screenshot(path=str(OUT/(route[1:]+'-mfa-'+str(width)+'.png')),full_page=True)
                        assert PASSWORD not in page.evaluate('JSON.stringify(localStorage)')
                        assert not page.url.endswith(PASSWORD)
                        page.locator('input[name=code]').fill(totp(factor['totp_secret'],clock[0]//30))
                        page.get_by_role('button',name='Войти',exact=True).click()
                        expect(page.get_by_role('heading',name='Сегодня' if route=='/app' else 'Ваш ULADIM',exact=True)).to_be_visible()
                        assert not errors, errors
                        cases.append({'case':route+' password-first MFA '+str(width),'expected':'no password or session before factor; then authenticated','actual':'passed'})
                        context.close()
                for route in ['/app','/account']:
                    clock[0] += 901
                    context = browser.new_context(viewport={'width':390,'height':844})
                    page = context.new_page();page.goto(origin+route)
                    page.get_by_role('button',name='Создать аккаунт',exact=True).click()
                    form = page.locator('dialog form') if route=='/app' else page.locator('form')
                    expect(form.locator('input[name=invitation]')).to_have_count(0)
                    email = route[1:]+'-signup@example.test'
                    form.locator('input[type=email]').fill(email)
                    form.locator('input[type=password]').fill(PASSWORD)
                    with page.expect_response('**/account/api/signup') as response:
                        form.get_by_role('button',name='Создать аккаунт',exact=True).click()
                    assert response.value.json()=={'accepted':True,'next':'check_email'}
                    expect(page.locator('input[name=code]')).to_be_visible()
                    old = mail[email]
                    with page.expect_response('**/account/api/resend-signup') as response:
                        page.get_by_role('button',name='Отправить код ещё раз',exact=True).click()
                    assert response.value.status==200 and mail[email]!=old
                    page.locator('input[name=code]').fill(mail[email])
                    page.get_by_role('button',name='Подтвердить почту',exact=True).click()
                    expect(page.locator('input[type=password]')).to_be_visible()
                    page.get_by_label('Электронная почта',exact=True).fill(email)
                    page.get_by_label('Пароль (минимум 7 символов)',exact=True).fill(PASSWORD)
                    page.get_by_role('button',name='Войти',exact=True).click()
                    expect(page.get_by_role('heading',name='Сегодня' if route=='/app' else 'Ваш ULADIM',exact=True)).to_be_visible()
                    expect(page.locator('input[name=code]')).to_have_count(0)
                    cases.append({'case':route+' open signup/resend/confirmation/non-MFA login','expected':'verified account, no invitation, no automatic MFA','actual':'passed'})
                    context.close()
                clock[0] += 901
                context=browser.new_context();page=context.new_page();page.goto(staff+'/')
                expect(page.locator('input[name=code]')).to_have_count(0)
                page.get_by_label('Электронная почта',exact=True).fill(actor['email'])
                page.get_by_label('Пароль (минимум 7 символов)',exact=True).fill(PASSWORD)
                page.get_by_role('button',name='Войти',exact=True).click()
                expect(page.locator('input[type=password]')).to_have_count(0)
                page.locator('input[name=code]').fill(totp(staff_factor['totp_secret'],clock[0]//30))
                page.get_by_role('button',name='Войти',exact=True).click()
                expect(page.get_by_role('heading',name='Обзор сервиса',exact=True)).to_be_visible()
                cases.append({'case':'Control mandatory password-first MFA','expected':'no staff session until factor','actual':'passed'})
                context.close();browser.close()
        finally:
            server.shutdown();server.server_close();thread.join(5)
    (OUT/'RESULT.json').write_text(json.dumps({'result':'passed','cases':cases,'fixture':'disposable SQLite, browser Chromium, synthetic mail capture; no production SMTP or physical device'},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':len(cases)},ensure_ascii=False))


if __name__=='__main__':main()
