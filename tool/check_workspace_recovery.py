"""Exercise the Clarity workspace on a disposable backend with responsive browsers."""
import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

from tool.check_web_platform import fixture, login
from tool.web_browser_navigation import open_settings, open_tab

VIEWPORTS = (
    ('compact', 320, 660), ('phone', 390, 844), ('folded', 360, 740),
    ('unfolded', 744, 720), ('ipad-portrait', 820, 1180),
    ('ipad-landscape', 1180, 820), ('desktop', 1440, 900),
)


def run(browser, origin, output, name, width, height):
    with browser.new_context(viewport={'width': width, 'height': height},
                             locale='ru-RU', timezone_id='Europe/Moscow', ignore_https_errors=origin.startswith('https:')) as context:
        page = context.new_page()
        page.clock.set_fixed_time(datetime(2026, 11, 10, 12, tzinfo=timezone.utc))
        page_errors = []
        page.on('pageerror', lambda error: page_errors.append(str(error)))

        def capture(screen):
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (name, screen)
            if output:
                page.evaluate('window.scrollTo(0, 0)')
                page.screenshot(path=output / f'{name}-{screen}.png', animations='disabled')

        account_responses = []

        def record_account_response(response):
            path = urlsplit(response.url).path
            if path.startswith('/account/api/'):
                account_responses.append((response.request.method, path, response.status))

        page.on('response', record_account_response)
        try:
            login(page, origin)
        except AssertionError as error:
            error.add_note(f'{name}: account responses {account_responses}; browser errors {page_errors}')
            raise
        finally:
            page.remove_listener('response', record_account_response)
        calendar_label = page.locator('.nav').get_by_role('button', name='Календарь', exact=True).locator('span').first
        assert calendar_label.evaluate('''label => {
            const text = document.createRange();
            text.selectNodeContents(label);
            return text.getClientRects().length === 1;
        }'''), (name, 'split calendar navigation label')
        expect(page.locator('.today-agenda h2')).to_be_visible()
        timeline = page.locator('.today-timeline')
        expect(timeline.locator('time')).to_have_text(['09:00', '14:00', '18:30'])
        expect(page.locator('.today-tasks time')).to_have_count(0)
        expect(page.locator('.today-progress progress')).to_have_attribute('value', '1')
        expect(page.locator('.reference-balance strong')).to_have_text('266 480,00 RUB')
        expect(page.locator('.reference-finance-legend')).to_contain_text('Доход · 150 000,00 RUB')
        expect(page.locator('.reference-finance-legend')).to_contain_text('Расход · 3 520,00 RUB')
        if width < 760:
            assert page.locator('.today-finance').bounding_box()['y'] < timeline.bounding_box()['y']
        capture('today')
        timeline.get_by_role('button', name='Встреча с семьёй', exact=True).click()
        event_dialog = page.get_by_role('dialog')
        expect(event_dialog.locator('[name=localStart]')).to_have_value('2026-11-10T18:30')
        event_dialog.get_by_role('button', name='Закрыть', exact=True).click()
        open_tab(page, 'Задачи')
        page.get_by_role('button', name='Добавить', exact=True).click()
        dialog = page.get_by_role('dialog')
        close = dialog.get_by_role('button', name='Закрыть', exact=True)
        assert not close.evaluate("button => button.matches(':focus-visible')")
        expect(dialog.get_by_role('heading')).to_be_focused()
        page.keyboard.press('Tab')
        expect(close).to_be_focused()
        assert close.evaluate("button => button.matches(':focus-visible')")
        close.click()

        open_tab(page, 'Календарь')
        page.locator('[name=calendar-day]').fill('2026-11-12')
        selected = page.locator('.calendar-date[aria-pressed=true]')
        expect(selected).to_be_visible()
        expect(page.locator('.calendar-agenda-date')).to_contain_text('12')
        page.locator('.calendar-agenda').get_by_role('button', name='Добавить событие', exact=True).click()
        dialog = page.get_by_role('dialog')
        expect(dialog.locator('[name=localStart]')).to_have_value('2026-11-12T09:00')
        dialog.get_by_role('button', name='Закрыть', exact=True).click()
        assert page.locator('.calendar-agenda input[type=date]').evaluate(
            '(input) => input.getBoundingClientRect().right <= input.closest("section").getBoundingClientRect().right')
        capture('calendar')

        open_tab(page, 'Заметки')
        expect(page.locator('.notes-library article')).to_contain_text('Планы на выходные')
        page.get_by_role('button', name='Редактировать', exact=True).first.click()
        expect(page.get_by_label('Текст заметки', exact=True)).to_be_visible()
        page.get_by_role('button', name='Закрыть', exact=True).click()
        capture('notes')

        open_tab(page, 'Финансы')
        page.locator('.finance-filter-panel summary').click()
        expect(page.locator('.ledger-row').first).to_be_visible()
        assert page.locator('.finance-filters').evaluate(
            '(filters) => [...filters.querySelectorAll("input, select")].every(field => field.getBoundingClientRect().right <= filters.getBoundingClientRect().right + 1)')
        capture('finance')

        open_tab(page, 'Профиль')
        open_settings(page, 'security')
        expect(page.locator('.settings-content').get_by_text('Google не подключён', exact=True)).to_be_visible()
        expect(page.locator('.settings-content .settings-group')).to_have_count(3)
        capture('account')
        assert not page_errors, page_errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', choices=('chromium', 'webkit', 'firefox'), default='chromium')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--compact-only', action='store_true')
    args = parser.parse_args()
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        binary = os.environ.get('ULADIM_CHROMIUM') if args.engine == 'chromium' else None
        options = {'executable_path': binary} if binary else {}
        browser = getattr(playwright, args.engine).launch(**options)
        for viewport in VIEWPORTS[:1] if args.compact_only else VIEWPORTS:
            # Each viewport represents a separate visit with an independent rate-limit budget.
            with fixture(https=args.engine=='webkit') as (origin, backend, actor, workspace):
                for title, start in [('Планирование дня', '2026-11-10T09:00:00'),
                                     ('Созвон по проекту', '2026-11-10T14:00:00'),
                                     ('Встреча с командой', '2026-11-11T11:00:00')]:
                    response = backend.batch(actor, workspace, [{
                        'id': str(uuid4()), 'action': 'record.put', 'record_id': str(uuid4()), 'revision': 0,
                        'kind': 'event', 'visibility': 'private', 'audience': [],
                        'data': {'title': title, 'schedule': {'localStart': start, 'timezone': 'Europe/Moscow',
                                 'allDay': False, 'repeat': 'none', 'interval': 1, 'until': None}},
                    }])
                    assert response['results'][0]['status'] == 'accepted', response
                run(browser, origin, args.output, *viewport)
        browser.close()
    print(f'Workspace recovery passed on {args.engine}')


if __name__ == '__main__':
    main()
