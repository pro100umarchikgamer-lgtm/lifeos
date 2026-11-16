"""Shared editor/date regressions; disposable production WSGI, never live data.

The content-box condition is a native-sizing surrogate, not a physical iOS test.
"""
import argparse
import json
import os
from pathlib import Path
from playwright.sync_api import expect, sync_playwright
from tool.check_finance_filter_fit import source_styles
from tool.check_web_platform import fixture, login, PASSWORD
from tool.web_browser_navigation import open_tab, open_finance_section


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', default='all')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.environ.get('ULADIM_CHROMIUM'))
        def case(name, run):
            context = browser.new_context(viewport={'width':390,'height':844}, locale='ru-RU', timezone_id='Europe/Moscow', service_workers='block', reduced_motion='reduce')
            context.route('**/assets/design.css', lambda route: route.fulfill(status=200, content_type='text/css', body=source_styles()+('\ninput[type=date],input[type=datetime-local]{box-sizing:content-box!important}' if name=='dates' else '')))
            page = context.new_page(); page.set_default_timeout(2500)
            errors=[]; page.on('pageerror', lambda error: errors.append(str(error)))
            try:
                if name not in ('setup-route-owner-login','setup-route-mfa'):login(page, origin)
                run(page)
                assert not errors, errors
                results.append({'case':name,'status':'passed'})
            except Exception as error:
                page.screenshot(path=str(args.output/(name+'-failure.jpg')),type='jpeg',quality=65)
                results.append({'case':name,'status':'failed','error':str(error),'page_errors':errors})
            finally: context.close()
        def task(page):
            page.locator('.intro').get_by_role('button',name='Добавить задачу',exact=True).click()
            editor=page.get_by_role('dialog'); expect(editor.get_by_label('Дата задачи',exact=True)).to_be_visible(); return editor
        def dates(page):
            page.set_viewport_size({'width':820,'height':1000});open_tab(page,'Финансы');open_finance_section(page,'ledger')
            page.locator('.finance-filter-panel>summary').click()
            page.evaluate("state.palette='pistachio';preferences()")
            # Keep the adverse condition after any fix; do not make the test green by removing it.
            for name in ['finance-from','finance-to']:page.locator('[name='+name+']').fill('2026-11-10')
            geometry=page.locator('.finance-filters input[type=date]').evaluate_all('''nodes=>nodes.map(e=>{const r=e.getBoundingClientRect(),p=e.parentElement.getBoundingClientRect();return {name:e.name,width:r.width,parent:p.width,right:r.right,parentRight:p.right,type:e.type};})''')
            assert all(row['right']<=row['parentRight']+1 for row in geometry),geometry
            assert all(row['type']=='date' for row in geometry)
            assert page.evaluate("state.financeFilters['finance-from']==='2026-11-10'")
            page.screenshot(path=str(args.output/'dates-tablet-surrogate.jpg'),type='jpeg',quality=70)
        def discard(page):
            editor=task(page);field=editor.get_by_label('Название задачи',exact=True);field.fill('Сохранить мой ввод')
            editor.get_by_role('button',name='Закрыть',exact=True).click()
            expect(editor).to_be_visible();expect(field).to_have_value('Сохранить мой ввод')
            expect(editor.get_by_role('button',name='Продолжить редактирование',exact=True)).to_be_visible()
            editor.get_by_role('button',name='Продолжить редактирование',exact=True).click()
            editor.press('Escape');expect(editor).to_be_visible()
            editor.get_by_role('button',name='Продолжить редактирование',exact=True).click()
            page.go_back();expect(editor).to_be_visible()
            expect(editor.get_by_role('button',name='Не сохранять',exact=True)).to_be_visible()
            page.screenshot(path=str(args.output/'task-discard-inline.jpg'),type='jpeg',quality=70)
            editor.get_by_role('button',name='Не сохранять',exact=True).click();expect(editor).to_have_count(0)
        def footer(page):
            editor=task(page)
            expect(editor.get_by_label('Время (необязательно)',exact=True)).to_be_hidden()
            expect(editor.get_by_label('Напомнить об этой задаче',exact=True)).to_be_hidden()
            editor.get_by_label('Дата задачи',exact=True).fill('2026-12-15')
            expect(editor.get_by_label('Время (необязательно)',exact=True)).to_be_visible()
            for height in [844,420]:
                page.set_viewport_size({'width':390,'height':height})
                expect(editor.get_by_role('button',name='Сохранить',exact=True)).to_be_in_viewport(ratio=1)
                expect(editor.get_by_role('button',name='Отмена',exact=True)).to_be_in_viewport(ratio=1)
            page.screenshot(path=str(args.output/'task-keyboard-height.jpg'),type='jpeg',quality=70)
        def pending(page):
            editor=task(page);editor.get_by_label('Название задачи',exact=True).fill('Ожидание сохранения')
            requests=[]
            def hold(route):
                if route.request.method=='POST':requests.append(route)
                else:route.continue_()
            page.route('**/account/api/sync*',hold)
            editor.get_by_role('button',name='Сохранить',exact=True).click()
            expect(editor.get_by_role('button',name='Сохранение…',exact=True)).to_be_disabled()
            expect(editor.get_by_label('Название задачи',exact=True)).to_be_disabled()
            expect(editor.get_by_role('button',name='Закрыть',exact=True)).to_be_disabled()
            expect(editor.get_by_role('button',name='Отмена',exact=True)).to_be_disabled()
            editor.press('Escape');expect(editor).to_be_visible();assert len(requests)==1
            requests[0].fulfill(status=500,content_type='application/json',body='{"error":"server_error"}')
            expect(editor.locator('form>.error')).not_to_be_empty()
            expect(editor.locator('button[type=submit]')).to_have_text('Повторить')
        def recovery(page):
            open_tab(page,'Финансы');open_finance_section(page,'ledger')
            page.get_by_role('button',name='Редактировать · Продукты на неделю',exact=True).click()
            editor=page.get_by_role('dialog');editor.locator('.editor-more>summary').click()
            expect(editor.get_by_role('button',name='Отказаться от этого локального изменения',exact=True)).to_be_hidden()
            expect(editor.get_by_role('button',name='Удалить',exact=True)).to_be_visible()
            editor.get_by_role('button',name='Отмена',exact=True).click();expect(editor).to_have_count(0)
        def actions(page):
            controls=page.locator('.today-tasks .task-actions button')
            sizes=controls.evaluate_all('nodes=>nodes.map(e=>({label:e.textContent,h:e.getBoundingClientRect().height,font:parseFloat(getComputedStyle(e).fontSize)}))')
            assert sizes and all(row['h']>=44 and row['font']>=14 for row in sizes),sizes
            open_tab(page,'Финансы');open_finance_section(page,'ledger');page.locator('.finance-filter-panel>summary').click()
            page.locator('[name=finance-search]').fill('Несуществующий результат')
            page.get_by_role('button',name='Сбросить фильтры',exact=True).click()
            expect(page.locator('[name=finance-search]')).to_have_value('');expect(page.locator('.ledger-row')).to_have_count(2)
        def note_discard(page):
            page.locator('.today-notes').get_by_role('button',name='Заметка',exact=True).click()
            editor=page.get_by_role('dialog');editor.locator('[name=body]').fill('Не возвращать отменённый черновик')
            editor.get_by_role('button',name='Отмена',exact=True).click()
            editor.get_by_role('button',name='Не сохранять',exact=True).click();expect(editor).to_have_count(0)
            page.locator('.today-notes').get_by_role('button',name='Заметка',exact=True).click()
            expect(page.get_by_role('dialog').locator('[name=body]')).to_have_value('')
        def recovery_refresh(page):
            open_tab(page,'Финансы');open_finance_section(page,'ledger')
            page.get_by_role('button',name='Редактировать · Продукты на неделю',exact=True).click()
            editor=page.get_by_role('dialog');editor.locator('[name=label]').fill('Сохранено до ошибки обновления')
            writes=[];reads=[];aborted_reads=[];failure=[True]
            def fail_read(route):
                if route.request.method=='POST':
                    writes.extend(route.request.post_data_json['operations']);route.continue_()
                else:
                    reads.append(route.request.url)
                    if writes and failure[0]:aborted_reads.append(route.request.url);route.abort()
                    else:route.continue_()
            page.route('**/account/api/sync*',fail_read)
            with page.expect_response(lambda response: response.request.method=='POST' and '/account/api/sync' in response.url) as saved:
                editor.get_by_role('button',name='Сохранить',exact=True).click()
            response=saved.value;receipt=response.json()
            expect(editor.locator('form>.error')).not_to_be_empty()
            assert len(writes)==1
            actual=next(r for r in backend.pull(actor,workspace,0)['records'] if r['id']==writes[0]['record_id'])
            evidence={'post_status':response.status,'receipt':receipt,'write_count':len(writes),'sync_read_count':len(reads),'aborted_sync_read_count':len(aborted_reads),'server_label':actual['data']['label'],'form_error':editor.locator('form>.error').inner_text(),'payload_disabled':editor.locator('[name=label]').is_disabled()}
            (args.output/'recovery-refresh-http.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
            accepted=receipt.get('results',[])
            assert response.status==200 and len(accepted)==1 and accepted[0].get('id')==writes[0]['id'] and accepted[0].get('record_id')==writes[0]['record_id'] and accepted[0].get('status')=='accepted',evidence
            assert actual['data']['label']=='Сохранено до ошибки обновления'
            assert len(aborted_reads)==1,evidence
            expect(editor.locator('[name=label]')).to_be_disabled()
            editor.locator('.editor-more>summary').click()
            reload=editor.get_by_role('button',name='Отказаться от этого локального изменения',exact=True)
            expect(reload).to_be_enabled()
            expect(editor.get_by_role('button',name='Удалить',exact=True)).to_be_disabled()
            reload.scroll_into_view_if_needed()
            page.screenshot(path=str(args.output/'recovery-after-failed-refresh.jpg'),type='jpeg',quality=70)
            failure[0]=False;reload.click();expect(editor).to_have_count(0)
            expect(page.locator('.ledger')).to_contain_text('Сохранено до ошибки обновления')
            assert len(writes)==1
            evidence.update(write_count=len(writes),sync_read_count=len(reads),aborted_sync_read_count=len(aborted_reads),recovered=True)
            (args.output/'recovery-refresh-http.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
        def setup_route(page,scenario):
            writes=[];checks=[];before=backend.pull(actor,workspace,0)['records']
            page.on('request',lambda request:writes.append(request.url) if request.method=='POST' and any('/account/api/'+path in request.url for path in ('staff/','control/')) else None)
            def sign_in(query):
                page.goto(origin+'/app'+query)
                page.get_by_label('Электронная почта',exact=True).fill('web@example.test')
                page.locator('input[name=password]').fill(PASSWORD)
                page.get_by_role('button',name='Войти',exact=True).click()
            def profile():
                expect(page.get_by_role('heading',name='Профиль',exact=True)).to_be_visible()
                expect(page.locator('.settings-content')).to_have_attribute('data-section','profile')
                expect(page.get_by_role('button',name='Активировать ULADIM Control',exact=True)).to_be_visible()
                expect(page.get_by_role('dialog')).to_have_count(0)
            if scenario=='owner-login':
                sign_in('?setup=owner');profile()
                assert page.evaluate('staffSetupIntent()')=='owner'
                activation=page.get_by_role('button',name='Активировать ULADIM Control',exact=True)
                geometry=activation.evaluate("e=>{const r=e.getBoundingClientRect(),header=document.querySelector('header').getBoundingClientRect(),nav=document.querySelector('.nav').getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,usable_top:Math.max(0,header.bottom),usable_bottom:Math.min(innerHeight,nav.top),viewport_width:innerWidth,scroll_y:scrollY};}")
                (args.output/'setup-owner-initial-geometry.json').write_text(json.dumps(geometry,indent=2)+'\n')
                expect(activation).to_be_in_viewport(ratio=1)
                assert geometry['top']>=geometry['usable_top'] and geometry['bottom']<=geometry['usable_bottom'] and geometry['left']>=0 and geometry['right']<=geometry['viewport_width'],geometry
                page.screenshot(path=str(args.output/'setup-owner-profile.jpg'),type='jpeg',quality=65)
                activation.click()
                panel=page.get_by_role('dialog');expect(panel).to_be_visible()
                expect(panel.locator('input[name=password]')).to_be_visible()
                expect(panel.locator('input[name=invitation]')).to_be_visible()
                panel.get_by_role('button',name='Закрыть',exact=True).click()
                expect(panel).to_have_count(0);page.evaluate('render()');profile()
                page.screenshot(path=str(args.output/'setup-owner-activation.jpg'),type='jpeg',quality=65)
                checks.append('owner intent survives actual password login; activation opens only on explicit click')
            elif scenario=='staff':
                page.goto(origin+'/app?setup=staff');profile()
                assert page.evaluate('staffSetupIntent()')=='staff'
                checks.append('authenticated staff setup opens Profile without a modal')
            elif scenario in ('normal','invalid'):
                if scenario=='invalid':page.goto(origin+'/app?setup=invalid')
                expect(page.get_by_role('heading',name='Сегодня',exact=True)).to_be_visible()
                expect(page.get_by_role('dialog')).to_have_count(0)
                checks.append(scenario+' launch stays on Today')
            elif scenario in ('security','deletion'):
                page.goto(origin+'/app?setup=owner&settings='+scenario)
                expect(page.locator('.settings-content')).to_have_attribute('data-section',scenario)
                assert 'settings=' not in page.url and 'setup=owner' in page.url
                expect(page.get_by_role('dialog')).to_have_count(0)
                checks.append(scenario+' deep link retains precedence and consumes only settings')
            elif scenario=='mfa':
                from backend.customer_mfa import CustomerMFA
                from backend.control import totp
                mfa=CustomerMFA(backend);enrollment=mfa.begin(actor,PASSWORD)
                recovery=mfa.enable(actor,PASSWORD,enrollment['enrollment'],totp(enrollment['totp_secret'],int(backend.clock())//30))
                sign_in('?setup=owner')
                expect(page.get_by_role('heading',name='Двухфакторная защита',exact=True)).to_be_visible()
                page.locator('input[name=code]').fill(recovery['recovery_codes'][0])
                page.get_by_role('button',name='Войти',exact=True).click();profile()
                checks.append('owner intent survives actual password plus MFA login')
            else:
                # Synthetic OAuth completion metadata; session/startup requests remain real WSGI.
                linked=scenario=='google-linked';setup='owner' if linked else 'staff'
                page.route('**/account/api/google/complete',lambda route:route.fulfill(json={'linked':True} if linked else {}))
                page.evaluate("async setup=>{history.replaceState(null,'','/app?google=complete');sessionStorage.setItem(STAFF_SETUP_KEY,setup);state.tab='today';state.settingsTab='';await googleReturn();}",setup)
                assert page.evaluate('sessionStorage.getItem(STAFF_SETUP_KEY)') is None
                if linked:expect(page.locator('.settings-content')).to_have_attribute('data-section','security')
                else:profile();assert 'setup=staff' in page.url
                checks.append('Google linked return keeps Security' if linked else 'Google return restores setup once to Profile')
            session=page.request.get(origin+'/account/api/session');assert session.ok and session.json()['control_available'] is False
            assert not writes,writes
            assert backend.pull(actor,workspace,0)['records']==before
            (args.output/('setup-route-'+scenario+'-proof.json')).write_text(json.dumps({'checks':checks,'fixture_user_id':actor['id'],'staff_or_control_posts':writes,'control_available':False,'records_unchanged':True,'scope':'Disposable real WSGI/password/MFA; synthetic Google completion metadata, no external provider or role grants.'},ensure_ascii=False,indent=2)+'\n')
        setup_cases=[('setup-route-'+scenario,lambda page,scenario=scenario:setup_route(page,scenario)) for scenario in ('owner-login','staff','normal','invalid','security','deletion','mfa','google-setup','google-linked')]
        for name,run in [('dates',dates),('discard',discard),('footer',footer),('pending',pending),('recovery',recovery),('actions',actions),('note-discard',note_discard),('recovery-refresh',recovery_refresh)]+setup_cases:
            if args.case in ['all',name] or args.case=='setup-route' and name.startswith('setup-route-'):
                # Each independent browser case gets its own records and real HTTP counters.
                with fixture() as (origin, backend, actor, workspace):case(name,run)
        browser.close()
    (args.output/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    for row in results:print(json.dumps(row,ensure_ascii=False))
    if any(row['status']=='failed' for row in results):raise SystemExit(1)

if __name__=='__main__':main()
