"""Saved category selection in the actual transaction form and cloud service."""
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from tool.check_web_platform import fixture, login


def main():
    out = Path('web_evidence/transaction-categories')
    out.mkdir(parents=True, exist_ok=True)
    with fixture() as (origin, backend, actor, workspace), sync_playwright() as p:
        browser = p.chromium.launch(**({'executable_path': os.environ['ULADIM_CHROMIUM']}
                                      if os.environ.get('ULADIM_CHROMIUM') else {}))
        context = browser.new_context(locale='ru-RU', viewport={'width': 390, 'height': 844},
                                      service_workers='block')
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        login(page, origin)
        page.get_by_role('button', name='Добавить операцию', exact=True).first.click()
        dialog = page.get_by_role('dialog')
        dialog.locator('[name=amount]').fill('2500')
        dialog.locator('[name=label]').fill('Category fixture purchase')
        dialog.locator('[name=direction]').select_option('income')
        expect(dialog.get_by_text('Категория расходов', exact=True)).to_be_hidden()
        dialog.locator('[name=direction]').select_option('expense')
        dialog.get_by_label('Категория расходов', exact=True).select_option('food')
        page.screenshot(path=str(out / 'expense-category-phone.png'), full_page=True)
        dialog.get_by_role('button', name='Сохранить', exact=True).click()
        expect(dialog).to_have_count(0)
        def saved():
            return next(row for row in backend.pull(actor, workspace, 0)['records']
                        if row['data'].get('label') == 'Category fixture purchase')
        row = saved()
        assert row['data']['category'] == 'food' and row['data']['amount_minor'] == 250000
        page.reload()
        expect(page.get_by_role('heading', name='Сегодня', exact=True)).to_be_visible()
        page.evaluate("id=>editRecord('transaction',records('transaction').find(r=>r.id===id))", row['id'])
        expect(dialog.get_by_label('Категория расходов', exact=True)).to_have_value('food')
        dialog.get_by_label('Категория расходов', exact=True).select_option('transport')
        dialog.get_by_role('button', name='Сохранить', exact=True).click()
        expect(dialog).to_have_count(0)
        assert saved()['data']['category'] == 'transport' and saved()['data']['amount_minor'] == 250000
        page.evaluate("id=>editRecord('transaction',records('transaction').find(r=>r.id===id))", row['id'])
        dialog.get_by_label('Категория расходов', exact=True).select_option('')
        dialog.get_by_role('button', name='Сохранить', exact=True).click()
        expect(dialog).to_have_count(0)
        assert 'category' not in saved()['data']
        assert saved()['data']['amount_minor'] == 250000
        assert not errors, errors
        context.close()
        browser.close()
    (out / 'result.json').write_text(json.dumps({'status': 'passed', 'checks': [
        'selected category persists after reload', 'editing category preserves exact monetary amount',
        'uncategorized clears optional metadata without changing the transaction'],
        'evidence': 'Actual Chromium/WSGI with disposable synthetic data only'}, indent=2) + '\n')
    print('TRANSACTION_CATEGORIES_PASSED')


if __name__ == '__main__':
    main()
