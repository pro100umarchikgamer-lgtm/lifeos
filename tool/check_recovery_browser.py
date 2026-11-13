"""Owned trash consent and opaque Control approval UI with synthetic API only.
Actual backend restore and authorization are separately tested by backend suite.
No production records, staff credentials or real user recovery requests.
"""
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
import json,os,time,uuid
from playwright.sync_api import sync_playwright,expect
from tool.check_web_platform import fixture,login

OUT=Path('web_evidence/recovery')

def main():
 OUT.mkdir(parents=True,exist_ok=True);now=int(time.time());checks=[];writes=[];requests=[];retry={'fail':True};enabled={'value':False}
 with fixture() as (origin,backend,actor,wid),sync_playwright() as p:
  record=dict(id=str(uuid.uuid4()),workspace_id=wid,owner_id=actor['id'],kind='note',visibility='private',audience=[],revision=2,deleted=True,seq=50,data={'body':'Личная удалённая заметка\nСодержимое видно только владельцу.'},consent_hash='a'*64,restorable=True,restore_error=None)
  foreign={**record,'id':str(uuid.uuid4()),'owner_id':str(uuid.uuid4()),'data':{'body':'Чужой секрет'}}
  browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}));context=browser.new_context(viewport={'width':390,'height':844},service_workers='block',reduced_motion='reduce');page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
  def asset_handler(name,mime):
   def handle(route):route.fulfill(path=str(Path('backend/webassets/app')/name),content_type=mime)
   return handle
  for name,mime in [('inbox.js','text/javascript'),('inbox.css','text/css'),('recovery.js','text/javascript'),('recovery.css','text/css')]:page.route('**/app/assets/'+name,asset_handler(name,mime))
  def session(route):
   response=route.fetch();data=response.json();data['record_recovery_available']=enabled['value'];route.fulfill(response=response,json=data)
  page.route('**/account/api/session',session)
  def api(route):
   path=urlsplit(route.request.url).path.removeprefix('/account/api/');body=route.request.post_data_json if route.request.method=='POST' else None
   if body is not None:writes.append((path,body))
   if path=='trash':data={'records':[record,foreign] if not requests or requests[0]['state']!='completed' else [],'next_before':None}
   elif path=='recovery/requests':data={'requests':requests,'next_before':None}
   elif path=='recovery/request':
    req=dict(id=str(uuid.uuid4()),user_id=actor['id'],workspace_id=wid,record_id=record['id'],kind='note',record_revision=record['revision'],consent_hash=record['consent_hash'],state='pending',revision=1,created_at=now,expires_at=now+7*86400,approved_at=0,completed_at=0,decision_reason='');requests.append(req);data={'request':req}
   elif path=='recovery/prepare':data={'request_id':requests[0]['id'],'grant':'G'*43,'expires_at':now+600}
   elif path=='recovery/commit':
    if retry['fail']:retry['fail']=False;route.abort();return
    requests[0].update(state='completed',revision=3,completed_at=now);data={'results':[{'id':body['operation_id'],'status':'accepted'}]}
   elif path=='recovery/cancel':requests[0].update(state='cancelled',revision=3);data={'request':requests[0]}
   else:data={}
   route.fulfill(json=data)
  page.route('**/account/api/trash**',api);page.route('**/account/api/recovery/**',api)
  login(page,origin);page.evaluate("referenceNavigate('account','security')");expect(page.get_by_role('button',name='Корзина и восстановление',exact=True)).to_have_count(0);checks.append('recovery_entry_hidden_until_backend_capability')
  enabled['value']=True;page.reload();expect(page.get_by_role('heading',name='Сегодня',exact=True)).to_be_visible();page.evaluate("referenceNavigate('account','security')");page.locator('.settings-content').get_by_role('button',name='Корзина и восстановление',exact=True).click();expect(page.get_by_role('heading',name='Корзина и восстановление',level=1,exact=True)).to_be_visible();expect(page.get_by_text('Чужой секрет',exact=False)).to_have_count(0);expect(page.get_by_role('button',name='Личная удалённая заметка',exact=True)).to_be_visible();page.evaluate('scrollTo(0,0)');page.screenshot(path=str(OUT/'phone-trash.png'),full_page=True);checks.append('owned_tombstone_preview_filters_foreign_records')
  page.get_by_role('button',name='Личная удалённая заметка',exact=True).click();expect(page.locator('.recovery-record-detail')).to_contain_text('Содержимое видно только владельцу.');send=page.get_by_role('button',name='Запросить восстановление',exact=True);expect(send).to_be_disabled();page.get_by_label('Разрешаю проверить запрос на восстановление этой записи',exact=True).check();send.click();expect(page.locator('.recovery-status')).to_contain_text('Запрос отправлен');assert requests[0]['state']=='pending' and any(path=='recovery/request' and body=={'record_id':record['id'],'revision':2,'consent_hash':'a'*64} for path,body in writes);expect(page.get_by_role('button',name='Восстановить запись',exact=True)).to_have_count(0);checks.append('explicit_owner_consent_binds_record_revision_and_hash')
  requests[0].update(state='approved',revision=2,approved_at=now,decision_reason='Владелец подтвердил запрос');page.get_by_role('button',name='Обновить',exact=True).click();page.get_by_role('button',name='Просмотреть запись',exact=True).click();restore=page.get_by_role('button',name='Восстановить запись',exact=True);expect(restore).to_be_disabled();page.get_by_label('Восстановить именно эту запись в моё пространство',exact=True).check();page.evaluate('scrollTo(0,0)');page.screenshot(path=str(OUT/'phone-approved-owner-review.png'),full_page=True);restore.click();expect(page.locator('.recovery-status')).to_contain_text('не подтверждено');retry_button=page.get_by_role('button',name='Повторить восстановление',exact=True);expect(retry_button).to_be_visible();retry_button.click();expect(page.locator('.recovery-status')).to_contain_text('Запись восстановлена');commits=[body for path,body in writes if path=='recovery/commit'];assert len(commits)==2 and commits[0]==commits[1];assert len([body for path,body in writes if path=='recovery/prepare'])==1;checks.append('approved_owner_final_action_and_lost_reply_retry_same_grant_operation')
  for width in [320,834,1440]:
   page.set_viewport_size({'width':width,'height':900});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(OUT/f'owner-recovery-{width}.png'),full_page=True)
  page.evaluate("referenceNavigate('account','signout')");page.locator('main').get_by_role('button',name='Выйти',exact=True).click();expect(page.get_by_role('heading',name='Войти',exact=True)).to_be_visible();assert page.evaluate('recoveryCenter().snapshot().records.length')==0;assert page.evaluate('recoveryCenter().snapshot().pending')==0;checks.append('signout_clears_record_previews_and_one_use_grants')
  # A separate fixture Control page receives metadata only; private content never renders.
  staff=origin.replace('localhost','control.localhost');staff_page=context.new_page();staff_page.on('pageerror',lambda error:errors.append(str(error)))
  staff_page.route(staff+'/',lambda route:route.fulfill(body=Path('backend/webassets/index.html').read_text().replace('__SURFACE__','control'),content_type='text/html'))
  permissions=['dashboard.read','records.recover'];requests[0].update(state='pending',revision=1)
  def control_api(route):
   path=urlsplit(route.request.url).path.removeprefix('/control/api/');body=route.request.post_data_json if route.request.method=='POST' else None
   if path=='session':data={'csrf':'fixture-csrf','user_id':str(uuid.uuid4()),'roles':['support'],'permissions':permissions}
   elif path=='dashboard':data={}
   elif path=='record-recovery':data={'requests':[{**requests[0],'data':record['data'],'title':'Личная удалённая заметка'}],'next_before':None}
   elif path=='record-recovery/approve':writes.append((path,body));requests[0].update(state='approved',revision=2);data={'request':requests[0]}
   else:data={}
   route.fulfill(json=data)
  staff_page.route('**/control/api/**',control_api);staff_page.goto(staff+'/');staff_page.get_by_label('Раздел Control',exact=True).select_option('record-recovery');expect(staff_page.get_by_role('heading',name='Запросы восстановления',exact=True)).to_be_visible();expect(staff_page.get_by_text('Личная удалённая заметка',exact=False)).to_have_count(0);expect(staff_page.get_by_text('Содержимое видно только владельцу.',exact=False)).to_have_count(0);staff_page.get_by_role('button',name='Рассмотреть запрос',exact=True).click();staff_page.get_by_label('Причина для журнала аудита',exact=True).fill('Проверен запрос владельца');staff_page.evaluate('scrollTo(0,0)');staff_page.screenshot(path=str(OUT/'control-opaque-request.png'),full_page=True);staff_page.get_by_role('button',name='Одобрить запрос',exact=True).click();expect(staff_page.locator('.control-recovery-status')).to_contain_text('одобрен');assert any(path=='record-recovery/approve' and body['consent_hash']=='a'*64 and body['request_id']==requests[0]['id'] for path,body in writes);staff_page.get_by_role('button',name='Все запросы',exact=True).click();staff_page.evaluate('scrollTo(0,0)');staff_page.screenshot(path=str(OUT/'control-opaque-approval.png'),full_page=True);checks.append('staff_opaque_metadata_only_reasoned_approval_never_silently_restores')
  assert not errors,errors;context.close();browser.close()
 result={'checks':checks,'scope':'Actual local UI with synthetic recovery and staff responses. No real records restored or staff privacy claims beyond UI rendering.'};(OUT/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
