"""Capture Clarity on the real app with disposable data and verify device revocation."""
import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from tool.check_web_platform import PASSWORD, fixture, login
from tool.web_browser_navigation import open_settings, open_tab

VIEWPORTS = (
    ('phone', 390, 844), ('ipad-portrait', 820, 1180),
    ('ipad-landscape', 1180, 820), ('desktop', 1440, 1000),
)


def prepare_devices(backend, actor):
    for label in ('Android · Pixel', 'Tablet · Safari', 'Old browser'):
        result = backend.login(actor['email'], PASSWORD)
        with backend.connect() as db:
            db.execute('UPDATE devices SET label=? WHERE id=?', (label, result['device_id']))
        if label == 'Old browser':
            backend.revoke_device(actor, result['device_id'], PASSWORD)


def capture(page, output, name, screen):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (name, screen)
    page.screenshot(path=str(output / f'{name}-{screen}.png'), animations='disabled')


def check_account(page, baseline):
    if baseline:
        page.get_by_role('button', name='Аккаунт и приватность', exact=True).last.click()
        return
    open_settings(page, 'security')
    for key in ('family_password_change', 'account_email_change', 'account_delete'):
        label = page.evaluate('key => t(key)', key)
        page.locator('.settings-content').get_by_role('button', name=label, exact=True).click()
        dialog = page.get_by_role('dialog')
        expect(dialog.get_by_role('button', name=label, exact=True)).to_be_visible()
        expect(dialog.get_by_role('button', name='Сохранить', exact=True)).to_have_count(0)
        dialog.get_by_role('button', name='Закрыть', exact=True).click()


def check_revocation(page, backend, actor):
    dialog = page.get_by_role('dialog')
    expect(dialog.get_by_text('Текущий сеанс', exact=True)).to_have_count(1)
    expect(dialog.locator('input[type=password]')).to_have_count(0)
    selected = dialog.locator('.device-row').filter(has_text='Android · Pixel')
    survivor = dialog.locator('.device-row').filter(has_text='Tablet · Safari')
    revoked = dialog.locator('.device-row').filter(has_text='Old browser')
    expect(revoked.get_by_role('button')).to_have_count(0)
    before = {device['label']: device for device in backend.list_devices(actor, '')['devices']}
    selected.get_by_role('button', name='Отозвать доступ', exact=True).click()
    confirm = page.locator('dialog[open]').last
    expect(confirm.get_by_text('Android · Pixel', exact=True)).to_be_visible()
    confirm.get_by_role('button', name='Закрыть', exact=True).click()
    assert not next(device for device in backend.list_devices(actor, '')['devices']
                    if device['id'] == before['Android · Pixel']['id'])['revoked_at']
    selected.get_by_role('button', name='Отозвать доступ', exact=True).click()
    confirm.get_by_label('Текущий пароль', exact=True).fill(PASSWORD)
    with page.expect_response(lambda response: response.url.endswith('/devices/revoke')) as response:
        confirm.get_by_role('button', name='Отозвать доступ', exact=True).click()
    assert response.value.status == 200
    assert response.value.request.post_data_json['device_id'] == before['Android · Pixel']['id']
    expect(page.get_by_role('dialog').get_by_text('Завершённые сеансы')).to_be_visible()
    expect(selected.get_by_role('button')).to_have_count(0)
    expect(survivor.get_by_role('button', name='Отозвать доступ', exact=True)).to_be_visible()
    expect(page.get_by_role('dialog').get_by_text('Текущий сеанс', exact=True)).to_have_count(1)
    after = {device['id']: device['revoked_at'] for device in backend.list_devices(actor, '')['devices']}
    assert [device['label'] for device in before.values()
            if device['revoked_at'] != after[device['id']]] == ['Android · Pixel']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('web_evidence/clarity-review'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with fixture() as (origin, backend, actor, _), sync_playwright() as p:
        prepare_devices(backend, actor)
        browser = p.chromium.launch()
        for name, width, height in VIEWPORTS:
            context = browser.new_context(
                viewport={'width': width, 'height': height}, locale='ru-RU',
                timezone_id='Europe/Moscow', color_scheme='light', reduced_motion='reduce',
            )
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            login(page, origin)
            if not args.baseline:
                side_width = page.locator('.today-side').bounding_box()['width']
                for panel in page.locator('.today-side .card').all():
                    assert panel.bounding_box()['width'] >= side_width - 1, name
            capture(page, args.output, name, 'today')
            open_tab(page, 'Финансы')
            expect(page.locator('.ledger')).to_contain_text('Продукты на неделю')
            if not args.baseline:
                first = page.locator('.ledger-row').first.bounding_box()
                assert first['y'] + first['height'] < height * .8, (name, first)
                for control in page.locator('.nav button:visible, .finance-toolbar button').all():
                    box = control.bounding_box()
                    assert min(box['width'], box['height']) >= 44, (name, box)
            capture(page, args.output, name, 'finance')
            open_tab(page, 'Профиль')
            if args.baseline:
                if width < 760:
                    page.locator('[name=settings-section]').select_option('appearance')
                else:
                    page.locator('.settings-navigation button').nth(1).click()
            else:
                open_settings(page, 'appearance')
            capture(page, args.output, name, 'settings')
            if args.baseline:
                if width < 760:
                    page.locator('[name=settings-section]').select_option('security')
                else:
                    page.locator('.settings-navigation button').nth(2).click()
            check_account(page, args.baseline)
            capture(page, args.output, name, 'account')
            if args.baseline:
                page.get_by_role('dialog').get_by_role('button', name='Закрыть', exact=True).click()
            page.get_by_role('button', name='Устройства и сессии', exact=True).click()
            expect(page.get_by_role('dialog')).to_be_visible()
            capture(page, args.output, name, 'devices')
            if not args.baseline and name == 'desktop':
                check_revocation(page, backend, actor)
            assert not errors, errors
            context.close()
        browser.close()
    print('Clarity review captured at 4 sizes. Device revocation checked.' if not args.baseline
          else 'Clarity baseline captured at 4 sizes.')


if __name__ == '__main__':
    main()
