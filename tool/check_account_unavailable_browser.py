"""Self erasure clears private state; target errors and stale checks cannot sign out a valid account.
Actual local WSGI authentication and erasing state; synthetic target failure only.
"""
import json,os,uuid
from playwright.sync_api import sync_playwright,expect
from tool.check_web_platform import fixture,login,PASSWORD


def seed_drafts(page,uid,wid):
 keys=['uladim-note-draft:'+uid+':'+wid+':new','uladim-task-action:'+uid+':'+wid+':quick']
 page.evaluate("keys=>keys.forEach(key=>sessionStorage.setItem(key,'private draft'))",keys)
 return keys


def wait_result(page):
 for attempt in range(150):
  if page.evaluate('window.unavailableResult!==null'):return
  page.wait_for_timeout(20)
 raise AssertionError('request did not finish')


def main():
 checks=[]
 with sync_playwright() as p:
  browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
  for scenario in ['self','session','target','late-check','cookie-switch']:
   with fixture() as (origin,backend,actor,wid):
    context=browser.new_context(viewport={'width':390,'height':844},service_workers='block');page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));login(page,origin);keys=seed_drafts(page,actor['id'],wid)
    if scenario in ['self','session']:
     now=int(backend.clock())
     with backend.transaction() as db:db.execute("INSERT INTO deletion_jobs VALUES(?,?,?,?,'erasing',NULL)",(str(uuid.uuid4()),actor['id'],now,now))
     route='session' if scenario=='session' else 'spaces'
     page.evaluate("path=>{window.unavailableResult=null;call(path).catch(error=>{report(error);window.unavailableResult=error.code;});}",route)
     wait_result(page);expect(page.locator('.focus-login')).to_be_visible();assert page.evaluate('state.session===null&&state.records.length===0&&state.spaces.length===0&&state.csrf===\'\'');assert not page.evaluate('keys=>keys.some(key=>sessionStorage.getItem(key)!==null)',keys);checks.append('actual_self_erasing_'+route+'_clears_private_ui_and_account_drafts')
    else:
     page.route('**/account/api/transfer',lambda r:r.fulfill(status=403,json={'error':'account_unavailable'}));held=[]
     if scenario=='late-check':page.route('**/account/api/session',lambda r:held.append(r))
     if scenario=='cookie-switch':
      result=backend.register('cookie-switch@example.test',PASSWORD);new_actor=backend.authenticate(result['token'])
      with backend.transaction() as db:db.execute('UPDATE users SET verified=1 WHERE id=?',(new_actor['id'],))
      assert page.evaluate("async body=>(await fetch('/account/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).ok",{'email':new_actor['email'],'password':PASSWORD})
     page.evaluate("()=>{window.unavailableResult=null;call('transfer',{target:'unavailable synthetic target'}).catch(error=>{report(error);window.unavailableResult=error.code;});}")
     if scenario=='cookie-switch':
      wait_result(page);expect(page.locator('.focus-login')).to_be_visible();assert page.evaluate('state.session===null&&state.records.length===0');assert not page.evaluate('keys=>keys.some(key=>sessionStorage.getItem(key)!==null)',keys);assert page.evaluate("async()=>(await(await fetch('/account/api/session')).json()).user_id")==new_actor['id'];checks.append('changed_browser_cookie_discards_old_private_view_without_revoking_new_session')
     elif scenario=='late-check':
      for attempt in range(100):
       if held:break
       page.wait_for_timeout(10)
      assert held,'target failure did not validate own session';page.unroute('**/account/api/session');result=backend.register('new-account@example.test',PASSWORD);new_actor=backend.authenticate(result['token'])
      with backend.transaction() as db:db.execute('UPDATE users SET verified=1 WHERE id=?',(new_actor['id'],))
      page.evaluate('clearIdentity();login()');page.get_by_label('Электронная почта',exact=True).fill(new_actor['email']);page.locator('input[name=password]').fill(PASSWORD);page.get_by_role('button',name='Войти',exact=True).click();expect(page.locator('.focus-login')).to_have_count(0);assert page.evaluate('uid=>state.session?.user_id===uid',new_actor['id']);new_keys=seed_drafts(page,new_actor['id'],'new-space');held[0].fulfill(status=403,json={'error':'account_unavailable'});wait_result(page);assert page.evaluate('uid=>state.session?.user_id===uid',new_actor['id']);assert page.evaluate('keys=>keys.every(key=>sessionStorage.getItem(key)!==null)',new_keys);expect(page.locator('.focus-login')).to_have_count(0);checks.append('late_self_validation_cannot_clear_new_account_or_its_drafts')
     else:
      wait_result(page);assert page.evaluate('window.unavailableResult')=='account_unavailable';assert page.evaluate('uid=>state.session?.user_id===uid',actor['id']);assert page.evaluate('keys=>keys.every(key=>sessionStorage.getItem(key)!==null)',keys);expect(page.get_by_role('heading',name='Сегодня',exact=True)).to_be_visible();checks.append('target_unavailable_preserves_valid_self_session_and_drafts')
    assert not errors,errors;context.close()
  browser.close()
 print(json.dumps({'checks':checks,'scope':'Actual local WSGI sessions and self erasing state; synthetic target failure and delayed validation, no production data or erasure worker.'}))
if __name__=='__main__':main()
