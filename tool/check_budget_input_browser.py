"""Focused budget entry acceptance using production WSGI and disposable data."""
import json
import os
import uuid
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from tool.check_web_platform import fixture, login


def main():
    out = Path('web_evidence/budget-input')
    out.mkdir(parents=True, exist_ok=True)
    checks = []
    with fixture() as (origin, backend, actor, wid), sync_playwright() as p:
        usd = str(uuid.uuid4())
        result = backend.batch(actor, wid, [{
            'id': str(uuid.uuid4()), 'action': 'record.put', 'record_id': usd,
            'revision': 0, 'kind': 'account', 'visibility': 'private', 'audience': [],
            'data': {'name': 'Счёт USD', 'currency': 'USD', 'opening_minor': 0},
        }])
        assert result['results'][0]['status'] == 'accepted'
        browser = p.chromium.launch(**({'executable_path': os.environ['ULADIM_CHROMIUM']}
                                      if os.environ.get('ULADIM_CHROMIUM') else {}))
        context = browser.new_context(viewport={'width': 390, 'height': 844},
                                      locale='ru-RU', timezone_id='Europe/Moscow',
                                      service_workers='block')
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        login(page, origin)
        page.evaluate('id=>{rememberTransactionAccount(transactionAccountKey(),id);editRecord("budget");}', usd)
        editor = page.locator('dialog.budget-editor[open]')
        expect(editor.locator('input[name=amount]')).to_have_value('')
        expect(editor.locator('[name=currency]')).to_have_value('USD')
        expect(editor.locator('select[name=period]')).to_have_value('month')
        assert editor.locator('input[type=date]:visible').count() == 0
        assert not editor.locator('input[name=end]').evaluate('(e)=>e.required')
        assert not editor.locator('.budget-options').evaluate('(e)=>e.open')
        expect(editor.locator('.budget-period-summary')).not_to_be_empty()
        start = page.evaluate('localDate().slice(0,7)+"-01"')
        editor.locator('input[name=name]').fill('Лимит на месяц')
        editor.locator('input[name=amount]').fill('0')
        editor.locator('button[type=submit]').click()
        expect(editor.locator('.error')).not_to_be_empty()
        assert len([r for r in backend.pull(actor, wid, 0)['records'] if r['kind'] == 'budget']) == 1
        editor.locator('input[name=amount]').fill('2500,50')
        editor.locator('button[type=submit]').click()
        expect(page.locator('dialog[open]')).to_have_count(0)
        budget = next(r for r in backend.pull(actor, wid, 0)['records']
                      if r['kind'] == 'budget' and r['data']['name'] == 'Лимит на месяц')
        assert budget['data'] == {
            'name': 'Лимит на месяц', 'currency': 'USD', 'limit_minor': 250050,
            'period': 'month', 'start_on': start, 'end_on': None,
            'rollover': 'none', 'participants': [],
        }, budget['data']
        checks.append('month: blank decimal amount, account currency, automatic first day, no end date; zero rejected; real save accepted')

        saved = {**budget['data'], 'rollover': 'both', 'start_on': '2026-10-01',
                 'end_on': '2030-12-31'}
        backend.batch(actor, wid, [{
            'id': str(uuid.uuid4()), 'action': 'record.put', 'record_id': budget['id'],
            'revision': budget['revision'], 'kind': 'budget', 'visibility': budget['visibility'],
            'audience': budget['audience'], 'data': saved,
        }])
        page.evaluate('async id=>{await refresh();editRecord("budget",records("budget").find(r=>r.id===id));}', budget['id'])
        editor = page.locator('dialog.budget-editor[open]')
        expect(editor.locator('input[name=amount]')).to_have_value('2500.50')
        expect(editor.locator('select[name=rollover]')).to_have_value('both')
        assert not editor.locator('.budget-options').evaluate('(e)=>e.open')
        editor.locator('input[name=name]').fill('Обновлённое название')
        editor.locator('button[type=submit]').click()
        expect(page.locator('dialog[open]')).to_have_count(0)
        edited = next(r for r in backend.pull(actor, wid, 0)['records'] if r['id'] == budget['id'])
        assert edited['data'] == {**saved, 'name': 'Обновлённое название'}, edited['data']
        checks.append('edit: changing name preserves amount, currency, original start/end, rollover, participants and visibility')

        page.evaluate('editRecord("budget")')
        editor = page.locator('dialog.budget-editor[open]')
        for period in ['week', 'year']:
            editor.locator('select[name=period]').select_option(period)
            assert editor.locator('input[type=date]:visible').count() == 0
            expect(editor.locator('.budget-period-summary')).not_to_be_empty()
            assert editor.locator('input[name=start]').input_value()
        editor.locator('select[name=period]').select_option('custom')
        expect(editor.locator('input[name=start]')).to_be_visible()
        expect(editor.locator('input[name=end]')).to_be_visible()
        assert editor.locator('input[name=end]').evaluate('(e)=>e.required')
        editor.locator('input[name=name]').fill('Поездка')
        editor.locator('input[name=amount]').fill('500')
        editor.locator('input[name=start]').fill('2026-12-10')
        editor.locator('input[name=end]').fill('2026-12-09')
        editor.locator('button[type=submit]').click()
        expect(editor).to_be_visible()
        assert not any(r['kind'] == 'budget' and r['data']['name'] == 'Поездка'
                       for r in backend.pull(actor, wid, 0)['records'])
        editor.locator('input[name=end]').fill('2026-12-20')
        editor.locator('button[type=submit]').click()
        expect(page.locator('dialog[open]')).to_have_count(0)
        custom = next(r for r in backend.pull(actor, wid, 0)['records']
                      if r['kind'] == 'budget' and r['data']['name'] == 'Поездка')
        assert custom['data']['start_on'] == '2026-12-10' and custom['data']['end_on'] == '2026-12-20'
        checks.append('week/year need no manual dates; custom alone reveals and validates both dates')

        for width, height in [(375, 812), (834, 1112)]:
            page.set_viewport_size({'width': width, 'height': height})
            page.evaluate('state.theme="dark";preferences();editRecord("budget");')
            editor = page.locator('dialog.budget-editor[open]')
            amount = editor.locator('input[name=amount]')
            amount.focus()
            assert amount.get_attribute('inputmode') == 'decimal'
            page.keyboard.press('Tab')
            assert editor.locator('[name=currency]').evaluate('(e)=>e===document.activeElement')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert editor.evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
            editor.locator('button[type=submit]').scroll_into_view_if_needed()
            assert editor.locator('button[type=submit]').evaluate('(e)=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.bottom<=innerHeight;}')
            page.screenshot(path=str(out / f'budget-{width}-dark.png'))
            editor.get_by_role('button', name='Закрыть', exact=True).click()
        checks.append('phone/tablet dark: no horizontal overflow, decimal keyboard and logical Tab order, reachable save action')
        assert not errors, errors
        context.close()
        browser.close()
    (out / 'result.json').write_text(json.dumps({'status': 'passed', 'checks': checks,
        'evidence': 'Production WSGI and actual Chromium; disposable synthetic records'},
        ensure_ascii=False, indent=2) + '\n')
    print('BUDGET_INPUT_PASSED', len(checks))


if __name__ == '__main__':
    main()
