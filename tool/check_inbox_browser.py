"""Inbox/announcement UX with loopback WSGI and synthetic notification API only.
No production messages, push transport, staff credentials, or real audience.
"""
from pathlib import Path
import json, os, time, uuid
from playwright.sync_api import sync_playwright, expect
from tool.check_web_platform import fixture, login

OUT=Path('web_evidence/inbox')

def main():
 OUT.mkdir(parents=True,exist_ok=True);checks=[];now=int(time.time())
 notices=[dict(id=str(uuid.uuid4()),kind='announcement',title='Новости ULADIM',body='Обновления и полезные подсказки теперь собраны в одном месте.\nВаши планы всегда под рукой.',presentation='inbox',created_at=now,starts_at=now-60,expires_at=now+86400,link='/app',read_at=0,dismissed_at=0,presented_at=0,active=True),dict(id=str(uuid.uuid4()),kind='reminder',title='Напоминание о встрече',body='Откройте календарь, чтобы проверить свои планы.',presentation='inbox',created_at=now-3600,starts_at=now-3600,expires_at=now+86400,link='/app',read_at=now-1800,dismissed_at=0,presented_at=0,active=True)]
 writes=[];requests=[];mode={'state':'ok'};preferences={'budget_enabled':False,'budget_thresholds':[50,80,100],'timezone':'UTC'}
 with fixture() as (origin,backend,actor,wid),sync_playwright() as p:
  browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
  context=browser.new_context(viewport={'width':390,'height':844},locale='ru-RU',reduced_motion='reduce',service_workers='block')
  page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
  # New static assets remain actual repository bytes while backend allowlist lands separately.
  def asset_handler(name,mime):
   def handle(route):route.fulfill(path=str(Path('backend/webassets/app')/name),content_type=mime)
   return handle
  for name,mime in [('inbox.js','text/javascript'),('inbox.css','text/css')]:
   page.route('**/app/assets/'+name,asset_handler(name,mime))
  def inbox(route):
   requests.append(route.request.url)
   if mode['state']=='offline':route.abort();return
   if mode['state']=='404':route.fulfill(status=404,json={'error':'not_found'});return
   suffix=route.request.url.split('/account/api/inbox',1)[1].split('?')[0]
   if suffix=='/settings':
    if route.request.method=='POST':
     body=route.request.post_data_json;writes.append((suffix,body));preferences.update(body)
    route.fulfill(json=preferences);return
   if route.request.method=='POST':
    body=route.request.post_data_json;writes.append((suffix,body))
    for item in notices:
     if body.get('all') or body.get('id')==item['id']:
      if suffix in ('/read','/dismiss'):item['read_at']=now
      if suffix in ('/presented','/dismiss'):item['presented_at']=now
      if suffix=='/dismiss':item['dismissed_at']=now
    route.fulfill(json={'updated':True});return
   route.fulfill(json={'notifications':notices,'unread_count':sum(not n['read_at'] and not n['dismissed_at'] for n in notices),'next_before':None})
  page.route('**/account/api/inbox**',inbox)
  page.goto(origin+'/app');expect(page.get_by_role('heading',name='Войти',exact=True)).to_be_visible();assert not requests
  login(page,origin);bell=page.get_by_role('button',name='Уведомления, новых: 1',exact=True);expect(bell).to_be_visible();assert bell.bounding_box()['height']>=44
  bell.click();expect(page.get_by_role('heading',name='Уведомления',exact=True)).to_be_visible();expect(page.locator('dialog')).to_have_count(0)
  expect(page.get_by_text('Новости ULADIM',exact=True)).to_be_visible();page.screenshot(path=str(OUT/'phone-inbox-new.png'),full_page=True);checks.append('logged_out_no_inbox_calls_and_header_bell_opens_dedicated_page')
  page.get_by_role('button',name='Новости ULADIM',exact=True).click();expect(page.locator('.inbox-detail')).to_be_visible();expect(page.locator('.inbox-detail')).to_contain_text('Ваши планы всегда под рукой.')
  expect(page.get_by_role('button',name='Уведомления',exact=True)).to_be_visible();assert any(path=='/read' for path,_ in writes)
  page.get_by_role('button',name='Назад к уведомлениям',exact=True).click();page.get_by_role('button',name='Прочитанные',exact=True).click();expect(page.get_by_role('button',name='Новости ULADIM',exact=True)).to_be_visible();checks.append('detail_marks_read_after_server_confirmation_and_read_filter')
  page.get_by_role('button',name='Новости ULADIM',exact=True).click();page.get_by_role('button',name='Убрать в историю',exact=True).click();page.get_by_role('button',name='Вся история',exact=True).click();expect(page.get_by_role('button',name='Новости ULADIM',exact=True)).to_be_visible();checks.append('dismiss_keeps_server_history')
  mode['state']='offline';page.get_by_role('button',name='Обновить',exact=True).click();expect(page.locator('.inbox-feedback')).to_contain_text('Не удалось обновить');expect(page.locator('.inbox-list')).to_contain_text('Новости ULADIM');mode['state']='ok';page.get_by_role('button',name='Повторить',exact=True).click();expect(page.locator('.inbox-feedback')).to_be_empty();checks.append('retry_preserves_last_confirmed_history')
  # A new message arriving during an editor must wait until the safe screen returns.
  startup={**notices[0], 'id':str(uuid.uuid4()),'title':'Начните день спокойно','presentation':'fullscreen','read_at':0,'dismissed_at':0,'presented_at':0};notices.insert(0,startup)
  page.evaluate("referenceNavigate('tasks')");page.get_by_role('button',name='Добавить',exact=True).click();page.get_by_label('Название задачи',exact=True).fill('Не потерять черновик');page.evaluate('inboxCenter().refresh()');page.wait_for_timeout(300)
  expect(page.locator('.inbox-startup-fullscreen')).to_have_count(0);expect(page.get_by_label('Название задачи',exact=True)).to_have_value('Не потерять черновик');checks.append('startup_never_interrupts_editor_draft')
  page.get_by_role('dialog').get_by_role('button',name='Закрыть',exact=True).click();page.evaluate("referenceNavigate('today')");expect(page.locator('.inbox-startup-fullscreen')).to_be_visible();expect(page.locator('.inbox-startup-fullscreen')).to_contain_text(startup['title']);assert page.locator('.inbox-startup-fullscreen').evaluate('e=>Math.abs(e.getBoundingClientRect().width-innerWidth)<1'),page.locator('.inbox-startup-fullscreen').evaluate('e=>({box:e.getBoundingClientRect().toJSON(),width:getComputedStyle(e).width,maxWidth:getComputedStyle(e).maxWidth})');page.screenshot(path=str(OUT/'phone-startup-fullscreen.png'),full_page=False)
  page.locator('.inbox-startup-fullscreen').get_by_role('button',name='Продолжить',exact=True).click();expect(page.locator('.inbox-startup-fullscreen')).to_have_count(0);assert startup['presented_at'] and startup['dismissed_at'];page.reload();expect(page.get_by_role('heading',name='Сегодня',exact=True)).to_be_visible();expect(page.locator('.inbox-startup-fullscreen')).to_have_count(0);checks.append('startup_fullscreen_dismiss_persisted_and_not_repeated_on_reload')
  banner={**startup,'id':str(uuid.uuid4()),'title':'Новый формат подсказок','presentation':'banner','read_at':0,'dismissed_at':0,'presented_at':0};notices.insert(0,banner);page.evaluate('inboxCenter().refresh()');expect(page.locator('.inbox-startup-banner')).to_be_visible();page.screenshot(path=str(OUT/'phone-startup-banner.png'),full_page=True);page.locator('.inbox-startup-banner').get_by_role('button',name='Закрыть сообщение',exact=True).click();checks.append('startup_banner_compact_dismissible')
  page.get_by_role('button',name='Уведомления',exact=True).click()
  for width in [320,834,1440]:
   page.set_viewport_size({'width':width,'height':900});page.screenshot(path=str(OUT/f'inbox-{width}.png'),full_page=True);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth,wide:[...document.querySelectorAll("*")].filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>({tag:e.tagName,cls:e.className,right:e.getBoundingClientRect().right})).slice(0,12)})')
  checks.append('phone_tablet_desktop_no_horizontal_overflow')
  page.set_viewport_size({'width':320,'height':900});page.evaluate("document.documentElement.style.fontSize='24px'");assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(OUT/'inbox-320-large-text.png'),full_page=True);page.evaluate("document.documentElement.style.fontSize=''");checks.append('narrow_screen_large_text_filters_remain_readable')
  page.evaluate("referenceNavigate('account','notifications')");budget=page.locator('.inbox-budget-settings');expect(budget).to_contain_text('Это не системные push-уведомления.');toggle=budget.get_by_label('Сообщать о порогах бюджета',exact=True);expect(toggle).not_to_be_checked();toggle.check();budget.get_by_label('Когда сообщать',exact=True).select_option('5');budget.get_by_role('button',name='Сохранить',exact=True).click();expect(budget).to_contain_text('Настройки сохранены');assert preferences['budget_enabled'] and preferences['budget_thresholds']==list(range(5,101,5));page.screenshot(path=str(OUT/'budget-history-settings.png'),full_page=True);checks.append('budget_history_optin_five_percent_preset_and_truthful_no_push_copy')
  page.evaluate("referenceNavigate('account','signout')");page.locator('main').get_by_role('button',name='Выйти',exact=True).click();expect(page.get_by_role('heading',name='Войти',exact=True)).to_be_visible();count=len(requests);page.evaluate('inboxCenter().refresh()');page.wait_for_timeout(100);assert len(requests)==count;assert page.evaluate('inboxCenter().snapshot().notifications.length')==0;checks.append('signout_clears_private_history_and_stops_protected_requests')
  mode['state']='404';login(page,origin);page.wait_for_timeout(250);expect(page.locator('#alerts')).to_be_empty();page.get_by_role('button',name='Уведомления',exact=True).click();expect(page.locator('.inbox-feedback')).to_contain_text('История уведомлений пока недоступна.');assert page.locator('.inbox-row').count()==0;mode['state']='ok';page.get_by_role('button',name='Повторить',exact=True).click();expect(page.locator('.inbox-feedback')).to_be_empty();checks.append('old_server_404_quiet_unavailable_no_fake_history_and_explicit_retry')
  page.evaluate("referenceNavigate('account')");expect(page.get_by_role('button',name='ULADIM Control',exact=True)).to_have_count(0);checks.append('ordinary_profile_has_no_control_entry')
  def own_staff_session(route):
   response=route.fetch();value=response.json();value['control_available']=True;route.fulfill(response=response,json=value)
  page.route('**/account/api/session',own_staff_session);page.reload();expect(page.get_by_role('heading',name='Сегодня',exact=True)).to_be_visible();page.evaluate("referenceNavigate('account')");expect(page.get_by_role('button',name='ULADIM Control',exact=True)).to_be_visible()
  handoffs=[]
  def handoff(route):
   handoffs.append(route.request.post_data_json);route.fulfill(json={'control_url':origin.replace('localhost','control.localhost')+'/admit','ticket':'T'*43,'expires_in':60})
  page.route('**/account/api/control/access',handoff);page.evaluate("() => {HTMLFormElement.prototype.submit=function(){window.__controlHandoff={method:this.method,action:this.action,fields:Array.from(this.elements,e=>[e.name,e.value])};};}");page.get_by_role('button',name='ULADIM Control',exact=True).click();page.wait_for_function('window.__controlHandoff');posted=page.evaluate('window.__controlHandoff');assert posted['method']=='post' and posted['action'].endswith('/admit') and posted['fields']==[['ticket','T'*43]] and handoffs==[{}];checks.append('own_staff_metadata_entry_posts_one_use_ticket_in_form_body')
  assert not errors,errors
  context.close();browser.close()
 summary={'checks':checks,'transport':'Actual local app and WSGI auth; synthetic inbox responses only. No real notification recipients.'};(OUT/'checks.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
