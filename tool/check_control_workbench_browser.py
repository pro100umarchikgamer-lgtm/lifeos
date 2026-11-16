"""Disposable Control UX journeys. All staff API writes stay in fixture handlers."""
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import json, os, time, uuid
from playwright.sync_api import sync_playwright, expect
from tool.control_browser_fixture import control_fixture, admit_control, choose_control_section

OUT = Path(os.environ.get('ULADIM_CONTROL_EVIDENCE', '/tmp/control-workbench-evidence'))

def main():
 OUT.mkdir(parents=True, exist_ok=True)
 writes, reads, errors, checks = [], [], [], []
 now = int(time.time())
 original, author, staff_id, ticket = (str(uuid.uuid4()) for _ in range(4))
 perms = ['dashboard.read','users.read','users.recover','records.recover','support.read','support.reply','staff.manage','users.moderate','announcements.manage','flags.manage','audit.read','plans.grant']
 users = [{ 'id': original, 'email':'original@example.test', 'display_name':'Наталья <script>', 'verified':1, 'created_at':now-500,'disabled_until':0,'active_devices':2,'last_seen_at':now-60 }, {'id':author,'email':'contact@example.test','display_name':None,'verified':1,'created_at':now-400,'disabled_until':0,'active_devices':1}]
 member = {'id':str(uuid.uuid4()),'email':'support@example.test','roles':['support'],'active':1,'revision':1,'base_permissions':['users.read','users.recover','records.recover','support.read','support.reply'],'permissions':['users.read','users.recover','records.recover','support.read','support.reply'],'denied_permissions':[]}
 roles = [{'key':'owner','rank':100,'permissions':perms}, {'key':'admin','rank':80,'permissions':perms}, {'key':'support','rank':20,'permissions':member['base_permissions']}, {'key':'moderator','rank':30,'permissions':['users.read','users.moderate','support.read','support.reply']}, {'key':'auditor','rank':10,'permissions':['dashboard.read','audit.read']}]
 cases, drafts = [], []
 fail_next, held = {}, {}
 detail = {}
 with control_fixture() as (_,origin,control,_,actor,wid,launch), sync_playwright() as p:
  browser=p.chromium.launch(**launch)
  context=browser.new_context(viewport={'width':1440,'height':1000},service_workers='block',reduced_motion='reduce')
  page=context.new_page();page.on('pageerror',lambda err: errors.append(str(err)));admit_control(page,origin,control)
  def api(route):
   nonlocal detail
   path=urlsplit(route.request.url).path.removeprefix('/control/api/');q=parse_qs(urlsplit(route.request.url).query);body=route.request.post_data_json if route.request.method=='POST' else None
   if body is not None: writes.append((path,body))
   if path in fail_next:
    code=fail_next.pop(path);route.fulfill(status=409,json={'error':code});return
   else: reads.append((path,q))
   if path=='session': data={'csrf':'synthetic','staff_id':staff_id,'user_id':actor['id'],'roles':['owner'],'permissions':perms,'base_permissions':perms,'denied_permissions':[]}
   elif path=='dashboard': data={'accounts':3}
   elif path=='users':
    result=users[1:] if 'before' in q else users[:1]
    if q.get('search'):result=[u for u in users if q['search'][0].casefold() in (u['email']+' '+(u.get('display_name') or '')+' '+u['id']).casefold()]
    data={'users':result,'next_before':None if 'before' in q or q.get('search') else str(now)+':'+original,'limit':50}
   elif path=='user': data={'user':next(u for u in users if u['id']==q['id'][0]),'devices':[],'entitlements':{'tier':'Free','source':'free','valid_until':None,'grants':[],'holds':{}}}
   elif path=='permissions': data={'roles':roles,'permissions':[{'key':v} for v in perms],'assignable_roles':['admin','support','moderator','auditor']}
   elif path=='staff': data={'staff':[member]}
   elif path=='staff/update': member.update(body);data={'updated':True}
   elif path=='staff/invite':data={'invitation':'synthetic-one-use-invitation'}
   elif path=='record-recovery/approve':
    request=next(item for item in detail['requests'] if item['id']==body['request_id']);request.update(state='approved',revision=request['revision']+1);data={'request':request}
   elif path=='flags':data={'compact_onboarding':{'enabled':True,'rollout':0,'revision':2},'chart_styles':{'enabled':False,'rollout':25,'revision':1}}
   elif path=='support':data={'tickets':[{'id':ticket,'subject':'Доступ к прежнему аккаунту','category':'account','state':'open','priority':'normal','user_id':author}]}
   elif path=='thread': data={'ticket':{'id':q['id'][0],'subject':'Доступ к прежнему аккаунту','category':'account','state':'open','priority':'normal','user_id':author},'messages':[]}
   elif path=='recovery-cases' and body:
    case={'id':str(uuid.uuid4()),**body,'state':'waiting_owner','revision':1,'created_at':now,'expires_at':now+86400};cases.append(case)
    detail={'case':case,'target':users[0],'source':{'kind':'ticket' if body.get('ticket_id') else 'manual','ticket_id':body.get('ticket_id'),'author_user_id':author,'same_account':False},'requests':[],'owner_url':'/app?settings=recovery&case='+case['id']};data=detail
   elif path=='recovery-cases': data={'cases':cases,'next_before':None}
   elif path=='recovery-case': data=detail
   elif path=='recovery-cases/update': detail['case']['revision']+=1;data={**detail,'recovery_requested':True}
   elif path=='announcements' and body is None: data={'announcements':drafts}
   elif path=='announcements/preview':data={**body,'recipient_count':0 if body['audience']=='newcomers' else len(body.get('user_ids',[]))}
   elif path=='announcements':
    data={**body,'id':str(uuid.uuid4()),'state':'draft','revision':1,'recipient_count':0,'starts_at':body.get('starts_at',now),'expires_at':253402300799 if body.get('no_expiry') else now+86400};drafts.append(data)
   else:data={}
   if held.get('path')==path:
    held.update(route=route,data=data);return
   route.fulfill(json=data)
  page.route('**/control/api/**',api);page.goto(control+'/');expect(page.get_by_role('heading',name='Обзор сервиса',exact=True)).to_be_visible()
  choose_control_section(page,'users');expect(page.get_by_text('original@example.test',exact=True)).to_be_visible(timeout=3000)
  assert any(path=='users' and not q.get('search') for path,q in reads)
  assert page.locator('main script').count()==0
  page.get_by_role('button',name='Следующая страница',exact=True).click();expect(page.get_by_text('contact@example.test',exact=True)).to_be_visible();checks.append('directory_loads_by_default_and_pages_without_html_injection')
  page.get_by_label('Имя, почта или ID',exact=True).fill('Наталья');page.get_by_role('button',name='Найти',exact=True).click();expect(page.get_by_text('original@example.test',exact=True)).to_be_visible();expect(page.get_by_text('contact@example.test',exact=True)).to_have_count(0);checks.append('unicode_search_replaces_previous_results')
  choose_control_section(page,'support');page.get_by_role('button',name='Открыть обращение',exact=True).click();page.get_by_role('button',name='Создать дело восстановления',exact=True).click()
  expect(page.get_by_role('button',name='Создать дело',exact=True)).to_be_disabled();page.get_by_label('Имя, почта или ID',exact=True).fill('original');page.get_by_role('button',name='Найти',exact=True).click();page.get_by_role('button',name='Выбрать аккаунт',exact=True).click()
  page.get_by_label('Причина для журнала аудита',exact=True).fill('Контакт из другого аккаунта; выбран оригинал');fail_next['recovery-cases']='revision_conflict';page.get_by_role('button',name='Создать дело',exact=True).click();expect(page.locator('main')).to_contain_text('Данные изменились');expect(page.get_by_label('Причина для журнала аудита',exact=True)).to_have_value('Контакт из другого аккаунта; выбран оригинал');expect(page.get_by_role('button',name='Создать дело',exact=True)).to_be_enabled();held['path']='recovery-cases';page.get_by_role('button',name='Создать дело',exact=True).click();expect(page.get_by_role('button',name='Создать дело',exact=True)).to_be_disabled();held.pop('path');held['route'].fulfill(json=held['data']);checks.append('failed_and_pending_case_writes_preserve_reason_and_disable_duplicates');expect(page.get_by_role('heading',name='Дело восстановления',exact=True)).to_be_visible()
  sent=next(body for path,body in writes if path=='recovery-cases');assert sent['target_user_id']==original and sent['ticket_id']==ticket and sent['target_user_id']!=author
  expect(page.locator('main')).to_contain_text('Обращение отправлено из другого аккаунта');page.set_viewport_size({'width':390,'height':1000});page.screenshot(path=str(OUT/'cross-account-case-390.png'),full_page=True);checks.append('cross_account_ticket_requires_explicit_original_target')
  page.get_by_role('button',name='Отправить письмо на исходную почту',exact=True).click();page.get_by_label('Причина для журнала аудита',exact=True).fill('Исходный адрес подтверждён');page.get_by_role('button',name='Отправить письмо',exact=True).click();expect(page.locator('main')).to_contain_text('Письмо запрошено');assert any(path=='recovery-cases/update' and body['action']=='send_reset' for path,body in writes);checks.append('case_reset_is_explicit_reasoned_action')
  detail['case']['kind']='records';detail['requests']=[{'id':str(uuid.uuid4()),'user_id':original,'workspace_id':wid,'record_id':str(uuid.uuid4()),'kind':'note','state':'pending','revision':2,'consent_hash':'synthetic-consent','expires_at':now+86400}];choose_control_section(page,'recovery-cases');page.get_by_role('button',name='Открыть дело',exact=True).click();page.get_by_role('button',name='Рассмотреть запрос',exact=True).click();page.get_by_label('Причина для журнала аудита',exact=True).fill('Согласие исходного владельца проверено');page.get_by_role('button',name='Одобрить запрос',exact=True).click();expect(page.locator('main')).to_contain_text('Запрос одобрен');approval=next(body for path,body in writes if path=='record-recovery/approve');assert approval['consent_hash']=='synthetic-consent' and approval['revision']==2;assert not any(path.endswith('/commit') for path,body in writes);checks.append('case_approval_uses_existing_revision_and_owner_consent_without_staff_restore')
  choose_control_section(page,'staff');page.get_by_role('button',name='Изменить права',exact=True).click();page.get_by_label('Ответы на обращения',exact=True).uncheck();page.screenshot(path=str(OUT/'staff-restrictions-390.png'),full_page=True);page.get_by_label('Причина для журнала аудита',exact=True).fill('Только чтение обращений');page.get_by_role('button',name='Сохранить и отозвать сессии',exact=True).click();assert any(path=='staff/update' and body['denied_permissions']==['support.reply'] for path,body in writes);checks.append('staff_editor_submits_deny_only_restrictions')
  page.get_by_label('Почта получателя',exact=True).fill('invited@example.test');page.get_by_label('Ответы на обращения',exact=True).uncheck();page.get_by_label('Причина для журнала аудита',exact=True).fill('Приглашение с ограничением ответа');assert page.locator('select[name=role] option[value=owner]').count()==0;page.get_by_role('button',name='Создать приглашение',exact=True).click();expect(page.get_by_label('Одноразовое приглашение',exact=True)).to_have_value('synthetic-one-use-invitation');assert any(path=='staff/invite' and body['denied_permissions']==['support.reply'] and body['roles']==['support'] for path,body in writes);checks.append('invitation_carries_restrictions_without_owner_role')
  choose_control_section(page,'announcements');page.get_by_role('button',name='Новое сообщение',exact=True).click();page.get_by_label('Заголовок',exact=True).fill('Добро пожаловать');page.get_by_label('Текст сообщения',exact=True).fill('Добро пожаловать после регистрации');page.get_by_label('Новые пользователи после регистрации',exact=True).check();expect(page.get_by_label('ID аккаунтов — по одному на строку',exact=True)).to_be_hidden();page.get_by_text('Время показа и срок',exact=True).click();page.get_by_label('Без даты завершения',exact=True).check();page.get_by_label('Причина для журнала аудита',exact=True).fill('Новое приветствие');page.get_by_role('button',name='Сохранить черновик',exact=True).click();expect(page.get_by_role('heading',name='Проверьте публикацию',exact=True)).to_be_visible();assert drafts[-1]['audience']=='newcomers' and drafts[-1]['user_ids']==[] and drafts[-1]['no_expiry'];expect(page.locator('main')).to_contain_text('Будущие пользователи');page.screenshot(path=str(OUT/'newcomer-evergreen-review-390.png'),full_page=True);checks.append('newcomers_need_no_manual_ids_and_allow_evergreen')
  choose_control_section(page,'users');expect(page.get_by_text('original@example.test',exact=True)).to_be_visible();page.get_by_label('Имя, почта или ID',exact=True).fill('missing-person');page.get_by_role('button',name='Найти',exact=True).click();expect(page.locator('main')).to_contain_text('По этим условиям аккаунтов нет');page.get_by_label('Имя, почта или ID',exact=True).fill('');page.get_by_role('button',name='Найти',exact=True).click();expect(page.get_by_text('original@example.test',exact=True)).to_be_visible();checks.append('empty_search_can_be_cleared_to_restore_directory')
  for width in (320,390,820):
   page.set_viewport_size({'width':width,'height':1000});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(OUT/f'directory-{width}.png'),full_page=True)
  choose_control_section(page,'staff');expect(page.get_by_role('heading',name='Команда Control',exact=True)).to_be_visible();page.get_by_role('button',name='Роль',exact=True).click();expect(page.get_by_role('listbox',name='Роль',exact=True)).to_be_visible();page.keyboard.press('End');page.keyboard.press('Enter');expect(page.get_by_role('listbox',name='Роль',exact=True)).to_be_hidden();checks.append('bounded_anchored_choices_work_by_keyboard')
  page.evaluate("document.documentElement.style.fontSize='24px'");assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');checks.append('small_viewports_and_large_text_do_not_overflow')
  choose_control_section(page,'flags');expect(page.get_by_text('Изменение не получает никто',exact=True)).to_have_count(2);expect(page.get_by_text('Изменение ещё не настроено',exact=True)).to_be_visible();page.get_by_role('button',name='Настроить',exact=True).first.click();page.get_by_text('Охват и причина изменения',exact=True).click();expect(page.get_by_label('Охват: 0–100%',exact=True)).to_have_value('0');checks.append('saved_zero_percent_flag_remains_zero_with_honest_effect')
  assert not errors,errors;browser.close()
 result={'checks':checks,'writes':'synthetic fixture API only','screenshots':str(OUT)};(OUT/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
