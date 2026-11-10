"""Real browser + production WSGI, disposable two-user data, no production traffic."""
from dataclasses import replace
import json
import tempfile
import threading
import uuid
from pathlib import Path
from wsgiref.simple_server import make_server
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright, expect
from backend.config import Settings
from backend.production import Application
from backend.service import Backend
from tool.check_pwa_browser import Quiet

OUT=Path('web_evidence/finance-release')
PASSWORD='synthetic-finance-release-password'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    checks=[]
    with tempfile.TemporaryDirectory() as folder:
        mail={}
        backend=Backend(Path(folder)/'finance.db',deliver=lambda e,c:mail.update({e:c}))
        backend.cipher=Fernet(Fernet.generate_key())
        with backend.connect() as db:db.execute('CREATE TABLE http_limits(key TEXT PRIMARY KEY,count BIGINT NOT NULL,until_at BIGINT NOT NULL)')
        actors=[]
        for email in ['finance-a@example.test','finance-b@example.test']:
            s=backend.register(email,PASSWORD);actor=backend.authenticate(s['token']);backend.verify(actor,mail[email]);actors.append(backend.authenticate(s['token']))
        actor=actors[0];wid=str(uuid.uuid4())
        backend.family(actor,{'id':str(uuid.uuid4()),'action':'workspace.create','workspace_id':wid,'kind':'personal','name':'Проверка финансов'})
        account=str(uuid.uuid4())
        backend.batch(actor,wid,[{'id':str(uuid.uuid4()),'action':'record.put','record_id':account,'revision':0,'kind':'account','visibility':'private','audience':[],'data':{'name':'Основной счёт','currency':'RUB','opening_minor':10000}}])
        settings=Settings.load({'DATABASE_URL':'postgresql://unused/test','EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),'RATE_LIMIT_KEY':'synthetic-finance-'+'x'*48,'SMTP_HOST':'localhost','SMTP_TLS':'none','EMAIL_FROM':'fixture@example.test'})
        server=make_server('127.0.0.1',0,lambda e,s:[],handler_class=Quiet);origin='http://localhost:'+str(server.server_port)
        server.set_app(Application(backend,replace(settings,site_origin=origin,control_origin='http://control.localhost:'+str(server.server_port),require_https=False)))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch()
                context=browser.new_context(viewport={'width':1440,'height':1000},color_scheme='light',locale='ru-RU')
                page=context.new_page();errors=[];requests=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('request',lambda r:requests.append({'url':r.url,'body':r.post_data or ''}))
                page.goto(origin+'/app');page.locator('input[name=email]').fill(actor['email']);page.locator('input[name=password]').fill(PASSWORD);page.get_by_role('button',name='Войти',exact=True).click()
                expect(page.get_by_role('heading',name='Сегодня',exact=True)).to_be_visible()
                page.get_by_role('navigation').get_by_role('button',name='Финансы',exact=True).click()
                expect(page.get_by_role('button',name='Импорт из файла',exact=True)).to_be_visible()
                checks.append({'case':'shared domain worker preserves exact KWD/JPY and rejects unsafe inputs','expected':'exact minor units or explicit rejection','actual':page.evaluate('''async()=>{
                  const parse=async(text,extension='csv')=>statementWorker({action:'parse',bytes:btoa(unescape(encodeURIComponent(text))),extension,encoding:'auto',delimiter:'auto',currency:'RUB'});
                  const mapping={header:0,date:0,amount:1,description:2,currency:3,dateFormat:'iso',decimal:'.',defaultCurrency:'RUB',direction:'signed'};
                  const data=await parse('date,amount,description,currency\\n2026-11-10,-1.234,Shop,KWD\\n2026-11-10,123,Salary,JPY');
                  const values=await statementWorker({action:'normalize',rows:data.rows,mapping});
                  if(values.preview[0].value.amount!==1234||values.preview[1].value.amount!==123)throw Error('minor units');
                  for(const [text,type]of [['<!DOCTYPE x><!ENTITY x SYSTEM "file:///etc/passwd">','csv'],['[{"date":"2026-11-10","amount":1.234}]','json'],['a,b\\n"unclosed','csv']]){let rejected=false;try{await parse(text,type);}catch{rejected=true;}if(!rejected)throw Error('unsafe parser input accepted');}
                  return 'passed';}''')})
                page.evaluate("""async()=>{
                  const large='date,amount,description\\n'+Array.from({length:10000},(_,i)=>'2026-11-10,-1.00,Item '+i).join('\\n');
                  const parse=text=>statementWorker({action:'parse',bytes:btoa(text),extension:'csv',encoding:'auto',delimiter:'auto',currency:'RUB'});
                  const table=await parse(large);if(table.rows.length!==10001)throw Error('large statement');
                  let rejected=false;try{await parse(large+'\\n2026-11-10,-1.00,Too many');}catch(e){rejected=e.code==='import_limit';}if(!rejected)throw Error('row limit');
                  const budget={id:'budget',data:{currency:'RUB',limit_minor:100000,start_on:'2026-11-01',end_on:null,period:'month',rollover:'both'}};
                  const records=[{id:'expense',data:{kind:'expense',label:'Shop',amount_minor:200000,currency:'RUB',date:'2026-11-10'}}];
                  const result=await statementWorker({action:'budgets',at:'2026-12-05',budgets:[budget],records});if(result.remaining.budget!=='0')throw Error('budget carry');
                }""")
                checks.append({'case':'10,000 rows, row limit and shared budget carry','expected':'bounded parser; exact Android budget remainder','actual':'passed'})
                statement='date;amount;description;currency\n2026-11-10;-1 234,56;Магазин;RUB\n2026-11-10;2000,00;<img src=x onerror=alert(1)>;RUB\n2026-02-30;10,00;Неверная дата;RUB'
                page.get_by_role('button',name='Импорт из файла',exact=True).click();dialog=page.get_by_role('dialog')
                dialog.locator('input[type=file]').set_input_files({'name':'statement.csv','mimeType':'text/csv','buffer':statement.encode()})
                expect(dialog.get_by_role('button',name='Проверить записи',exact=True)).to_be_visible()
                dialog.locator('select[name=date]').select_option('0');dialog.locator('select[name=amount]').select_option('1');dialog.locator('select[name=description]').select_option('2');dialog.locator('select[name=decimal]').select_option(',')
                dialog.get_by_role('button',name='Проверить записи',exact=True).click()
                expect(dialog.locator('tbody tr')).to_have_count(3)
                assert dialog.locator('tbody input:checked').count()==2
                assert dialog.locator('tbody img').count()==0
                checks.append({'case':'preview handles invalid date and literal HTML','expected':'2 selectable / 3 rows; no HTML execution','actual':'passed'})
                page.screenshot(path=str(OUT/'import-preview-1440-light.png'),full_page=True)
                dropped=[False]
                def lost_response(route):
                    if route.request.method=='POST' and not dropped[0]:
                        dropped[0]=True;route.fetch();route.abort()
                    else:route.continue_()
                page.route('**/account/api/sync',lost_response)
                dialog.get_by_role('button',name='Импортировать выбранное',exact=True).click()
                expect(dialog.get_by_role('button',name='Повторить',exact=True)).to_be_enabled()
                dialog.get_by_role('button',name='Повторить',exact=True).click()
                expect(dialog.locator('tbody input:checked')).to_have_count(0)
                stored=[r for r in backend.pull(actor,wid,0)['records'] if r['kind']=='transaction']
                assert len(stored)==2 and {r['data']['amount_minor'] for r in stored}=={123456,200000}
                checks.append({'case':'lost response then same operation retry','expected':'2 records exactly once','actual':'passed'})
                page.unroute('**/account/api/sync',lost_response)
                dialog.get_by_role('button',name='Закрыть',exact=True).click()
                expect(page.locator('.account-balance strong')).to_have_text('865,44 RUB')
                checks.append({'case':'visible account balance immediately after import','expected':'865.44 RUB, including opening balance','actual':'passed'})
                page.get_by_role('button',name='Импорт из файла',exact=True).click();dialog=page.get_by_role('dialog')
                dialog.locator('input[type=file]').set_input_files({'name':'renamed.csv','mimeType':'text/csv','buffer':statement.encode()})
                dialog.locator('select[name=date]').select_option('0');dialog.locator('select[name=amount]').select_option('1');dialog.locator('select[name=description]').select_option('2');dialog.locator('select[name=decimal]').select_option(',')
                dialog.get_by_role('button',name='Проверить записи',exact=True).click();expect(dialog.locator('tbody tr')).to_have_count(3)
                assert dialog.locator('tbody input:checked').count()==0
                checks.append({'case':'same content under renamed file','expected':'all existing records excluded','actual':'passed'})
                dialog.get_by_role('button',name='Закрыть',exact=True).click()
                # After the literal-XSS assertion, use ordinary synthetic copy for visual review.
                injected=next(r for r in backend.pull(actor,wid,0)['records'] if r['kind']=='transaction' and r['data']['kind']=='income')
                backend.batch(actor,wid,[{'id':str(uuid.uuid4()),'action':'record.put','record_id':injected['id'],'revision':injected['revision'],'kind':'transaction','visibility':'private','audience':[],'data':{**injected['data'],'label':'Пополнение счёта'}}])
                page.evaluate('async()=>{await refresh();render();}')
                expect(page.locator('.ledger')).to_contain_text('Пополнение счёта')
                checks.append({'case':'incremental sync updates existing record','expected':'external edit visible without losing existing records','actual':'passed'})
                for method in ['bar','line','smooth','donut','compact']:
                    page.locator('select[name=chart-mode]').select_option(method)
                    expect(page.locator('.chart-legend')).to_contain_text('RUB')
                for width in [320,375,390,430,768,1024,1280,1440]:
                    for theme in ['light','dark']:
                        page.set_viewport_size({'width':width,'height':900 if width>600 else 844})
                        page.evaluate("theme=>{state.theme=theme;preferences();}",theme)
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,theme,'page overflow')
                        violations=page.locator('.finance-filters input,.finance-filters select,.intro button,.nav button').evaluate_all('''els=>els.filter(e=>{const r=e.getBoundingClientRect();return r.width<24||r.height<24||r.left<0||r.right>innerWidth+1;}).map(e=>e.name||e.textContent)''')
                        assert not violations,(width,theme,violations)
                        if width in [390,768,1440]:
                            page.locator('select[name=chart-mode]').select_option('bar')
                            page.screenshot(path=str(OUT/('finance-'+str(width)+'-'+theme+'.png')),full_page=True)
                checks.append({'case':'8 widths × 2 themes, geometry','expected':'no page overflow or clipped controls','actual':'passed'})
                page.set_viewport_size({'width':1440,'height':1000});page.evaluate("document.documentElement.style.fontSize='200%'")
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                checks.append({'case':'200% root text','expected':'no page overflow','actual':'passed'})
                assert not any('date;amount;description' in r['body'] or '"bytes"' in r['body'] or 'multipart/form-data' in r['body'] for r in requests)
                assert all(r['url'].startswith(origin) for r in requests)
                assert page.evaluate("Object.keys(localStorage).every(k=>k==='uladim-interface')")
                checks.append({'case':'file privacy, third-party egress, localStorage','expected':'only normalized transactions sent; interface preferences only','actual':'passed'})
                try:backend.pull(actors[1],wid,0)
                except Exception as e:assert getattr(e,'code',None)=='workspace_forbidden'
                else:raise AssertionError('second user read first workspace')
                checks.append({'case':'second user against imported workspace','expected':'workspace_forbidden','actual':'passed'})
                # Exercise the newly retained in-memory cursor against a real grant revocation.
                family=str(uuid.uuid4());backend.family(actor,{'id':str(uuid.uuid4()),'workspace_id':family,'action':'workspace.create','kind':'family','name':'Семейная проверка'})
                invite=backend.family(actor,{'id':str(uuid.uuid4()),'workspace_id':family,'action':'invite.create','email':actors[1]['email'],'role':'parent','profile_id':None})
                backend.accept(actors[1],{'id':str(uuid.uuid4()),'invitation':invite['invitation']})
                note=str(uuid.uuid4());backend.batch(actor,family,[{'id':str(uuid.uuid4()),'action':'record.put','record_id':note,'revision':0,'kind':'note','visibility':'private','audience':[],'data':{'body':'Временный доступ к заметке'}}])
                backend.batch(actor,family,[{'id':str(uuid.uuid4()),'action':'record.grant','record_id':note,'revision':1,'user_id':actors[1]['id'],'can_edit':False,'revoke':False}])
                second=browser.new_context(viewport={'width':390,'height':844},locale='ru-RU');other=second.new_page();other.goto(origin+'/app');other.locator('input[name=email]').fill(actors[1]['email']);other.locator('input[name=password]').fill(PASSWORD);other.get_by_role('button',name='Войти',exact=True).click()
                expect(other.get_by_text('Временный доступ к заметке',exact=True)).to_be_visible()
                backend.batch(actor,family,[{'id':str(uuid.uuid4()),'action':'record.grant','record_id':note,'revision':2,'user_id':actors[1]['id'],'can_edit':False,'revoke':True}])
                other.evaluate('async()=>{await refresh();render();}')
                expect(other.get_by_text('Временный доступ к заметке',exact=True)).to_have_count(0)
                denied=other.evaluate('''async wid=>{try{const result=await call('sync',{workspace_id:wid,operations:[{id:crypto.randomUUID(),action:'record.put',record_id:crypto.randomUUID(),revision:0,kind:'transaction',visibility:'private',audience:[],data:{kind:'income',amount_minor:1,currency:'RUB',date:'2026-11-10',label:'forbidden',account_id:null}}]});return result.results[0].error||result.results[0].status;}catch(e){return e.code;}}''',wid)
                assert denied=='workspace_forbidden',denied
                assert len([r for r in backend.pull(actor,wid,0)['records'] if r['kind']=='transaction'])==2
                checks.append({'case':'second browser, grant revocation and foreign workspace write','expected':'revoked data removed from memory; foreign write rejected by server','actual':'passed'})
                second.close()
                assert not errors,errors
                context.close();browser.close()
        finally:server.shutdown()
    (OUT/'result.json').write_text(json.dumps({'status':'passed','environment':'disposable SQLite / production WSGI / Chromium; not physical device or live production','checks':checks},ensure_ascii=False,indent=2)+'\n')
    print('FINANCE_BROWSER_PASSED',len(checks))

if __name__=='__main__':main()
