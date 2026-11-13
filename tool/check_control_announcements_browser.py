"""Control composer rendered from real local assets with synthetic staff API.
No staff credentials, actual staff access, broadcasts, or real recipients.
"""
from pathlib import Path
from urllib.parse import urlsplit
import json, os, time, uuid
from playwright.sync_api import sync_playwright, expect
from tool.check_web_platform import fixture

OUT=Path('web_evidence/inbox')

def main():
 OUT.mkdir(parents=True,exist_ok=True);writes=[];checks=[];drafts=[];permissions=['dashboard.read','users.read','applications.manage','staff.manage','support.read','audit.read','flags.manage','announcements.manage','users.recover'];self_id=str(uuid.uuid4());count={'value':12}
 with fixture() as (origin,_,actor,wid),sync_playwright() as p:
  browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}));context=browser.new_context(viewport={'width':1440,'height':1024},service_workers='block',reduced_motion='reduce');page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
  # Fixture-only root response: production admission is separately enforced by backend tests.
  control=origin.replace('localhost','control.localhost')
  def document(route):route.fulfill(body=Path('backend/webassets/index.html').read_text().replace('__SURFACE__','control'),content_type='text/html')
  page.route(control+'/',document)
  def api(route):
   path=urlsplit(route.request.url).path.removeprefix('/control/api/');body=route.request.post_data_json if route.request.method=='POST' else None
   if body is not None:writes.append((path,body))
   if path=='session':data={'csrf':'fixture-csrf','staff_id':'fixture-staff','user_id':self_id,'roles':['admin'],'permissions':permissions}
   elif path=='user':data={'user':{'id':actor['id'],'email':'web@example.test','verified':1,'disabled_until':0},'devices':[],'entitlements':{'tier':'Free','source':'free','valid_until':None,'grants':[],'holds':{}}}
   elif path=='user/recovery':data={'recovery_requested':True}
   elif path=='dashboard':data={'accounts':12,'support_pending':2}
   elif path=='announcements' and body is None:data={'announcements':drafts}
   elif path=='announcements/preview':data={**body,'recipient_count':count['value'] if body['audience']=='all' else len(body['user_ids'])}
   elif path=='announcements':
    data={**body,'id':str(uuid.uuid4()),'revision':1,'state':'draft','recipient_count':count['value'] if body['audience']=='all' else len(body['user_ids'])};drafts.insert(0,data)
   elif path=='announcements/publish':
    data=next(d for d in drafts if d['id']==body['id']);data.update(state='published',revision=2,recipient_count=count['value'] if data['audience']=='all' else len(data['user_ids']))
   else:data={}
   route.fulfill(json=data)
  page.route('**/control/api/**',api);page.goto(control+'/');expect(page.get_by_role('heading',name='Обзор сервиса',exact=True)).to_be_visible()
  nav=page.get_by_label('Раздел Control',exact=True);assert nav.locator('option').count()==8;nav.select_option('announcements');expect(page.get_by_role('heading',name='Уведомления',exact=True)).to_be_visible();page.get_by_role('button',name='Новое сообщение',exact=True).click()
  expect(page.get_by_label('Только мне — проверка',exact=True)).to_be_checked();expect(page.get_by_label('В центре уведомлений',exact=True)).to_be_checked();checks.append('capability_navigation_preserves_existing_sections_and_defaults_self')
  page.get_by_label('Заголовок',exact=True).fill('Обновления ULADIM');page.get_by_label('Текст сообщения',exact=True).fill('Уведомления и напоминания теперь в одном месте.\nЛичные записи остаются вашими.');page.get_by_label('Причина для журнала аудита',exact=True).fill('Проверка сообщения для собственного аккаунта')
  page.get_by_label('Баннер при входе',exact=True).check();expect(page.locator('.control-announcement-preview')).to_have_attribute('data-format','banner');page.screenshot(path=str(OUT/'control-preview-banner.png'),full_page=True)
  page.get_by_label('Полный экран при входе',exact=True).check();expect(page.locator('.control-announcement-preview')).to_have_attribute('data-format','fullscreen');page.screenshot(path=str(OUT/'control-preview-fullscreen.png'),full_page=True)
  page.get_by_label('В центре уведомлений',exact=True).check();page.get_by_role('button',name='Сохранить черновик',exact=True).click();expect(page.get_by_role('heading',name='Проверьте публикацию',exact=True)).to_be_visible();assert drafts[0]['audience']=='users' and drafts[0]['user_ids']==[self_id];assert not any(path=='announcements/publish' for path,_ in writes);checks.append('three_plain_text_previews_and_self_draft_no_automatic_publish')
  page.screenshot(path=str(OUT/'control-self-review.png'),full_page=True);page.get_by_role('button',name='Назад к черновикам',exact=True).click();page.get_by_role('button',name='Новое сообщение',exact=True).click()
  page.get_by_label('Заголовок',exact=True).fill('Плановое обновление');page.get_by_label('Текст сообщения',exact=True).fill('Сообщение для проверки подтверждения аудитории.');page.get_by_label('Причина для журнала аудита',exact=True).fill('Проверка формы; реальной рассылки нет');page.get_by_label('Все подтверждённые аккаунты',exact=True).check();page.get_by_role('button',name='Сохранить черновик',exact=True).click();expect(page.get_by_role('heading',name='Проверьте публикацию',exact=True)).to_be_visible();publish=page.get_by_role('button',name='Опубликовать',exact=True);expect(publish).to_be_disabled();expect(page.locator('.control-publish-summary')).to_contain_text('12');page.screenshot(path=str(OUT/'control-broadcast-review.png'),full_page=True);checks.append('broadcast_requires_concrete_summary_and_typed_confirmation')
  # Validate the guarded write using the synthetic API only.
  count['value']=13;page.get_by_label('Введите ВСЕМ 12',exact=True).fill('ВСЕМ 12');expect(publish).to_be_enabled();publish.click();expect(page.get_by_label('Введите ВСЕМ 13',exact=True)).to_be_visible();expect(page.get_by_role('button',name='Опубликовать',exact=True)).to_be_disabled();assert not any(path=='announcements/publish' for path,_ in writes);page.get_by_label('Введите ВСЕМ 13',exact=True).fill('ВСЕМ 13');page.get_by_role('button',name='Опубликовать',exact=True).click();checks.append('audience_count_change_requires_new_confirmation');expect(page.get_by_text('Опубликовано',exact=True)).to_be_visible();assert any(path=='announcements/publish' for path,_ in writes);checks.append('explicit_publish_in_synthetic_fixture_only')
  nav=page.get_by_label('Раздел Control',exact=True);nav.select_option('announcements');page.get_by_role('button',name='Новое сообщение',exact=True).click();page.get_by_label('Заголовок',exact=True).fill('<img src=x onerror=alert(1)>');assert page.locator('.control-announcement-preview img').count()==0;checks.append('plain_text_preview_never_injects_html');page.get_by_label('Заголовок',exact=True).fill('Новости ULADIM');page.get_by_label('Текст сообщения',exact=True).fill('Проверяйте сообщения и напоминания в удобное время.')
  for width in [390,834,1440]:
   page.set_viewport_size({'width':width,'height':1000});page.screenshot(path=str(OUT/f'control-composer-{width}.png'),full_page=True);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  checks.append('responsive_control_composer_without_overflow');page.evaluate("id=>staffUser(id)",actor['id']);page.get_by_role('button',name='Отправить письмо восстановления',exact=True).click();expect(page.locator('main')).to_contain_text('защита MFA сохраняется');page.get_by_label('Причина для журнала аудита',exact=True).fill('Обращение владельца аккаунта');page.get_by_role('button',name='Отправить письмо',exact=True).click();expect(page.get_by_role('heading',name='Письмо восстановления запрошено',exact=True)).to_be_visible();assert any(path=='user/recovery' and body['user_id']==actor['id'] for path,body in writes);checks.append('staff_recovery_requires_reason_and_owner_completes_email_flow');page.get_by_label('Раздел Control',exact=True).select_option('dashboard');expect(page.get_by_role('heading',name='Обзор сервиса',exact=True)).to_be_visible();expect(page.get_by_label('Раздел Control',exact=True)).to_have_count(1);checks.append('return_to_control_overview_keeps_one_navigation');permissions.remove('announcements.manage');page.reload();expect(page.get_by_role('heading',name='Обзор сервиса',exact=True)).to_be_visible();assert page.get_by_label('Раздел Control',exact=True).locator('option[value=announcements]').count()==0;expect(page.locator('.control-overview-links').get_by_role('button',name='Уведомления',exact=False)).to_have_count(0);checks.append('notification_management_hidden_without_server_permission');assert not errors,errors;context.close();browser.close()
 summary={'checks':checks,'transport':'Synthetic staff API and locally rendered Control assets. No real staff session or real recipients.'};(OUT/'control-checks.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
