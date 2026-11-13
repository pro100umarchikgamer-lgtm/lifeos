"""Focused real-browser check of finance destinations, reports and exact budget figures."""
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
import uuid
from wsgiref.simple_server import make_server
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright, expect
from backend.config import Settings
from backend.production import Application
from backend.service import Backend
from tool.check_pwa_browser import Quiet
from tool.web_browser_navigation import open_tab, open_finance_section

OUT=Path(os.environ.get('ULADIM_FINANCE_VIEWS_EVIDENCE','web_evidence/finance-views'))


def assert_money_lines(page,label):
    failures=page.locator('main .money-number:visible').evaluate_all("""items=>items.map(e=>{
        const range=document.createRange();range.selectNodeContents(e);
        const rect=e.getBoundingClientRect(),parent=e.parentElement.getBoundingClientRect();
        return {text:e.textContent,lines:range.getClientRects().length,
                contained:rect.left>=parent.left-1&&rect.right<=parent.right+1,
                exact:e.parentElement.textContent===e.parentElement.getAttribute('aria-label')};
    }).filter(value=>value.lines!==1||!value.contained||!value.exact)""")
    if failures:
        page.screenshot(path=str(OUT/('money-failure-'+label+'.png')),full_page=True)
        raise AssertionError((label,failures))
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(label,'overflow')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        mail={}
        backend=Backend(Path(folder)/'views.db',deliver=lambda email,code:mail.update({email:code}))
        backend.cipher=Fernet(Fernet.generate_key())
        with backend.connect() as db:
            db.execute('CREATE TABLE http_limits(key TEXT PRIMARY KEY,count BIGINT NOT NULL,until_at BIGINT NOT NULL)')
        password='synthetic-finance-views-password'
        identity=backend.register('finance-views@example.test',password)
        actor=backend.authenticate(identity['token']);backend.verify(actor,mail[actor['email']]);actor=backend.authenticate(identity['token'])
        workspace=str(uuid.uuid4())
        backend.family(actor,{'id':str(uuid.uuid4()),'action':'workspace.create','workspace_id':workspace,'kind':'personal','name':'Проверка финансов'})
        first,second,usd,budget=[str(uuid.uuid4()) for _ in range(4)]
        def record(kind,data,record_id=None):
            return {'id':str(uuid.uuid4()),'action':'record.put','record_id':record_id or str(uuid.uuid4()),'revision':0,'kind':kind,'visibility':'private','audience':[],'data':data}
        backend.batch(actor,workspace,[
            record('account',{'name':'Основной счёт','currency':'RUB','opening_minor':100000},first),
            record('account',{'name':'Второй счёт','currency':'RUB','opening_minor':30000},second),
            record('account',{'name':'Долларовый счёт','currency':'USD','opening_minor':10000},usd),
            record('transaction',{'kind':'income','amount_minor':500000,'currency':'RUB','date':'2026-11-10','label':'Зарплата','account_id':first}),
            record('transaction',{'kind':'expense','amount_minor':20000,'currency':'RUB','date':'2026-11-11','label':'Продукты','account_id':first,'category':'food'}),
            record('transaction',{'kind':'expense','amount_minor':3000,'currency':'RUB','date':'2026-11-12','label':'Транспорт','account_id':second,'category':'transport'}),
            record('transaction',{'kind':'expense','amount_minor':550,'currency':'USD','date':'2026-11-12','label':'Кофе USD','account_id':usd}),
            record('budget',{'name':'Расходы месяца','currency':'RUB','limit_minor':50000,'start_on':'2026-10-01','end_on':None,'period':'month','rollover':'positive','participants':[]},budget),
        ])
        settings=Settings.load({'DATABASE_URL':'postgresql://unused/test','EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),'RATE_LIMIT_KEY':'synthetic-views-'+'x'*48,'SMTP_HOST':'localhost','SMTP_TLS':'none','EMAIL_FROM':'fixture@example.test'})
        server=make_server('127.0.0.1',0,lambda e,s:[],handler_class=Quiet);origin='http://localhost:'+str(server.server_port)
        app=Application(backend,replace(settings,site_origin=origin,control_origin='http://control.localhost:'+str(server.server_port),require_https=False))
        server.set_app(app);threading.Thread(target=server.serve_forever,daemon=True).start()
        checks=[]
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
                context=browser.new_context(viewport={'width':1440,'height':1000},locale='ru-RU',service_workers='block',reduced_motion='reduce')
                page=context.new_page();page.clock.install(time=datetime(2026,11,13,12,tzinfo=timezone.utc));errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(origin+'/app');page.locator('input[name=email]').fill(actor['email']);page.locator('input[name=password]').fill(password);page.get_by_role('button',name='Войти',exact=True).click()
                expect(page.get_by_role('heading',name='Сегодня',exact=True)).to_be_visible()
                open_tab(page,'Финансы')
                expect(page.locator('main')).to_have_attribute('data-finance-view','overview')
                expect(page.locator('.finance-metric.balance')).to_contain_text('6 070,00 RUB')
                expect(page.locator('.finance-metric.balance')).to_contain_text('94,50 USD')
                expect(page.locator('.finance-metric.expense')).to_contain_text('230,00 RUB')
                expect(page.locator('.finance-metric.expense')).to_contain_text('5,50 USD')
                assert page.locator('.finance-accounts,.finance-budgets').count()==0
                assert page.locator('.finance-content>.card').count()==2
                for mode in ['bar','line','smooth','donut','compact','categories']:
                    page.locator('select[name=chart-mode]').select_option(mode)
                    if mode=='compact':expect(page.locator('.finance-analysis canvas')).to_be_hidden()
                    else:expect(page.locator('.finance-analysis canvas')).to_be_visible()
                checks.append('overview has currency-separated true totals, chart and recent ledger; no duplicate management cards')
                expect(page.locator('.chart-category-legend')).to_contain_text('Питание')
                groups=page.evaluate("financeExpenseGroups(records('transaction'),'RUB').map(group=>[group.id,String(group.amount)])")
                assert groups==[['food','20000'],['transport','3000']],groups
                unassigned=page.evaluate("financeExpenseGroups([{kind:'transaction',data:{kind:'expense',currency:'RUB',amount_minor:111,category:'unknown'}}],'RUB').map(group=>[group.id,String(group.amount)])")
                assert unassigned==[['','111']],unassigned
                checks.append('expense donut uses saved categories only, preserves exact currency totals and keeps unknown entries uncategorized')
                import_button=page.locator('.reference-finance-group button:visible,.finance-toolbar button:visible').filter(has_text='Импортировать выписку')
                import_button.click()
                expect(page.get_by_role('dialog').locator('input[type=file]')).to_be_visible()
                page.get_by_role('dialog').get_by_role('button',name='Закрыть',exact=True).click()
                open_finance_section(page,'accounts')
                assert page.evaluate('scrollY')==0,'Independent finance view must start at the top, not jump to an old anchor'
                assert page.locator('main h1').bounding_box()['y']>=page.locator('#root>header').bounding_box()['height']
                page.locator('.finance-toolbar').get_by_role('button',name='Счёт',exact=True).click()
                expect(page.get_by_role('dialog').get_by_label('Название',exact=True)).to_be_visible()
                page.get_by_role('dialog').get_by_role('button',name='Закрыть',exact=True).click()
                expect(page.locator('.finance-account-report')).to_have_count(3)
                assert page.locator('.ledger,.finance-analysis').count()==0
                page.locator('.finance-account-report').filter(has_text='Основной счёт').click()
                expect(page.locator('main')).to_have_attribute('data-finance-view','report')
                expect(page.locator('main h1')).to_have_text('Основной счёт')
                expect(page.locator('.ledger')).to_contain_text('Продукты')
                expect(page.locator('.ledger')).not_to_contain_text('Транспорт')
                expect(page.locator('.ledger')).not_to_contain_text('Кофе USD')
                expect(page.locator('.finance-metric.balance')).to_contain_text('5 800,00 RUB')
                assert page.locator('.finance-metric').filter(has_text='USD').count()==0
                checks.append('account card opens a full report limited to its account and currency')
                page.locator('.finance-report-back').click()
                expect(page.locator('main')).to_have_attribute('data-finance-view','accounts')
                page.locator('.finance-account-report').filter(has_text='Долларовый счёт').click()
                expect(page.locator('select[name=chart-currency]')).to_have_value('USD')
                page.evaluate("referenceNavigate('money')")
                expect(page.locator('select[name=chart-currency]')).to_have_value('USD')
                expect(page.locator('.chart-category-legend')).to_contain_text('5,50 USD')
                checks.append('leaving an account report retains its filter and keeps chart currency aligned')
                open_finance_section(page,'budgets')
                expect(page.locator('.finance-budget-card')).to_have_count(1)
                expect(page.locator('.finance-budget-remaining')).to_contain_text('770,00 RUB')
                expect(page.locator('.budget-metrics')).to_contain_text('230,00 RUB')
                expect(page.locator('.budget-metrics')).to_contain_text('1 000,00 RUB')
                assert page.locator('.finance-analysis,.ledger,.finance-accounts').count()==0
                checks.append('budget shows actual current-period spending, positive carry allowance and remainder from shared engine')
                page.evaluate("state.financeFilters={};referenceNavigate('money')")
                for width in [320,375,820,1440]:
                    page.set_viewport_size({'width':width,'height':950})
                    for theme in ['light','dark']:
                        page.evaluate("theme=>{state.theme=theme;preferences();redrawFinance?.();}",theme)
                        for view in ['', 'accounts','budgets']:
                            open_finance_section(page,view)
                            expect(page.locator('main h1')).to_be_visible()
                            page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                            if not page.evaluate('document.documentElement.scrollWidth<=innerWidth'):
                                page.screenshot(path=str(OUT/'overflow.png'),full_page=True)
                                print(page.locator('main *').evaluate_all('els=>els.filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>({tag:e.tagName,cls:e.className,w:e.getBoundingClientRect().width,r:e.getBoundingClientRect().right,text:e.textContent.slice(0,55)})).slice(0,25)'))
                                raise AssertionError((width,theme,view,'overflow'))
                            controls=page.locator('main button:visible,main select:visible').evaluate_all('''els=>els.filter(e=>{const r=e.getBoundingClientRect();const scroll=e.closest('.finance-navigation');return !scroll&&(r.width<24||r.height<24||r.left<0||r.right>innerWidth+1);}).map(e=>e.textContent)''')
                            assert not controls,(width,theme,view,controls)
                            if width in [375,1440]:page.screenshot(path=str(OUT/(str(width)+'-'+theme+'-'+(view or 'overview')+'.png')),full_page=True)
                checks.append('independent finance destinations fit 320/375/820/1440 pixels in both themes')
                # A real negative UZS balance reproduces the review's split-decimal
                # case; a narrow tablet used to split the same figures in metrics.
                uzs=str(uuid.uuid4())
                result=backend.batch(actor,workspace,[
                    record('account',{'name':'Семейный счёт для поездок и повседневных покупок','currency':'UZS','opening_minor':849202038000-755960221000},uzs),
                    record('transaction',{'kind':'expense','amount_minor':849202038000,'currency':'UZS','date':'2026-11-13','label':'Поездка и бронирование семейного отдыха','account_id':uzs,'category':'leisure'}),
                ])
                assert all(item['status']=='accepted' for item in result['results']),result
                page.evaluate("async()=>{state.financeFilters={};await refresh();render();}")
                for width in [320,834]:
                    page.set_viewport_size({'width':width,'height':1000})
                    for theme in ['light','dark']:
                        page.evaluate("theme=>{state.theme=theme;preferences();}",theme)
                        open_finance_section(page,'')
                        expect(page.locator('.finance-metric.balance .money-display[aria-label$=" UZS"] .money-number')).to_have_text('-7 559 602 210,00')
                        expect(page.locator('.finance-metric.expense .money-display[aria-label$=" UZS"] .money-number')).to_have_text('8 492 020 380,00')
                        page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                        assert_money_lines(page,str(width)+'-'+theme+'-overview')
                        page.screenshot(path=str(OUT/('money-'+str(width)+'-'+theme+'-overview.png')),full_page=True)
                        open_finance_section(page,'accounts')
                        expect(page.locator('.finance-account-amount[aria-label$=" UZS"] .money-number')).to_have_text('-7 559 602 210,00')
                        page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                        assert_money_lines(page,str(width)+'-'+theme+'-accounts')
                        page.screenshot(path=str(OUT/('money-'+str(width)+'-'+theme+'-accounts.png')),full_page=True)
                page.set_viewport_size({'width':320,'height':1000})
                open_tab(page,'Финансы');page.locator('select[name=chart-currency]').select_option('UZS')
                expect(page.locator('.chart-category-row .money-display')).to_contain_text('8 492 020 380,00 UZS')
                assert_money_lines(page,'320-category-legend')
                open_finance_section(page,'ledger');assert_money_lines(page,'320-ledger')
                open_tab(page,'Сегодня');assert_money_lines(page,'320-today-balances')
                checks.append('large debit numbers and decimals stay on one line; only currency may wrap in 320px accounts and 834px metrics, both themes, legends, ledger and Today')
                assert not errors,errors
                context.close();browser.close()
        finally:server.shutdown()
    (OUT/'checks.json').write_text(json.dumps({'status':'passed','screenshots':'real Chromium; production WSGI; synthetic data','styles':'production bundle','checks':checks},ensure_ascii=False,indent=2)+'\n')
    print('FINANCE_VIEWS_BROWSER_PASSED',len(checks))


if __name__=='__main__':main()
