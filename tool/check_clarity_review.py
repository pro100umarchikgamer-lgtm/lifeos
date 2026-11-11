"""Capture Clarity on the real app with disposable data and verify device revocation."""
import argparse
import uuid
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



def check_review_findings(browser, origin, backend, actor, wid):
    def put(kind, data, record=None, revision=0):
        record = record or str(uuid.uuid4())
        result = backend.batch(actor, wid, [{
            'id': str(uuid.uuid4()), 'action': 'record.put', 'record_id': record,
            'revision': revision, 'kind': kind, 'visibility': 'private',
            'audience': [], 'data': data,
        }])
        assert result['results'][0]['status'] == 'accepted', result
        return record

    old = put('note', {'body': 'Earlier review note'})
    put('note', {'body': 'Later review note'})
    put('note', {'body': 'Latest created note'})
    put('note', {'body': 'Recently edited note'}, old, 1)
    sending = put('account', {'name': 'Sending', 'currency': 'EUR', 'opening_minor': 10000})
    receiving = put('account', {'name': 'Receiving', 'currency': 'USD', 'opening_minor': 0})
    put('transfer', {'from_id': sending, 'to_id': receiving, 'sent_minor': 9000,
                     'received_minor': 10000, 'date': '2026-11-11'})
    context = browser.new_context(locale='ru-RU')
    try:
        page = context.new_page()
        login(page, origin)
        expect(page.locator('.today-notes .note-link').first).to_have_text('Recently edited note')
        open_tab(page, 'Финансы')
        page.locator('.finance-filter-panel summary').click()
        page.locator('[name=finance-account]').select_option(receiving)
        expect(page.locator('.ledger .transfer')).to_have_text('100,00 USD')
    finally:
        context.close()

    recipient_email = 'ownership-recipient@example.test'
    registration = backend.register(recipient_email, PASSWORD)
    with backend.connect() as db:
        db.execute('UPDATE users SET verified=1 WHERE email=?', (recipient_email,))
    recipient = backend.authenticate(registration['token'])
    family = str(uuid.uuid4())
    def family_action(action, **values):
        return backend.family(actor, {'id': str(uuid.uuid4()), 'workspace_id': family,
                                      'action': action, **values})
    family_action('workspace.create', kind='family', name='Ownership fixture')
    invitation = family_action('invite.create', email=recipient_email, role='parent', profile_id=None)
    backend.accept(recipient, {'id': str(uuid.uuid4()), 'invitation': invitation['invitation']})
    from backend.account_lifecycle import AccountLifecycle
    lifecycle = AccountLifecycle(backend)
    proposal = lifecycle.transfer(actor, family, recipient['id'], PASSWORD)
    assert lifecycle.transfer(actor, family, recipient['id'], PASSWORD) == proposal
    context = browser.new_context(locale='ru-RU')
    try:
        page = context.new_page()
        page.goto(origin+'/app')
        page.get_by_label('Электронная почта', exact=True).fill(recipient_email)
        page.locator('input[name=password]').fill(PASSWORD)
        page.get_by_role('button', name='Войти', exact=True).click()
        open_tab(page, 'Профиль')
        open_settings(page, 'family')
        page.locator('.settings-content .settings-row').filter(has_text='Ownership fixture').click()
        dialog = page.get_by_role('dialog')
        dialog.get_by_label('Текущий пароль', exact=True).fill(PASSWORD)
        with page.expect_response(lambda response: response.url.endswith('/accept-transfer')) as response:
            dialog.locator('button[type=submit]').click()
        assert response.value.status == 200
        assert lifecycle.deletion_status(recipient)['incoming_transfers'] == []
        assert lifecycle.deletion_status(actor)['ownership_transfer_required'] == []
    finally:
        context.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('web_evidence/clarity-review'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with fixture() as (origin, backend, actor, wid), sync_playwright() as p:
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
                side = page.locator('.today-side')
                if side.evaluate("element => getComputedStyle(element).display") == 'contents':
                    side = page.locator('.today-grid')
                content_width = side.evaluate("""element => {
                    const style = getComputedStyle(element);
                    return element.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
                }""")
                for panel in page.locator('.today-side .card').all():
                    assert abs(panel.bounding_box()['width'] - content_width) <= 1, name
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
        if not args.baseline:
            check_review_findings(browser, origin, backend, actor, wid)
        browser.close()
    print('Clarity review captured at 4 sizes. Device revocation checked.' if not args.baseline
          else 'Clarity baseline captured at 4 sizes.')


if __name__ == '__main__':
    main()
