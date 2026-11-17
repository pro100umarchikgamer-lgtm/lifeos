"""Context help routes and draft-safe disclosure in the actual local app."""
from pathlib import Path
import json,os
from playwright.sync_api import sync_playwright,expect
from tool.check_web_platform import fixture,login

def main():
 with fixture() as (origin,_,actor,wid),sync_playwright() as p:
  browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}));context=browser.new_context(viewport={'width':390,'height':844},service_workers='block',reduced_motion='reduce');page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
  def asset(name,mime):
   def serve(route):route.fulfill(path=str(Path('backend/webassets/app')/name),content_type=mime)
   return serve
  for name,mime in [('inbox.js','text/javascript'),('inbox.css','text/css'),('recovery.js','text/javascript'),('recovery.css','text/css')]:page.route('**/app/assets/'+name,asset(name,mime))
  login(page,origin);page.get_by_label('Что нужно сделать?',exact=True).fill('Сохранить мой черновик');help=page.locator('.context-help');assert not help.get_attribute('open');help.locator('summary').click();expect(page.get_by_label('Что нужно сделать?',exact=True)).to_have_value('Сохранить мой черновик');expect(help.locator('a')).to_have_attribute('target','_blank')
  for tab,section,topic in [('today','','today'),('tasks','','tasks'),('calendar','','calendar'),('notes','','notes'),('money','','finances'),('account','','account'),('account','security','security'),('account','notifications','notifications')]:
   page.evaluate('([tab,section])=>referenceNavigate(tab,section)',[tab,section]);help=page.locator('.context-help');expect(help).to_have_count(1);expect(help.locator('a')).to_have_attribute('href','/faq#'+topic)
  assert not errors,errors;context.close();browser.close()
 print(json.dumps({'checks':['context_disclosure_preserves_quick_draft','eight_sections_link_stable_faq_topics_in_separate_tab'],'scope':'Actual app UI, local WSGI auth; FAQ public content owned separately.'}))
if __name__=='__main__':main()
