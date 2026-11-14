"""Targeted settings and honest refresh status against disposable backend records."""
import os
from pathlib import Path
from playwright.sync_api import expect, sync_playwright
from tool.check_web_platform import fixture, login, PASSWORD
from tool.check_clarity_review import prepare_devices
from tool.web_browser_navigation import open_tab, open_settings


def main():
    out = Path('web_evidence/focus-completion')
    out.mkdir(parents=True, exist_ok=True)
    with fixture() as (origin, backend, actor, wid), sync_playwright() as p:
        prepare_devices(backend, actor)
        browser = p.chromium.launch(**({'executable_path': os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
        page = browser.new_page(viewport={'width': 1440, 'height': 1000}, locale='ru-RU', timezone_id='Europe/Moscow')
        login(page, origin)
        expect(page.locator('.workspace-sync')).to_contain_text('Обновлено')
        page.route('**/account/api/spaces', lambda route: route.abort())
        page.evaluate('refresh().catch(()=>{})')
        expect(page.locator('.workspace-sync')).to_contain_text('Не удалось обновить')
        page.unroute('**/account/api/spaces')
        page.evaluate('refresh()')
        expect(page.locator('.workspace-sync')).to_contain_text('Обновлено')
        page.locator('.header-theme').click()
        expect(page.locator('body')).to_have_attribute('data-theme', 'dark')
        page.locator('.header-profile').click()
        open_settings(page, 'devices')
        expect(page.locator('.settings-content .device-group')).to_have_count(2)
        expect(page.locator('dialog[open]')).to_have_count(0)
        selected = page.locator('.device-row').filter(has_text='Android · Pixel')
        selected.get_by_role('button', name='Отозвать доступ', exact=True).click()
        confirmation = selected.locator('.device-revoke-inline')
        expect(page.locator('dialog[open]')).to_have_count(0)
        confirmation.get_by_label('Текущий пароль', exact=True).fill(PASSWORD)
        confirmation.get_by_role('button', name='Отозвать доступ', exact=True).click()
        expect(page.locator('dialog[open]')).to_have_count(0)
        expect(selected.get_by_role('button')).to_have_count(0)
        expect(page.locator('.device-row').filter(has_text='Tablet · Safari').get_by_role('button')).to_be_visible()
        # A delayed devices response cannot populate another settings section.
        page.evaluate("openSettings('devices'); openSettings('appearance')")
        expect(page.locator('.settings-content[data-section=appearance]')).to_be_visible()
        expect(page.locator('.device-group')).to_have_count(0)
        expect(page.locator('#alerts')).to_be_empty(timeout=10000)
        for name, width, height in [('small-phone', 320, 700), ('phone', 375, 812), ('ipad', 820, 1180), ('desktop', 1440, 1000), ('keyboard', 375, 450)]:
            page.set_viewport_size({'width': width, 'height': height})
            for theme in ['light', 'dark']:
                page.evaluate("theme=>{state.theme=theme;preferences();render()}", theme)
                open_tab(page, 'Сегодня')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (name, theme)
                if name == 'ipad':
                    side_width = page.locator('.today-side').bounding_box()['width']
                    for card in page.locator('.today-side .card').all():
                        assert abs(card.bounding_box()['width'] - side_width) <= 1, (name, theme)
                page.screenshot(path=str(out / f'{name}-{theme}-today.png'), full_page=True)
                page.locator('.header-profile').click()
                open_settings(page, 'devices')
                expect(page.locator('.device-group').first).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (name, theme)
                page.screenshot(path=str(out / f'{name}-{theme}-devices.png'), full_page=True)
        current=page.locator('.device-row').filter(has_text='Текущий сеанс')
        current.get_by_role('button', name='Отозвать доступ', exact=True).click()
        confirmation=current.locator('.device-revoke-inline')
        expect(page.locator('dialog[open]')).to_have_count(0)
        confirmation.get_by_label('Текущий пароль', exact=True).fill(PASSWORD)
        confirmation.get_by_role('button', name='Отозвать доступ', exact=True).click()
        expect(page.get_by_role('button', name='Войти', exact=True)).to_be_visible()
        browser.close()
    print('PASS: refresh status, theme, device page, selected revocation, stale response, 20 responsive screenshots, current-session logout')


if __name__ == '__main__':
    main()
