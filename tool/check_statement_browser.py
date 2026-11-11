"""User-facing statement acceptance against the WSGI app and a disposable database."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from wsgiref.simple_server import make_server
from uuid import uuid4
import os

from cryptography.fernet import Fernet
from playwright.sync_api import expect, sync_playwright
from backend.config import Settings
from backend.production import Application
from backend.service import Backend
from tool.check_pwa_browser import Quiet
from tool.check_statement_documents import statement_pdf, statement_xlsx
from tool.web_test_tls import enable_test_tls

PASSWORD = 'synthetic-statement-acceptance-pass'
OUT = Path('web_evidence/statement-import-' + os.environ.get('ULADIM_BROWSER', 'chromium'))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as directory:
        codes = {}
        backend = Backend(Path(directory) / 'bank.db', deliver=lambda e, c: codes.update({e: c}))
        backend.cipher = Fernet(Fernet.generate_key())
        with backend.connect() as db:
            db.execute('CREATE TABLE http_limits(key TEXT PRIMARY KEY,count BIGINT NOT NULL,until_at BIGINT NOT NULL)')
        email = 'statement@example.test'
        session = backend.register(email, PASSWORD)
        actor = backend.authenticate(session['token'])
        backend.verify(actor, codes[email])
        actor = backend.authenticate(session['token'])
        workspace = str(uuid4())
        backend.family(actor, {'id': str(uuid4()), 'action': 'workspace.create', 'workspace_id': workspace,
                               'kind': 'personal', 'name': 'Проверка выписок'})
        settings = Settings.load({
            'DATABASE_URL': 'postgresql://unused/test', 'EMAIL_QUEUE_KEY': Fernet.generate_key().decode(),
            'RATE_LIMIT_KEY': 'statement-fixture-' + 'x' * 48, 'SMTP_HOST': 'localhost',
            'SMTP_TLS': 'none', 'EMAIL_FROM': 'fixture@example.test',
        })
        server = make_server('127.0.0.1', 0, lambda e, s: [], handler_class=Quiet)
        engine = os.environ.get('ULADIM_BROWSER', 'chromium')
        if engine == 'webkit':
            enable_test_tls(server, directory)
        origin = ('https' if engine == 'webkit' else 'http') + '://localhost:' + str(server.server_port)
        server.set_app(Application(backend, replace(settings, site_origin=origin, require_https=False)))
        Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as playwright:
                browser = getattr(playwright, engine).launch()
                run(browser, backend, actor, workspace, origin)
                browser.close()
        finally:
            server.shutdown()
            server.server_close()


def run(browser, backend, actor, workspace, origin):
    context = browser.new_context(viewport={'width': 1180, 'height': 820}, locale='ru-RU', ignore_https_errors=origin.startswith('https:'))
    page = context.new_page()
    page.goto(origin + '/app/')
    page.locator('input[name=email]').fill(actor['email'])
    page.locator('input[name=password]').fill(PASSWORD)
    page.get_by_role('button', name='Войти', exact=True).click()
    expect(page.get_by_role('heading', name='Сегодня', exact=True)).to_be_visible()
    page.get_by_role('navigation').get_by_role('button', name='Финансы', exact=True).click()
    launch = page.get_by_role('button', name='Импортировать выписку', exact=True)
    launch.click()
    dialog = page.get_by_role('dialog')
    expect(dialog.get_by_text('Для импорта нужен счёт.', exact=False)).to_be_visible()
    expect(dialog.locator('input[type=file]')).to_be_hidden()
    dialog.get_by_role('button', name='Создать счёт', exact=True).click()
    editor = page.locator('dialog[open]').last
    editor.locator('input[name=name]').fill('Основной счёт')
    editor.get_by_role('button', name='Сохранить', exact=True).click()
    expect(dialog.locator('input[type=file]')).to_be_visible()
    with page.expect_file_chooser():
        dialog.locator('input[type=file]').click()
    assert dialog.locator('input[type=file]').get_attribute('accept') is None

    def upload(name, contents):
        if isinstance(contents, str):
            contents = contents.encode()
        dialog.locator('input[type=file]').set_input_files({
            'name': name, 'mimeType': 'application/octet-stream', 'buffer': contents,
        })
        expect(dialog.locator('tbody tr').first).to_be_visible()

    def records():
        result = []
        cursor = 0
        while True:
            batch = backend.pull(actor, workspace, cursor)
            result.extend(row for row in batch['records'] if row['kind'] == 'transaction')
            if not batch['more']:
                return result
            cursor = batch['cursor']

    def close():
        dialog.get_by_role('button', name='Закрыть', exact=True).click()
        expect(dialog).to_have_count(0)

    def save(expected, select=False):
        before = {row['id'] for row in records()}
        if select:
            for checkbox in dialog.locator('tbody input[type=checkbox]:enabled').all():
                checkbox.check()
        confirm = dialog.get_by_role('button', name='Импортировать выбранное', exact=True)
        expect(confirm).to_be_enabled()
        confirm.click()
        expect(dialog.get_by_text('Импорт завершён.', exact=False)).to_be_visible(timeout=15000)
        actual = [(row['data']['currency'], row['data']['amount_minor']) for row in records() if row['id'] not in before]
        assert sorted(actual) == sorted(expected), (len(actual), len(expected), set(actual), set(expected))

    statement = 'Дата операции;Дата платежа;Сумма операции;Валюта операции;Описание\n' + '\n'.join(
        f'11.11.2026 09:41:00;12.11.2026;-1 234,56;RUB;Покупка {i}' for i in range(145))
    upload('statement.csv', statement.encode('cp1251'))
    expect(dialog.get_by_text('145 выбрано', exact=False)).to_be_visible()
    expect(dialog.locator('details[open]')).to_have_count(0)
    page.screenshot(path=str(OUT / 'import-tablet.png'))
    for width,height,name in [(390,844,'phone'),(768,900,'foldable-open'),(1440,1000,'desktop')]:
        page.set_viewport_size({'width':width,'height':height})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        confirm_box = dialog.get_by_role('button', name='Импортировать выбранное', exact=True).bounding_box()
        assert confirm_box and confirm_box['y'] + confirm_box['height'] <= height, (name, confirm_box)
        page.screenshot(path=str(OUT / f'import-{name}.png'))
    page.set_viewport_size({'width':1180,'height':820})
    save([('RUB', 123456)] * 145)
    close()
    expect(page.locator('.ledger')).to_contain_text('Покупка')
    launch.click()
    upload('renamed.txt', statement.encode('cp1251'))
    expect(dialog.get_by_role('button', name='Импортировать выбранное', exact=True)).to_be_disabled()
    close()

    samples = [
        ('statement.txt', 'Date\tAmount\tDescription\n2026-11-10T23:58:00-05:00\t+12.05\tIncome', 1205),
        ('statement.json', '{"transactions":[{"bookingDate":"2026-11-11","amount":-1.23,"currency":"RUB","transactionId":"bank-42","description":"Coffee"}]}', 123),
        ('statement.ofx', 'OFXHEADER:100\nDATA:OFXSGML\n\n<OFX><CURDEF>RUB<BANKTRANLIST><STMTTRN><DTPOSTED>20261111090000[-5:EST]<TRNAMT>-5.43<FITID>43<NAME>Shop</STMTTRN></BANKTRANLIST></OFX>', 543),
        ('statement.qif', "!Type:Bank\nD11/21'26\nT-12.05\nPStore\n^\n", 1205),
        ('bank-credit.tsv', 'Date\tDebit\tCredit\tDescription\n2026-11-22\t0,00\t13,21\tBank credit', 1321),
        ('bank-debit.tsv', 'Date\tDebit\tCredit\tDescription\n2026-11-23\t16,54\t0,00\tBank debit', 1654),
    ]
    for name, text, amount in samples:
        launch.click()
        upload(name, text)
        save([('RUB', amount)])
        close()

    directions = {r['data']['label']: r['data']['kind'] for r in records()}
    assert directions['Bank credit'] == 'income' and directions['Bank debit'] == 'expense'

    header = (710, [(30,'Date'),(125,'Description'),(320,'Amount'),(440,'Currency')])
    page_one = [header, (686, [(30,'2026-11-09'),(125,'PDF merchant'),(320,'-42.19'),(440,'RUB')])]
    page_two = [header, (686, [(30,'2026-11-10'),(125,'PDF income'),(320,'+57.21'),(440,'RUB')]),
                (640, [(125,'Total'),(320,'15.02'),(440,'RUB')])]
    launch.click()
    upload('statement.pdf', statement_pdf(page_one,page_two))
    expect(dialog.get_by_role('button', name='Импортировать выбранное', exact=True)).to_be_disabled()
    save([('RUB',4219),('RUB',5721)], select=True)
    close()

    launch.click()
    upload('statement.xlsx', statement_xlsx(date_1904=True))
    save([('RUB',123456)])
    close()

    usd_account = str(uuid4())
    backend.batch(actor, workspace, [{
        'id': str(uuid4()), 'action': 'record.put', 'record_id': usd_account, 'revision': 0, 'kind': 'account',
        'visibility': 'private', 'audience': [], 'data': {'name': 'Доллары', 'currency': 'USD', 'opening_minor': 0},
    }])
    page.evaluate('async () => {await refresh();render()}')
    launch.click()
    upload('multi.csv', 'Date;Amount;Currency;Description\n2026-11-14;1.05;USD;USD income\n2026-11-14;-1.02;RUB;RUB expense')
    expect(dialog.locator('.statement-currency')).to_have_count(2)
    save([('USD', 105), ('RUB', 102)])
    close()

    launch.click()
    upload('repeated.csv', 'Date;Amount;Currency;Description\n2026-11-15;-1.02;RUB;Two real purchases\n2026-11-15;-1.02;RUB;Two real purchases')
    save([('RUB', 102), ('RUB', 102)])
    close()
    launch.click()
    upload('possible.csv', 'Date;Amount;Currency;Description;Transaction ID\n2026-11-15;-1.02;RUB;Two real purchases;another-id')
    expect(dialog.get_by_text('Возможный дубль', exact=False)).to_be_visible()
    expect(dialog.get_by_role('button', name='Импортировать выбранное', exact=True)).to_be_disabled()
    save([('RUB',102)], select=True)
    close()
    launch.click()
    upload('overlap.csv', 'Date;Amount;Currency;Description;Transaction ID\n2026-11-15;-1.02;RUB;Renamed by bank;another-id')
    expect(dialog.get_by_role('button', name='Импортировать выбранное', exact=True)).to_be_disabled()
    close()

    launch.click()
    upload('invalid.csv', 'Date;Debit;Credit;Description\n04/05/2026;1.03;;Ambiguous day')
    dialog.get_by_role('button', name='Исправить строку', exact=True).click()
    editor = page.locator('dialog[open]').last
    editor.locator('input[name=date]').fill('2026-05-04')
    editor.get_by_role('button', name='Сохранить', exact=True).click()
    save([('RUB', 103)])
    assert next(row['data']['kind'] for row in records() if row['data']['label'] == 'Ambiguous day') == 'expense'
    close()
    context.close()
    print('STATEMENT_BROWSER_OK', len(records()), 'transactions persisted')


if __name__ == '__main__':
    main()
