"""Clarity iteration: real disposable backend, actual browser writes and visual evidence."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright, expect
from tool.check_web_platform import fixture, login
OUT=Path('web_evidence/clarity');OUT.mkdir(parents=True,exist_ok=True)
with fixture() as (origin,backend,actor,wid),sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':1000},locale='ru-RU',timezone_id='Europe/Moscow',reduced_motion='reduce')
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(origin+'/');expect(page.locator('.product-hero')).to_be_visible();page.screenshot(path=str(OUT/'public-desktop-light.png'),full_page=True)
    login(page,origin)
    page.get_by_label('Что нужно сделать?',exact=True).fill('Задача из быстрого ввода')
    page.get_by_role('button',name='Добавить задачу',exact=True).click()
    expect(page.get_by_text('Задача из быстрого ввода',exact=True)).to_be_visible()
    assert len([r for r in backend.pull(actor,wid,0)['records'] if r['kind']=='task' and r['data']['title']=='Задача из быстрого ввода'])==1
    checks=['quick_task_persisted_once'];geometry=[]
    def lose_response(route):
        route.fetch();route.fulfill(status=502,content_type='application/json',body='{"error":"server_error"}')
    page.route('**/account/api/sync',lose_response)
    page.get_by_label('Что нужно сделать?',exact=True).fill('Проверка потерянного ответа')
    page.get_by_role('button',name='Добавить задачу',exact=True).click()
    expect(page.locator('.quick-capture input')).to_have_attribute('readonly','')
    expect(page.locator('.quick-capture button')).to_be_enabled()
    page.unroute('**/account/api/sync',lose_response)
    page.locator('.quick-capture button').click()
    expect(page.get_by_text('Проверка потерянного ответа',exact=True)).to_be_visible()
    assert len([r for r in backend.pull(actor,wid,0)['records'] if r['kind']=='task' and r['data']['title']=='Проверка потерянного ответа'])==1
    checks.append('lost_response_retry_no_duplicate')
    page.route('**/account/api/spaces',lambda route:route.fulfill(status=503,content_type='application/json',body='{"error":"service_unavailable"}'),times=1)
    page.get_by_label('Что нужно сделать?',exact=True).fill('Сохранено перед ошибкой обновления')
    page.get_by_role('button',name='Добавить задачу',exact=True).click()
    expect(page.locator('.quick-capture input')).to_have_attribute('readonly','')
    expect(page.locator('.quick-capture button')).to_be_enabled()
    page.locator('.quick-capture button').click()
    expect(page.get_by_text('Сохранено перед ошибкой обновления',exact=True)).to_be_visible()
    assert len([r for r in backend.pull(actor,wid,0)['records'] if r['kind']=='task' and r['data']['title']=='Сохранено перед ошибкой обновления'])==1
    checks.append('accepted_save_failed_refresh_retry_no_duplicate')
    expect(page.locator('#alerts .toast')).to_have_count(0,timeout=6000)
    for theme in ('light','dark'):
        page.evaluate('v=>{state.theme=v;preferences()}',theme)
        for width in (320,375,390,430,768,1024,1280,1440):
            page.set_viewport_size({'width':width,'height':900})
            for tab,label in [('today','Сегодня'),('money','Финансы'),('account','Профиль')]:
                page.locator('.nav').get_by_role('button',name=label,exact=True).click()
                expect(page.locator('h1')).to_be_visible()
                if tab=='account':page.locator('[name=settings-section]').select_option('profile') if width<760 else page.locator('.settings-navigation').get_by_role('button',name='Профиль',exact=True).click()
                overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth')
                geometry.append({'theme':theme,'width':width,'tab':tab,'overflow':overflow})
                page.screenshot(path=str(OUT/f'{tab}-{width}-{theme}.png'))
                assert not overflow,(theme,width,tab,'page overflow')
                if tab=='account':
                    expect(page.locator('[name=settings-section]' if width<760 else '.settings-navigation')).to_be_visible()
                    expect(page.get_by_role('heading',name='Поддержка',exact=True)).to_have_count(0)
                    page.locator('[name=settings-section]').select_option('appearance') if width<760 else page.locator('.settings-navigation').get_by_role('button',name='Оформление',exact=True).click()
                    expect(page.get_by_label('Язык',exact=True)).to_be_visible()
        checks.append(theme+'_responsive_8_widths')
    page.goto(origin+'/');expect(page.locator('.product-hero')).to_be_visible()
    for theme in ('light','dark'):
        page.evaluate('v=>document.body.dataset.theme=v',theme)
        for width in (375,768,1440):
            page.set_viewport_size({'width':width,'height':900})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(OUT/f'public-{width}-{theme}.png'))
    assert not errors,errors
    (OUT/'results.json').write_text(json.dumps({'checks':checks,'geometry':geometry,'page_errors':errors},ensure_ascii=False,indent=2))
    browser.close()
print('Clarity UX: quick-task persistence, settings separation, 48 viewport/theme checks passed')
