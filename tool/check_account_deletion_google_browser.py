"""Actual local Google-only reauth -> deletion request/cancel with synthetic RSA.
Exercises real challenge/result/proof/session binding. Never contacts real Google.
"""
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs,urlsplit,urlencode
import json,os,tempfile,threading,uuid
from wsgiref.simple_server import make_server
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright,expect
from backend.config import Settings
from backend.production import Application
from backend.service import Backend
from backend.tests.test_google_identity import SyntheticGoogle,CLIENT
from tool.check_pwa_browser import Quiet
from tool.web_test_tls import enable_test_tls

OUT=Path('web_evidence/account-deletion-google')

def main():
 OUT.mkdir(parents=True,exist_ok=True);checks=[]
 with tempfile.TemporaryDirectory() as directory:
  mail={};backend=Backend(Path(directory)/'google-deletion.db',deliver=lambda email,code:mail.update({email:code}));backend.cipher=Fernet(Fernet.generate_key())
  with backend.connect() as db:db.execute('CREATE TABLE http_limits(key TEXT PRIMARY KEY,count BIGINT NOT NULL,until_at BIGINT NOT NULL)')
  settings=Settings.load({'DATABASE_URL':'postgresql://unused/test','EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),'RATE_LIMIT_KEY':'synthetic-google-deletion-'+'x'*36,'SMTP_HOST':'127.0.0.1','SMTP_TLS':'none','EMAIL_FROM':'fixture@example.test','GOOGLE_OAUTH_CLIENT_ID':CLIENT,'GOOGLE_OAUTH_CLIENT_SECRET':'synthetic-test-only','REGISTRATION_MODE':'open'})
  server=make_server('127.0.0.1',0,lambda env,start:[],handler_class=Quiet);pin=enable_test_tls(server,directory);origin='https://localhost:'+str(server.server_port);application=Application(backend,replace(settings,site_origin=origin,control_origin='https://control.localhost:'+str(server.server_port),require_https=False));provider=SyntheticGoogle();application.google.verifier=provider;server.set_app(application);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   with sync_playwright() as p:
    browser=p.chromium.launch(args=['--ignore-certificate-errors-spki-list='+pin]);context=browser.new_context(viewport={'width':390,'height':844},service_workers='block',reduced_motion='reduce');page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)));mode={'value':'same'};writes=[]
    def authorize(route):
     params=parse_qs(urlsplit(route.request.url).query);assert params['code_challenge_method']==['S256'];query={'state':params['state'][0]}
     if mode['value']=='cancelled':query['error']='access_denied'
     else:query['code']=provider.sign(params['nonce'][0],**({'sub':'other-subject','email':'other@gmail.com'} if mode['value']=='mismatch' else {}))
     route.fulfill(status=302,headers={'Location':origin+'/account/api/google/callback?'+urlencode(query)},body='')
    context.route('https://accounts.google.com/o/oauth2/v2/auth?*',authorize)
    def track(request):
     if request.method=='POST' and urlsplit(request.url).path in ['/account/api/deletion','/account/api/cancel-deletion']:writes.append((urlsplit(request.url).path,request.post_data_json))
    page.on('request',track);page.goto(origin+'/app');page.get_by_role('button',name='Продолжить с Google',exact=True).click();expect(page.locator('.nav')).to_be_visible();uid=page.evaluate('state.session.user_id')
    with backend.connect() as db:actor=dict(db.execute('SELECT id,email,verified FROM users WHERE id=?',(uid,)).fetchone())
    wid=str(uuid.uuid4());rid=str(uuid.uuid4());backend.family(actor,{'id':str(uuid.uuid4()),'action':'workspace.create','workspace_id':wid,'kind':'personal','name':'Личное пространство'});backend.batch(actor,wid,[{'id':str(uuid.uuid4()),'action':'record.put','record_id':rid,'revision':0,'kind':'note','visibility':'private','audience':[],'data':{'body':'Synthetic retained record'}}]);page.reload();expect(page.get_by_role('heading',name='Сегодня',exact=True)).to_be_visible();cookie=next(item['value'] for item in context.cookies() if item['name']=='__Host-uladim_account')
    page.evaluate('deletion()');page.get_by_role('button',name='Продолжить удаление',exact=True).click();expect(page.locator('input[type=password]')).to_have_count(0);page.get_by_role('button',name='Подтвердить через Google',exact=True).click();expect(page.locator('.account-deletion-proof')).to_contain_text('Google подтверждён');assert page.evaluate('state.session.user_id')==uid;assert next(item['value'] for item in context.cookies() if item['name']=='__Host-uladim_account')==cookie;checks.append('actual_google_only_reauth_keeps_original_customer_session')
    page.get_by_role('button',name='Продолжить удаление',exact=True).click();page.get_by_label('Введите DELETE',exact=True).fill('DELETE');page.get_by_role('button',name='Запросить удаление',exact=True).click();expect(page.locator('.account-deletion-pending')).to_contain_text('Удаление запланировано');assert writes and 'reauth_token' in writes[0][1] and 'password' not in writes[0][1];first_proof=writes[0][1]['reauth_token'];assert not page.evaluate('(proof)=>Object.values(localStorage).concat(Object.values(sessionStorage)).some(value=>value.includes(proof))',first_proof);assert first_proof not in page.locator('body').inner_text() and first_proof not in page.url
    replay=page.evaluate("""async proof=>{const session=await(await fetch('/account/api/session')).json();const response=await fetch('/account/api/cancel-deletion',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf},body:JSON.stringify({reauth_token:proof})});return {status:response.status,data:await response.json()};}""",first_proof);assert replay['status']!=200 and replay['data']['error']=='reauth_required';checks.append('actual_google_proof_is_one_use_and_not_stored')
    page.get_by_role('button',name='Отменить запрос',exact=True).click();page.get_by_role('button',name='Подтвердить через Google',exact=True).click();expect(page.locator('.account-deletion-proof')).to_contain_text('Google подтверждён');page.get_by_role('button',name='Отменить запрос',exact=True).click();page.get_by_role('button',name='Отменить удаление',exact=True).click();expect(page.locator('.account-deletion-status')).to_contain_text('отменён');assert writes[-1][1]['reauth_token']!=first_proof
    with backend.connect() as db:assert db.execute('SELECT state FROM deletion_jobs WHERE user_id=?',(uid,)).fetchone()['state']=='cancelled';assert db.execute('SELECT COUNT(*) AS n FROM web_sessions WHERE user_id=?',(uid,)).fetchone()['n']==1;assert db.execute('SELECT deleted FROM records WHERE id=?',(rid,)).fetchone()['deleted']==0
    checks.append('actual_fresh_google_reauth_cancels_without_replacing_session_or_erasing_records')
    for value in ['mismatch','cancelled']:
     mode['value']=value;page.get_by_role('button',name='Продолжить удаление',exact=True).click();page.get_by_role('button',name='Подтвердить через Google',exact=True).click();expect(page.locator('.account-deletion-status')).to_contain_text('тот же Google-аккаунт' if value=='mismatch' else 'не завершено');assert page.evaluate('state.session.user_id')==uid;assert not page.evaluate('deletionCenter().snapshot().proof');assert next(item['value'] for item in context.cookies() if item['name']=='__Host-uladim_account')==cookie;checks.append('actual_google_'+value+'_keeps_identity_without_proof');page.evaluate('scrollTo(0,0)');page.screenshot(path=str(OUT/(value+'.png')),full_page=True)
    assert not errors,errors;context.close();browser.close()
  finally:server.shutdown();server.server_close();thread.join(5)
 result={'checks':checks,'scope':'Real local WSGI lifecycle, Google challenges/proofs and synthetic RSA provider; no real Google account, deletion worker or production data.'};(OUT/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
