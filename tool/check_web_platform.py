"""Web product acceptance against actual WSGI + disposable synthetic records.
No production access. Screenshots are evidence, not automatically accepted baselines.
"""
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import json, os, sys, tempfile, threading, uuid
from wsgiref.simple_server import make_server
from cryptography.fernet import Fernet
from tool.web_browser_navigation import open_tab, open_settings, open_finance_section
from playwright.sync_api import sync_playwright, expect
from backend.config import Settings
from backend.production import Application
from backend.service import Backend
from tool.check_pwa_browser import Quiet
from tool.web_test_tls import enable_test_tls

OUT=Path('web_evidence/platform')
PASSWORD='synthetic-web-platform-password'
@contextmanager
def fixture(https=False):
    with tempfile.TemporaryDirectory() as folder:
        mail={}
        dsn=os.environ.get('ULADIM_WEB_TEST_DATABASE_URL','')
        schema=None
        if dsn:
            from urllib.parse import urlsplit
            from backend.postgres import PostgresBackend
            import psycopg
            from psycopg import sql
            if urlsplit(dsn).path!='/lifeos_test':raise RuntimeError('Fixture refuses non-test database')
            schema='web_'+uuid.uuid4().hex
            with psycopg.connect(dsn,autocommit=True) as db:db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
            backend=PostgresBackend(dsn,Fernet(Fernet.generate_key()),schema=schema,migrate=True)
            deliver=backend._deliver
            def capture(db,email,code,purpose):
                deliver(db,email,code,purpose);mail[email]=code
            backend._deliver=capture
        else:
            backend=Backend(Path(folder)/'fixture.db',deliver=lambda e,c:mail.update({e:c}))
            backend.cipher=Fernet(Fernet.generate_key())
        with backend.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS http_limits(key TEXT PRIMARY KEY,count BIGINT NOT NULL,until_at BIGINT NOT NULL)')
        session=backend.register('web@example.test',PASSWORD);actor=backend.authenticate(session['token'])
        backend.verify(actor,mail[actor['email']]);actor=backend.authenticate(session['token'])
        wid=str(uuid.uuid4());backend.family(actor,{'id':str(uuid.uuid4()),'action':'workspace.create','workspace_id':wid,'kind':'personal','name':'Личное пространство'})
        def put(kind,data):
            rid=str(uuid.uuid4());backend.batch(actor,wid,[{'id':str(uuid.uuid4()),'action':'record.put','record_id':rid,'revision':0,'kind':kind,'visibility':'private','audience':[],'data':data}]);return rid
        put('task',{'title':'Подготовить план на неделю','completed':0,'assignment':'any','assignees':[],'review':0})
        put('task',{'title':'Забрать заказ','completed':1,'assignment':'any','assignees':[],'review':0})
        put('note',{'body':'Планы на выходные\nПровести время с близкими и выбраться за город.'})
        account=put('account',{'name':'Основной счёт','currency':'RUB','opening_minor':12000000})
        put('transaction',{'kind':'expense','amount_minor':352000,'currency':'RUB','date':'2026-11-10','label':'Продукты на неделю','account_id':account})
        put('transaction',{'kind':'income','amount_minor':15000000,'currency':'RUB','date':'2026-11-01','label':'Зарплата','account_id':account})
        put('budget',{'name':'Повседневные расходы','currency':'RUB','limit_minor':3000000,'period':'month','start_on':'2026-11-01','end_on':None,'rollover':'none','participants':[]})
        put('event',{'title':'Встреча с семьёй','schedule':{'localStart':'2026-11-10T18:30:00','timezone':'Europe/Moscow','allDay':False,'repeat':'weekly','interval':1,'until':None}})
        settings=Settings.load({'DATABASE_URL':'postgresql://example/db','EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),'RATE_LIMIT_KEY':'fixture-'+'x'*48,'SMTP_HOST':'127.0.0.1','SMTP_TLS':'none','EMAIL_FROM':'fixture@example.test'})
        server=make_server('127.0.0.1',0,lambda e,s:[],handler_class=Quiet)
        if https: enable_test_tls(server,folder)
        origin=('https' if https else 'http')+'://localhost:'+str(server.server_port)
        server.set_app(Application(backend,replace(settings,site_origin=origin,control_origin='http://control.localhost:'+str(server.server_port),require_https=False)))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:yield origin,backend,actor,wid
        finally:
            server.shutdown();server.server_close();thread.join(5)
            if schema:
                backend.close()
                with psycopg.connect(dsn,autocommit=True) as db:db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))

