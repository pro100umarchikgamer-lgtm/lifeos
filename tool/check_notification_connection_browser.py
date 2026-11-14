"""Connection failure/retry UX with synthetic PushManager and local WSGI auth.
No OS delivery, push-provider, endpoint, or physical-device success claim.
"""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from tool.check_web_platform import fixture,login
from tool.check_web_push_browser import KEY

OUT=Path('web_evidence/notification-connection')
SETUP="""() => {
 window.__permissionCalls=0;window.__browserCalls=0;window.__subscription=null;
 Object.defineProperty(Notification,'permission',{get:()=> 'granted'});Notification.requestPermission=async()=>{window.__permissionCalls++;return 'granted';};
 notificationWorker=async()=>({supported:true,registration:{pushManager:{getSubscription:async()=>window.__subscription,subscribe:async()=>{window.__browserCalls++;if(window.__failBrowser)throw new DOMException('SECRET_ENDPOINT_MUST_NOT_RENDER','AbortError');window.__subscription={toJSON:()=>({endpoint:'https://push.invalid/SECRET_ENDPOINT',keys:{p256dh:'SECRET_KEY',auth:'SECRET_AUTH'}}),unsubscribe:async()=>true};return window.__subscription;}}}});
}"""

def main():
 OUT.mkdir(parents=True,exist_ok=True);checks=[]
 with fixture() as (origin,_,actor,wid),sync_playwright() as p:
  browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
  for mode in ['save-once','save-permanent','browser']:
   context=browser.new_context(viewport={'width':390,'height':844},service_workers='block',reduced_motion='reduce');page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)));settings={'enabled':mode=='save-permanent','lead_minutes':15,'priority':'high','last_delivery':None};writes=[]
   def asset_handler(name,mime):
    def handle(route):route.fulfill(path=str(Path('backend/webassets/app')/name),content_type=mime)
    return handle
   for name,mime in [('inbox.js','text/javascript'),('inbox.css','text/css'),('recovery.js','text/javascript'),('recovery.css','text/css')]:page.route('**/app/assets/'+name,asset_handler(name,mime))
   def api(route):
    suffix=route.request.url.split('/account/api/notifications',1)[1].split('?')[0]
    if suffix=='/prepare':route.fulfill(json={'application_server_key':KEY});return
    if suffix=='/subscribe':
     writes.append(route.request.post_data_json)
     if mode=='save-permanent':route.fulfill(status=400,json={'error':'push_subscription_invalid'});return
     if mode=='save-once' and len(writes)==1:route.fulfill(status=503,json={'error':'server_error'});return
     settings['enabled']=True
    route.fulfill(json=settings)
   page.route('**/account/api/notifications**',api);login(page,origin);page.evaluate(SETUP);page.evaluate('window.__failBrowser='+('true' if mode=='browser' else 'false'));page.evaluate("referenceNavigate('account','notifications')");enable=page.get_by_role('button',name='Включить уведомления',exact=True);expect(enable).to_be_enabled();assert page.evaluate('window.__permissionCalls')==0;enable.click();expect(page.locator('.notification-feedback')).to_contain_text('Разрешение получено');retry=page.get_by_role('button',name='Повторить подключение',exact=True);expect(retry).to_be_enabled();expect(page.locator('.notification-status')).not_to_contain_text('Включены на этом устройстве');support=page.locator('.notification-diagnostics');assert not support.get_attribute('open');support.get_by_text('Сведения для поддержки',exact=True).click();expect(support).to_contain_text('browser-registration' if mode=='browser' else 'save');expect(support).to_contain_text('AbortError' if mode=='browser' else 'push_subscription_invalid' if mode=='save-permanent' else 'server_error');assert 'SECRET_' not in page.locator('body').inner_text();assert page.evaluate('window.__browserCalls')==1 and page.evaluate('window.__permissionCalls')==0
   if mode=='save-once':
    retry.click();expect(page.locator('.notification-status')).to_contain_text('Включены на этом устройстве');assert len(writes)==2 and writes[0]==writes[1];assert page.evaluate('window.__browserCalls')==1;checks.append('save_503_explicit_retry_reuses_subscription_and_same_payload')
   elif mode=='save-permanent':checks.append('permanent_400_shows_whitelisted_save_stage_and_code_only')
   else:assert not writes;checks.append('granted_permission_browser_registration_failure_never_claims_enabled')
   page.evaluate('scrollTo(0,0)');page.screenshot(path=str(OUT/(mode+'.png')),full_page=True);assert not errors,errors;context.close()
  browser.close()
 result={'checks':checks,'scope':'Synthetic browser registration and notification API. No real OS/push-provider or physical-device delivery verification.'};(OUT/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
