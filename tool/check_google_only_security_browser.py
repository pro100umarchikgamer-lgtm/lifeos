"""Google-only security controls offer the existing email password setup route.
Synthetic method metadata; no emails, passwords or security settings are changed.
"""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from tool.check_web_platform import fixture,login

def main():
 with fixture() as (origin,_,actor,wid),sync_playwright() as p:
  browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}));context=browser.new_context(viewport={'width':390,'height':844},service_workers='block',reduced_motion='reduce');page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)));writes=[]
  def asset(name,mime):
   def serve(route):route.fulfill(path=str(Path('backend/webassets/app')/name),content_type=mime)
   return serve
  for name in ['inbox.js','inbox.css','recovery.js','recovery.css','account-deletion.js','account-deletion.css']:page.route('**/app/assets/'+name,asset(name,'text/javascript' if name.endswith('.js') else 'text/css'))
  page.route('**/account/api/google',lambda route:route.fulfill(json={'has_password':False,'google_linked':True,'google_web_enabled':False}))
  login(page,origin)
  for method,label in [('changePassword','Пароль'),('changeEmail','Почта'),('customerMfa','Защита')]:
   page.evaluate("referenceNavigate('account','security')");page.evaluate('method=>window[method]()',method);panel=page.locator('.settings-inline-panel');expect(panel).to_contain_text('Дополнительная защита сохранится');expect(panel.get_by_role('button',name='Настроить пароль по почте',exact=True)).to_be_visible();expect(panel.locator('input[type=password]')).to_have_count(0)
  page.evaluate("referenceNavigate('account','devices')");page.locator('.device-row button').first.click();panel=page.locator('.settings-inline-panel');expect(panel).to_contain_text('Дополнительная защита сохранится');expect(panel.locator('input[type=password]')).to_have_count(0);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');assert not errors,errors;context.close();browser.close()
 print(json.dumps({'checks':['four_google_only_security_controls_offer_real_email_setup_exit_without_password_form'],'scope':'Synthetic method metadata with actual local UI/auth. No emails sent or security settings changed.'}))
if __name__=='__main__':main()
