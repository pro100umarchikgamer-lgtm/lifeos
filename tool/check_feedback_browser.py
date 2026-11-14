"""Focused acceptance of the owner's November 13 recorded interactions.

Uses existing HTTP/SQLite fixture and synthetic records only.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import uuid
from playwright.sync_api import sync_playwright, expect
from tool.check_web_platform import fixture, login
from tool.web_browser_navigation import open_tab

OUT = Path(os.environ.get('ULADIM_FEEDBACK_EVIDENCE', 'web_evidence/feedback-afternoon'))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    checks = []
    with fixture() as (origin, backend, actor, workspace), sync_playwright() as p:
        account = next(r['id'] for r in backend.pull(actor, workspace, 0)['records'] if r['kind'] == 'account')
        operations = []
        for index in range(40):
            operations.append({'id': str(uuid.uuid4()), 'action': 'record.put', 'record_id': str(uuid.uuid4()),
                               'revision': 0, 'kind': 'transaction', 'visibility': 'private', 'audience': [],
                               'data': {'kind': 'income' if index < 2 else 'expense', 'amount_minor': 1000 + index,
                                        'currency': 'RUB', 'date': '2026-11-13', 'label': ('Возврат ' if index < 2 else 'Питание ') + str(index),
                                        'account_id': account, 'category': 'transfers' if index < 2 else 'food'}})
        backend.batch(actor, workspace, operations)
        browser = p.chromium.launch(**({'executable_path': os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
        context = browser.new_context(viewport={'width': 1194, 'height': 834}, locale='ru-RU', service_workers='block', reduced_motion='reduce')
        page = context.new_page()
        page.clock.install(time=datetime(2026, 11, 13, 12, tzinfo=timezone.utc))
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.set_viewport_size({'width': 1600, 'height': 1200})
        page.goto(origin + '/app')
        expect(page.locator('.auth-form-panel')).to_be_visible()
        rect = page.locator('main.login').bounding_box()
        assert abs(rect['x'] * 2 + rect['width'] - 1600) < 2, rect
        assert abs(rect['y'] * 2 + rect['height'] - 1200) < 2, rect
        page.screenshot(path=str(OUT / 'desktop-login.png'), full_page=True)
        checks.append('large-screen login is centered in both directions with no empty strip on one side')
        page.set_viewport_size({'width': 1194, 'height': 834})
        login(page, origin)
        open_tab(page, 'Финансы')
        income = page.locator('button.finance-metric.income')
        expect(income).to_be_visible()
        income.click()
        expect(page.locator('[name=breakdown-kind]')).to_have_value('income')
        expect(page.locator('.chart-category-legend')).to_contain_text('Переводы')
        page.locator('button.chart-category-row').filter(has_text='Переводы').click()
        expect(page.locator('.ledger')).to_contain_text('Возврат 0')
        expect(page.locator('.ledger')).not_to_contain_text('Питание')
        expect(page.locator('.ledger')).not_to_contain_text('Зарплата')
        page.screenshot(path=str(OUT / 'tablet-income-drilldown.png'), full_page=True)
        checks.append('income card opens saved category totals; category opens only its own exact transactions')
        page.locator('button.finance-metric.expense').click()
        expect(page.locator('[name=breakdown-kind]')).to_have_value('expense')
        page.locator('button.chart-category-row').filter(has_text='Питание').click()
        expect(page.locator('.ledger')).to_contain_text('Питание')
        expect(page.locator('.ledger')).not_to_contain_text('Возврат')
        assert page.locator('.ledger-rows').evaluate('e=>e.scrollHeight>e.clientHeight'), 'filled ledger must scroll within its panel'
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(OUT / 'tablet-expense-drilldown.png'), full_page=True)
        checks.append('expense detail excludes income; tablet history scrolls inside a bounded panel')
        open_tab(page, 'Задачи')
        page.locator('.intro button').click()
        expect(page.locator('input[name=name]')).to_have_attribute('placeholder', 'Например, купить продукты')
        expect(page.locator('.record-options>summary')).to_contain_text('Личная')
        expect(page.locator('.task-editor-status input')).to_be_visible()
        assert page.get_by_text('Отказаться от этого локального изменения', exact=True).count() == 0
        page.screenshot(path=str(OUT / 'tablet-task-editor.png'), full_page=True)
        page.locator('.editor-cancel').click()
        checks.append('task editor explains entry, shows current privacy, aligns status, and has a plain Cancel action')
        page.set_viewport_size({'width': 390, 'height': 844})
        page.reload()
        expect(page.get_by_role('heading', name='Сегодня', exact=True)).to_be_visible()
        open_tab(page, 'Календарь')
        expect(page.locator('.calendar-layout')).to_have_attribute('data-mode', 'month')
        today_button = page.locator('.calendar-today')
        assert today_button.evaluate('e=>e.scrollWidth<=e.clientWidth'), 'Today shortcut must not wrap into a vertical word'
        page.screenshot(path=str(OUT / 'phone-calendar.png'), full_page=True)
        open_tab(page, 'Заметки')
        page.screenshot(path=str(OUT / 'phone-notes.png'), full_page=True)
        open_tab(page, 'Финансы')
        page.screenshot(path=str(OUT / 'phone-finance.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        checks.append('phone exposes the requested full month and a readable Today shortcut; all destinations stay within viewport width')
        assert not errors, errors
        browser.close()
    (OUT / 'checks.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2) + '\n')
    print('\n'.join(checks))


if __name__ == '__main__':
    main()