def login(page,origin):
    page.goto(origin+'/app');page.get_by_label('Электронная почта',exact=True).fill('web@example.test')
    page.locator('input[name=password]').fill(PASSWORD);page.get_by_role('button',name='Войти',exact=True).click()
    expect(page.get_by_role('heading',name='Сегодня',exact=True)).to_be_visible()

def main():
    OUT.mkdir(parents=True,exist_ok=True);checks=[]
    with fixture() as (origin,backend,actor,wid),sync_playwright() as p:
        browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
        context=browser.new_context(viewport={'width':375,'height':812},timezone_id='Europe/Moscow',locale='ru-RU',reduced_motion='reduce',service_workers='block')
        context.tracing.start(screenshots=True,snapshots=True,sources=True)
        page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            login(page,origin)
            page.locator('.nav').get_by_role('button',name='Задачи',exact=True).click()
            task = page.locator('.task-row').filter(has_text='Подготовить план на неделю')
            writes = []

            def fail_refresh(route):
                if route.request.method == 'POST':
                    writes.append(route.request.post_data_json['operations'][0]['id'])
                    route.continue_()
                elif len(writes) == 1:
                    route.abort()
                else:
                    route.continue_()

            page.route('**/account/api/sync*', fail_refresh)
            task.get_by_role('checkbox').click()
            retry = task.get_by_role('button', name='Повторить', exact=True)
            expect(retry).to_be_visible()
            expect(task.get_by_role('checkbox')).to_be_checked()
            page.unroute('**/account/api/sync*', fail_refresh)

            def track_writes(route):
                if route.request.method == 'POST':
                    writes.append(route.request.post_data_json['operations'][0]['id'])
                route.continue_()

            page.route('**/account/api/sync*', track_writes)
            retry.click()
            expect(retry).to_have_count(0)
            page.unroute('**/account/api/sync*', track_writes)
            assert len(writes) == 1, writes
            checks.append('accepted_task_recovers_without_resubmitting')

            writes.clear()
            page.route('**/account/api/sync*', fail_refresh)
            page.get_by_role('button', name='Добавить', exact=True).click()
            editor = page.get_by_role('dialog')
            field = editor.get_by_label('Название задачи', exact=True)
            field.fill('Accepted task survives refresh failure')
            editor.get_by_role('button', name='Сохранить', exact=True).click()
            retry = editor.get_by_role('button', name='Повторить', exact=True)
            expect(retry).to_be_enabled()
            expect(field).to_be_disabled()
            expect(editor.get_by_text('Изменения сохранены. Повторите обновление списка.')).to_be_visible()
            page.unroute('**/account/api/sync*', fail_refresh)
            page.route('**/account/api/sync*', track_writes)
            retry.click()
            expect(editor).to_have_count(0)
            expect(page.get_by_text('Accepted task survives refresh failure', exact=True)).to_be_visible()
            page.unroute('**/account/api/sync*', track_writes)
            assert len(writes) == 1, writes
            checks.append('accepted_editor_locks_fields_until_refresh')

            page.get_by_label('Поиск задач',exact=True).fill('заказ')
            expect(page.get_by_text('Забрать заказ',exact=True)).to_be_visible()
            expect(page.get_by_text('Подготовить план на неделю',exact=True)).to_have_count(0)
            page.get_by_label('Статус задачи',exact=True).select_option('open')
            expect(page.get_by_text('Забрать заказ',exact=True)).to_have_count(0);checks.append('task_search_and_completion_filter')
            page.locator('.nav').get_by_role('button',name='Календарь',exact=True).click()
            page.get_by_role('button',name='Новое событие',exact=True).click()
            d=page.get_by_role('dialog');d.get_by_label('Название',exact=True).fill('Проверяемое событие')
            d.locator('[name=localStart]').fill('2026-11-12T14:30')
            d.locator('.event-options > summary').click()
            d.locator('[name=timezone]').fill('Asia/Tashkent')
            d.get_by_role('button',name='Сохранить',exact=True).click();expect(d).to_have_count(0)
            events=[r for r in backend.pull(actor,wid,0)['records'] if r['kind']=='event']
            assert any(r['data']['title']=='Проверяемое событие' and r['data']['schedule']['timezone']=='Asia/Tashkent' for r in events)
            checks.append('event_create_shared_protocol')
            open_tab(page,'Заметки')
            page.get_by_role('button',name='Редактировать',exact=True).first.click();d=page.get_by_role('dialog')
            d.get_by_label('Текст заметки',exact=True).fill('Длинная заметка\n'+'Текст '*1000)
            d.get_by_role('button',name='Сохранить',exact=True).click();expect(d).to_have_count(0)
            assert any(r['data'].get('body','').startswith('Длинная заметка') for r in backend.pull(actor,wid,0)['records'])
            page.get_by_role('button',name='Редактировать',exact=True).first.click();d=page.get_by_role('dialog')
            d.locator('.editor-more > summary').click()
            d.get_by_role('button',name='Удалить',exact=True).click()
            page.get_by_role('button',name='Отменить',exact=True).click()
            assert not any(r['deleted'] for r in backend.pull(actor,wid,0)['records']);checks.append('note_edit_and_cancel_before_delete')
            page.locator('.nav').get_by_role('button',name='Финансы',exact=True).click()
            expect(page.locator('.finance-metric').first).to_be_visible()
            account_id=next(r['id'] for r in backend.pull(actor,wid,0)['records'] if r['kind']=='account')
            page.get_by_role('button',name='Добавить операцию',exact=True).click()
            d=page.get_by_role('dialog');d.locator('[name=amount]').fill('125,50');d.locator('[name=label]').fill('Покупка из браузера')
            d.locator('[name=account]').select_option(account_id);d.locator('[name=date]').fill('2026-11-12')
            d.get_by_role('button',name='Сохранить',exact=True).click();expect(page.locator('.ledger')).to_contain_text('Покупка из браузера')
            saved=[r for r in backend.pull(actor,wid,0)['records'] if r['kind']=='transaction' and r['data']['label']=='Покупка из браузера']
            assert len(saved)==1 and saved[0]['data']['amount_minor']==12550 and saved[0]['data']['account_id']==account_id
            open_finance_section(page,'accounts')
            assert ''.join(page.locator('.account-balance .finance-account-amount').inner_text().split()).replace(',','.')=='266354.50RUB'
            checks.append('browser_financial_write_and_exact_account_balance')
            for theme in ('light','dark'):
                page.evaluate("value=>{state.theme=value;preferences();}",theme)
                for width in (375,768,1024,1440):
                    page.set_viewport_size({'width':width,'height':900})
                    for tab,label in [('today','Сегодня'),('calendar','Календарь'),('tasks','Задачи'),('notes','Заметки'),('money','Финансы'),('account','Профиль')]:
                        open_tab(page,label)
                        selected=page.locator(f'.nav button[data-tab="{tab}"][data-section=""][aria-current=page]:visible')
                        if tab=='account' and width>=760:
                            # Desktop profile lives in the shared header and
                            # sidebar identity control, outside the module list.
                            expect(page.locator('.header-profile')).to_have_accessible_name('Профиль')
                            expect(page.locator('.reference-identity')).to_be_visible()
                            expect(page.locator('.reference-breadcrumb strong')).to_have_text(label)
                        else:
                            expect(selected).to_have_count(1)
                            expect(selected.locator('span:not(.reference-nav-count)')).to_have_text('Обзор финансов' if tab=='money' and width>=760 else label)
                        if width<760:
                            expect(page.locator('.nav button[data-tab]:visible')).to_have_count(6)
                            expect(page.locator('.nav .nav-more')).to_be_hidden()
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(theme,width,tab)
                        for control in page.locator('.nav button:visible').all():
                            box=control.bounding_box();assert box and box['width']>=44 and box['height']>=44,(width,tab,'touch-target')
                            expect(control).not_to_have_accessible_name('')
                            label_span=control.locator(':scope > span:not(.reference-nav-count):not(.reference-avatar)')
                            if label_span.count():
                                assert label_span.evaluate('(s)=>{const a=s.getBoundingClientRect(),b=s.closest("button").getBoundingClientRect();return a.left>=b.left&&a.right<=b.right&&a.top>=b.top&&a.bottom<=b.bottom}'),(width,tab,'nav-label-clipped')
                        if tab=='tasks':
                            page.locator('[name=task-search]').fill('');page.locator('[name=task-status]').select_option('all')
                        if tab=='calendar':
                            page.locator('[name=calendar-day]').fill('2026-11-12')
                            contrasts=page.locator('.calendar-date').evaluate_all(r'''dates=>dates.map(d=>{
                                const style=getComputedStyle(d),card=getComputedStyle(d.closest('.card'));
                                const rgb=s=>s.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});
                                const lum=s=>rgb(s).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);
                                const fg=lum(style.color),bg=lum(style.backgroundColor==='rgba(0, 0, 0, 0)'?card.backgroundColor:style.backgroundColor);
                                return (Math.max(fg,bg)+.05)/(Math.min(fg,bg)+.05);
                            })''')
                            assert contrasts and min(contrasts)>=4.5,(theme,width,'calendar date contrast',min(contrasts))
                        if tab=='account':
                            if width<760:
                                expect(page.locator('.settings-navigation')).to_be_hidden()
                                expect(page.locator('.reference-profile-options button:visible')).to_have_count(8)
                            else:
                                expect(page.locator('.settings-navigation')).to_be_visible()
                            open_settings(page,'profile')
                            expect(page.locator('.profile-summary .account-email')).to_have_text('web@example.test')
                            for option in ('Оформление','Аккаунт и приватность','Устройства и сессии'):
                                expect(page.locator('.reference-profile-options').get_by_role('button',name=option,exact=True)).to_be_visible()
                            expect(page.get_by_role('heading',name='Поддержка',exact=True)).to_have_count(0)
                            open_settings(page,'support')
                            expect(page.get_by_role('heading',name='Поддержка',exact=True)).to_be_visible()
                        page.screenshot(path=str(OUT/f'{tab}-{width}-{theme}.png'),full_page=False)
                    open_tab(page,'Финансы')
                    page.get_by_role('button',name='Добавить операцию',exact=True).click()
                    d=page.get_by_role('dialog');expect(d).to_be_visible()
                    d.locator('[name=amount]').fill('125,50');d.locator('[name=label]').fill('Проверка экранной формы')
                    assert d.evaluate('(d)=>d.scrollWidth<=d.clientWidth'),(theme,width,'form-overflow')
                    page.screenshot(path=str(OUT/f'transaction-form-{width}-{theme}.png'),full_page=False)
                    if width==375:
                        page.set_viewport_size({'width':375,'height':420})
                        d.locator('[name=label]').focus()
                        save=d.get_by_role('button',name='Сохранить',exact=True);save.scroll_into_view_if_needed()
                        box=save.bounding_box();assert box and box['y']>=0 and box['y']+box['height']<=420,'keyboard-height form button clipped'
                        field=d.locator('[name=label]').bounding_box();assert field['y']+field['height']<=box['y'],'short-height submit overlays text field'
                        page.screenshot(path=str(OUT/f'keyboard-height-form-{theme}.png'))
                        page.set_viewport_size({'width':812,'height':375})
                        save.scroll_into_view_if_needed();box=save.bounding_box();assert box and box['y']>=0 and box['y']+box['height']<=375,'landscape form button clipped'
                        page.screenshot(path=str(OUT/f'landscape-form-{theme}.png'))
                        page.set_viewport_size({'width':width,'height':900})
                    d.get_by_role('button',name='Закрыть',exact=True).click()
                checks.append('responsive_'+theme)
            page.set_viewport_size({'width':375,'height':812});page.evaluate("document.documentElement.style.fontSize='24px'")
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert page.locator('.nav').evaluate('n=>[...n.querySelectorAll("button span:last-child")].filter(s=>s.getClientRects().length).every(s=>s.scrollWidth<=s.clientWidth||getComputedStyle(s).overflow==="hidden")'),'scaled nav text spills outside buttons'
            page.screenshot(path=str(OUT/'text-scale-150-percent.png'))
            checks.append('text_scale_150_percent')
            assert not errors,errors
        finally:
            if sys.exc_info()[0]:page.screenshot(path=str(OUT/'failure.png'),full_page=True)
            context.tracing.stop(path=str(OUT/'trace.zip'))
            context.close();browser.close()
    (OUT/'RESULT.json').write_text(json.dumps({'checks':checks,'result':'passed','backend':'actual WSGI / disposable PostgreSQL fixture' if os.environ.get('ULADIM_WEB_TEST_DATABASE_URL') else 'actual WSGI / disposable SQLite fixture; production not tested'},ensure_ascii=False,indent=2))
    print('Platform acceptance:',', '.join(checks))

if __name__=='__main__':main()
