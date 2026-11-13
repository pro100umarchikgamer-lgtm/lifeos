"""Deletion review/auth UX with synthetic lifecycle/Google responses, local auth.
No production account, family, credentials, deletion worker or real Google login.
"""
from pathlib import Path
import json,os,time,uuid
from playwright.sync_api import sync_playwright,expect
from tool.check_web_platform import fixture,login

OUT=Path('web_evidence/account-deletion');PROOF='R'*43

def main():
 OUT.mkdir(parents=True,exist_ok=True);checks=[];now=int(time.time())
 with fixture() as (origin,_,actor,wid),sync_playwright() as p:
  browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
  for mode in ['google','google-mismatch','google-cancelled','google-unavailable','family','transfer','staff','erasing']:
   context=browser.new_context(viewport={'width':390,'height':844},service_workers='block',reduced_motion='reduce');page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)));writes=[];auth={'count':0};family_id=str(uuid.uuid4());target_id=str(uuid.uuid4());status={'request':None,'ownership_transfer_required':[],'incoming_transfers':[],'has_password':not mode.startswith('google'),'google_linked':mode.startswith('google'),'google_reauth_available':mode.startswith('google') and mode!='google-unavailable','mfa_required':mode.startswith('google'),'grace_seconds':86400,'cancel_available':False,'staff_offboarding_required':mode=='staff','local_data_deleted':False}
   if mode=='erasing':status.update(request={'state':'erasing','due_at':now},cancel_available=False)
   if mode in ('family','transfer'):status['ownership_transfer_required']=[{'id':family_id,'name':'Семья и общие планы','eligible_parent_id':target_id if mode=='transfer' else None,'eligible_parent_label':'partner@example.test' if mode=='transfer' else None,'pending_until':None,'workspace_revision':3,'close_family_available':True}]
   def asset(name,mime):
    def serve(route):route.fulfill(path=str(Path('backend/webassets/app')/name),content_type=mime)
    return serve
   for name in ['inbox.js','inbox.css','recovery.js','recovery.css','account-deletion.js','account-deletion.css']:page.route('**/app/assets/'+name,asset(name,'text/javascript' if name.endswith('.js') else 'text/css'))
   def api(route):
    suffix=route.request.url.split('/account/api/',1)[1].split('?')[0];body=route.request.post_data_json if route.request.method=='POST' else None
    if body is not None:writes.append((suffix,body))
    if suffix=='google/reauth/start':data={'authorization_url':origin+'/synthetic-reauth','expires_in':600}
    elif suffix=='google/complete':
     auth['count']+=1
     data={'error':'google_identity_mismatch' if mode=='google-mismatch' else 'google_cancelled'} if mode!='google' else {'reauth_token':PROOF if auth['count']==1 else 'S'*43,'expires_in':300}
    elif suffix=='close-family':status['ownership_transfer_required']=[];data={'dissolved':True}
    elif suffix=='transfer':status['ownership_transfer_required'][0]['pending_until']=now+86400;data={'transfer_id':str(uuid.uuid4()),'recipient_confirmation_required':True}
    elif suffix=='deletion' and body is not None:status.update(request={'state':'pending','due_at':now+86400},cancel_available=True);data={'state':'pending','due_at':now+86400}
    elif suffix=='cancel-deletion':status.update(request={'state':'cancelled'},cancel_available=False);data={'cancelled':True}
    else:data=status
    route.fulfill(json=data)
   for suffix in ['deletion','cancel-deletion','close-family','transfer','google/reauth/start','google/complete']:page.route('**/account/api/'+suffix,api)
   page.route(origin+'/synthetic-reauth',lambda route:route.fulfill(status=302,headers={'Location':origin+'/app?google=return'},body=''))
   login(page,origin);page.evaluate('deletion()');expect(page.get_by_role('heading',name='Удаление аккаунта',level=1,exact=True)).to_be_visible();expect(page.locator('dialog[open]')).to_have_count(0);expect(page.locator('.account-deletion-panel')).to_contain_text('общие записи');expect(page.locator('.account-deletion-panel')).to_contain_text('устройстве')
   if mode=='google-unavailable':
    page.get_by_role('button',name='Продолжить удаление',exact=True).click();expect(page.get_by_role('button',name='Подтвердить через Google',exact=True)).to_have_count(0);expect(page.get_by_role('button',name='Запросить удаление',exact=True)).to_be_disabled();page.get_by_role('button',name='Восстановить вход по почте',exact=True).click();expect(page.locator('dialog[open]')).to_have_count(1);checks.append('unavailable_google_offers_existing_email_recovery_without_bypassing_mfa')
   elif mode in ['google-mismatch','google-cancelled']:
    page.get_by_role('button',name='Продолжить удаление',exact=True).click();page.get_by_role('button',name='Подтвердить через Google',exact=True).click();expect(page.locator('.account-deletion-status')).to_contain_text('тот же Google-аккаунт' if mode=='google-mismatch' else 'не завершено');assert page.evaluate('state.session.user_id')==actor['id'];assert not page.evaluate('deletionCenter().snapshot().proof');assert not any(path=='deletion' for path,body in writes);checks.append(mode+'_preserves_signed_in_identity_without_proof_or_delete')
   elif mode=='google':
    page.get_by_role('button',name='Продолжить удаление',exact=True).click();expect(page.locator('input[type=password]')).to_have_count(0);page.get_by_role('button',name='Подтвердить через Google',exact=True).click();expect(page.get_by_role('heading',name='Удаление аккаунта',level=1,exact=True)).to_be_visible();expect(page.locator('.account-deletion-proof')).to_contain_text('Google подтверждён');assert page.evaluate('state.session.user_id')==actor['id'];assert PROOF not in page.locator('body').inner_text();assert not page.evaluate('(proof)=>Object.values(localStorage).concat(Object.values(sessionStorage)).some(value=>value.includes(proof))',PROOF);page.get_by_role('button',name='Продолжить удаление',exact=True).click();page.get_by_label('Код дополнительной защиты',exact=True).fill('123456');page.get_by_label('Введите DELETE',exact=True).fill('DELETE');page.get_by_role('button',name='Запросить удаление',exact=True).click();expect(page.locator('.account-deletion-panel')).to_contain_text('запланировано');assert any(path=='deletion' and body=={'reauth_token':PROOF,'code':'123456','confirmation':'DELETE'} for path,body in writes);assert not page.evaluate('deletionCenter().snapshot().proof');page.get_by_role('button',name='Отменить запрос',exact=True).click();expect(page.get_by_role('button',name='Подтвердить через Google',exact=True)).to_be_visible();page.get_by_role('button',name='Подтвердить через Google',exact=True).click();expect(page.locator('.account-deletion-proof')).to_contain_text('Google подтверждён');page.get_by_role('button',name='Отменить запрос',exact=True).click();page.get_by_label('Код дополнительной защиты',exact=True).fill('654321');page.get_by_role('button',name='Отменить удаление',exact=True).click();expect(page.locator('.account-deletion-status')).to_contain_text('отменён');assert any(path=='cancel-deletion' and body=={'reauth_token':'S'*43,'code':'654321'} for path,body in writes);checks.append('google_only_reauth_return_keeps_identity_memory_only_proof_single_use_and_mfa')
   elif mode=='family':
    expect(page.get_by_role('button',name='Продолжить удаление',exact=True)).to_have_count(0);page.get_by_role('button',name='Закрыть семейное пространство',exact=True).click();expect(page.locator('.account-deletion-review')).to_contain_text('всех участников');page.get_by_label('Текущий пароль',exact=True).fill('synthetic-close-password');page.get_by_label('Введите CLOSE FAMILY',exact=True).fill('CLOSE FAMILY');page.get_by_role('button',name='Подтвердить закрытие',exact=True).click();expect(page.get_by_role('button',name='Продолжить удаление',exact=True)).to_be_visible();assert any(path=='close-family' and body=={'workspace_id':family_id,'revision':3,'confirmation':'CLOSE FAMILY','password':'synthetic-close-password'} for path,body in writes);page.get_by_role('button',name='Продолжить удаление',exact=True).click();expect(page.get_by_label('Текущий пароль',exact=True)).to_have_value('');checks.append('sole_parent_close_has_family_impact_literal_revision_and_fresh_delete_auth')
   elif mode=='transfer':
    page.get_by_role('button',name='Передать управление',exact=True).click();expect(page.locator('.account-deletion-review')).to_contain_text('partner@example.test');page.get_by_label('Текущий пароль',exact=True).fill('synthetic-transfer-password');page.get_by_label('Понимаю последствия передачи управления',exact=True).check();page.get_by_role('button',name='Запросить передачу',exact=True).click();expect(page.locator('.account-deletion-panel')).to_contain_text('подтверждения');assert any(path=='transfer' and body['user_id']==target_id for path,body in writes);checks.append('transfer_identifies_recipient_and_waits_for_recipient_confirmation')
   elif mode=='erasing':expect(page.get_by_role('button',name='Продолжить удаление',exact=True)).to_have_count(0);expect(page.get_by_role('button',name='Отменить запрос',exact=True)).to_have_count(0);expect(page.locator('.account-deletion-panel')).to_contain_text('Удаление уже началось');checks.append('erasing_is_in_progress_without_new_request_or_false_cancel')
   else:expect(page.get_by_role('button',name='Продолжить удаление',exact=True)).to_have_count(0);expect(page.locator('.account-deletion-panel')).to_contain_text('Control');checks.append('staff_offboarding_blocker_has_explanation_without_fake_delete')
   page.evaluate('scrollTo(0,0)');page.screenshot(path=str(OUT/(mode+'.png')),full_page=True)
   for width in [320,834,1440]:page.set_viewport_size({'width':width,'height':900});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
   assert not errors,errors;context.close()
  browser.close()
 result={'checks':checks,'scope':'Synthetic lifecycle and Google reauthentication responses with actual local app and WSGI session. No actual deletion or Google provider claim.'};(OUT/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
