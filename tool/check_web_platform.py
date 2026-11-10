"""Web product acceptance against actual WSGI + disposable synthetic records.
No production access. Screenshots are evidence, not automatically accepted baselines.
"""
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import json, os, tempfile, threading, uuid
from wsgiref.simple_server import make_server
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright, expect
from backend.config import Settings
from backend.production import Application
from backend.service import Backend
from tool.check_pwa_browser import Quiet

OUT=Path('web_evidence/platform')
PASSWORD='synthetic-web-platform-password'
@contextmanager
def fixture():
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
        server=make_server('127.0.0.1',0,lambda e,s:[],handler_class=Quiet);origin='http://localhost:'+str(server.server_port)
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
        context=browser.new_context(viewport={'width':375,'height':812},timezone_id='Europe/Moscow',reduced_motion='reduce')
        page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        login(page,origin)
        page.locator('.nav').get_by_role('button',name='Задачи',exact=True).click()
        page.get_by_label('Поиск задач',exact=True).fill('заказ')
        expect(page.get_by_text('Забрать заказ',exact=True)).to_be_visible()
        expect(page.get_by_text('Подготовить план на неделю',exact=True)).to_have_count(0)
        page.get_by_label('Статус задачи',exact=True).select_option('open')
        expect(page.get_by_text('Забрать заказ',exact=True)).to_have_count(0);checks.append('task_search_and_completion_filter')
        page.locator('.nav').get_by_role('button',name='Календарь',exact=True).click()
        page.get_by_role('button',name='Добавить',exact=True).click()
        d=page.get_by_role('dialog');d.get_by_label('Название',exact=True).fill('Проверяемое событие')
        d.locator('[name=localStart]').fill('2026-11-12T14:30');d.locator('[name=timezone]').fill('Asia/Tashkent')
        d.get_by_role('button',name='Сохранить',exact=True).click();expect(d).to_have_count(0)
        events=[r for r in backend.pull(actor,wid,0)['records'] if r['kind']=='event']
        assert any(r['data']['title']=='Проверяемое событие' and r['data']['schedule']['timezone']=='Asia/Tashkent' for r in events)
        checks.append('event_create_shared_protocol')
        page.locator('.nav').get_by_role('button',name='Заметки',exact=True).click()
        page.get_by_role('button',name='Редактировать',exact=True).first.click();d=page.get_by_role('dialog')
        d.get_by_label('Текст заметки',exact=True).fill('Длинная заметка\n'+'Текст '*1000)
        d.get_by_role('button',name='Сохранить',exact=True).click();expect(d).to_have_count(0)
        assert any(r['data'].get('body','').startswith('Длинная заметка') for r in backend.pull(actor,wid,0)['records'])
        page.get_by_role('button',name='Редактировать',exact=True).first.click();d=page.get_by_role('dialog')
        d.get_by_role('button',name='Удалить',exact=True).click()
        page.get_by_role('button',name='Отменить',exact=True).click()
        assert not any(r['deleted'] for r in backend.pull(actor,wid,0)['records']);checks.append('note_edit_and_cancel_before_delete')
        page.locator('.nav').get_by_role('button',name='Финансы',exact=True).click()
        expect(page.locator('.finance-total')).to_be_visible()
        checks.append('real_finance_overview')
        for theme in ('light','dark'):
            page.evaluate("value=>{state.theme=value;preferences();}",theme)
            for width in (375,768,1024,1440):
                page.set_viewport_size({'width':width,'height':900})
                for tab,label in [('today','Сегодня'),('calendar','Календарь'),('tasks','Задачи'),('notes','Заметки'),('money','Финансы'),('account','Профиль')]:
                    page.locator('.nav').get_by_role('button',name=label,exact=True).click();expect(page.locator('.nav button[aria-current=page]')).to_have_text(label)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(theme,width,tab)
                    for control in page.locator('.nav button').all():
                        box=control.bounding_box();assert box and box['width']>=44 and box['height']>=44,(width,tab,'touch-target')
                        assert control.locator('span:last-child').evaluate('(s)=>{const r=document.createRange();r.selectNodeContents(s);return r.getClientRects().length===1}'),(width,tab,'nav-label-wrap')
                    page.screenshot(path=str(OUT/f'{tab}-{width}-{theme}.png'),full_page=True)
                page.locator('.nav').get_by_role('button',name='Финансы',exact=True).click()
                page.get_by_role('button',name='Добавить',exact=True).click()
                page.get_by_role('dialog').get_by_role('button',name='Расход или доход',exact=True).click()
                d=page.get_by_role('dialog');expect(d).to_be_visible()
                d.locator('[name=amount]').fill('125,50');d.locator('[name=label]').fill('Проверка экранной формы')
                assert d.evaluate('(d)=>d.scrollWidth<=d.clientWidth'),(theme,width,'form-overflow')
                page.screenshot(path=str(OUT/f'transaction-form-{width}-{theme}.png'),full_page=True)
                d.get_by_role('button',name='Закрыть',exact=True).click()
            checks.append('responsive_'+theme)
        page.set_viewport_size({'width':375,'height':812});page.evaluate("document.documentElement.style.fontSize='24px'")
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');checks.append('text_scale_150_percent')
        assert not errors,errors
        context.close();browser.close()
    (OUT/'RESULT.json').write_text(json.dumps({'checks':checks,'result':'passed','backend':'actual WSGI / disposable PostgreSQL fixture' if os.environ.get('ULADIM_WEB_TEST_DATABASE_URL') else 'actual WSGI / disposable SQLite fixture; production not tested'},ensure_ascii=False,indent=2))
    print('Platform acceptance:',', '.join(checks))

if __name__=='__main__':main()
