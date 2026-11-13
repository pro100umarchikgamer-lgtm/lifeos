"""Real local recovery request -> opaque staff approval -> owner canonical restore.
Disposable SQLite, synthetic accounts and loopback-only pinned TLS. No production.
"""
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit
import io,json,os,tempfile,threading,uuid
from wsgiref.simple_server import make_server
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright,expect
from backend.config import Settings
from backend.control import Control,totp
from backend.production import Application
from backend.service import Backend
from tool.check_pwa_browser import Quiet
from tool.web_test_tls import enable_test_tls

OUT=Path('web_evidence/recovery-live');PASSWORD='synthetic-recovery-browser-password';PRIVATE='Личная заметка для восстановления\nPRIVATE_OWNER_PAYLOAD_ONLY'

def sign_in(page,site,email):
 page.goto(site+'/app');page.get_by_label('Электронная почта',exact=True).fill(email);page.locator('input[name=password]').fill(PASSWORD);page.get_by_role('button',name='Войти',exact=True).click();expect(page.locator('.nav')).to_be_visible()

def main():
 OUT.mkdir(parents=True,exist_ok=True);checks=[]
 with tempfile.TemporaryDirectory() as directory:
  mail={};backend=Backend(Path(directory)/'recovery.db',deliver=lambda email,code:mail.update({email:code}));backend.cipher=Fernet(Fernet.generate_key())
  with backend.connect() as db:db.execute('CREATE TABLE http_limits(key TEXT PRIMARY KEY,count BIGINT NOT NULL,until_at BIGINT NOT NULL)')
  actors={}
  for email in ['owner@example.test','customer@example.test']:
   session=backend.register(email,PASSWORD);actor=backend.authenticate(session['token']);backend.verify(actor,mail[email]);actors[email]=backend.authenticate(session['token'])
  actor=actors['customer@example.test'];wid=str(uuid.uuid4());rid=str(uuid.uuid4());backend.family(actor,{'id':str(uuid.uuid4()),'action':'workspace.create','workspace_id':wid,'kind':'personal','name':'Личное пространство'})
  backend.batch(actor,wid,[{'id':str(uuid.uuid4()),'action':'record.put','record_id':rid,'revision':0,'kind':'note','visibility':'private','audience':[],'data':{'body':PRIVATE}}]);backend.batch(actor,wid,[{'id':str(uuid.uuid4()),'action':'record.delete','record_id':rid,'revision':1}]);enrollment=Control(backend).bootstrap('owner@example.test')
  settings=Settings.load({'DATABASE_URL':'postgresql://unused/test','EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),'RATE_LIMIT_KEY':'synthetic-recovery-browser-'+'x'*36,'SMTP_HOST':'127.0.0.1','SMTP_TLS':'none','EMAIL_FROM':'fixture@example.test'})
  server=make_server('127.0.0.1',0,lambda env,start:[],handler_class=Quiet);pin=enable_test_tls(server,directory,('app.uladim.test','control.uladim.test'));site='https://app.uladim.test:'+str(server.server_port);control='https://control.uladim.test:'+str(server.server_port);application=Application(backend,replace(settings,site_origin=site,control_origin=control,require_https=False));commits=[]
  def lose_success_reply(env,start):
   if env.get('PATH_INFO')!='/account/api/recovery/commit':return application(env,start)
   raw=env['wsgi.input'].read(int(env.get('CONTENT_LENGTH') or 0));env['wsgi.input']=io.BytesIO(raw);commits.append(json.loads(raw));captured={}
   def capture(status,headers,exc_info=None):captured.update(status=status,headers=headers)
   result=b''.join(application(env,capture))
   if len(commits)==1:
    assert captured['status'].startswith('200') and json.loads(result)['results'][0]['status']=='accepted'
    # Fault only the reply after the actual canonical transaction has committed.
    body=b'{"error":"server_error"}';start('503 Synthetic lost success reply',[('Content-Type','application/json'),('Cache-Control','no-store'),('Content-Length',str(len(body)))]);return [body]
   start(captured['status'],captured['headers']);return [result]
  server.set_app(lose_success_reply);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   with sync_playwright() as p:
    browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}),proxy={'server':os.environ['HTTPS_PROXY'],'bypass':'.uladim.test'} if os.environ.get('HTTPS_PROXY') else None,args=['--host-resolver-rules=MAP *.uladim.test 127.0.0.1','--ignore-certificate-errors-spki-list='+pin]);customer=browser.new_context(viewport={'width':390,'height':844},service_workers='block',reduced_motion='reduce');staff=browser.new_context(viewport={'width':1440,'height':1000},service_workers='block',reduced_motion='reduce');page=customer.new_page();admin=staff.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)));admin.on('pageerror',lambda error:errors.append(str(error)))
    sign_in(page,site,actor['email']);page.evaluate("referenceNavigate('account','security')");page.locator('.settings-content').get_by_role('button',name='Корзина и восстановление',exact=True).click();page.get_by_role('button',name='Личная заметка для восстановления',exact=True).click();expect(page.locator('.recovery-record-detail')).to_contain_text('PRIVATE_OWNER_PAYLOAD_ONLY');expect(page.get_by_role('button',name='Запросить восстановление',exact=True)).to_be_disabled();page.get_by_label('Разрешаю проверить запрос на восстановление этой записи',exact=True).check();page.get_by_role('button',name='Запросить восстановление',exact=True).click();expect(page.locator('.recovery-status')).to_contain_text('Запрос отправлен');checks.append('actual_owned_tombstone_consent_request')
    with backend.connect() as db:pending=dict(db.execute('SELECT * FROM record_recovery_requests WHERE record_id=?',(rid,)).fetchone())
    assert pending['state']=='pending';page.evaluate('scrollTo(0,0)');page.screenshot(path=str(OUT/'owner-pending.png'),full_page=True)
    denied=admin.goto(control+'/');assert denied.status==404;sign_in(admin,site,'owner@example.test');admin.locator('header').get_by_role('button',name='Профиль',exact=True).click();admin.get_by_role('button',name='ULADIM Control',exact=True).click();expect(admin.get_by_role('heading',name='ULADIM Control',exact=True)).to_be_visible();admin.get_by_label('Электронная почта',exact=True).fill('owner@example.test');admin.locator('input[name=password]').fill(PASSWORD);admin.get_by_role('button',name='Войти',exact=True).click();admin.get_by_label('Код подтверждения',exact=True).fill(totp(enrollment['totp_secret'],int(backend.clock())//30));admin.get_by_role('button',name='Войти',exact=True).click();expect(admin.get_by_role('heading',name='Обзор сервиса',exact=True)).to_be_visible()
    with admin.expect_response('**/control/api/record-recovery') as queue:admin.get_by_label('Раздел Control',exact=True).select_option('record-recovery')
    response=queue.value.json();assert response['requests'] and 'PRIVATE_OWNER_PAYLOAD_ONLY' not in json.dumps(response);assert all('data' not in item and 'body' not in item and 'title' not in item for item in response['requests']);expect(admin.get_by_text('PRIVATE_OWNER_PAYLOAD_ONLY',exact=False)).to_have_count(0);admin.get_by_role('button',name='Рассмотреть запрос',exact=True).click();admin.get_by_label('Причина для журнала аудита',exact=True).fill('Подтверждён запрос владельца; содержимое скрыто');admin.screenshot(path=str(OUT/'staff-opaque-review.png'),full_page=True);admin.get_by_role('button',name='Одобрить запрос',exact=True).click();expect(admin.locator('.control-recovery-status')).to_contain_text('одобрен');checks.append('actual_private_control_admission_mfa_metadata_only_approval')
    with backend.connect() as db:assert db.execute('SELECT deleted FROM records WHERE id=?',(rid,)).fetchone()['deleted']==1
    page.get_by_role('button',name='Обновить',exact=True).click();page.get_by_role('button',name='Просмотреть запись',exact=True).click();expect(page.locator('.recovery-record-detail')).to_contain_text(PRIVATE);expect(page.get_by_role('button',name='Восстановить запись',exact=True)).to_be_disabled();page.get_by_label('Восстановить именно эту запись в моё пространство',exact=True).check();page.evaluate('scrollTo(0,0)');page.screenshot(path=str(OUT/'owner-approved-review.png'),full_page=True)
    page.get_by_role('button',name='Восстановить запись',exact=True).click();expect(page.locator('.recovery-status')).to_contain_text('не подтверждено');page.get_by_role('button',name='Повторить восстановление',exact=True).click();expect(page.locator('.recovery-status')).to_contain_text('Запись восстановлена');assert len(commits)==2 and commits[0]==commits[1]
    with backend.connect() as db:
     restored=db.execute('SELECT * FROM records WHERE id=?',(rid,)).fetchone();assert restored['deleted']==0 and restored['revision']==3;assert db.execute('SELECT body FROM notes WHERE id=?',(rid,)).fetchone()['body']==PRIVATE;assert db.execute('SELECT state FROM record_recovery_requests WHERE id=?',(pending['id'],)).fetchone()['state']=='completed'
    checks.append('actual_owner_commit_lost_reply_idempotent_same_grant_operation');page.evaluate('scrollTo(0,0)');page.screenshot(path=str(OUT/'owner-restored.png'),full_page=True);assert page.evaluate('recoveryCenter().snapshot().pending')==0
    for width in [320,834,1440]:page.set_viewport_size({'width':width,'height':900});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert not errors,errors;customer.close();staff.close();browser.close()
  finally:server.shutdown();server.server_close();thread.join(5)
 result={'checks':checks,'scope':'Real local WSGI+SQLite canonical batch with disposable users, staff MFA and pinned same-site TLS. No production records or credentials.'};(OUT/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
