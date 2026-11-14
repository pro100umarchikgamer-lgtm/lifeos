"""Password deletion request/cancel against actual local WSGI + disposable DB.
No deletion worker runs and no production account or records are accessed.
"""
from pathlib import Path
import json,os
from playwright.sync_api import sync_playwright,expect
from tool.check_web_platform import fixture,login,PASSWORD

OUT=Path('web_evidence/account-deletion-live')

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 with fixture() as (origin,backend,actor,wid),sync_playwright() as p:
  browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}));context=browser.new_context(viewport={'width':390,'height':844},service_workers='block',reduced_motion='reduce');page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
  def asset(name,mime):
   def serve(route):route.fulfill(path=str(Path('backend/webassets/app')/name),content_type=mime)
   return serve
  for name in ['inbox.js','inbox.css','recovery.js','recovery.css','account-deletion.js','account-deletion.css']:page.route('**/app/assets/'+name,asset(name,'text/javascript' if name.endswith('.js') else 'text/css'))
  login(page,origin);page.evaluate('deletion()');page.get_by_role('button',name='Продолжить удаление',exact=True).click();page.get_by_label('Текущий пароль',exact=True).fill(PASSWORD);page.get_by_label('Введите DELETE',exact=True).fill('DELETE');page.get_by_role('button',name='Запросить удаление',exact=True).click();expect(page.locator('.account-deletion-pending')).to_contain_text('Удаление запланировано')
  with backend.connect() as db:
   job=db.execute('SELECT * FROM deletion_jobs WHERE user_id=?',(actor['id'],)).fetchone();assert job['state']=='pending' and job['due_at']-job['requested_at']==86400
  page.evaluate('scrollTo(0,0)');page.screenshot(path=str(OUT/'actual-request-pending.png'),full_page=True);page.get_by_role('button',name='Отменить запрос',exact=True).click();expect(page.get_by_label('Текущий пароль',exact=True)).to_have_value('');page.get_by_label('Текущий пароль',exact=True).fill(PASSWORD);page.get_by_role('button',name='Отменить удаление',exact=True).click();expect(page.locator('.account-deletion-status')).to_contain_text('отменён')
  with backend.connect() as db:assert db.execute('SELECT state FROM deletion_jobs WHERE user_id=?',(actor['id'],)).fetchone()['state']=='cancelled';assert db.execute('SELECT COUNT(*) AS n FROM records WHERE owner_id=?',(actor['id'],)).fetchone()['n']>0
  assert not errors,errors;context.close();browser.close()
 result={'checks':['actual_password_request_has_24h_grace','actual_cancel_requires_fresh_password_and_keeps_records'],'scope':'Actual local account lifecycle request/cancel. No worker erasure, production account or Google provider claim.'};(OUT/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
