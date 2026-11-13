"""Notification UX + actual service-worker Notification API on a disposable account.

Subscription/provider transport is synthetic: no owner's device is contacted.
CDP injects push messages into the real worker, which checks the real session,
uses the browser's showNotification/getNotifications APIs, and posts receipts.
This cannot prove a physical device banner, sound, or a public push provider.
"""
from contextlib import contextmanager
from pathlib import Path
import json,os,time,uuid
from playwright.sync_api import sync_playwright,expect
from tool.check_web_platform import fixture,login
from tool.web_browser_navigation import open_tab,open_settings
from backend.production import Application

OUT=Path('web_evidence/notifications')
KEY='BOfjSvBlV87t2wZatd2QHZO4boIt-qSLdAoFW_t5U3DU6UcxDqEybIgsW7jLSwoKVNi-NnmJ1Aq2LxyXrM8F2Qc'
SUBSCRIPTION=str(uuid.uuid4())
FAKE_SUBSCRIPTION="""(() => {
 window.__permissionRequests=0;window.__unsubscribeCalls=0;window.__subscribeCalls=0;const request=Notification.requestPermission.bind(Notification);
 Notification.requestPermission=(...args)=>{window.__permissionRequests++;return request(...args);};
 let current=null;
 const make=()=>({endpoint:'https://push.invalid/synthetic',toJSON(){return {endpoint:this.endpoint,keys:{p256dh:'synthetic',auth:'synthetic'}};},async unsubscribe(){window.__unsubscribeCalls++;current=null;return true;}});
 Object.defineProperty(PushManager.prototype,'getSubscription',{value:async()=>current});
 Object.defineProperty(PushManager.prototype,'subscribe',{value:async()=>{window.__subscribeCalls++;current=make();return current;}});
 window.__existingPushSubscription=()=>{current=make();};
})();"""

@contextmanager
def synthetic_notification_api():
 original=Application.__call__
 data={'enabled':False,'subscription_id':SUBSCRIPTION,'lead_minutes':15,'priority':'high','last_delivery':None}
 receipts=[];writes=[]
 def application(self,environ,start_response):
  path=environ.get('PATH_INFO','')
  if path.startswith('/account/api/notifications'):
   suffix=path.removeprefix('/account/api/notifications');body={}
   if environ.get('REQUEST_METHOD')=='POST':
    body=json.loads(environ['wsgi.input'].read(int(environ.get('CONTENT_LENGTH') or 0)) or b'{}');writes.append((suffix,body))
   if suffix=='/prepare':result={'application_server_key':KEY}
   elif suffix=='/subscribe':data.update(enabled=True,lead_minutes=body['lead_minutes'],priority=body['priority']);result=data
   elif suffix=='/unsubscribe':data['enabled']=False;result=data
   elif suffix=='/receipt':
    receipts.append(body)
    if data['last_delivery'] and data['last_delivery']['id']==body['delivery_id']:data['last_delivery']['state']=body['state']
    result={'ok':True}
   elif suffix=='/test':
    data['last_delivery']={'id':str(uuid.uuid4()),'state':'queued'};result={'delivery_id':data['last_delivery']['id'],'state':'queued'}
   else:result={'supported':True,'application_server_key':KEY,**data}
   encoded=json.dumps(result).encode();start_response('200 OK',[('Content-Type','application/json'),('Cache-Control','no-store'),('Content-Length',str(len(encoded)))]);return [encoded]
  return original(self,environ,start_response)
 Application.__call__=application
 try:yield data,receipts,writes
 finally:Application.__call__=original

