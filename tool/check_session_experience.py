"""Owner feedback: quiet refresh, inline security and a real sign-out flow.

Uses the production WSGI app with disposable synthetic data only.
"""
import json
import os
import uuid
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from tool.check_web_platform import PASSWORD, fixture, login
from tool.web_browser_navigation import open_settings, open_tab


def main():
    out = Path('web_evidence/session-experience')
    out.mkdir(parents=True, exist_ok=True)
    checks = []
    with fixture() as (origin, backend, actor, workspace), sync_playwright() as p:
        other = backend.login(actor['email'], PASSWORD)
        with backend.connect() as db:
            db.execute('UPDATE devices SET label=? WHERE id=?', ('Другой телефон', other['device_id']))
        browser = p.chromium.launch(**({'executable_path': os.environ['ULADIM_CHROMIUM']}
                                      if os.environ.get('ULADIM_CHROMIUM') else {}))
        context = browser.new_context(locale='ru-RU', viewport={'width': 390, 'height': 844},
                                      service_workers='block')
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        login(page, origin)
        open_tab(page, 'Профиль')
        # The identity must remain readable and the workspace selector must
        # never cover the header controls when narrow layouts are populated.
        for width in (320,390,834,1440):
            page.set_viewport_size({'width':width,'height':900})
            identity=page.locator('.profile-identity')
            assert identity.bounding_box()['width']>=150,(width,identity.bounding_box())
            assert identity.locator('dt').evaluate('(e)=>e.getBoundingClientRect().height<=parseFloat(getComputedStyle(e).lineHeight)*2+1'),(width,'vertical identity label')
            assert identity.locator('dd').evaluate('(e)=>e.getBoundingClientRect().height<=parseFloat(getComputedStyle(e).lineHeight)*2+1'),(width,'vertical email')
            if width<760:
                expect(page.locator('.settings-navigation')).to_be_hidden()
                expect(page.locator('.reference-profile-options button:visible')).to_have_count(7)
                workspace_box=page.locator('.reference-workspace').bounding_box()
                theme_box=page.locator('.header-theme').bounding_box()
                assert workspace_box['x']+workspace_box['width']<=theme_box['x']-3,(width,'workspace covers theme')
                assert page.locator('.header-theme').evaluate('(e)=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}'),(width,'theme control obscured')
            page.screenshot(path=str(out/f'profile-{width}.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        checks.append('identity stays readable, header controls unobscured, and seven mobile settings destinations are explicit')
        open_settings(page, 'devices')
        row = page.locator('.device-row').filter(has_text='Другой телефон')
        row.get_by_role('button', name='Отозвать доступ', exact=True).click()
        expect(page.locator('dialog[open]')).to_have_count(0)
        expect(row.get_by_label('Текущий пароль', exact=True)).to_be_visible()
        row.get_by_label('Текущий пароль', exact=True).fill('wrong-password')
        row.locator('button[type=submit]').click()
        expect(row.locator('.error')).not_to_be_empty()
        assert not next(d for d in backend.list_devices(actor, '')['devices']
                        if d['id'] == other['device_id'])['revoked_at']
        row.get_by_role('button', name='Отменить', exact=True).click()
        expect(row.locator('input')).to_have_count(0)
        row.get_by_role('button', name='Отозвать доступ', exact=True).click()
        row.get_by_label('Текущий пароль', exact=True).fill(PASSWORD)
        row.locator('button[type=submit]').click()
        expect(page.locator('.devices-panel')).to_contain_text('Завершённые сеансы')
        assert next(d for d in backend.list_devices(actor, '')['devices']
                    if d['id'] == other['device_id'])['revoked_at']
        checks.append('inline revoke: cancel and wrong password leave session active; valid password revokes selected device')

        open_settings(page, 'security')
        google_status=page.locator('#google-status')
        expect(google_status).to_contain_text('Google не подключён')
        contrast=google_status.evaluate('''e=>{
            const rgb=s=>s.match(/[\\d.]+/g).map(Number);
            const lum=c=>c.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
            const fg=rgb(getComputedStyle(e).color);let bg=[255,255,255];
            for(let p=e;p;p=p.parentElement){const c=rgb(getComputedStyle(p).backgroundColor);if(c.length<4||c[3]>0){bg=c;break;}}
            const a=lum(fg),b=lum(bg);return(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
        }''')
        assert contrast>=4.5,('Google status contrast',contrast)
        page.get_by_role('button', name='Google', exact=True).click()
        expect(page.locator('dialog[open]')).to_have_count(0)
        expect(page.locator('.settings-inline-panel')).to_contain_text('Google')
        page.locator('.settings-inline-panel').get_by_role('button', name='Отменить', exact=True).click()
        page.get_by_role('button', name=page.evaluate("t('family_password_change')"), exact=True).click()
        expect(page.locator('dialog[open]')).to_have_count(0)
        expect(page.locator('.settings-inline-panel input[type=password]')).to_have_count(2)
        checks.append('Google and password settings open inline, not in extra windows')

        open_tab(page, 'Сегодня')
        field = page.locator('input[name=quick-task]')
        field.fill('Черновик остаётся при синхронизации')
        page.evaluate('window.feedbackField=document.querySelector("input[name=quick-task]")')
        page.evaluate('backgroundRefresh()')
        expect(field).to_have_value('Черновик остаётся при синхронизации')
        assert page.evaluate('feedbackField===document.activeElement && feedbackField.isConnected')
        checks.append('background refresh preserves focused draft and DOM when data are unchanged')
        backend.batch(actor, workspace, [{'id': str(uuid.uuid4()), 'action': 'record.put',
            'record_id': str(uuid.uuid4()), 'revision': 0, 'kind': 'note',
            'visibility': 'private', 'audience': [], 'data': {'body': 'Запись с другого устройства'}}])
        page.evaluate('backgroundRefresh()')
        assert page.evaluate('feedbackField===document.activeElement && feedbackField.isConnected')
        page.locator('.intro h1').click()
        expect(page.locator('.today-notes')).to_contain_text('Запись с другого устройства')
        expect(field).to_have_value('Черновик остаётся при синхронизации')
        checks.append('changed remote records appear after editing finishes while the draft is preserved')
        page.screenshot(path=str(out / 'today-phone.png'), full_page=True)

        open_tab(page, 'Профиль')
        page.locator('.profile-logout').click()
        expect(page.locator('dialog[open]')).to_have_count(0)
        expect(page.get_by_role('heading', name='Выйти из аккаунта?', exact=True)).to_be_visible()
        second = context.new_page()
        second.goto(origin + '/app')
        expect(second.get_by_role('heading', name='Сегодня', exact=True)).to_be_visible()
        page.bring_to_front()
        page.route('**/account/api/logout', lambda route: route.abort())
        page.locator('.signout-panel button[type=submit]').click()
        expect(page.locator('.signout-panel .error')).not_to_be_empty()
        expect(page.get_by_role('heading', name='Выйти из аккаунта?', exact=True)).to_be_visible()
        page.unroute('**/account/api/logout')
        page.screenshot(path=str(out / 'signout-phone.png'), full_page=True)
        page.locator('.signout-panel button[type=submit]').click()
        expect(page.get_by_role('button', name='Войти', exact=True)).to_be_visible()
        expect(second.get_by_role('button', name='Войти', exact=True)).to_be_visible()
        expect(page.locator('.reference-sidebar')).to_have_count(0)
        expect(second.get_by_text('Планы на выходные', exact=False)).to_have_count(0)
        assert len(backend.pull(actor, workspace, 0)['records']) > 0
        checks.append('sign-out failure stays recoverable; success clears private UI in both tabs without deleting records')
        assert not errors, errors
        context.close()
        browser.close()
    (out / 'result.json').write_text(json.dumps({'status': 'passed', 'checks': checks,
        'evidence': 'Disposable account; actual browser and production WSGI'}, ensure_ascii=False, indent=2) + '\n')
    print('SESSION_EXPERIENCE_PASSED', len(checks))


if __name__ == '__main__':
    main()
