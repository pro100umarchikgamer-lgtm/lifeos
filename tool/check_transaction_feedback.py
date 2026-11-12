"""Transaction-entry feedback against the existing disposable browser fixture."""
import json
import os
from pathlib import Path
import uuid

from playwright.sync_api import expect, sync_playwright

from tool.check_web_platform import fixture, login
from tool.web_browser_navigation import open_tab


OUT = Path('web_evidence/transaction-feedback')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    checks = []
    with fixture() as (origin, backend, actor, workspace), sync_playwright() as p:
        initial = backend.pull(actor, workspace, 0)['records']
        primary = next(r['id'] for r in initial if r['kind'] == 'account')
        secondary = str(uuid.uuid4())
        backend.batch(actor, workspace, [{
            'id': str(uuid.uuid4()), 'action': 'record.put', 'record_id': secondary,
            'revision': 0, 'kind': 'account', 'visibility': 'private', 'audience': [],
            'data': {'name': 'Точный счёт', 'currency': 'KWD', 'opening_minor': 0},
        }])
        browser = p.chromium.launch(**({'executable_path': os.environ['ULADIM_CHROMIUM']}
                                      if os.environ.get('ULADIM_CHROMIUM') else {}))
        context = browser.new_context(viewport={'width': 820, 'height': 1180},
                                      locale='ru-RU', timezone_id='Europe/Moscow',
                                      service_workers='block')
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        login(page, origin)

        def new_transaction():
            page.get_by_role('button', name='Добавить операцию', exact=True).first.click()
            return page.locator('dialog[open]')

        dialog = new_transaction()
        expect(dialog.locator('[name=account]')).to_have_value(primary)
        expect(dialog.locator('[name=amount]')).to_have_value('')
        expect(dialog.locator('[name=amount]')).to_have_attribute('placeholder', '0.00')
        expect(dialog.locator('[name=amount]')).to_have_attribute('inputmode', 'decimal')
        # Typing, rather than replacing the value, catches the reported extra zero.
        dialog.locator('[name=amount]').press_sequentially('2500')
        expect(dialog.locator('[name=amount]')).to_have_value('2500')
        today = dialog.locator('[name=date]').input_value()
        dialog.get_by_role('button', name='Сохранить', exact=True).click()
        expect(dialog).to_have_count(0)
        added = [r for r in backend.pull(actor, workspace, 0)['records']
                 if r['kind'] == 'transaction' and r['id'] not in {r['id'] for r in initial}]
        assert len(added) == 1, added
        expense = added[0]
        assert expense['data'] == {'kind': 'expense', 'amount_minor': 250000,
                                   'currency': 'RUB', 'date': today, 'label': '',
                                   'account_id': primary}, expense
        open_tab(page, 'Финансы')
        expect(page.locator('.ledger')).to_contain_text('− 2 500,00 RUB')
        page.screenshot(path=str(OUT / 'saved-expense-finance.png'), full_page=True)
        page.reload()
        expect(page.get_by_role('heading', name='Сегодня', exact=True)).to_be_visible()
        open_tab(page, 'Финансы')
        expect(page.locator('.ledger')).to_contain_text('− 2 500,00 RUB')
        checks.append('Today: type 2500, save 250000 minor units, visible in Finance after reload')

        # Changing a cancelled or rejected form must not replace the last saved account.
        dialog = new_transaction()
        dialog.locator('[name=account]').select_option(secondary)
        expect(dialog.locator('[name=currency]')).to_have_value('KWD')
        expect(dialog.locator('[name=amount]')).to_have_attribute('placeholder', '0.000')
        dialog.get_by_role('button', name='Закрыть', exact=True).click()
        dialog = new_transaction()
        expect(dialog.locator('[name=account]')).to_have_value(primary)
        dialog.locator('[name=account]').select_option(secondary)
        dialog.locator('[name=amount]').fill('0')
        dialog.get_by_role('button', name='Сохранить', exact=True).click()
        expect(dialog.locator('.error')).not_to_be_empty()
        dialog.get_by_role('button', name='Закрыть', exact=True).click()
        dialog = new_transaction()
        expect(dialog.locator('[name=account]')).to_have_value(primary)
        checks.append('Cancelled and invalid entries do not remember their account')

        dialog.locator('[name=account]').select_option(secondary)
        dialog.locator('[name=amount]').press_sequentially('1.234')
        dialog.locator('[name=label]').fill('Точная сумма KWD')
        dialog.get_by_role('button', name='Сохранить', exact=True).click()
        expect(dialog).to_have_count(0)
        exact = next(r for r in backend.pull(actor, workspace, 0)['records']
                     if r['kind'] == 'transaction' and r['data']['label'] == 'Точная сумма KWD')
        assert exact['data']['amount_minor'] == 1234 and exact['data']['currency'] == 'KWD'
        page.reload()
        expect(page.get_by_role('heading', name='Сегодня', exact=True)).to_be_visible()
        dialog = new_transaction()
        expect(dialog.locator('[name=account]')).to_have_value(secondary)
        expect(dialog.locator('[name=currency]')).to_have_value('KWD')
        expect(dialog.locator('[name=amount]')).to_have_value('')
        expect(dialog.locator('[name=amount]')).to_have_attribute('placeholder', '0.000')
        dialog.get_by_role('button', name='Закрыть', exact=True).click()
        checks.append('Successful KWD entry remembers its account and currency after reload')

        # Editing keeps the saved amount/account rather than applying creation defaults.
        page.evaluate("id=>editRecord('transaction',records('transaction').find(r=>r.id===id))", expense['id'])
        dialog = page.locator('dialog[open]')
        expect(dialog.locator('[name=account]')).to_have_value(primary)
        expect(dialog.locator('[name=amount]')).to_have_value('2500.00')
        dialog.get_by_role('button', name='Закрыть', exact=True).click()
        checks.append('Existing transaction retains its original account and amount')

        key = 'uladim-transaction-account:' + actor['id'] + ':' + workspace
        page.evaluate("([key,id])=>sessionStorage.setItem(key,id)", [key, str(uuid.uuid4())])
        dialog = new_transaction()
        expect(dialog.locator('[name=account]')).to_have_value(primary)
        dialog.get_by_role('button', name='Закрыть', exact=True).click()
        # No accounts is still a valid transaction flow; the preference cannot select a stale ID.
        page.evaluate("()=>{state.records=state.records.filter(r=>r.kind!=='account');render();}")
        dialog = new_transaction()
        expect(dialog.locator('[name=account]')).to_have_value('')
        expect(dialog.locator('[name=amount]')).to_have_value('')
        dialog.get_by_role('button', name='Закрыть', exact=True).click()
        checks.append('Unavailable remembered account falls back to an existing account or none')
        assert not errors, errors
        assert page.evaluate("Object.keys(localStorage).every(key=>key==='uladim-interface')")
        context.close()
        browser.close()
    (OUT / 'result.json').write_text(json.dumps({
        'status': 'passed', 'fixture': 'disposable SQLite / production WSGI / system Chromium',
        'checks': checks,
    }, ensure_ascii=False, indent=2) + '\n')
    print('TRANSACTION_FEEDBACK_PASSED', len(checks))


if __name__ == '__main__':
    main()
