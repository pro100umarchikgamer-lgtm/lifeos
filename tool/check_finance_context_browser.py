"""Real iPad-sized browser regressions for report entry and overview scope."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

from playwright.sync_api import expect, sync_playwright

from tool.check_web_platform import fixture, login
from tool.web_browser_navigation import open_finance_section, open_tab


OUT = Path(os.environ.get('ULADIM_FINANCE_CONTEXT_EVIDENCE',
                          'web_evidence/finance-context'))


def check_case(case, chromium):
    # Every case gets real, independent records and the production HTTP app.
    with fixture() as (origin, backend, actor, workspace):
        primary = next(r['id'] for r in backend.pull(actor, workspace, 0)['records']
                       if r['kind'] == 'account')
        usd = str(uuid.uuid4())
        operations = []
        for kind, data, record_id in [
            ('account', {'name': 'Hamkor USD', 'currency': 'USD', 'opening_minor': 10000}, usd),
            ('transaction', {'kind': 'expense', 'amount_minor': 550, 'currency': 'USD',
                             'date': '2026-11-12', 'label': 'Кофе USD', 'account_id': usd}, str(uuid.uuid4())),
        ]:
            operations.append({'id': str(uuid.uuid4()), 'action': 'record.put',
                               'record_id': record_id, 'revision': 0, 'kind': kind,
                               'visibility': 'private', 'audience': [], 'data': data})
        result = backend.batch(actor, workspace, operations)
        assert all(item['status'] == 'accepted' for item in result['results']), result
        context = chromium.new_context(viewport={'width': 834, 'height': 1194},
                                       locale='ru-RU', timezone_id='Europe/Moscow',
                                       is_mobile=True, has_touch=True,
                                       service_workers='block', reduced_motion='reduce')
        page = context.new_page()
        page.clock.install(time=datetime(2026, 11, 13, 12, tzinfo=timezone.utc))
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def account_report(name='Hamkor USD'):
            open_finance_section(page, 'accounts')
            page.locator('.finance-account-report').filter(has_text=name).click()
            expect(page.locator('main')).to_have_attribute('data-finance-view', 'report')
            expect(page.locator('main h1')).to_have_text(name)

        def add_transaction():
            page.locator('.finance-toolbar').get_by_role('button', name='Добавить операцию', exact=True).click()
            return page.locator('dialog[open]')

        try:
            login(page, origin)
            open_tab(page, 'Финансы')
            if case == 'add':
                dialog = add_transaction()
                expect(dialog.locator('[name=account]')).to_have_value(primary)
                expect(dialog.locator('[name=currency]')).to_have_value('RUB')
                dialog.get_by_role('button', name='Закрыть', exact=True).click()
                account_report()
                dialog = add_transaction()
                page.screenshot(path=str(OUT / 'account-add.png'), full_page=True)
                expect(dialog.locator('[name=account]')).to_have_value(usd)
                expect(dialog.locator('[name=currency]')).to_have_value('USD')
                expect(dialog.locator('[name=amount]')).to_have_value('')
                dialog.locator('[name=amount]').fill('12.34')
                dialog.locator('[name=label]').fill('Из отчёта USD')
                dialog.get_by_role('button', name='Сохранить', exact=True).click()
                expect(dialog).to_have_count(0)
                saved = next(r for r in backend.pull(actor, workspace, 0)['records']
                             if r['kind'] == 'transaction' and r['data']['label'] == 'Из отчёта USD')
                assert saved['data']['account_id'] == usd, saved
                assert saved['data']['currency'] == 'USD' and saved['data']['amount_minor'] == 1234, saved
                expect(page.locator('.finance-metric.balance')).to_contain_text('82,16 USD')
                page.screenshot(path=str(OUT / 'account-saved.png'), full_page=True)
                open_finance_section(page, '')
                dialog = add_transaction()
                expect(dialog.locator('[name=account]')).to_have_value(usd)
                dialog.get_by_role('button', name='Закрыть', exact=True).click()
                # Missing report references must never open a different account's form.
                account_report()
                page.evaluate("id=>{state.records=state.records.filter(r=>r.id!==id);render();}", usd)
                expect(page.get_by_text('Счёт больше недоступен', exact=True)).to_be_visible()
                expect(page.locator('.finance-toolbar').get_by_role('button', name='Добавить операцию', exact=True)).to_be_disabled()
            elif case == 'overview':
                account_report()
                expect(page.locator('select[name=chart-currency]')).to_have_value('USD')
                open_finance_section(page, '')
                page.screenshot(path=str(OUT / 'report-to-overview.png'), full_page=True)
                expect(page.locator('[name=finance-account]')).to_have_value('')
                expect(page.locator('select[name=chart-currency]')).to_have_value('RUB')
                expect(page.locator('.finance-metric.balance')).to_contain_text('266 480,00 RUB')
                expect(page.locator('.finance-metric.balance')).to_contain_text('94,50 USD')
                expect(page.locator('.finance-metric.expense')).to_contain_text('3 520,00 RUB')
                expect(page.locator('.finance-metric.expense')).to_contain_text('5,50 USD')
                expect(page.locator('.finance-filter-panel > summary')).to_have_text('Фильтры')
                account_report()
                open_tab(page, 'Сегодня')
                open_tab(page, 'Финансы')
                expect(page.locator('[name=finance-account]')).to_have_value('')
            else:
                page.locator('.finance-filter-panel > summary').click()
                page.locator('[name=finance-account]').select_option(primary)
                page.locator('[name=finance-from]').fill('2026-11-02')
                page.locator('[name=finance-to]').fill('2026-11-12')
                page.locator('[name=finance-search]').fill('Продукты')
                account_report()
                page.locator('.finance-filter-panel > summary').click()
                page.locator('[name=finance-search]').fill('Кофе')
                page.locator('[name=finance-from]').fill('2026-11-11')
                open_finance_section(page, '')
                page.screenshot(path=str(OUT / 'overview-filters-restored.png'), full_page=True)
                expect(page.locator('[name=finance-account]')).to_have_value(primary)
                expect(page.locator('[name=finance-from]')).to_have_value('2026-11-02')
                expect(page.locator('[name=finance-to]')).to_have_value('2026-11-12')
                expect(page.locator('[name=finance-search]')).to_have_value('Продукты')
                expect(page.locator('select[name=chart-currency]')).to_have_value('RUB')
                expect(page.locator('.ledger')).to_contain_text('Продукты на неделю')
                expect(page.locator('.ledger')).not_to_contain_text('Кофе USD')
                # Deliberate chart-currency choice without an account is also overview scope.
                page.locator('.finance-filter-panel > summary').click()
                page.locator('[name=finance-account]').select_option('')
                page.locator('[name=finance-search]').fill('')
                page.locator('select[name=chart-currency]').select_option('USD')
                account_report('Основной счёт')
                open_finance_section(page, '')
                expect(page.locator('[name=finance-account]')).to_have_value('')
                expect(page.locator('select[name=chart-currency]')).to_have_value('USD')
                # A report draw queued before sign-out must not restore the old scope.
                page.evaluate("""id=>{
                    state.financeReportFilters={account:id,'finance-search':'Private report context'};
                    referenceNavigate('money','report');clearIdentity();
                }""", usd)
                page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                assert page.evaluate('JSON.stringify(state.financeReportFilters)') == '{}'
                assert page.evaluate('JSON.stringify(state.financeFilters)') == '{}'
            assert not errors, errors
        finally:
            context.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=['add', 'overview', 'filters', 'all'], default='all')
    args = parser.parse_args()
    cases = ['add', 'overview', 'filters'] if args.case == 'all' else [args.case]
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**({'executable_path': os.environ['ULADIM_CHROMIUM']}
                                                if os.environ.get('ULADIM_CHROMIUM') else {}))
        try:
            for case in cases:
                check_case(case, browser)
                print('FINANCE_CONTEXT_CASE_PASSED', case, flush=True)
        finally:
            browser.close()
    (OUT / 'result.json').write_text(json.dumps({'status': 'passed', 'cases': cases,
        'fixture': 'production WSGI; disposable synthetic SQLite; 834px touch Chromium'}, indent=2) + '\n')


if __name__ == '__main__':
    main()
