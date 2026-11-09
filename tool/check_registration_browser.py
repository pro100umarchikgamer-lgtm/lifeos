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
            p=sync_playwright().start()
            try:
                browser = p.chromium.launch()
                for width, height in [(390,844),(834,1194),(1440,1000)]:
                    preview=browser.new_context(viewport={'width':width,'height':height},color_scheme='light')
                    public=preview.new_page();public.goto(origin+'/')
                    expect(public.get_by_role('link',name='Начать бесплатно',exact=True)).to_have_attribute('href','/app?action=signup')
                    assert public.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    public.screenshot(path=str(OUT/('product-home-'+str(width)+'.png')),full_page=True)
                    public.goto(origin+'/early-access')
                    expect(public.get_by_role('link',name='Начать бесплатно',exact=True)).to_be_visible()
                    expect(public.locator('input[name=website]')).to_have_count(0)
                    preview.close()
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
                        expect(page.get_by_role('heading',name='Сегодня',exact=True)).to_be_visible()
                        assert not errors, errors
                        cases.append({'case':route+' password-first MFA '+str(width),'expected':'no password or session before factor; then authenticated','actual':'passed'})
                        context.close()
                for route in ['/app','/account']:
                    clock[0] += 901
                    context = browser.new_context(viewport={'width':390,'height':844})
                    page = context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(origin+route)
                    page.get_by_role('button',name='Создать аккаунт',exact=True).click()
                    if route=='/account':
                        expect(page.get_by_role('heading',name='Создать аккаунт',exact=True)).to_be_visible()
                    form = page.locator('dialog form') if route=='/app' else page.locator('form')
                    expect(form.locator('input[name=invitation]')).to_have_count(0)
                    email = route[1:]+'-signup@example.test'
                    form.locator('input[type=email]').fill(email)
                    form.locator('input[type=password]').fill(PASSWORD)
                    with page.expect_response('**/account/api/signup') as response:
                        form.get_by_role('button',name='Создать аккаунт',exact=True).click()
                    assert response.value.json()=={'accepted':True,'next':'check_email'}
                    expect(page.locator('input[name=code]')).to_be_visible()
                    if route=='/app':
                        expect(page.get_by_role('dialog',name='Подтвердить почту',exact=True)).to_be_visible()
                        expect(page.get_by_role('dialog').get_by_role('button',name='Закрыть',exact=True)).to_have_count(1)
                    old = mail[email]
                    with page.expect_response('**/account/api/resend-signup') as response:
                        page.get_by_role('button',name='Отправить код ещё раз',exact=True).click()
                    assert response.value.status==200 and mail[email]!=old
                    page.locator('input[name=code]').fill(mail[email])
                    with page.expect_response('**/account/api/confirm-signup') as confirmation_response:
                        page.get_by_role('button',name='Подтвердить почту',exact=True).click()
                    assert confirmation_response.value.status == 200
                    expect(page.locator('input[name=code]')).to_have_count(0)
                    expect(page.get_by_role('heading',name='Войти',exact=True)).to_be_visible()
                    expect(page.locator('input[type=password]')).to_be_visible()
                    page.get_by_label('Электронная почта',exact=True).fill(email)
                    page.get_by_label('Пароль (минимум 7 символов)',exact=True).fill(PASSWORD)
                    with page.expect_response('**/account/api/login') as login_response:
                        page.get_by_role('button',name='Войти',exact=True).click()
                    assert login_response.value.status == 200, (route, login_response.value.status, login_response.value.json())
                    expect(page.get_by_role('heading',name='Сегодня',exact=True)).to_be_visible()
                    expect(page.locator('input[name=code]')).to_have_count(0)
                    expect(page.locator('select[name=workspace]')).to_have_count(0)
                    # Both entry points now lead to the same PWA/account and setup.
                    page.get_by_role('button',name='Создать личное пространство',exact=True).click()
                    page.get_by_role('dialog').get_by_label('Название',exact=True).fill('First personal space')
                    page.get_by_role('dialog').get_by_role('button',name='Сохранить',exact=True).click()
                    expect(page.locator('.getting-started')).to_be_visible()
                    expect(page.locator('select[name=workspace]')).to_have_count(1)
                    page.get_by_role('button',name='Задача',exact=True).click()
                    page.get_by_label('Название задачи',exact=True).fill('First verified task')
                    page.get_by_role('dialog').get_by_role('button',name='Сохранить',exact=True).click()
                    expect(page.get_by_text('First verified task',exact=True)).to_be_visible()
                    page.get_by_role('button',name='Заметки',exact=True).click()
                    page.get_by_role('button',name='Добавить',exact=True).click()
                    page.get_by_label('Текст заметки',exact=True).fill('First verified note')
                    page.get_by_role('dialog').get_by_role('button',name='Сохранить',exact=True).click()
                    page.get_by_role('button',name='Редактировать',exact=True).click()
                    expect(page.get_by_role('dialog').get_by_role('button',name='Удалить',exact=True)).to_be_visible()
                    page.get_by_label('Текст заметки',exact=True).fill('Edited verified note')
                    page.get_by_role('dialog').get_by_role('button',name='Сохранить',exact=True).click()
                    expect(page.get_by_text('Edited verified note',exact=True)).to_be_visible()
                    page.get_by_role('button',name='Финансы',exact=True).click()
                    page.get_by_role('button',name='Добавить',exact=True).click()
                    page.get_by_role('dialog').get_by_role('button',name='Счёт',exact=True).click()
                    page.get_by_role('dialog').get_by_label('Название',exact=True).fill('First account')
                    page.get_by_label('Начальный остаток',exact=True).fill('10000')
                    page.get_by_role('dialog').get_by_role('button',name='Сохранить',exact=True).click()
                    page.get_by_role('button',name='Добавить',exact=True).click()
                    page.get_by_role('dialog').get_by_role('button',name='Расход или доход',exact=True).click()
                    page.get_by_label('Сумма',exact=True).fill('1250,50')
                    page.locator('select[name=account]').select_option(label='First account · RUB')
                    page.get_by_label('Название или описание',exact=True).fill('First expense')
                    page.get_by_role('dialog').get_by_role('button',name='Сохранить',exact=True).click()
                    expect(page.get_by_text('First expense',exact=True)).to_be_visible()
                    page.screenshot(path=str(OUT/(route[1:]+'-first-finances.png')),full_page=True)
                    for fw,fh in [(834,1194),(1440,1000)]:
                        page.set_viewport_size({'width':fw,'height':fh})
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                        page.screenshot(path=str(OUT/(route[1:]+'-first-finances-'+str(fw)+'.png')),full_page=True)
                    with backend.connect() as db:
                        uid = db.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()['id']
                        rows = db.execute('SELECT kind FROM records WHERE owner_id=? AND deleted=0',(uid,)).fetchall()
                        assert sorted(row['kind'] for row in rows)==['account','note','task','transaction']
                    cases.append({'case':route+' first workspace/task/note/edit/account/expense','expected':'four real records owned by the verified account; usable edit/delete controls','actual':'passed'})
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
            except Exception:
                diagnostic={'url':page.url,'body':page.locator('body').inner_text(),'errors':errors if 'errors' in locals() else []}
                (OUT/'FAILURE.json').write_text(json.dumps(diagnostic,ensure_ascii=False,indent=2))
                page.screenshot(path=str(OUT/'failure-masked.png'),full_page=True,mask=[page.locator('input')])
                raise
            finally:
                p.stop()
        finally:
            server.shutdown();server.server_close();thread.join(5)
    (OUT/'RESULT.json').write_text(json.dumps({'result':'passed','cases':cases,'fixture':'disposable SQLite, browser Chromium, synthetic mail capture; no production SMTP or physical device'},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':len(cases)},ensure_ascii=False))


if __name__=='__main__':main()
