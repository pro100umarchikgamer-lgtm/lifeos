"""Exercise the Clarity workspace on a disposable backend with responsive browsers."""
import argparse
import os
from pathlib import Path

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
                             locale='ru-RU', timezone_id='Europe/Moscow') as context:
        page = context.new_page()
        page_errors = []
        page.on('pageerror', lambda error: page_errors.append(str(error)))

        def capture(screen):
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (name, screen)
            if output:
                page.evaluate('window.scrollTo(0, 0)')
                page.screenshot(path=output / f'{name}-{screen}.png', animations='disabled')

        login(page, origin)
        calendar_label = page.locator('.nav > button').filter(has_text='Календарь').locator('span:last-child')
        assert calendar_label.evaluate('''label => {
            const text = document.createRange();
            text.selectNodeContents(label);
            return text.getClientRects().length === 1;
        }'''), (name, 'split calendar navigation label')
        expect(page.locator('.today-agenda h2')).to_be_visible()
        capture('today')
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
        page.locator('.calendar-agenda').get_by_role('button', name='Событие', exact=True).click()
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
    with fixture() as (origin, _, _, _), sync_playwright() as playwright:
        binary = os.environ.get('ULADIM_CHROMIUM') if args.engine == 'chromium' else None
        options = {'executable_path': binary} if binary else {}
        browser = getattr(playwright, args.engine).launch(**options)
        for viewport in VIEWPORTS[:1] if args.compact_only else VIEWPORTS:
            run(browser, origin, args.output, *viewport)
        browser.close()
    print(f'Workspace recovery passed on {args.engine}')


if __name__ == '__main__':
    main()
