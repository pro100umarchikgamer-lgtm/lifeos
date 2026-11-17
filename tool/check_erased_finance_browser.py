"""Actual account erasure -> peer sync -> safe financial display.

Uses synthetic users and a disposable local database; no provider calls or
production erasure. The existing privacy fixture supplies canonical mutations.
"""
from dataclasses import replace
import json
import os
from pathlib import Path
import threading
from wsgiref.simple_server import make_server

from playwright.sync_api import sync_playwright, expect
from backend.production import Application
from backend.tests.test_account_privacy import AccountPrivacySQLiteTests, PASSWORD
from tool.check_pwa_browser import Quiet
from tool.web_browser_navigation import open_tab, open_finance_section

OUT = Path('web_evidence/erased-finance')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    case = AccountPrivacySQLiteTests('test_all_owned_payloads_erase_peer_money_survives_and_structural_stubs_are_deleted_immutable')
    case.setUp()
    server = None
    try:
        backend = case.backend
        workspace = case.family()
        erased = case.put(case.owner, workspace, 'account', {'name':'OWNER_NAME_MUST_DISAPPEAR','currency':'USD','opening_minor':10000})
        active = case.put(case.peer, workspace, 'account', {'name':'Мой счёт','currency':'EUR','opening_minor':2000})
        transfer = case.put(case.peer, workspace, 'transfer', {'from_id':erased,'to_id':active,'sent_minor':700,'received_minor':650,'date':'2026-11-02'})
        expense = case.put(case.peer, workspace, 'transaction', {'kind':'expense','amount_minor':350,'currency':'USD','date':'2026-11-01','label':'Мой расход','account_id':erased})
        case.erase(case.owner)
        with backend.connect() as db:
            db.execute('CREATE TABLE http_limits(key TEXT PRIMARY KEY,count BIGINT NOT NULL,until_at BIGINT NOT NULL)')
        server = make_server('127.0.0.1', 0, lambda e,s:[], handler_class=Quiet)
        origin = 'http://localhost:'+str(server.server_port)
        settings = replace(case.settings, site_origin=origin, control_origin='http://control.localhost:'+str(server.server_port), require_https=False)
        server.set_app(Application(backend, settings))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        checks = []
        with sync_playwright() as p:
            browser = p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
            context = browser.new_context(viewport={'width':390,'height':844}, locale='ru-RU', service_workers='block', reduced_motion='reduce')
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error:errors.append(str(error)))
            page.goto(origin+'/app')
            page.get_by_label('Электронная почта', exact=True).fill(case.peer['email'])
            page.locator('input[name=password]').fill(PASSWORD)
            page.get_by_role('button', name='Войти', exact=True).click()
            expect(page.get_by_role('heading', name='Сегодня', exact=True)).to_be_visible()
            assert page.evaluate('state.space') == workspace
            assert page.evaluate('id=>accountReference(id).currency', erased) == 'USD'
            assert page.evaluate('records("account").map(r=>r.id)') == [active]
            assert page.evaluate('state.records.some(r=>r.deleted&&r.structural_reference)')
            checks.append('actual_worker_erasure_sync_keeps_only_currency_reference_outside_active_accounts')
            open_tab(page,'Финансы')
            open_finance_section(page,'ledger')
            row = page.locator('.ledger-row').filter(has_text='Перевод')
            expect(row).to_contain_text('7,00 USD')
            expect(row).to_contain_text('Удалённый счёт → Мой счёт')
            expect(page.locator('.ledger')).to_contain_text('3,50 USD')
            assert 'OWNER_NAME_MUST_DISAPPEAR' not in page.locator('body').inner_text()
            row.get_by_role('button').click()
            detail = page.get_by_role('dialog')
            expect(detail).to_contain_text('7,00 USD')
            expect(detail).to_contain_text('6,50 EUR')
            expect(detail.locator('input,select,button[type=submit]')).to_have_count(0)
            page.screenshot(path=str(OUT/'phone-preserved-transfer.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            detail.get_by_role('button',name='Закрыть',exact=True).click()
            page.set_viewport_size({'width':1440,'height':1000})
            page.screenshot(path=str(OUT/'desktop-preserved-ledger.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            checks.append('peer_transfer_and_expense_keep_exact_currencies_with_read_only_removed_account_details')
            assert not errors, errors
            context.close()
            browser.close()
        records = {r['id']:r for r in backend.pull(case.peer,workspace,0)['records']}
        assert records[transfer]['data']['sent_minor'] == 700 and records[transfer]['data']['received_minor'] == 650
        assert records[expense]['data']['amount_minor'] == 350 and records[expense]['data']['account_id'] is None
        result = {'checks':checks,'scope':'Actual disposable SQLite erasure worker and Web sync. No production accounts or data.'}
        (OUT/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(result,ensure_ascii=False))
    finally:
        if server:
            server.shutdown()
            server.server_close()
        case.doCleanups()


if __name__ == '__main__':
    main()