def main():
 OUT.mkdir(parents=True,exist_ok=True);checks=[]
 with synthetic_notification_api() as (status,receipts,writes),fixture() as (origin,backend,actor,wid),sync_playwright() as p:
  # Headless Shell 141 denies notifications despite an explicit context grant.
  # Exercise the real Notification API in the matching full Chromium build.
  browser=p.chromium.launch(executable_path=os.environ.get('ULADIM_CHROMIUM') or p.chromium.executable_path)
  context=browser.new_context(viewport={'width':390,'height':844},permissions=['notifications'],timezone_id='Asia/Tashkent',locale='ru-RU')
  context.add_init_script(FAKE_SUBSCRIPTION)
  page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
  cdp=context.new_cdp_session(page);registrations=[];cdp.on('ServiceWorker.workerRegistrationUpdated',lambda event:registrations.extend(event['registrations']));cdp.send('ServiceWorker.enable')
  login(page,origin);assert page.evaluate('window.__permissionRequests')==0
  open_tab(page,'Профиль');open_settings(page,'notifications')
  enable=page.get_by_role('button',name='Включить уведомления',exact=True);expect(enable).to_be_enabled(timeout=20000)
  assert page.evaluate('window.__permissionRequests')==0;checks.append('no_startup_permission_prompt')
  assert not page.locator('.notification-options').get_attribute('open');assert page.locator('main h1').bounding_box()['y']>=page.locator('header').bounding_box()['height'];enable.click()
  expect(page.get_by_text('Включены на этом устройстве',exact=True)).to_be_visible();assert status['enabled'];assert writes[-1][1]['timezone']=='Asia/Tashkent'
  page.evaluate('scrollTo(0,0)');page.screenshot(path=str(OUT/'phone-enabled.png'),full_page=True);checks.append('explicit_enable_device_only_and_options_folded')
  page.locator('.notification-options summary').click();page.get_by_label('До начала события',exact=True).select_option('30');page.get_by_label('Приоритет доставки',exact=True).select_option('normal');page.get_by_role('button',name='Сохранить параметры',exact=True).click();expect(page.get_by_text('Параметры сохранены',exact=True)).to_be_visible();assert status['lead_minutes']==30 and status['priority']=='normal';checks.append('calendar_lead_and_standard_priority_preferences')
  page.locator('.notification-options summary').click()
  page.wait_for_function('navigator.serviceWorker.controller!==null')
  registration=next(item['registrationId'] for item in reversed(registrations) if item['scopeURL']==origin+'/app')
  def count_notifications():return page.evaluate('(async()=> (await (await navigator.serviceWorker.ready).getNotifications()).length)()')
  def clear_notifications():page.evaluate('(async()=>{for(const item of await (await navigator.serviceWorker.ready).getNotifications())item.close();})()')
  def push(**changes):
   delivery=changes.get('delivery_id') or str(uuid.uuid4());payload={'v':1,'delivery_id':delivery,'subscription_id':SUBSCRIPTION,'recipient_user_id':actor['id'],'receipt_token':'R'*43,'title':'ULADIM','body':'Проверка уведомлений','url':'/app','tag':'uladim-'+delivery,'priority':'high','sent_at':int(time.time()*1000)};payload.update(changes)
   cdp.send('ServiceWorker.deliverPushMessage',{'origin':origin,'registrationId':registration,'data':json.dumps(payload)});return delivery
  def wait_receipt(delivery,state):
   deadline=time.time()+8
   while time.time()<deadline:
    page.wait_for_timeout(100)
    if any(item['delivery_id']==delivery and item['state']==state for item in receipts):return
   raise AssertionError((delivery,state,receipts))
  page.get_by_role('button',name='Проверить доставку',exact=True).click();expect(page.locator('.notification-delivery')).to_contain_text('Уведомление в очереди');test_delivery=status['last_delivery']['id'];status['last_delivery']['state']='accepted';expect(page.locator('.notification-delivery')).to_contain_text('Push-сервис принял',timeout=6000)
  delivery=push(delivery_id=test_delivery);wait_receipt(delivery,'displayed');expect(page.locator('.notification-delivery')).to_contain_text('Передано системе устройства',timeout=6000);assert count_notifications()==1;checks.append('test_button_distinguishes_queue_provider_and_system_receipt')
  shown=page.evaluate('(async()=>{const n=(await (await navigator.serviceWorker.ready).getNotifications())[0];return {title:n.title,body:n.body,tag:n.tag,interaction:n.requireInteraction,data:n.data};})()')
  assert shown['title']=='ULADIM' and shown['interaction'] and shown['data']['url']=='/app';checks.append('actual_service_worker_showNotification_and_token_receipt')
  worker=context.service_workers[0]
  click=worker.evaluate("""async () => {
   const actions=[],original=self.clients.matchAll.bind(self.clients);
   self.clients.matchAll=async()=>[{url:'https://external.invalid/app',navigate:async()=>actions.push('external')},{url:self.location.origin+'/app',navigate:async url=>actions.push(url),focus:async()=>actions.push('focus')}];
   try {
    let pending;const event=new Event('notificationclick');
    Object.defineProperties(event,{notification:{value:{data:{url:'/app'},close(){actions.push('close');}}},waitUntil:{value:p=>{pending=p;}}});
    self.dispatchEvent(event);await pending;return actions;
   }finally{self.clients.matchAll=original;}
  }""")
  assert click==['close','/app','focus'],click;checks.append('worker_click_routes_to_same_origin_app_with_synthetic_clients')
  clear_notifications();delivery=push(recipient_user_id=str(uuid.uuid4()));wait_receipt(delivery,'suppressed');assert count_notifications()==0;checks.append('account_switch_inflight_suppressed')
  status['enabled']=False;delivery=push();wait_receipt(delivery,'suppressed');assert count_notifications()==0;status['enabled']=True;checks.append('disabled_subscription_inflight_suppressed')
  delivery=push(subscription_id=str(uuid.uuid4()));wait_receipt(delivery,'suppressed');assert count_notifications()==0;checks.append('replaced_subscription_inflight_suppressed')
  before=len(receipts);push(url='https://external.invalid/');push(sent_at=1);cdp.send('ServiceWorker.deliverPushMessage',{'origin':origin,'registrationId':registration,'data':'x'*8193});page.wait_for_timeout(700);assert len(receipts)==before and count_notifications()==0;checks.append('unsafe_destination_and_expired_payload_rejected')
  # Genuine WSGI logout removes the session before another injected push.
  page.evaluate("(async()=>{const s=await (await fetch('/account/api/session')).json();await fetch('/account/api/logout',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':s.csrf},body:'{}'});})()")
  delivery=push();wait_receipt(delivery,'suppressed');assert count_notifications()==0;checks.append('real_logged_out_session_suppresses_push')
  login(page,origin)
  page.evaluate('window.__existingPushSubscription()');before=len([item for item in writes if item[0]=='/subscribe'])
  page.evaluate('refreshNotificationTimezone()');page.wait_for_timeout(500)
  assert len([item for item in writes if item[0]=='/subscribe'])==before+1 and writes[-1][1]['lead_minutes']==30 and writes[-1][1]['priority']=='normal';assert page.evaluate('window.__permissionRequests')==0;checks.append('existing_optin_timezone_refresh_no_permission_prompt')
  open_tab(page,'Профиль');open_settings(page,'notifications');expect(page.get_by_text('Включены на этом устройстве',exact=True)).to_be_visible(timeout=20000);page.get_by_role('button',name='Выключить на устройстве',exact=True).click();expect(page.get_by_text('Выключены на этом устройстве',exact=True)).to_be_visible();assert page.evaluate('window.__unsubscribeCalls')==1 and not status['enabled'];checks.append('explicit_disable_server_and_browser')
  page.get_by_role('button',name='Включить уведомления',exact=True).click();expect(page.get_by_text('Включены на этом устройстве',exact=True)).to_be_visible()
  before_subscriptions=page.evaluate('window.__subscribeCalls');before_unsubscribe=page.evaluate('window.__unsubscribeCalls');status['enabled']=False;status['last_delivery']={'id':str(uuid.uuid4()),'state':'failed','error_code':'subscription_gone'}
  page.evaluate("openSettings('notifications')");expect(page.get_by_role('button',name='Включить уведомления',exact=True)).to_be_enabled(timeout=20000);page.get_by_role('button',name='Включить уведомления',exact=True).click();expect(page.get_by_text('Включены на этом устройстве',exact=True)).to_be_visible();assert page.evaluate('window.__subscribeCalls')==before_subscriptions+1 and page.evaluate('window.__unsubscribeCalls')==before_unsubscribe+1;checks.append('expired_provider_endpoint_reconnects_with_fresh_subscription')
  page.goto(origin+'/app?notification=calendar&workspace='+wid+'&day=2026-11-20');expect(page.get_by_role('heading',name='Календарь',exact=True)).to_be_visible();assert 'notification=' not in page.url;checks.append('authorized_calendar_notification_deep_link')
  open_tab(page,'Профиль');open_settings(page,'notifications');expect(page.get_by_role('button',name='Выключить на устройстве',exact=True)).to_be_visible(timeout=20000);page.get_by_role('button',name='Выключить на устройстве',exact=True).click();expect(page.get_by_text('Выключены на этом устройстве',exact=True)).to_be_visible();assert not status['enabled'];checks.append('disable_stale_server_optin_without_local_subscription')
  for width in [320,834,1440]:
   page.set_viewport_size({'width':width,'height':900});page.screenshot(path=str(OUT/f'notifications-{width}.png'),full_page=True);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');
  checks.append('phone_tablet_desktop_no_horizontal_overflow')
  keys=page.evaluate('Object.keys(localStorage)');assert all(key=='uladim-interface' or key.startswith('uladim-note-draft:') for key in keys),keys
  cached=page.evaluate('(async()=>{const urls=[];for(const key of await caches.keys())for(const r of await (await caches.open(key)).keys())urls.push(r.url);return urls;})()');assert not any('/account/' in url for url in cached);checks.append('no_account_or_notification_data_in_web_storage')
  assert not errors,errors
  context.close()
  # Browser denial and iOS installation instructions never request permission.
  for name,script,expected in [('denied',"Object.defineProperty(Notification,'permission',{get:()=> 'denied'});",'Уведомления запрещены'),('old-worker',"const send=ServiceWorker.prototype.postMessage;ServiceWorker.prototype.postMessage=function(message,...args){if(message?.type!=='uladim-notifications-capabilities')return send.call(this,message,...args);};",'обновление ещё устанавливается'),('ios',"Object.defineProperty(navigator,'platform',{get:()=> 'MacIntel'});Object.defineProperty(navigator,'maxTouchPoints',{get:()=>5});",'На iPhone и iPad')]:
   ctx=browser.new_context(viewport={'width':390,'height':844},permissions=['notifications']);ctx.add_init_script(FAKE_SUBSCRIPTION+script);pg=ctx.new_page();login(pg,origin);open_tab(pg,'Профиль');open_settings(pg,'notifications');expect(pg.locator('.notification-status')).to_contain_text(expected,timeout=20000);assert pg.evaluate('window.__permissionRequests')==0;ctx.close();checks.append(name+'_clear_guidance_without_prompt')
  ctx=browser.new_context(viewport={'width':390,'height':844});ctx.add_init_script(FAKE_SUBSCRIPTION+"let permission='default';Object.defineProperty(Notification,'permission',{get:()=>permission});Notification.requestPermission=()=>{window.__permissionRequests++;permission='denied';return Promise.resolve(permission);};")
  pg=ctx.new_page();login(pg,origin);open_tab(pg,'Профиль');open_settings(pg,'notifications');expect(pg.get_by_role('button',name='Включить уведомления',exact=True)).to_be_enabled(timeout=20000);assert pg.evaluate('window.__permissionRequests')==0
  pg.get_by_role('button',name='Включить уведомления',exact=True).click();expect(pg.locator('.notification-status')).to_contain_text('Уведомления запрещены');assert pg.evaluate('window.__permissionRequests')==1;ctx.close();checks.append('permission_request_only_on_enable_with_synthetic_denial')
  browser.close()
 summary={'checks':checks,'transport':'Synthetic subscription and CDP-injected push; actual WSGI session, service worker and browser Notification API. No physical device/banner/provider claim.'};(OUT/'checks.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
