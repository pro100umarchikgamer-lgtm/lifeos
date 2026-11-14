"""A missing new static module cannot break the existing app on an older server."""
from pathlib import Path
import json,os
from playwright.sync_api import sync_playwright,expect
from tool.check_web_platform import fixture,login

def main():
 with fixture() as (origin,_,actor,wid),sync_playwright() as p:
  browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}));context=browser.new_context(viewport={'width':390,'height':844},service_workers='block');page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
  page.route('**/app/assets/inbox.js',lambda route:route.abort());login(page,origin);page.get_by_role('button',name='Уведомления',exact=True).click();expect(page.get_by_role('heading',name='Уведомления',exact=True)).to_be_visible();expect(page.get_by_text('История уведомлений пока недоступна.',exact=True)).to_be_visible();assert page.locator('.inbox-row').count()==0;page.evaluate("referenceNavigate('tasks')");expect(page.get_by_role('heading',name='Задачи',exact=True)).to_be_visible();assert not errors,errors;context.close();browser.close()
 print(json.dumps({'checks':['missing_inbox_asset_keeps_login_and_existing_sections_working_without_fake_history'],'scope':'Actual local app and WSGI auth; aborted optional static asset only.'}))
if __name__=='__main__':main()
